r"""
The sweep, tested on its bytes.

The frame's test is that a file keeps its own line ending. Every assertion
about a file compares the bytes whole, because a check on the ending class
passes on a corrupt `\r\r\n` file that a byte compare catches.

Each test builds its own repository under `tmp_path`. A fresh `git init`
under temp inherits `core.autocrlf=true` from Git for Windows, and under
`autocrlf=true` a turned ending shows no diff. So the recipe here writes
bytes and turns `autocrlf` off.
"""
from __future__ import annotations

import codecs
import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

import sweep

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
}


def git(root: Path, *args: str) -> str:
    """Run git under a pinned identity, so a commit here is replayable."""
    out = subprocess.run(["git", "-C", str(root), *args],
                         capture_output=True, text=True,
                         env={**os.environ, **GIT_ENV})
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout

ALPHA_CRLF = b"alpha\r\nbeta\r\n"
ALPHA_LF = b"alpha\nbeta\n"

# A transform file that holds the word it replaces. The sweep excludes the
# transform, so the file's own bytes prove the exclusion.
UPPER = b"def transform(text, path):\n    return text.replace('alpha', 'ALPHA')\n"
RAISER = b"def transform(text, path):\n    raise ValueError('boom')\n"
CR_BACK = (b"def transform(text, path):\n"
           b"    new = text.replace('alpha', 'ALPHA')\n"
           b"    return new.replace(chr(10), chr(13) + chr(10))\n")


def repo(tmp_path, files: dict[str, bytes]):
    """A real repository, built from bytes, with git's ending rewrite off."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "core.autocrlf", "false")
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixtures")
    return root


def upper(*args: str) -> list[str]:
    """The plain edit every test that is not about the edit uses."""
    return [*args, "--pattern", "alpha", "--replace", "ALPHA"]


# ---------------------------------------------------------------------------
# The bytes
# ---------------------------------------------------------------------------

def test_each_file_keeps_its_own_ending(tmp_path, capsys):
    """The frame's test: every file keeps every byte that is not the edit."""
    root = repo(tmp_path, {
        "a.py": ALPHA_CRLF,
        "b.py": ALPHA_LF,
        "bomcrlf.py": codecs.BOM_UTF8 + ALPHA_CRLF,
        "nofinal.py": b"alpha\r\nbeta",
        "latin1.py": b"alpha \xe9 beta\n",
    })

    code = sweep.main(upper("--glob", "*.py", "--diff"), root)

    assert code == 4                       # the latin-1 file is skipped
    assert (root / "a.py").read_bytes() == b"ALPHA\r\nbeta\r\n"
    assert (root / "b.py").read_bytes() == b"ALPHA\nbeta\n"
    assert (root / "bomcrlf.py").read_bytes() == (codecs.BOM_UTF8
                                                  + b"ALPHA\r\nbeta\r\n")
    assert (root / "nofinal.py").read_bytes() == b"ALPHA\r\nbeta"
    assert (root / "latin1.py").read_bytes() == b"alpha \xe9 beta\n"
    out = capsys.readouterr().out
    assert "touched 4:" in out
    assert "a.py 1 matches (CRLF)" in out
    assert "b.py 1 matches (LF)" in out
    assert "skipped (not utf-8) 1:" in out
    assert "-alpha" in out and "+ALPHA" in out     # the --diff body


def test_the_stat_reports_the_write(tmp_path, capsys):
    """The stat is the output `autocrlf=true` hides: a turned ending shows none."""
    root = repo(tmp_path, {"a.py": ALPHA_CRLF})

    assert sweep.main(upper("--glob", "*.py"), root) == 0

    out = capsys.readouterr().out
    assert " a.py | 2 +-" in out
    assert "1 file changed, 1 insertion(+), 1 deletion(-)" in out


def test_a_bom_survives(tmp_path):
    """The tool notes the BOM from the bytes, so it can put the BOM back."""
    root = repo(tmp_path, {"a.py": codecs.BOM_UTF8 + ALPHA_LF})

    assert sweep.main(upper("--glob", "*.py"), root) == 0
    assert (root / "a.py").read_bytes() == codecs.BOM_UTF8 + b"ALPHA\nbeta\n"


def test_a_file_with_no_one_ending_is_skipped(tmp_path, capsys):
    """A mixed file and a lone CR are skipped, listed, and left alone."""
    root = repo(tmp_path, {"mixed.py": b"alpha\r\nbeta\n",
                           "lonecr.py": b"alpha\rbeta\r\n"})

    code = sweep.main(upper("--glob", "*.py"), root)

    assert code == 4
    assert (root / "mixed.py").read_bytes() == b"alpha\r\nbeta\n"
    assert (root / "lonecr.py").read_bytes() == b"alpha\rbeta\r\n"
    out = capsys.readouterr().out
    assert "skipped (mixed endings) 2:" in out
    assert "mixed.py" in out and "lonecr.py" in out


