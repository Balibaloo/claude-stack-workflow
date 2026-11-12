r"""
The state page: what a session needs from the stack, and nothing else.

    python tools/state.py                      # every held frame
    python tools/state.py --sid 2555d93f       # one session's frames
    python tools/state.py --since 2026-09-17   # for the Principal's return

The stack is the history, and nobody reads it whole. A session that took
a hand-off and read the whole stack spent 35k of context. This tool
prints the frames that a session holds and the frames that wait on the
Principal, in about 3k tokens. It reads `plans/stack.md` in place and
never edits it.

`--since` prints the page for the Principal's return. It holds four
sections: what closed, what was decided under an assumption, what waits
on the Principal, and what the Principal ruled.

The tool reads the format of the kit's `stack.md` template:

* A frame starts at a heading `### <n>. <name>` and ends at the next
  heading. A heading inside a fenced code block is not a frame, so the
  template's worked example is never read as a frame.
* The frames of the stack stand between `## Stack` and `## Parked`.
* The session that holds a frame writes the first eight characters of
  its session id in the heading, as `[a1b2c3d4]`. The form `(a1b2c3d4)`
  is read too.
* A frame's first bullet says what the frame is. The other fields are
  `- Waits on:`, `- Reasoning:` and the status lines.
* A status line is `- Status <date> <time> (<peer name>): <text>`. The
  time and the peer name can be absent, as on the template's bottom frame.
* A popped frame moves to `plans/archive/stack-<date>.md`.
* A rating such as `[high]`, `[med]` or `[low]` on a Waits on line is
  optional. The kit does not define one, and the tool prints none when
  the line has none.

Set `PRINCIPAL` below to the words your stack uses for the Principal.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

#: The words that name the Principal in the stack. The kit's stack template
#: writes "the Principal". If your sessions write a name, such as "Ada",
#: set the name here. The status tool reads this constant too.
PRINCIPAL = "the Principal"

# The name with no article, for a match in any position.
WHO = re.sub(r"^the\s+", "", PRINCIPAL, flags=re.IGNORECASE)
_WHO = r"(?:\b[Tt]he\s+)?\b" + re.escape(WHO) + r"\b"

HEAD = re.compile(r"^### (\d+)\.\s+(.*)$")
SID = re.compile(r"\[([0-9a-f]{8})\]|\(([0-9a-f]{8})\)")
HOLDERS = re.compile(r"\s*(?:\[[0-9a-f]{8}\]|\([0-9a-f]{8}\))")
FENCE = re.compile(r"^\s*(?:```|~~~)")
STATUS = re.compile(r"^- Status (\d{4}-\d\d-\d\d(?: \d\d:\d\d)?)"
                    r"(?: \(([^)]*)\))?:\s?(.*)$")
RATING = re.compile(r"\[(high|med|low)\]|\b(high|medium|low) impact\b")
WORKFLOW = re.compile(r"\b(Meta|[Tt]he project's) workflow\b")
NAMED = re.compile(_WHO)
# The stack's rule 3 makes the order the assistant's. So a wait on the
# Principal's order is not a wait for a decision.
ORDER_WAIT = re.compile(_WHO + r"'s order|" + _WHO + r" orders it")
# A mark cites a word that the Principal gave. It is not a wait for a word
# that the Principal has not given, so it opens no decision.
CITED = re.compile(r"\((?:ruled|reasoned|observed)[^)]*\)")

FIELD_LIMIT = 200
STATUS_LIMIT = 400


def cut(text: str, limit: int) -> str:
    """Cut a text at a limit, and show the cut."""
    if len(text) <= limit:
        return text
    return text[:max(limit - 3, 0)].rstrip() + "..."


@dataclass
class Frame:
    """One frame of the stack, read from its heading to the next heading."""

    number: str
    heading: str
    start: int
    end: int
    lines: list[str] = field(default_factory=list)
    holders: list[str] = field(default_factory=list)

    @property
    def holder(self) -> str:
        """The last session id in the heading holds the frame."""
        return self.holders[-1] if self.holders else ""

    @property
    def title(self) -> str:
        """The heading without the session ids.

        The tag `(Principal)` stays, because it says the frame is the
        Principal's ask.
        """
        return "%s. %s" % (self.number, HOLDERS.sub("", self.heading).strip())

    def first(self, prefix: str) -> tuple[int, str] | None:
        for i, line in enumerate(self.lines):
            if line.startswith(prefix):
                return i, line
        return None

    @property
    def what(self) -> str:
        """The frame's first bullet, which says what the frame is."""
        hit = self.first("- ")
        return hit[1][2:].strip() if hit else ""

    @property
    def workflow(self) -> str:
        """The workflow of the frame: "Meta", "The project's", or empty.

        The first bullet names it first. A status line names the workflow
        of its own statement, so the status lines are read last.
        """
        hit = self.first("- ")
        rest = self.lines[1:]
        for line in ([hit[1]] if hit else []) + \
                [x for x in rest if not STATUS.match(x)] + \
                [x for x in rest if STATUS.match(x)]:
            m = WORKFLOW.search(line)
            if m:
                word = m.group(1)
                return word[:1].upper() + word[1:]
        return ""

    def field_text(self, prefix: str) -> str:
        hit = self.first(prefix)
        return hit[1][len(prefix):].strip() if hit else ""

    @property
    def waits(self) -> str:
        return self.field_text("- Waits on:")

    @property
    def statuses(self) -> list[int]:
        """The indexes of the status lines, in the order of the file."""
        return [i for i, line in enumerate(self.lines) if STATUS.match(line)]

    @property
    def rating(self) -> str:
        """The rating of the Waits on line first, then of any line, or empty."""
        for line in [self.waits] + self.lines:
            m = RATING.search(line)
            if m:
                word = m.group(1) or m.group(2)
                return "med" if word == "medium" else word
        return ""

    @property
    def waits_on_principal(self) -> bool:
        """The Waits on line names the Principal for a decision.

        A wait on the order does not count, and a cited mark does not
        count. A wait that starts with "nothing" waits on nobody, whatever
        follows.
        """
        if self.waits.lower().startswith("nothing"):
            return False
        rest = CITED.sub("", ORDER_WAIT.sub("", self.waits))
        return bool(NAMED.search(rest))


