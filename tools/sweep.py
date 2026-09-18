r"""
One mechanical edit over many tracked files, with each file's bytes kept.

    python tools/sweep.py --glob "tests/*.py" \
        --pattern "old_name" --replace "new_name"
    python tools/sweep.py --glob "src/**/*.py" --transform fix.py --dry

One rename across 48 test files, done by hand through four sub-agents,
cost about 30 minutes and about 0.6M tokens. A mechanical edit across
many files is a script. This tool is the part every such script repeats:
the file set, the bytes, the line endings, the report.

The tool is language-agnostic. It reads bytes and writes bytes, so it
sweeps a repository written in any language. Only the tool itself is
Python.

Three hazards are the reason it exists:

* `Path.write_text` turns each LF into CRLF on Windows, and turns an
  existing CRLF into `\r\r\n`. The tool writes bytes, then reads them back
  and compares them. A check on the ending class passes on a corrupt file.
* `re.sub`'s replacement template eats a backslash. `"C:\temp\new"` writes
  a TAB and a NEWLINE with no error. The replacement is a function by
  default, so a backslash stays a backslash. That hazard was measured at
  23 strikes before this tool existed.
* `fnmatch` lets `*` cross a separator, treats `**` as two stars, and folds
  case on Windows. Selection uses `PurePosixPath.full_match`.

Exit codes, no overlap: 0 when at least one file changed and nothing was
skipped, 1 when nothing changed and nothing was skipped, 2 for a usage
error or a handled error before any write, 3 for a write mismatch, and 4
when the run completed and at least one file was skipped.
"""
from __future__ import annotations

import argparse
import codecs
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

BOM = codecs.BOM_UTF8

def _self_rel(root: Path) -> str:
    """This file's path inside the repository, so no sweep rewrites its own rule.

    The first run of one rename script rewrote its own lookup table, and
    every later file read the rewritten rule. An empty string means the
    tool lives outside the repository it sweeps, which excludes nothing.
    """
    try:
        return Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return ""

# The report prints the skips in this order, whatever order the files came in.
REASONS = ("binary", "unreadable", "mixed endings", "not utf-8",
           "edit returned CR")

# The edit takes the text with LF endings and the file's repository-relative
# path. It returns the new text and the number of matches.
Edit = Callable[[str, str], tuple[str, int]]


class Usage(Exception):
    """A bad invocation, or a hook that fails. Both exit 2, before any write."""


@dataclass
class Touch:
    """One file the edit changed, with the bytes the tool means to write."""

    rel: str
    data: bytes
    matches: int
    ending: str


# ---------------------------------------------------------------------------
# Select
# ---------------------------------------------------------------------------

def select(root: Path, globs: list[str], excludes: list[str]) -> list[str]:
    """The tracked files that match a glob, minus the excluded ones."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         capture_output=True)
    if out.returncode != 0:
        raise Usage(f"git ls-files: {out.stderr.decode('utf-8', 'replace').strip()}")
    # An untracked file is never selected. A mechanical edit is a change to
    # the tree, and an untracked file is not the tree's.
    tracked = [p for p in out.stdout.decode("utf-8").split("\0") if p]

    # A transform outside the repository has no path inside it, and an empty
    # pattern must never reach `full_match`.
    excludes = [x for x in excludes if x]
    keep: list[str] = []
    for rel in dict.fromkeys(tracked):      # a conflicted path is listed per stage
        pure = PurePosixPath(rel)
        if not any(pure.full_match(g) for g in globs):
            continue
        if any(pure.full_match(x) for x in excludes):
            continue
        if not (root / rel).is_file():      # a deleted file is still in the index
            continue
        keep.append(rel)
    return keep


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------

def classify(data: bytes) -> tuple[str, str, bool, str]:
    """Return the skip reason, the ending, the BOM flag and the LF text."""
    if b"\x00" in data[:8192]:
        return "binary", "", False, ""

    # The tool must know the file had a BOM to put it back, so it never
    # decodes with `utf-8-sig`.
    bom = data.startswith(BOM)
    body = data[len(BOM):] if bom else data

    crlf = body.count(b"\r\n")
    lf = body.count(b"\n")
    cr = body.count(b"\r")
    if crlf == 0 and cr == 0:
        ending = "LF"
    elif crlf == lf and cr == crlf:
        ending = "CRLF"
    else:
        # A mixed file has no one ending, and a lone CR is mixed too. The
        # frame's test is that a file keeps its own ending.
        return "mixed endings", "", bom, ""

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return "not utf-8", ending, bom, ""
    return "", ending, bom, text.replace("\r\n", "\n")


def encode(text: str, ending: str, bom: bool) -> bytes:
    """The file's own ending and its BOM, put back on the edited text."""
    out = text.replace("\n", "\r\n") if ending == "CRLF" else text
    return (BOM if bom else b"") + out.encode("utf-8")


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

