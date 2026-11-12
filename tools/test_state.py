"""
The state page, tested against stacks that the tests write.

The fixture holds three frames in the kit's format. Frame 10 is held by
one session and has two status lines. Frame 11 waits on the Principal
with a `[med]` rating. Frame 12 stands under `## Parked` and must not
print. One more test builds a stack from the kit's own `stack.md`
template, which is copied below, and adds two frames to it.

The fixtures write "the Principal", and `fit` turns those words into the
words of `state.PRINCIPAL`. So the tests pass after an installer sets the
constant. Build every stack and every expected text through `fit`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import state


def fit(text: str, who: str | None = None) -> str:
    """The text with "the Principal" in the words of the constant, or of `who`."""
    who = state.PRINCIPAL if who is None else who
    return text.replace("the Principal", who).replace(
        "The Principal", who[:1].upper() + who[1:])


RAW_STACK = """# The task stack

## Stack

### 10. The held frame refreshes the index (2026-10-17) (Principal) [aaaa1111]

- Meta workflow. The index is stale after a commit (observed: the build).
- Ends when: the index refreshes.
- Waits on: nothing.
- Reasoning: `plans/archive/x.md`.
- Status 2026-10-17 10:00 (peer-01): the first line.
- Status 2026-10-17 11:00 (peer-01): the second line.

### 11. The open ask waits on the Principal (2026-10-17)

- The project's workflow. A story.
- Ends when: the Principal rules.
- Waits on: the Principal's ruling on the index [med].
- Reasoning: `plans/archive/y.md`.

## Parked

### 12. A parked frame that must not print (2026-10-01) [bbbb2222]

- Meta workflow.
- Waits on: the Principal's order.
- Status 2026-10-01 09:00 (peer-02): parked words.
"""
STACK = fit(RAW_STACK)

# The kit's `stack.md`, copied whole with LF line ends. A test below
# compares this copy to the kit's file when the kit's file is there.
TEMPLATE = """# The task stack

Copy this to `plans/stack.md`. Keep the rules. Push one frame: the
destination from grill question 2. That frame sits at the bottom and
waits on everything above it.

Delete this paragraph and the two above it after you copy the file.

---

The open work, in order, in one file that survives a context compaction.
Top frame first. A frame changes by push, pop, or a status line. "Where
are we" is answered from this file.

Rules:

1. Push a frame before starting it. Pop it when its "ends when" holds.
2. Write the status line with the date at every change and before any
   compaction.
3. Frames are the assistant's to open, order and close. The Principal's
   asks are frames too, marked "(Principal)". The Principal can pop or
   reorder anything.
4. Linear. A frame that waits on another says which.
5. A frame is five lines: what, ends when, waits on, a pointer to the
   reasoning, and a dated status. The status line carries the peer name.
6. The session that holds a frame writes the first eight characters of
   its session id in the heading. A popped frame moves verbatim to
   `plans/archive/stack-<date>.md`.
7. Every frame carries a name of a few words in its heading, and every
   mention of it carries that name with the number. A number alone is an
   index into this file, so a reader who meets one has to open the file
   to learn what it means. That holds in a status line, in a commit
   message, in a message to a peer, and when you answer the Principal.
8. Every conclusion carries a mark with a headline-long reason:
   (observed: where), (reasoned: why), or (ruled: why). Say which
   workflow it is about, the meta workflow or the project's own.

## Stack

### 1. The destination

- (ruled: the Principal, {{date}}) {{The end state, from grill question
  2. A careful person does X and gets Y.}}
- Ends when: {{what the Principal must see before they declare
  finished}}.
- Waits on: every frame above this one.
- Reasoning: `plans/composition.md`, Purpose.
- Status {{date}}: the bottom frame. Open.

## Parked

Items that are true and not yet worth a frame. Each one names where it
came from and which workflow it is about. A parked item leaves this list
when it becomes a frame or when evidence kills it.

---

## How a frame reads when it is working

This is an example, not a frame. Delete it once you have written two of
your own.

