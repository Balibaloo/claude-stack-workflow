r"""
Append one status line to a frame of the stack, and commit the stack alone.

    python tools/status.py 12 --sid 2555d93f --text "the scope report is in"
    python tools/status.py 12 --sid 2555d93f --body line.txt
    python tools/status.py 12 --sid 2555d93f --ruling "their words" --at 14:20

Two steps failed often enough by hand to become a tool. A status time
typed from memory was wrong on 22 recorded occasions. A status line passed
through a shell heredoc lost a backslash on 30. So the time comes from the
clock here, never from an argument. The body comes from a file or from one
argument, never from a shell heredoc.

The line is `- Status <date> <time> (<peer name>): <body>`, the form of
the kit's `stack.md`. It goes after the frame's last status line. A frame
with no status line takes it after its `- Reasoning:` line, else after its
last bullet. The file keeps its own line end.

The peer name comes from the hook's enrolment of the session, in
`.handover/sessions/<sid>.json` at the root of the checkout. A session
with no enrolment gets its session id in the line and a warning. The tool
never refuses a status line for a missing name.

`--ruling` writes the Principal's words as a ruling line. The words are
quoted whole, with the time that the Principal said them and the frame's
workflow. `state.py --since` prints the line back to the Principal.

The commit holds the stack alone, by pathspec, so a file that another
change staged stays staged and stays out of the commit. The summary line
names the frame by its number and its name, as the stack's rule 7 asks.

The tool imports `state.py` for the frame reader and `handover.py` for the
root of the checkout. Keep the three files in one directory.

Exit codes: 0 the line is written and committed, or written with
`--no-commit`. 1 the line is written and the commit failed. 2 a usage
error, an empty body, or a frame that the stack does not hold.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import handover
import state

#: The type and scope of the summary line, from the commit standard of
#: `CONTRIBUTING.md`. Change it if your standard writes another form.
SUMMARY_PREFIX = "docs(plans)"
SUMMARY_LIMIT = 72

DATED = re.compile(r"\s*\(\d{4}-\d\d-\d\d\)")
TAG = re.compile(r"\s*\(Principal\)")
WORKFLOWS = {"meta": "Meta", "project": "The project's"}


def _clock() -> datetime:
    """The clock. Tests replace this, and no argument does."""
    return datetime.now()


def one_line(text: str) -> str:
    """Join the lines of a body with one space each."""
    return re.sub(r"\s*\r?\n\s*", " ", text).strip()


def mailbox_root(stack: Path) -> Path:
    """The directory that holds `.handover`, the way `handover.py` finds it.

    Outside git, `handover._root` answers the directory it starts in, which
    is `plans/`. The mailbox then sits one level up, beside `plans/`.
    """
    start = stack.resolve().parent
    root = handover._root(start)
    if root == start and start.name == "plans":
        return start.parent
    return root


def peer_name(stack: Path, sid: str) -> str:
    """The name that the hook enrolled for the session, or empty.

    The enrolment is read without building a mailbox, so a repository
    with no `.handover` stays without one.
    """
    path = mailbox_root(stack) / handover.BOX / "sessions" / (sid[:8] + ".json")
    try:
        row = handover._read_json(path) or {}
    except handover.Unreadable:
        return ""
    return str(row.get("name") or "")


def name_of(stack: Path, sid: str) -> str:
    name = peer_name(stack, sid)
    if not name:
        print("WARNING: no enrolment names session %s, so the line carries the "
              "session id." % sid)
    return name or sid


def find(text: str, frame: str) -> state.Frame | None:
    """The frame of that number anywhere in the stack, held or parked."""
    bare = [r.rstrip("\r") for r in text.split("\n")]
    found = [f for f in state.parse(bare, bounded=False) if f.number == str(frame)]
    return found[0] if found else None


def insert(text: str, frame: str, line: str) -> tuple[str, int]:
    """Insert one line into a frame. Return the new text and the line index.

    The line goes after the frame's last status line, or after its
    Reasoning line when it has no status line, or after its last bullet.
    The file's own line end is kept, so a CRLF file stays CRLF and an LF
    file stays LF.
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    raw = text.split("\n")
    f = find(text, frame)
    if f is None:
        raise KeyError(frame)
    marks = f.statuses
    if marks:
        at = marks[-1]
    else:
        hit = f.first("- Reasoning:")
        if hit:
            at = hit[0]
        else:
            bullets = [i for i, b in enumerate(f.lines) if b.startswith("- ")]
            at = bullets[-1] if bullets else 0
    # A bullet can wrap. Its continuation runs to the next line that is
    # blank or starts a bullet or a heading, and the new line goes after it.
    while at + 1 < len(f.lines):
        nxt = f.lines[at + 1]
        if not nxt.strip() or nxt.startswith("- ") or nxt.startswith("#"):
            break
        at += 1
    index = f.start + at + 1
    raw.insert(index, line + ("\r" if eol == "\r\n" else ""))
    return "\n".join(raw), index