def test_a_binary_file_is_skipped(tmp_path, capsys):
    root = repo(tmp_path, {"a.py": ALPHA_LF, "blob.bin": b"\x00\x01alpha\n"})

    code = sweep.main(upper("--glob", "*"), root)

    assert code == 4
    assert (root / "blob.bin").read_bytes() == b"\x00\x01alpha\n"
    assert (root / "a.py").read_bytes() == b"ALPHA\nbeta\n"
    out = capsys.readouterr().out
    assert "skipped (binary) 1:" in out
    assert "blob.bin" in out


def test_the_write_check_catches_a_turned_ending(tmp_path, monkeypatch, capsys):
    r"""`write_text` turns a CRLF file into `\r\r\n`, and the byte compare sees it."""
    root = repo(tmp_path, {"a.py": ALPHA_CRLF})

    def turned(path, data):
        path.write_bytes(data.replace(b"\n", b"\r\n"))

    monkeypatch.setattr(sweep, "write_bytes", turned)
    code = sweep.main(upper("--glob", "*.py"), root)

    assert code == 3
    assert "write mismatch: a.py" in capsys.readouterr().out
    assert (root / "a.py").read_bytes() == b"ALPHA\r\r\nbeta\r\r\n"


def test_a_failed_write_stops_the_run(tmp_path, monkeypatch, capsys):
    """A half-swept tree needs exit 3. Python's own 1 is "nothing changed"."""
    root = repo(tmp_path, {"a.py": ALPHA_LF, "b.py": ALPHA_LF})
    real = sweep.write_bytes
    seen = []

    def failing(path, data):
        seen.append(path)
        if len(seen) == 2:
            raise PermissionError(13, "denied")
        real(path, data)

    monkeypatch.setattr(sweep, "write_bytes", failing)
    code = sweep.main(upper("--glob", "*.py"), root)

    assert code == 3
    assert (root / "a.py").read_bytes() == b"ALPHA\nbeta\n"
    assert (root / "b.py").read_bytes() == ALPHA_LF
    assert "write failed: b.py" in capsys.readouterr().out


def test_an_unreadable_file_is_skipped(tmp_path, monkeypatch, capsys):
    """A file the tool cannot read is a skip, not a traceback."""
    root = repo(tmp_path, {"a.py": ALPHA_LF, "b.py": ALPHA_LF})
    real = Path.read_bytes

    def refuse(self, *args, **kwargs):
        if self.name == "b.py":
            raise PermissionError(13, "denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", refuse)
    code = sweep.main(upper("--glob", "*.py"), root)

    assert code == 4
    out = capsys.readouterr().out
    assert "skipped (unreadable) 1:" in out
    assert "touched 1:" in out


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def test_an_untracked_file_is_not_selected(tmp_path, capsys):
    """A mechanical edit changes the tree, and an untracked file is not the tree's."""
    root = repo(tmp_path, {"a.py": ALPHA_LF})
    (root / "b.py").write_bytes(ALPHA_LF)

    assert sweep.main(upper("--glob", "*.py"), root) == 0

    assert (root / "b.py").read_bytes() == ALPHA_LF
    out = capsys.readouterr().out
    assert "selected 1 files" in out
    assert "b.py" not in out


def test_the_glob_is_a_full_match(tmp_path, capsys):
    """`**` crosses a separator, a single `*` does not, and case counts."""
    root = repo(tmp_path, {"top.py": ALPHA_LF, "pkg/nested.py": ALPHA_LF})

    assert sweep.main(upper("--glob", "**/*.py", "--dry"), root) == 0
    out = capsys.readouterr().out
    assert "selected 2 files" in out
    assert "top.py" in out and "pkg/nested.py" in out

    assert sweep.main(upper("--glob", "*.py", "--dry"), root) == 0
    out = capsys.readouterr().out
    assert "selected 1 files" in out
    assert "nested.py" not in out

    assert sweep.main(upper("--glob", "TOP.PY", "--dry"), root) == 1
    assert "selected 0 files" in capsys.readouterr().out


def test_exclude_removes_a_matched_file(tmp_path, capsys):
    root = repo(tmp_path, {"a.py": ALPHA_LF, "b.py": ALPHA_LF})

    code = sweep.main(upper("--glob", "*.py", "--exclude", "b.py"), root)

    assert code == 0
    assert (root / "a.py").read_bytes() == b"ALPHA\nbeta\n"
    assert (root / "b.py").read_bytes() == ALPHA_LF
    assert "selected 1 files" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The edit
# ---------------------------------------------------------------------------