```
### 12. The index is stale after a commit (2026-09-17) (Principal) [a1b2c3d4]

- The project's workflow. The index is built once and never refreshed,
  so a change's own symbols are invisible to every later read (observed:
  the build path, and the report in plans/archive/).
- Ends when, each line priced from the anchors, walls counted apart:
  1. A scope report names the index's writers and readers: 50k. Buys:
     the design names real paths, not guessed ones.
  2. A design record, reviewed before any code: 80k. Buys: the
     contract is fixed before an implementer reads it.
  3. The refresh is built with a pinned test: 110k. Buys: a change's
     own symbols are visible to every later read.
  4. A diff review after every pass, on a worktree at the pass's
     commit, its fixes in: 110k. Buys: the change is read by a context
     that never wrote it.
  Total: 350k in agents, about 120k in this context.
- Waits on: nothing.
- Reasoning: the grill of 2026-09-17.
- Status 2026-09-17 14:25 (peer-02): frame 12, the stale index, pushed.
  The scope agent is out, read-only, cap 60k.
- Status 2026-09-17 14:52 (peer-02): the scope report is in, 76k on the
  harness line against 50k priced (observed: the harness usage).
```

Three things make that frame work.

1. **Each ends-when line carries a price and the behaviour the price
   buys.** A line with a price and no behaviour is not understood well
   enough to start. Split it into its own frame.
2. **The status line records the actual beside the estimate.** The
   actual comes from the harness usage line, never from the agent's own
   report of what it used.
3. **Every claim carries a mark.** A reader six weeks later can tell an
   observation from a guess without asking anyone.
"""

TWO_FRAMES = fit("""### 3. Port the state tool (2026-11-12) [aaaa1111]

- Meta workflow. A hand-off read the whole stack (observed: the count).
- Ends when: the state page prints in about 3k tokens.
- Waits on: nothing.
- Reasoning: `plans/archive/grill-2026-11-12.md`.
- Status 2026-11-12 09:00 (peer-01): pushed and claimed.

### 2. Choose the test runner (2026-11-12)

- The project's workflow. Two runners fit the suite.
- Ends when: the Principal picks one.
- Waits on: the Principal's ruling on the runner.
- Reasoning: `plans/archive/grill-2026-11-12.md`.