def parse(lines: list[str], bounded: bool = True) -> list[Frame]:
    """Read the frames between `## Stack` and `## Parked`.

    The lines carry no line end. With `bounded` false, every frame of the
    file is read, because a status line can go to a parked frame too. A
    line inside a fenced code block never starts or ends a frame.
    """
    lo, hi = 0, len(lines)
    if bounded:
        fenced = False
        for i, line in enumerate(lines):
            if FENCE.match(line):
                fenced = not fenced
            elif fenced:
                continue
            elif line.rstrip() == "## Stack" and lo == 0:
                lo = i + 1
            elif line.startswith("## Parked"):
                hi = i
                break
    frames: list[Frame] = []
    current: Frame | None = None
    fenced = False
    for i in range(lo, hi):
        line = lines[i]
        if FENCE.match(line):
            fenced = not fenced
        heading = not fenced and line.startswith("#")
        m = HEAD.match(line) if heading else None
        if heading and current is not None:
            current.end = i
            frames.append(current)
            current = None
        if m:
            text = m.group(2).rstrip()
            # Every id in the heading counts, wherever it stands, so a
            # trailing tag such as "(parked)" does not unhold a frame.
            current = Frame(number=m.group(1), heading=text, start=i, end=i + 1,
                            holders=[a or b for a, b in SID.findall(text)])
        if current is not None:
            current.lines.append(line)
    if current is not None:
        current.end = hi
        frames.append(current)
    return frames


def read_lines(path: Path) -> list[str]:
    """The file's lines with no line end, whatever line end the file uses."""
    text = path.read_bytes().decode("utf-8")
    return [line.rstrip("\r") for line in text.split("\n")]


def open_frames(stack: Path | None = None) -> set[int]:
    """The numbers of the frames that the stack holds, held or parked.

    A frame closes when it moves to `plans/archive`, so every frame left in
    the stack file is open. A parked frame is open too, because it still
    owes its work. A test or a tool that asks whether a frame is open asks
    this one reader.
    """
    path = stack if stack is not None else default_stack()
    return {int(f.number) for f in parse(read_lines(path), bounded=False)}


def status_line(line: str, limit: int) -> str:
    """Cut a status line in its body, so the time and the peer name stay."""
    m = STATUS.match(line)
    if not m:
        return cut(line, limit)
    head = "- Status %s%s: " % (m.group(1), " (%s)" % m.group(2) if m.group(2) else "")
    return head + cut(m.group(3), max(limit - len(head), 40))


def print_frame(frame: Frame, limit: int, out: list[str]) -> None:
    """Four lines: the heading, the first bullet, the wait, the last status."""
    out.append(frame.title)
    out.append("  What: %s" % cut(frame.what or "(none)", FIELD_LIMIT))
    out.append("  Waits on: %s" % cut(frame.waits or "(none)", FIELD_LIMIT))
    marks = frame.statuses
    out.append("  " + (status_line(frame.lines[marks[-1]], limit)
                       if marks else "(no status line)"))