def test_the_replacement_is_literal(tmp_path):
    r"""`re.sub`'s template reads `\t` as a TAB. The default replacement does not."""
    root = repo(tmp_path, {"a.py": b"path X\n"})

    code = sweep.main(["--glob", "*.py", "--pattern", "X",
                       "--replace", r"C:\temp\new"], root)

    assert code == 0
    assert (root / "a.py").read_bytes() == rb"path C:\temp\new" + b"\n"


def test_template_opts_into_a_backreference(tmp_path):
    root = repo(tmp_path, {"a.py": b"alpha beta\n"})

    code = sweep.main(["--glob", "*.py", "--pattern", "(alpha)",
                       "--replace", r"\1-\1", "--template"], root)

    assert code == 0
    assert (root / "a.py").read_bytes() == b"alpha-alpha beta\n"


def test_a_replacement_that_holds_a_cr_is_skipped(tmp_path, capsys):
    r"""The tool owns the endings. `--template` reads `\r` as a CR."""
    root = repo(tmp_path, {"a.py": ALPHA_LF})

    code = sweep.main(["--glob", "*.py", "--pattern", "beta",
                       "--replace", r"\r", "--template"], root)

    assert code == 4
    assert (root / "a.py").read_bytes() == ALPHA_LF
    out = capsys.readouterr().out
    assert "skipped (edit returned CR) 1:" in out
    assert "touched 0:" in out

    # The literal form takes a real CR straight from the command line.
    code = sweep.main(["--glob", "*.py", "--pattern", "beta",
                       "--replace", "\r"], root)

    assert code == 4
    assert (root / "a.py").read_bytes() == ALPHA_LF
    assert "skipped (edit returned CR) 1:" in capsys.readouterr().out


def test_dry_writes_nothing(tmp_path, capsys):
    root = repo(tmp_path, {"a.py": ALPHA_LF})

    code = sweep.main(upper("--glob", "*.py", "--dry"), root)

    assert code == 0
    assert (root / "a.py").read_bytes() == ALPHA_LF
    assert "would touch 1:" in capsys.readouterr().out


def test_no_match_changes_nothing(tmp_path, capsys):
    root = repo(tmp_path, {"a.py": ALPHA_LF})

    code = sweep.main(["--glob", "*.py", "--pattern", "zeta",
                       "--replace", "ZETA"], root)

    assert code == 1
    assert (root / "a.py").read_bytes() == ALPHA_LF
    out = capsys.readouterr().out
    assert "touched 0:" in out
    assert "unchanged 1" in out


# ---------------------------------------------------------------------------
# The transform
# ---------------------------------------------------------------------------

def test_a_transform_edits_and_excludes_itself(tmp_path, capsys):
    """A sweep cannot rewrite its own rule, so the transform file is excluded."""
    root = repo(tmp_path, {"a.py": ALPHA_CRLF, "xform.py": UPPER})

    code = sweep.main(["--glob", "*.py", "--transform", str(root / "xform.py")],
                      root)

    assert code == 0
    assert (root / "a.py").read_bytes() == b"ALPHA\r\nbeta\r\n"
    assert (root / "xform.py").read_bytes() == UPPER
    assert "selected 1 files" in capsys.readouterr().out


def test_a_transform_that_returns_cr_is_skipped(tmp_path, capsys):
    """The tool owns the endings, so a hook that returns a CR writes nothing."""
    root = repo(tmp_path, {"a.py": ALPHA_LF, "xform.py": CR_BACK})

    code = sweep.main(["--glob", "*.py", "--transform", str(root / "xform.py")],
                      root)

    assert code == 4
    assert (root / "a.py").read_bytes() == ALPHA_LF
    out = capsys.readouterr().out
    assert "skipped (edit returned CR) 1:" in out
    assert "touched 0:" in out


def test_a_transform_outside_the_repository(tmp_path, capsys):
    """The transform has no path inside the repository, and no empty pattern."""
    root = repo(tmp_path, {"a.py": ALPHA_LF})
    outside = tmp_path / "xform.py"
    outside.write_bytes(UPPER)

    code = sweep.main(["--glob", "*.py", "--transform", str(outside)], root)

    assert code == 0
    assert (root / "a.py").read_bytes() == b"ALPHA\nbeta\n"
    assert "selected 1 files" in capsys.readouterr().out