""")


def write(root: Path, text: str, eol: str = "\n") -> Path:
    path = root / "plans" / "stack.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", eol).encode("utf-8"))
    return path


@pytest.fixture
def repo(tmp_path):
    """A directory that holds the fixture stack under `plans/`."""
    write(tmp_path, STACK)
    return tmp_path


def page(repo: Path, *argv: str, capsys=None) -> str:
    assert state.main(["--stack", str(repo / "plans" / "stack.md"), *argv]) == 0
    return capsys.readouterr().out


# The plain page.

def test_the_held_frame_prints_its_four_lines(repo, capsys):
    out = page(repo, "--sid", "aaaa1111", capsys=capsys)
    assert "## Held by aaaa1111" in out
    assert "10. The held frame refreshes the index (2026-10-17) (Principal)\n" in out
    assert "  What: Meta workflow. The index is stale after a commit" in out
    assert "  Waits on: nothing." in out
    assert "  - Status 2026-10-17 11:00 (peer-01): the second line." in out
    assert "the first line" not in out, "only the last status line prints"


def test_a_long_session_id_selects_by_its_first_eight_characters(repo, capsys):
    out = page(repo, "--sid", "aaaa1111-2222-3333", capsys=capsys)
    assert "10. The held frame" in out


def test_without_a_sid_every_holder_prints(repo, capsys):
    out = page(repo, capsys=capsys)
    assert "## Held by aaaa1111" in out
    assert "bbbb2222" not in out, "a parked frame's holder is not live"


def test_the_parked_frame_never_prints(repo, capsys):
    out = page(repo, capsys=capsys)
    assert "12. A parked" not in out and "parked words" not in out


def test_the_open_decision_carries_its_rating(repo, capsys):
    out = page(repo, capsys=capsys)
    assert fit("[med] 11. The open ask waits on the Principal (2026-10-17): "
               "the Principal's ruling on the index [med].") in out
    assert "Live" not in out, "the kit has no cap on live things"
    assert out.rstrip().endswith("Read the frame's Reasoning line before you act on it.")


def test_a_decision_with_no_rating_prints_no_rating(repo, capsys):
    write(repo, STACK.replace(" on the index [med].", " on the index."))
    out = page(repo, capsys=capsys)
    assert fit("\n11. The open ask waits on the Principal (2026-10-17): "
               "the Principal's ruling on the index.\n") in out
    assert "unrated" not in out


def test_a_long_status_line_keeps_its_time_and_name(repo, capsys):
    write(repo, STACK.replace("the second line.", "word " * 200))
    out = page(repo, "--sid", "aaaa1111", "--limit", "120", capsys=capsys)
    line = [x for x in out.splitlines() if "- Status" in x][0].strip()
    assert line.startswith("- Status 2026-10-17 11:00 (peer-01): word")
    assert line.endswith("...") and len(line) <= 120


def test_the_print_never_edits_the_stack(repo, capsys):
    before = (repo / "plans" / "stack.md").read_bytes()
    page(repo, capsys=capsys)
    assert (repo / "plans" / "stack.md").read_bytes() == before


def test_a_crlf_stack_prints_the_same_page(repo, capsys):
    lf = page(repo, "--sid", "aaaa1111", capsys=capsys)
    write(repo, STACK, eol="\r\n")
    crlf = page(repo, "--sid", "aaaa1111", capsys=capsys)
    assert lf.split("\n", 1)[1] == crlf.split("\n", 1)[1]


def test_order_waits_are_not_open_decisions(repo, capsys):
    extra = fit("".join(
        "### %d. Order %d (2026-10-17)\n\n- Meta workflow.\n"
        "- Waits on: %s\n\n" % (n, n, wait) for n, wait in (
            (20, "the Principal's order. Recommended after frame 9."),
            (21, "nothing. The Principal orders it."),
            (22, "the Principal's order, and the Principal's ruling on the door."))))
    write(repo, STACK.replace("## Parked", extra + "## Parked"))
    out = page(repo, capsys=capsys)
    assert "20. Order" not in out and "21. Order" not in out
    assert "22. Order 22" in out, "a decision beside an order still counts"


def test_a_cited_ruling_is_not_an_open_decision(repo, capsys):
    """A mark cites a word that was given. A wait names a word not yet given."""
    extra = fit("".join(
        "### %d. Cited %d (2026-10-17)\n\n- Meta workflow.\n"
        "- Waits on: %s\n\n" % (n, n, wait) for n, wait in (
            (30, "the gate. The repair is ruled (ruled: the Principal, "
                 "2026-10-24 01:05, \"Yes\")."),
            (31, "frame 9's end (reasoned: the Principal's own price)."),
            (32, "the Principal's ruling on the cap (observed: frame 9's count)."))))
    write(repo, STACK.replace("## Parked", extra + "## Parked"))
    out = page(repo, capsys=capsys)
    assert "30. Cited" not in out and "31. Cited" not in out
    assert "32. Cited 32" in out, "a wait beside a mark still counts"


def test_a_tag_after_the_sid_does_not_unhold_a_frame(repo, capsys):
    write(repo, STACK.replace("[aaaa1111]", "[aaaa1111] (parked)"))
    out = page(repo, "--sid", "aaaa1111", capsys=capsys)
    assert "10. The held frame refreshes the index (2026-10-17) (Principal) (parked)" in out


def test_a_sid_in_round_brackets_holds_a_frame(repo, capsys):
    write(repo, STACK.replace("[aaaa1111]", "(aaaa1111)"))
    out = page(repo, "--sid", "aaaa1111", capsys=capsys)
    assert "10. The held frame refreshes the index (2026-10-17) (Principal)\n" in out


WRAPPED = fit(RAW_STACK.replace(
    "- Meta workflow. The index is stale after a commit (observed: the build).\n",
    "- Meta workflow. The index is stale after a commit (observed: the\n"
    "  build), and the second line of the bullet prints.\n").replace(
    "- Status 2026-10-17 11:00 (peer-01): the second line.\n",
    "- Status 2026-10-17 11:00 (peer-01): the second line\n"
    "  wraps to a third line.\n").replace(
    "- Waits on: the Principal's ruling on the index [med].\n",
    "- Waits on: the scope report of frame 10, and then a ruling by\n"
    "  the Principal on the index [med].\n"))


def test_a_wrapped_bullet_prints_whole(repo, capsys):
    write(repo, WRAPPED)
    out = page(repo, "--sid", "aaaa1111", capsys=capsys)
    assert ("  What: Meta workflow. The index is stale after a commit (observed: "
            "the build), and the second line of the bullet prints.") in out
    assert ("  - Status 2026-10-17 11:00 (peer-01): the second line wraps to a "
            "third line.") in out


def test_a_wrapped_wait_that_names_the_principal_on_its_second_line(repo, capsys):
    write(repo, WRAPPED)
    out = page(repo, capsys=capsys)
    decisions = out.split("## Open decisions\n")[1].split("\n\n")[0]
    assert decisions == fit("[med] 11. The open ask waits on the Principal "
                            "(2026-10-17): the scope report of frame 10, and then "
                            "a ruling by the Principal on the index [med].")


def test_a_wrapped_assumption_prints_on_the_since_page(repo, capsys):
    write(repo, fit(RAW_STACK.replace(
        "- Status 2026-10-17 11:00 (peer-01): the second line.\n",
        "- Status 2026-10-18 01:00 (peer-01): the cheap fix runs, and the\n"
        "  mark wraps (assumed: the Principal takes the cheap fix).\n")))
    out = page(repo, "--since", "2026-10-17", capsys=capsys)
    section = out.split("## Decided under assumption")[1].split("## Waits")[0]
    assert fit("the mark wraps (assumed: the Principal takes the cheap fix).") in section


def test_a_session_with_no_frame_says_so(repo, capsys):
    out = page(repo, "--sid", "cccc3333", capsys=capsys)
    assert "## Held by cccc3333\nNo frame." in out


def test_a_bad_sid_or_a_missing_stack_exits_2(repo, tmp_path):
    assert state.main(["--stack", str(repo / "plans" / "stack.md"),
                       "--sid", "../x"]) == 2
    assert state.main(["--stack", str(tmp_path / "none.md")]) == 2


def test_a_principal_with_a_name_is_matched_by_the_constant(repo, tmp_path):
    """An installer whose stack writes a name sets `PRINCIPAL` to it.

    The test edits a copy of the tool the way an installer edits the tool,
    and runs the copy as a script.
    """
    source = Path(state.__file__).read_bytes().decode("utf-8")
    lines = re.findall(r'^PRINCIPAL = ".*"', source, flags=re.MULTILINE)
    assert len(lines) == 1
    name = "Grace" if state.PRINCIPAL == "Ada" else "Ada"
    copy = tmp_path / "named" / "state.py"
    copy.parent.mkdir()
    copy.write_bytes(source.replace(lines[0], 'PRINCIPAL = "%s"' % name)
                     .encode("utf-8"))
    write(repo, fit(RAW_STACK.replace(
        "## Parked", "### 15. Waits on the order (2026-10-17)\n\n"
        "- Waits on: the Principal's order.\n\n## Parked"), name))
    run = subprocess.run([sys.executable, str(copy), "--since", "2026-10-01",
                          "--stack", str(repo / "plans" / "stack.md")],
                         capture_output=True)
    out = run.stdout.decode("utf-8").replace("\r\n", "\n")
    assert run.returncode == 0, run.stderr
    assert "## Waits on %s\n[med] 11. The open ask" % name in out
    assert "15. Waits on the order" not in out


# The reader of open frames.

def test_open_frames_reads_every_frame_of_the_stack_held_or_parked(tmp_path):
    path = tmp_path / "stack.md"
    path.write_bytes((
        "# Stack page\n## Stack\n### 5. A held frame [aaaaaaaa]\n- Meta workflow.\n"
        "## The batches\n### 6. A frame under another section\n"
        "## Parked\n### 7. A parked frame\n"
        "- Status 2026-10-28 01:00 (peer-01): parked\n").encode("utf-8"))
    assert state.open_frames(path) == {5, 6, 7}


def test_a_heading_in_a_code_block_is_not_a_frame(tmp_path):
    path = tmp_path / "stack.md"
    path.write_bytes((
        "## Stack\n### 5. A frame\n- Meta workflow.\n\n## Example\n\n"
        "```\n### 12. An example\n- Status 2026-09-17 14:25 (peer-02): x\n```\n"
        ).encode("utf-8"))
    assert state.open_frames(path) == {5}


# The kit's own template, with two frames pushed on it.

def from_template(root: Path) -> Path:
    text = fit(TEMPLATE).replace("{{date}}", "2026-11-12")
    return write(root, text.replace("### 1. The destination", TWO_FRAMES
                                    + "### 1. The destination"))


def test_the_template_with_two_frames_reads_as_three_frames(tmp_path, capsys):
    stack = from_template(tmp_path)
    assert state.open_frames(stack) == {1, 2, 3}, "the worked example is not a frame"
    frames = {f.number: f for f in state.parse(state.read_lines(stack))}
    assert sorted(frames) == ["1", "2", "3"]
    bottom = frames["1"]
    assert bottom.waits == "every frame above this one."
    assert not bottom.waits_on_principal
    assert bottom.lines[bottom.statuses[-1]] == "- Status 2026-11-12: the bottom frame. Open."
    assert frames["3"].holder == "aaaa1111" and frames["3"].workflow == "Meta"
    assert frames["2"].workflow == "The project's"

    out = page(tmp_path, "--sid", "aaaa1111", capsys=capsys)
    assert "3. Port the state tool (2026-11-12)\n" in out
    assert "  - Status 2026-11-12 09:00 (peer-01): pushed and claimed." in out
    decisions = out.split("## Open decisions\n")[1].split("\n\n")[0]
    assert decisions == fit("2. Choose the test runner (2026-11-12): "
                            "the Principal's ruling on the runner.")
    assert "12. The index is stale" not in out

    out = page(tmp_path, capsys=capsys)
    assert "## Held by aaaa1111" in out and "a1b2c3d4" not in out


def test_the_template_prints_a_since_page(tmp_path, capsys):
    from_template(tmp_path)
    out = page(tmp_path, "--since", "2026-11-01", capsys=capsys)
    assert fit("## Waits on the Principal\n2. Choose the test runner") in out
    rulings = out.split("## Rulings since 2026-11-01\n")[1]
    assert rulings.strip() == "None.", "a dated mark on a bullet is not a status line"


def test_the_copy_of_the_template_matches_the_kit():
    """The copy above is the kit's file. Outside the kit, the file is absent."""
    kit = Path(__file__).resolve().parent.parent / "stack.md"
    if not kit.is_file():
        pytest.skip("no kit stack.md beside tools/")
    text = kit.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if not text.startswith("# The task stack\n\nCopy this to `plans/stack.md`."):
        pytest.skip("the stack.md beside tools/ is not the kit's template")
    assert text == TEMPLATE, "the kit's stack.md changed. Copy it into TEMPLATE again."


