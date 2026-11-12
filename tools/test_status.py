"""
The status tool, tested on stacks that the tests write.

Every test that commits builds its own git repository under `tmp_path`.
A fresh `git init` under temp inherits `core.autocrlf=true` from Git for
Windows, so the environment turns `autocrlf` and signing off. The clock is
replaced, so every line carries 2031-01-02 03:04. The expected texts come
from `state.PRINCIPAL` through `fit` and from `status.SUMMARY_PREFIX`, so
the tests pass after an installer sets the two constants.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

import state
import status
from test_state import STACK, TEMPLATE, TWO_FRAMES, fit

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "core.autocrlf", "GIT_CONFIG_VALUE_1": "false",
}


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


def write(root: Path, text: str, eol: str = "\n") -> Path:
    path = root / "plans" / "stack.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", eol).encode("utf-8"))
    return path


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repository that holds the fixture stack, committed."""
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)
    git(tmp_path, "init", "-q")
    write(tmp_path, STACK)
    (tmp_path / "other.txt").write_bytes(b"one\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(status, "_clock", lambda: datetime(2031, 1, 2, 3, 4))


def enrol(root: Path, sid: str, name: str) -> None:
    sessions = root / ".handover" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / (sid + ".json")).write_bytes(
        json.dumps({"sid": sid, "name": name}).encode("utf-8"))


def append(repo: Path, *argv: str) -> int:
    return status.main(["--stack", str(repo / "plans" / "stack.md"), *argv])


def lines_of(repo: Path) -> list[str]:
    return (repo / "plans" / "stack.md").read_bytes().decode("utf-8").split("\n")


def test_the_line_goes_after_the_last_status_and_reads_the_clock(repo, clock):
    enrol(repo, "aaaa1111", "peer-39")
    assert append(repo, "10", "--sid", "aaaa1111", "--text", "a new\nline",
                  "--no-commit") == 0
    lines = lines_of(repo)
    at = lines.index("- Status 2026-10-17 11:00 (peer-01): the second line.")
    assert lines[at + 1] == "- Status 2031-01-02 03:04 (peer-39): a new line"


def test_the_enrolment_is_found_outside_git(tmp_path, clock):
    """Outside git, the mailbox sits beside `plans/`."""
    write(tmp_path, STACK)
    enrol(tmp_path, "aaaa1111", "peer-40")
    if subprocess.run(["git", "-C", str(tmp_path), "rev-parse"],
                      capture_output=True).returncode == 0:
        pytest.skip("the temp directory is inside a git repository")
    assert append(tmp_path, "10", "--sid", "aaaa1111", "--text", "x",
                  "--no-commit") == 0
    assert "- Status 2031-01-02 03:04 (peer-40): x" in lines_of(tmp_path)


def test_lf_stays_lf(repo, clock):
    append(repo, "10", "--sid", "aaaa1111", "--text", "x", "--no-commit")
    assert b"\r" not in (repo / "plans" / "stack.md").read_bytes()


def test_crlf_stays_crlf(repo, clock):
    write(repo, STACK, eol="\r\n")
    append(repo, "10", "--sid", "aaaa1111", "--text", "x", "--no-commit")
    data = (repo / "plans" / "stack.md").read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
    assert b"- Status 2031-01-02 03:04 (aaaa1111): x\r\n" in data


def test_a_frame_with_no_status_takes_the_line_after_its_reasoning(repo, clock):
    append(repo, "11", "--sid", "aaaa1111", "--text", "x", "--no-commit")
    lines = lines_of(repo)
    at = lines.index("- Reasoning: `plans/archive/y.md`.")
    assert lines[at + 1] == "- Status 2031-01-02 03:04 (aaaa1111): x"


def test_a_parked_frame_takes_a_line_too(repo, clock):
    append(repo, "12", "--sid", "bbbb2222", "--text", "x", "--no-commit")
    lines = lines_of(repo)
    at = lines.index("- Status 2026-10-01 09:00 (peer-02): parked words.")
    assert lines[at + 1] == "- Status 2031-01-02 03:04 (bbbb2222): x"


def test_a_sid_with_no_enrolment_is_written_and_warned(repo, clock, capsys):
    assert append(repo, "10", "--sid", "eeee5555", "--text", "x",
                  "--no-commit") == 0
    assert "WARNING" in capsys.readouterr().out
    assert b"(eeee5555): x" in (repo / "plans" / "stack.md").read_bytes()


def test_a_ruling_carries_the_words_and_the_workflow(repo, clock):
    enrol(repo, "aaaa1111", "peer-39")
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "yes do it",
           "--at", "02:35", "--no-commit")
    assert fit('- Status 2031-01-02 03:04 (peer-39): **ruled. The Principal, '
               '2031-01-02 02:35, in the terminal: "yes do it"** (ruled: the '
               "Principal, in their words). The project's workflow.") in lines_of(repo)