def frame_name(frame: state.Frame) -> str:
    """The frame's name: the heading with no session id, tag or push date."""
    return DATED.sub("", TAG.sub("", state.HOLDERS.sub("", frame.heading))).strip()


def ruling_body(words: str, at: str, day: str, workflow: str) -> str:
    """The Principal's words as a ruling line, with its time and its workflow."""
    who = state.PRINCIPAL[:1].upper() + state.PRINCIPAL[1:]
    body = ('**ruled. %s, %s %s, in the terminal: "%s"** (ruled: %s, in their '
            'words).' % (who, day, at, one_line(words), state.PRINCIPAL))
    if workflow:
        body += " %s workflow." % workflow
    return body


def summary(frame: str, name: str) -> str:
    """The summary line: the frame's number and name, cut at a word."""
    line = "%s: frame %s, %s" % (SUMMARY_PREFIX, frame, name.replace("`", ""))
    if len(line) > SUMMARY_LIMIT:
        line = line[:SUMMARY_LIMIT + 1].rsplit(" ", 1)[0]
    return line.rstrip(" .,;:")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def commit(stack: Path, frame: str, name: str, body: str, when: str, sid: str) -> int:
    """Commit the stack by pathspec, so nothing else that is staged goes in."""
    repo = stack.resolve().parent
    path = str(stack.resolve())
    git(repo, "add", "--", path)
    prose = ("The status tool appends one line to frame %s, %s, at %s for "
             "session %s. The line reads: %s" % (
                 frame, name, when, sid, state.cut(body, 300)))
    done = git(repo, "commit", "-m", summary(frame, name), "-m", prose, "--", path)
    if done.returncode != 0:
        print("the line is written and the commit failed:", file=sys.stderr)
        print((done.stdout + done.stderr).strip(), file=sys.stderr)
        return 1
    sha = git(repo, "rev-parse", "--short=8", "HEAD").stdout.strip()
    print("committed %s" % sha)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Append one status line to a frame and commit the stack.")
    p.add_argument("frame", help="the frame number")
    p.add_argument("--sid", required=True, help="the session that writes the line")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--body", help="a file that holds the body")
    src.add_argument("--text", help="the body as one argument")
    src.add_argument("--ruling", help="the Principal's words, written as a ruling")
    p.add_argument("--at", default=None,
                   help="HH:MM of the Principal's words, for --ruling. It goes "
                        "in the body. The clock's time by default")
    p.add_argument("--date", default=None,
                   help="YYYY-MM-DD of the Principal's words, for --ruling, when "
                        "they were said before midnight. Today by default")
    p.add_argument("--workflow", default=None, choices=sorted(WORKFLOWS),
                   help="the workflow of a ruling, when the frame names none")
    p.add_argument("--stack", default=None, help="the stack, plans/stack.md by default")
    p.add_argument("--no-commit", action="store_true",
                   help="write the line and commit nothing")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bad = handover._check_sid(args.sid)
    if bad:
        print("--sid is not usable: %s" % bad, file=sys.stderr)
        return 2
    sid = args.sid[:8]
    stack = Path(args.stack) if args.stack else state.default_stack()
    if not stack.is_file():
        print("no stack at %s" % stack, file=sys.stderr)
        return 2
    now = _clock()
    text = stack.read_bytes().decode("utf-8")
    when = now.strftime("%Y-%m-%d %H:%M")
    found = find(text, args.frame)
    if found is None:
        print("the stack holds no frame %s, so no line was written." % args.frame,
              file=sys.stderr)
        return 2

    if args.body is not None:
        body = one_line(Path(args.body).read_bytes().decode("utf-8"))
    elif args.text is not None:
        body = one_line(args.text)
    else:
        workflow = found.workflow
        if not workflow and args.workflow:
            workflow = WORKFLOWS[args.workflow]
        if not workflow:
            print("WARNING: the frame names no workflow and --workflow is not "
                  "given, so the ruling carries no workflow.")
        at = args.at
        if not at:
            at = now.strftime("%H:%M")
            print("WARNING: no --at, so the ruling carries the clock's time %s." % at)
        elif not re.fullmatch(r"\d\d:\d\d", at):
            print("WARNING: --at %r is not HH:MM. It is written as given." % at)
        day = args.date or now.strftime("%Y-%m-%d")
        if args.date and not re.fullmatch(r"\d{4}-\d\d-\d\d", args.date):
            print("WARNING: --date %r is not YYYY-MM-DD. It is written as given."
                  % args.date)
        body = ruling_body(args.ruling, at, day, workflow)
    if not body:
        print("the body is empty, so no line was written.", file=sys.stderr)
        return 2

    name = name_of(stack, sid)
    line = "- Status %s (%s): %s" % (when, name, body)
    new, index = insert(text, args.frame, line)
    with open(stack, "wb") as fh:
        fh.write(new.encode("utf-8"))
    print("frame %s, line %d: - Status %s (%s)" % (args.frame, index + 1, when, name))
    if args.no_commit:
        return 0
    return commit(stack, args.frame, frame_name(found), body, when, sid)


if __name__ == "__main__":
    sys.exit(main())