# The page for the Principal's return, `--since`.

SINCE_STACK = fit(RAW_STACK.replace(
    "- Status 2026-10-17 11:00 (peer-01): the second line.\n",
    "- Status 2026-10-17 11:00 (peer-01): the second line.\n"
    "- Status 2026-10-18 01:00 (peer-01): the cheap fix runs (assumed: the "
    "Principal takes the cheap fix).\n"
    "- Status 2026-10-18 02:00 (peer-01): **ruled. The Principal, 2026-10-18 "
    "01:58, in the terminal: \"yes\"** (ruled: the Principal, in their words).\n"
    "- Status 2026-10-15 09:00 (peer-01): old (assumed: an old guess) "
    "and (ruled: the Principal, 2026-10-14 10:00).\n").replace(
    "- Reasoning: `plans/archive/y.md`.\n",
    "- Reasoning: `plans/archive/y.md`.\n"
    "- Status 2026-10-18 03:00 (peer-02): the ask stands (ruled: the "
    "Principal, 2026-10-17 22:00, on the scope).\n").replace(
    "### 11. The open ask",
    "### 13. A high ask (2026-10-17)\n\n- Meta workflow.\n"
    "- Waits on: the Principal's ruling [high].\n\n### 14. An order (2026-10-17)\n\n"
    "- Meta workflow.\n- Waits on: the Principal's order.\n\n"
    "### 11. The open ask"))