def test_a_ruling_finds_the_workflow_on_another_bullet(repo, clock):
    old = STACK.replace("- The project's workflow. A story.",
                        "- A story.\n- Meta workflow.")
    write(repo, old)
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "yes", "--at", "23:50",
           "--date", "2031-01-01", "--no-commit")
    text = (repo / "plans" / "stack.md").read_bytes().decode()
    assert fit('**ruled. The Principal, 2031-01-01 23:50, in the terminal: "yes"** '
               '(ruled: the Principal, in their words). Meta workflow.') in text


def test_a_ruling_takes_the_workflow_flag_when_the_frame_names_none(repo, clock, capsys):
    write(repo, STACK.replace("- The project's workflow. A story.", "- A story."))
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "no", "--at", "01:00",
           "--no-commit")
    assert "the ruling carries no workflow" in capsys.readouterr().out
    assert any(x.endswith(fit('"no"** (ruled: the Principal, in their words).'))
               for x in lines_of(repo))
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "yes", "--at", "01:01",
           "--workflow", "project", "--no-commit")
    assert any(x.endswith(fit('"yes"** (ruled: the Principal, in their words). '
                              "The project's workflow.")) for x in lines_of(repo))


def test_a_ruling_with_no_at_carries_the_clock_and_a_warning(repo, clock, capsys):
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "go", "--no-commit")
    assert "carries the clock's time 03:04" in capsys.readouterr().out
    assert any(fit("The Principal, 2031-01-02 03:04, in the terminal") in x
               for x in lines_of(repo))


def test_the_ruling_line_reads_back_as_a_ruling(repo, clock, capsys):
    append(repo, "11", "--sid", "aaaa1111", "--ruling", "yes do it",
           "--at", "02:35", "--no-commit")
    capsys.readouterr()
    assert state.main(["--stack", str(repo / "plans" / "stack.md"),
                       "--since", "2031-01-01"]) == 0
    rulings = capsys.readouterr().out.split("## Rulings since 2031-01-01\n")[1]
    assert rulings.startswith(fit("11. The open ask waits on the Principal "
                                  "(2026-10-17) :: - Status 2031-01-02 03:04"))


def test_a_body_file_keeps_its_backslashes(repo, clock, tmp_path):
    body = tmp_path / "body.txt"
    body.write_bytes(b"C:\\Users\\x and \\n stay\n")
    append(repo, "10", "--sid", "aaaa1111", "--body", str(body), "--no-commit")
    assert b"C:\\Users\\x and \\n stay" in (repo / "plans" / "stack.md").read_bytes()


def test_an_empty_body_writes_nothing(repo, clock):
    before = (repo / "plans" / "stack.md").read_bytes()
    assert append(repo, "10", "--sid", "aaaa1111", "--text", " \n ") == 2
    assert (repo / "plans" / "stack.md").read_bytes() == before


def test_the_commit_holds_the_stack_alone(repo, clock, capsys):
    (repo / "other.txt").write_bytes(b"two\n")
    git(repo, "add", "other.txt")
    assert append(repo, "10", "--sid", "aaaa1111", "--text", "one two three") == 0
    assert "committed" in capsys.readouterr().out
    files = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert files == ["plans/stack.md"]
    assert git(repo, "log", "-1", "--format=%s") == \
        status.SUMMARY_PREFIX + ": frame 10, The held frame refreshes the index"
    body = git(repo, "log", "-1", "--format=%b")
    assert body == ("The status tool appends one line to frame 10, The held frame "
                    "refreshes the index, at 2031-01-02 03:04 for session aaaa1111. "
                    "The line reads: one two three")
    assert git(repo, "diff", "--cached", "--name-only") == "other.txt", \
        "the other staged file stays staged and out of the commit"


def test_a_long_name_is_cut_at_a_word_within_72_characters(repo, clock):
    write(repo, STACK.replace("The held frame refreshes the index",
                              "The held frame refreshes the index after every "
                              "commit on every branch of the repository"))
    git(repo, "commit", "-qam", "longer")
    assert append(repo, "10", "--sid", "aaaa1111", "--text", "x") == 0
    line = git(repo, "log", "-1", "--format=%s")
    full = (status.SUMMARY_PREFIX + ": frame 10, The held frame refreshes the index "
            "after every commit on every branch of the repository")
    assert len(line) <= 72
    assert full.startswith(line) and full[len(line)] == " ", "the cut falls at a word"
    word = full[len(line) + 1:].split(" ")[0]
    assert len(line) + 1 + len(word) > 72, "no word that fits is dropped"
    if status.SUMMARY_PREFIX == "docs(plans)":
        assert line == "docs(plans): frame 10, The held frame refreshes the index after every"