def _relative(root: Path, spec: str) -> str:
    """The named file's path inside the repository, or a pattern that matches none."""
    try:
        return Path(spec).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _hook(path: Path) -> Edit:
    """Load `transform(text, path)` from the Python file the caller names."""
    if not path.is_file():
        raise Usage(f"--transform {path}: no such file")
    spec = importlib.util.spec_from_file_location("sweep_transform", path)
    if spec is None or spec.loader is None:
        raise Usage(f"--transform {path}: not loadable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise Usage(f"--transform {path}: {exc!r}") from exc
    fn = getattr(module, "transform", None)
    if not callable(fn):
        raise Usage(f"--transform {path}: no transform(text, path) function")

    def edit(text: str, rel: str) -> tuple[str, int]:
        new = fn(text, rel)
        if not isinstance(new, str):
            raise Usage(f"--transform returned {type(new).__name__}, not str")
        # A transform applies once to the whole file, so the report counts one.
        return new, 1

    return edit


def build_edit(args: argparse.Namespace, root: Path) -> tuple[Edit, list[str]]:
    """The edit, and the transform's own path, which no sweep may rewrite."""
    regex = args.pattern is not None or args.replace is not None
    if regex and args.transform:
        raise Usage("--pattern and --transform: give exactly one edit form")
    if not regex and not args.transform:
        raise Usage("no edit: give --pattern with --replace, or --transform")

    if args.transform:
        if args.template:
            raise Usage("--template applies to --replace only")
        return _hook(Path(args.transform)), [_relative(root, args.transform)]

    if args.pattern is None or args.replace is None:
        raise Usage("--pattern needs --replace")
    try:
        rx = re.compile(args.pattern, re.MULTILINE)
    except re.error as exc:
        raise Usage(f"--pattern does not compile: {exc}") from exc

    # The replacement is literal by default. `re.sub`'s template reads a
    # backslash as an escape, which corrupted 23 patches before this tool
    # existed. A function replacement is literal.
    text = args.replace
    repl: str | Callable[[re.Match], str] = text if args.template else (lambda m: text)

    def edit(body: str, rel: str) -> tuple[str, int]:
        return rx.subn(repl, body)

    return edit, []


def plan(root: Path, chosen: list[str],
         edit: Edit) -> tuple[list[Touch], dict[str, list[str]], int]:
    """Read and edit every selected file in memory, before the first write."""
    touches: list[Touch] = []
    skips: dict[str, list[str]] = {}
    unchanged = 0

    for rel in chosen:
        try:
            data = (root / rel).read_bytes()
        except OSError:                     # a locked or unreadable file
            skips.setdefault("unreadable", []).append(rel)
            continue
        reason, ending, bom, text = classify(data)
        if reason:
            skips.setdefault(reason, []).append(rel)
            continue
        try:
            new, matches = edit(text, rel)
        except Usage:
            raise
        except Exception as exc:            # a hook that raises stops the run
            raise Usage(f"the edit failed on {rel}: {exc!r}") from exc
        # The tool owns the endings, so no edit form may put a CR in the text.
        # `--replace` with a CR, and `--template` with the escape, both wrote
        # one that the byte compare cannot catch: the bytes were intended.
        if "\r" in new:
            skips.setdefault("edit returned CR", []).append(rel)
            continue
        if new == text:
            unchanged += 1
            continue
        touches.append(Touch(rel, encode(new, ending, bom), matches, ending))

    return touches, skips, unchanged


# ---------------------------------------------------------------------------
# Write and check
# ---------------------------------------------------------------------------

def write_bytes(path: Path, data: bytes) -> None:
    """The one writer. `Path.write_text` turns each LF into CRLF on Windows."""
    path.write_bytes(data)


def write_all(root: Path, touches: list[Touch]) -> str:
    """Write each file and read it back. Return the message of a failure."""
    for touch in touches:
        path = root / touch.rel
        try:
            write_bytes(path, touch.data)
            # A check on the ending class passes on a corrupt `\r\r\n` file.
            # A byte compare does not.
            back = path.read_bytes()
        except OSError as exc:
            # A half-swept tree needs its own exit code. Python's own 1 is
            # the code the table gives to "nothing changed".
            return f"write failed: {touch.rel}: {exc}"
        if back != touch.data:
            return f"write mismatch: {touch.rel}"
    return ""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def report(root: Path, chosen: list[str], touches: list[Touch],
           skips: dict[str, list[str]], unchanged: int,
           dry: bool, full_diff: bool) -> None:
    """One fact per line, in the order the design record gives."""
    print(f"selected {len(chosen)} files")
    for reason in REASONS:
        listed = skips.get(reason) or []
        if listed:
            print(f"skipped ({reason}) {len(listed)}:")
            for rel in listed:
                print(f"  {rel}")

    print(f"{'would touch' if dry else 'touched'} {len(touches)}:")
    for touch in touches:
        print(f"  {touch.rel} {touch.matches} matches ({touch.ending})")
    print(f"unchanged {unchanged}")

    if dry or not touches:
        return
    rels = [touch.rel for touch in touches]
    print(_git(root, "diff", "--stat", "--", *rels), end="")
    if full_diff:
        print(_git(root, "diff", "--", *rels), end="")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python tools/sweep.py",
                                 description="One mechanical edit over many files.")
    ap.add_argument("--glob", action="append", default=[], metavar="PATTERN",
                    help="select tracked files by full_match, repeatable")
    ap.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                    help="drop matched files, applied after the globs")
    ap.add_argument("--pattern", metavar="REGEX", help="the regex to replace")
    ap.add_argument("--replace", metavar="TEXT", help="the literal replacement")
    ap.add_argument("--template", action="store_true",
                    help="read the replacement as a re.sub template")
    ap.add_argument("--transform", metavar="FILE",
                    help="a Python file with transform(text, path) -> str")
    ap.add_argument("--dry", action="store_true", help="write nothing")
    ap.add_argument("--diff", action="store_true", help="print the full diff")
    return ap


def main(argv: list[str], root: Path) -> int:
    args = parser().parse_args(argv)
    try:
        if not args.glob:
            raise Usage("no --glob: nothing to select")
        # The hook loads before any file is read, so a bad hook changes nothing.
        edit, extra = build_edit(args, root)
        chosen = select(root, args.glob, [*args.exclude, _self_rel(root), *extra])
        touches, skips, unchanged = plan(root, chosen, edit)
    except Usage as exc:
        print(f"sweep: {exc}", file=sys.stderr)
        return 2

    if not args.dry:
        bad = write_all(root, touches)
        if bad:
            print(bad)
            return 3

    report(root, chosen, touches, skips, unchanged, args.dry, args.diff)
    if any(skips.values()):
        return 4
    return 0 if touches else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], Path.cwd()))