def archive(repo: Path, day: str, text: str) -> None:
    path = repo / "plans" / "archive" / ("stack-%s.md" % day)
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


@pytest.fixture
def since_repo(repo):
    write(repo, SINCE_STACK)
    archive(repo, "2026-10-18", "# Archive\n\n### 7. A closed index frame "
            "(2026-10-10) [aaaa1111]\n\n- Status 2026-10-18 00:00 (x): closed.\n")
    archive(repo, "2026-10-16", "### 6. Closed too early (2026-10-01)\n")
    archive(repo, "grill-2026-10-18", "### 5. Not a stack archive\n")
    return repo


def test_since_prints_four_sections_and_nothing_else(since_repo, capsys):
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    heads = [x for x in out.splitlines() if x.startswith("## ")]
    assert heads == ["## Closed since 2026-10-17",
                     "## Decided under assumption since 2026-10-17",
                     fit("## Waits on the Principal"), "## Rulings since 2026-10-17"]
    assert "Held by" not in out


def test_since_lists_the_archived_frames_from_the_date(since_repo, capsys):
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    assert "7. A closed index frame (2026-10-10) (archived 2026-10-18)" in out
    assert "6. Closed too early" not in out
    assert "5. Not a stack archive" not in out


def test_since_lists_assumptions_and_rulings_newest_first(since_repo, capsys):
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    section = out.split("## Decided under assumption")[1].split("## Waits")[0]
    assert fit("(assumed: the Principal takes the cheap fix)") in section
    assert "an old guess" not in out, "a line before the date stays out"
    rulings = out.split("## Rulings since 2026-10-17")[1]
    rows = [x for x in rulings.splitlines() if x.strip() and "::" in x]
    assert rows[0].startswith(fit("11. The open ask waits on the Principal "
                                  "(2026-10-17) :: - Status 2026-10-18 03:00"))
    assert rows[1].startswith("10. The held frame") and '"yes"' in rows[1]
    assert len(rows) == 2