def test_a_failed_commit_exits_1_and_keeps_the_line(repo, clock, capsys):
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-commit").write_bytes(b"#!/bin/sh\nexit 1\n")
    (hooks / "pre-commit").chmod(0o755)
    assert append(repo, "10", "--sid", "aaaa1111", "--text", "x") == 1
    assert "the commit failed" in capsys.readouterr().err
    assert "- Status 2031-01-02 03:04 (aaaa1111): x" in lines_of(repo)


def test_the_line_goes_after_a_wrapped_last_status(repo, clock):
    """A wrapped status keeps its continuation lines above the new line."""
    wrapped = STACK.replace(
        "- Status 2026-10-17 11:00 (peer-01): the second line.\n",
        "- Status 2026-10-17 11:00 (peer-01): the second line\n"
        "  continues here\n  and here.\n")
    write(repo, wrapped)
    append(repo, "10", "--sid", "aaaa1111", "--text", "x", "--no-commit")
    lines = lines_of(repo)
    at = lines.index("  and here.")
    assert lines[at - 1] == "  continues here"
    assert lines[at + 1] == "- Status 2031-01-02 03:04 (aaaa1111): x"
    assert lines[at + 2] == ""


def test_the_line_goes_after_a_wrapped_reasoning_line(repo, clock):
    """A frame with no status takes the line after the last wrapped line."""
    write(repo, STACK.replace(
        "- Reasoning: `plans/archive/y.md`.\n",
        "- Reasoning: `plans/archive/y.md`, and the grill of\n  2026-10-17.\n"))
    append(repo, "11", "--sid", "aaaa1111", "--text", "x", "--no-commit")
    lines = lines_of(repo)
    at = lines.index("  2026-10-17.")
    assert lines[at - 1] == "- Reasoning: `plans/archive/y.md`, and the grill of"
    assert lines[at + 1] == "- Status 2031-01-02 03:04 (aaaa1111): x"


def test_a_missing_body_file_exits_2_in_one_line(repo, clock, tmp_path, capsys):
    before = (repo / "plans" / "stack.md").read_bytes()
    assert append(repo, "10", "--sid", "aaaa1111",
                  "--body", str(tmp_path / "none.txt")) == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1 and "Traceback" not in err
    assert "none.txt" in err
    assert (repo / "plans" / "stack.md").read_bytes() == before


def test_a_stack_that_is_not_utf8_exits_2_in_one_line(repo, clock, capsys):
    path = repo / "plans" / "stack.md"
    path.write_bytes("## Stack\n### 1. Caf\xe9 [aaaa1111]\n- What.\n".encode("cp1252"))
    before = path.read_bytes()
    assert append(repo, "1", "--sid", "aaaa1111", "--text", "x") == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1 and "Traceback" not in err
    assert path.read_bytes() == before


def test_an_unknown_frame_writes_nothing(repo, clock):
    before = (repo / "plans" / "stack.md").read_bytes()
    assert append(repo, "99", "--sid", "aaaa1111", "--text", "x") == 2
    assert (repo / "plans" / "stack.md").read_bytes() == before


def test_a_bad_sid_writes_nothing(repo, clock):
    before = (repo / "plans" / "stack.md").read_bytes()
    assert append(repo, "10", "--sid", "../x", "--text", "x") == 2
    assert (repo / "plans" / "stack.md").read_bytes() == before


def test_the_template_takes_lines_on_its_own_frames(repo, clock):
    """The kit's template: the bottom frame, a pushed frame, never the example."""
    text = TEMPLATE.replace("{{date}}", "2026-11-12").replace(
        "### 1. The destination", TWO_FRAMES + "### 1. The destination")
    write(repo, text)
    assert append(repo, "1", "--sid", "aaaa1111", "--text", "x", "--no-commit") == 0
    assert append(repo, "2", "--sid", "aaaa1111", "--text", "y", "--no-commit") == 0
    assert append(repo, "12", "--sid", "aaaa1111", "--text", "z", "--no-commit") == 2
    frames = {f.number: f for f in state.parse(lines_of(repo))}
    bottom = frames["1"].lines
    at = bottom.index("- Status 2026-11-12: the bottom frame. Open.")
    assert bottom[at + 1] == "- Status 2031-01-02 03:04 (aaaa1111): x"
    ask = frames["2"].lines
    at = ask.index("- Reasoning: `plans/archive/grill-2026-11-12.md`.")
    assert ask[at + 1] == "- Status 2031-01-02 03:04 (aaaa1111): y"
    assert lines_of(repo).count("- Status 2031-01-02 03:04 (aaaa1111): z") == 0