def decision_row(frame: Frame) -> str:
    """One open decision: the rating if the line has one, the title, the wait."""
    rated = "[%s] " % frame.rating if frame.rating else ""
    return "%s%s: %s" % (rated, frame.title, cut(frame.waits, FIELD_LIMIT))


def render(stack: Path, sid: str = "", limit: int = STATUS_LIMIT) -> str:
    """The state page as one text."""
    frames = parse(read_lines(stack))
    held = [f for f in frames if f.holder]
    out: list[str] = ["State of %s, printed %s." % (
        stack.as_posix(), time.strftime("%Y-%m-%d %H:%M"))]

    if sid:
        groups = [(sid, [f for f in held if f.holder == sid[:8]])]
    else:
        by: dict[str, list[Frame]] = {}
        for f in held:
            by.setdefault(f.holder, []).append(f)
        groups = sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for holder, mine in groups:
        out.append("")
        out.append("## Held by %s" % holder[:8])
        if not mine:
            out.append("No frame.")
        for f in mine:
            print_frame(f, limit, out)

    out += ["", "## Open decisions"]
    asks = [f for f in frames if f.waits_on_principal]
    out += [decision_row(f) for f in asks] or ["None."]

    out += ["", "## Next", "Read the frame's Reasoning line before you act on it."]
    return "\n".join(out) + "\n"


ARCHIVE = re.compile(r"^stack-(\d{4}-\d\d-\d\d)\.md$")
# A decision taken for the Principal while they are away carries this mark.
ASSUMED = ("(assumed:",)
RULED_MARK = re.compile(r"\(ruled: " + _WHO + r"(?:, (\d{4}-\d\d-\d\d))?")
RULING_KEY = re.compile(_WHO + r", (\d{4}-\d\d-\d\d)(?: about)? (\d\d:\d\d)")
QUOTE = re.compile(r'"([^"]{4,})"')
RANK = {"high": 0, "med": 1, "low": 2, "": 3}
NAME_LIMIT = 100
ROW_LIMIT = 300
SINCE_LIMIT = 12000


def archives_since(stack: Path, since: str) -> list[tuple[str, Path]]:
    """The archive files dated at or after `since`, newest first."""
    archive = stack.resolve().parent / "archive"
    dated = []
    if archive.is_dir():
        for path in archive.iterdir():
            m = ARCHIVE.match(path.name)
            if m and m.group(1) >= since:
                dated.append((m.group(1), path))
    return sorted(dated, reverse=True)


def closed_since(archives: list[tuple[str, Path]]) -> list[str]:
    """The frame headings of the archive files, newest file first."""
    rows: list[str] = []
    for day, path in archives:
        for f in parse(read_lines(path), bounded=False):
            name = HOLDERS.sub("", f.heading).strip()
            rows.append(cut("%s. %s" % (f.number, name), NAME_LIMIT)
                        + " (archived %s)" % day)
    return rows


def dated_statuses(frames: list[tuple[Frame, str]],
                   since: str) -> list[tuple[str, Frame, str, str]]:
    """Every status line dated at or after `since`, newest first.

    Each frame comes with its mark: "closed" for a frame of the archive,
    and empty for a frame of the stack.
    """
    rows = []
    for f, closed in frames:
        for i in f.statuses:
            line = f.lines[i]
            when = STATUS.match(line).group(1)
            if when[:10] >= since:
                rows.append((when, f, closed, line))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def is_assumed(line: str) -> bool:
    return any(mark in line for mark in ASSUMED)


def is_ruling(line: str, since: str) -> bool:
    """A status in the Principal's words, by its start or by a ruling mark.

    A mark with a date counts when the date is at or after `since`. A mark
    with no date, such as "(ruled: the Principal, in their words)", counts
    by the status line's own date, which the caller already filtered.
    """
    body = STATUS.match(line).group(3)
    if body.startswith("**ruled"):
        return True
    return any(not day or day >= since for day in RULED_MARK.findall(line))


def ruling_key(line: str) -> str:
    """What makes two ruling rows the same ruling: its time, else its words."""
    m = RULING_KEY.search(line)
    if m:
        return "at %s %s" % m.groups()
    m = QUOTE.search(line)
    if m:
        return "words " + m.group(1)
    return "line " + line


def since_row(frame: Frame, closed: str, line: str, again: int = 0) -> str:
    name = cut(HOLDERS.sub("", frame.heading).strip(), 80)
    tail = " (cited again %d times)" % again if again else ""
    mark = " (%s)" % closed if closed else ""
    return cut("%s. %s%s :: %s" % (frame.number, name, mark, line),
               ROW_LIMIT - len(tail)) + tail