def test_since_ranks_the_waits_and_drops_the_order_waits(since_repo, capsys):
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    section = out.split(fit("## Waits on the Principal"))[1].split("## Rulings")[0]
    rows = [x for x in section.splitlines() if x.startswith("[")]
    assert rows[0].startswith("[high] 13. A high ask")
    assert rows[1].startswith("[med] 11. The open ask")
    assert "14. An order" not in out


def test_since_cuts_the_oldest_rows_to_the_cap(since_repo, capsys):
    many = fit("".join("- Status 2026-10-18 %02d:%02d (peer-01): (assumed: the "
                       "Principal's question %d %s).\n" % (h, m, h * 60 + m, "x" * 200)
                       for h in range(4, 10) for m in range(0, 60, 2)))
    write(since_repo, SINCE_STACK.replace(
        "- Reasoning: `plans/archive/x.md`.\n",
        "- Reasoning: `plans/archive/x.md`.\n" + many))
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    assert len(out) <= 12000
    assert "older rows cut to keep the page under 12000 characters." in out
    assert fit("the Principal's question 598") in out, "the newest row stays"
    assert fit("the Principal's question 240 ") not in out, "the oldest row goes"


def test_since_refuses_a_value_that_is_not_a_date(since_repo):
    assert state.main(["--stack", str(since_repo / "plans" / "stack.md"),
                       "--since", "yesterday"]) == 2


def with_statuses(repo: Path, *lines: str) -> None:
    """Add status lines to frame 10 of the `--since` fixture, through `fit`."""
    write(repo, SINCE_STACK.replace(
        "- Reasoning: `plans/archive/x.md`.\n",
        "- Reasoning: `plans/archive/x.md`.\n" + "".join(fit(x) + "\n" for x in lines)))


def rulings_of(out: str) -> list[str]:
    return [x for x in out.split("## Rulings since")[1].splitlines() if "::" in x]