def test_a_transform_that_raises_writes_nothing(tmp_path):
    root = repo(tmp_path, {"a.py": ALPHA_LF, "xform.py": RAISER})

    code = sweep.main(["--glob", "*.py", "--transform", str(root / "xform.py")],
                      root)

    assert code == 2
    assert (root / "a.py").read_bytes() == ALPHA_LF


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [
    ["--glob", "*.py", "--pattern", "a", "--replace", "b",
     "--transform", "x.py"],                       # both edit forms
    ["--glob", "*.py"],                            # neither edit form
    ["--glob", "*.py", "--pattern", "(", "--replace", "b"],   # a bad regex
    ["--pattern", "a", "--replace", "b"],          # no glob
    ["--glob", "*.py", "--transform", "nope.py"],  # a missing hook
])
def test_a_usage_error_exits_2(tmp_path, argv):
    root = repo(tmp_path, {"a.py": ALPHA_LF})

    assert sweep.main(argv, root) == 2
    assert (root / "a.py").read_bytes() == ALPHA_LF


# ---------------------------------------------------------------------------
# Glob selection, which is a translation now and not `PurePath.full_match`
# ---------------------------------------------------------------------------

# Every pattern shape the tool documents, plus the shapes that break a naive
# translation: a star beside a separator, a `**` inside a larger segment, a
# class, a range, a negation, and a path holding regex metacharacters.
GLOBS = [
    "tests/*.py", "*.py", "**/*.py", "src/**/*.py", "src/**", "**",
    "a/**/b", "?.py", "[ab].py", "[!ab].py", "[a-c].py", "[]].py",
    "TESTS/*.PY", "a**b/x", "**/**/*.py", "src/*/x.py", "*", "**.py",
    "src/**/", "./x.py", "a+b.py", "a(b).py", "a.b|c", "x[.py",
    "tools/sweep.py", "tools/*.py", "**/test_*.py", "a/*/*/d.py",
    "[!a]*.py", "*[0-9].py", "s?c/*.py", "**/x", "x/**", "a/**",
]
PATHS = [
    "a.py", "b.py", "c.py", "d.py", "x.py", "x/a.py", "tests/x.py",
    "tests/sub/x.py", "tests/test_a.py", "src/a.py", "src/a/b.py",
    "src/a/b/c.py", "src/x.py", "a/b", "a/x/b", "ab/x", "aXXb/x",
    "aX/Yb/x", "src", "tools/sweep.py", "tools/test_sweep.py",
    "a+b.py", "a(b).py", "a.b|c", "x[.py", "].py", "a1.py", "a/b/c/d.py",
    "sxc/a.py", "x", "x/y", "x/y/z", "a/b/c",
]


@pytest.mark.skipif(not hasattr(PurePosixPath, "full_match"),
                    reason="no reference implementation before Python 3.13")
@pytest.mark.parametrize("glob", GLOBS)
def test_the_translation_agrees_with_full_match(glob):
    """The translator must answer exactly what `PurePath.full_match` answers.

    This is the whole specification. `full_match` arrived in Python 3.13
    and the kit must run on less, so the translation carries the
    behaviour. Where an interpreter has the reference, every case is
    compared against it, and a disagreement is a defect in the
    translation and never a new opinion about globs.
    """
    for path in PATHS:
        pure = PurePosixPath(path)
        assert sweep._full_match(pure, glob) == pure.full_match(glob), (
            f"{glob!r} against {path!r}")


@pytest.mark.parametrize("glob,path,expected", [
    ("tests/*.py", "tests/x.py", True),
    ("tests/*.py", "tests/sub/x.py", False),    # a star never crosses a /
    ("**/*.py", "a.py", True),                  # ** matches zero segments
    ("**/*.py", "src/a/b.py", True),
    ("a/**/b", "a/b", True),
    ("a/**/b", "a/x/y/b", True),
    ("src/**", "src/a.py", True),
    ("src/**", "src", False),                   # a trailing ** needs a segment
    ("a**b/x", "aXXb/x", True),
    ("a**b/x", "aX/Yb/x", False),               # ** inside a segment is a star
    ("TESTS/*.PY", "tests/x.py", False),        # nothing folds case
    ("[ab].py", "a.py", True),
    ("[!ab].py", "c.py", True),
    ("[a-c].py", "b.py", True),
    ("[a-c].py", "d.py", False),
    ("a+b.py", "a+b.py", True),                 # a metacharacter is a literal
    ("a(b).py", "a(b).py", True),
    ("a.b|c", "a.b|c", True),
    ("a.b|c", "aXb|c", False),                  # a dot is a literal dot
])
def test_the_documented_glob_rules(glob, path, expected):
    """The rules the docstring states, checked on every interpreter."""
    assert sweep._full_match(PurePosixPath(path), glob) is expected


def test_a_glob_compiles_once(monkeypatch):
    """Selection asks per file and per pattern, so the compile is cached."""
    sweep._matcher.cache_clear()
    for _ in range(50):
        sweep._full_match(PurePosixPath("src/a/b.py"), "src/**/*.py")
    info = sweep._matcher.cache_info()
    assert info.misses == 1 and info.hits == 49