def fold_rulings(rows: list[tuple[str, Frame, str, str]]) -> list[str]:
    """One row per ruling, newest first, with the count of later citations.

    The first status that carries a ruling keeps the row. A later status
    with the same key only repeats or cites it, so it adds to the count.
    """
    first: dict[str, list] = {}
    for when, f, closed, line in sorted(rows, key=lambda r: r[0]):
        key = ruling_key(line)
        if key in first:
            first[key][4] += 1
        else:
            first[key] = [when, f, closed, line, 0]
    kept = sorted(first.values(), key=lambda r: r[0], reverse=True)
    return [since_row(f, closed, line, again) for _, f, closed, line, again in kept]


def render_since(stack: Path, since: str, cap: int = SINCE_LIMIT) -> str:
    """The page for the Principal's return: four sections and nothing else.

    The Principal's attention is the scarcest budget, and a return should
    cost one screen. So the page holds at `cap` characters. The oldest rows
    of the closed, the assumed and the ruled sections go, the longest
    section first, and the page says how many went. The waits are never
    cut, because they are what the Principal must answer.
    """
    frames = parse(read_lines(stack))
    head = ["State since %s of %s, printed %s." % (
        since, stack.as_posix(), time.strftime("%Y-%m-%d %H:%M"))]
    archives = archives_since(stack, since)
    closed = closed_since(archives)
    # A frame that closed while the Principal was away took its status
    # lines to the archive, so the archive is read too.
    every = [(f, "") for f in frames] + [
        (f, "closed") for _, path in archives
        for f in parse(read_lines(path), bounded=False)]
    statuses = dated_statuses(every, since)
    assumed = [since_row(f, shut, line) for _, f, shut, line in statuses
               if is_assumed(line)]
    ruled = fold_rulings([r for r in statuses if is_ruling(r[3], since)])
    asks = sorted([f for f in frames if f.waits_on_principal],
                  key=lambda f: RANK.get(f.rating, 3))
    waits = [decision_row(f) for f in asks]

    sections = [("Closed since %s" % since, closed),
                ("Decided under assumption since %s" % since, assumed),
                ("Waits on %s" % PRINCIPAL, waits),
                ("Rulings since %s" % since, ruled)]
    shown = [len(rows) for _, rows in sections]
    cuttable = (0, 1, 3)

    def page() -> str:
        out = list(head)
        for (title, rows), n in zip(sections, shown):
            out += ["", "## " + title]
            out += rows[:n] or ["None."]
            if n < len(rows):
                out.append("%d older rows cut to keep the page under %d characters."
                           % (len(rows) - n, cap))
        return "\n".join(out) + "\n"

    text = page()
    while len(text) > cap:
        sizes = {i: sum(len(r) + 1 for r in sections[i][1][:shown[i]])
                 for i in cuttable if shown[i]}
        if not sizes:
            break
        longest = max(sizes, key=lambda i: sizes[i])
        shown[longest] -= 1
        text = page()
    return text


def _git(start: Path, *args: str) -> str:
    """One git question, answered with an empty string when git cannot."""
    try:
        out = subprocess.run(["git", *args], cwd=str(start),
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def default_stack() -> Path:
    """`plans/stack.md` of the checkout, so a worktree reads its own stack."""
    top = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    return (Path(top) if top else Path.cwd()) / "plans" / "stack.md"


def check_sid(sid: str) -> str:
    """The reason that a session id is not usable, or empty."""
    if not sid or len(sid) > 64:
        return "a session id holds 1 to 64 characters"
    for ch in sid:
        if not (ch.isalnum() or ch in "-_"):
            return "a session id holds letters, digits, dash and underscore only"
    return ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Print the state page from the stack.")
    p.add_argument("--sid", default="", help="print the frames this session holds")
    p.add_argument("--stack", default=None, help="the stack, plans/stack.md by default")
    p.add_argument("--limit", type=int, default=STATUS_LIMIT,
                   help="characters of the last status line")
    p.add_argument("--since", default="",
                   help="YYYY-MM-DD: print what closed, what was assumed, what "
                        "waits on the Principal and what the Principal ruled "
                        "since that date, and nothing else")
    args = p.parse_args(argv)
    bad = check_sid(args.sid) if args.sid else ""
    if bad:
        print("a session id is not usable: %s" % bad, file=sys.stderr)
        return 2
    stack = Path(args.stack) if args.stack else default_stack()
    if not stack.is_file():
        print("no stack at %s" % stack, file=sys.stderr)
        return 2
    if args.since:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", args.since):
            print("--since takes a date, YYYY-MM-DD", file=sys.stderr)
            return 2
        text = render_since(stack, args.since)
    else:
        text = render(stack, args.sid, args.limit)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