def test_an_undated_ruling_mark_counts_by_the_status_date(since_repo, capsys):
    with_statuses(since_repo,
                  '- Status 2026-10-17 16:51 (peer-7d): the Principal, 2026-10-17 '
                  'about 16:50, in the terminal: "File writes were always '
                  'permitted" (ruled: the Principal, in their words).',
                  "- Status 2026-10-16 09:00 (peer-7d): (ruled: the Principal, in "
                  "their words) before the date.")
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    assert any("File writes were always permitted" in r for r in rulings_of(out))
    assert "before the date" not in out


def test_a_ruling_cited_again_is_folded_into_the_first(since_repo, capsys):
    with_statuses(since_repo,
                  "- Status 2026-10-18 05:00 (peer-01): as ruled (ruled: the "
                  "Principal, 2026-10-18 01:58, the same).",
                  "- Status 2026-10-18 06:00 (peer-01): again (ruled: the "
                  "Principal, 2026-10-18 01:58).")
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    rows = rulings_of(out)
    assert len(rows) == 2
    assert rows[1].startswith("10. The held frame") and '"yes"' in rows[1]
    assert rows[1].endswith("(cited again 2 times)")


def test_only_the_assumed_mark_counts_as_an_assumption(since_repo, capsys):
    with_statuses(since_repo,
                  "- Status 2026-10-18 06:00 (peer-01): a plan step (reasoned: "
                  "the Principal's design).",
                  "- Status 2026-10-18 07:00 (peer-01): taken by timeout.")
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    section = out.split("## Decided under assumption")[1].split("## Waits")[0]
    assert fit("(assumed: the Principal takes the cheap fix)") in section
    assert "a plan step" not in section
    assert "taken by timeout" not in section, "the kit defines no timeout phrase"


def test_a_wait_of_nothing_is_no_decision_and_impact_words_rate(since_repo, capsys):
    text = SINCE_STACK.replace(
        fit("- Waits on: the Principal's ruling [high]."),
        fit("- Waits on: nothing. The Principal ruled the shape [high].")).replace(
        fit("- Waits on: the Principal's ruling on the index [med]."),
        fit("- Waits on: the Principal's ruling, medium impact."))
    write(since_repo, text)
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    section = out.split(fit("## Waits on the Principal"))[1].split("## Rulings")[0]
    rows = [x for x in section.splitlines() if x.strip()]
    assert rows == [fit("[med] 11. The open ask waits on the Principal (2026-10-17): "
                        "the Principal's ruling, medium impact.")]


def test_a_ruling_on_a_closed_frame_shows_from_the_archive(since_repo, capsys):
    archive(since_repo, "2026-10-18", fit(
            "### 7. A closed index frame (2026-10-10) [aaaa1111]\n\n"
            "- Status 2026-10-18 00:30 (x): **ruled. The Principal, 2026-10-18 "
            '00:29, in the terminal: "close it"** (ruled: the Principal, in '
            "their words).\n"
            "- Status 2026-10-18 00:40 (x): closed (assumed: they wanted it closed).\n"))
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    assert any(r.startswith("7. A closed index frame (2026-10-10) (closed) :: ")
               and "close it" in r for r in rulings_of(out))
    assert "(closed) :: - Status 2026-10-18 00:40" in out


def test_the_cap_cuts_closed_rows_and_never_the_waits(since_repo, capsys):
    many = "".join("### %d. A closed frame with a long name number %d %s (2026-10-10)\n"
                   % (n, n, "y" * 60) for n in range(300, 420))
    archive(since_repo, "2026-10-18", many)
    with_statuses(since_repo, *[
        "- Status 2026-10-18 %02d:%02d (peer-01): (ruled: the Principal, "
        "2026-10-18 %02d:%02d) words %s." % (h, m, h, m, "z" * 150)
        for h in range(4, 8) for m in range(0, 60, 6)])
    out = page(since_repo, "--since", "2026-10-17", capsys=capsys)
    assert len(out) <= 12000
    closed = out.split("## Closed since")[1].split("## Decided")[0]
    assert "older rows cut to keep the page under 12000 characters." in closed
    assert "300. A closed frame" in closed, "the first row of the newest file stays"
    assert "419. A closed frame" not in closed
    rulings = out.split("## Rulings since")[1]
    assert "older rows cut" in rulings
    assert "[high] 13. A high ask" in out and "[med] 11. The open ask" in out
