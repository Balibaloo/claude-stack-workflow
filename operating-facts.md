# Operating facts

Copy this to `plans/operating-facts.md`. Fill the sections from the
grill. Delete a section that this project has no use for.

This file holds what a session must know and cannot derive. A fact
enters when a session pays to learn it. The purpose is that the next
session does not pay again.

Read only the section a frame needs. Never read the whole file at a
wake.

---

## The machine

{{The operating system, the shell, and anything a command must know.
Fill this from the first frame that runs a command and gets it wrong.}}

## The repository

- Path: {{absolute path}}
- Branch: {{the working branch}}
- Interpreter or toolchain: {{the exact command}}
- Line endings: run `git ls-files --eol` and `git config
  core.autocrlf`. Record both answers. They can disagree, and a session
  that assumes one of them rewrites whole files by accident.

## The suite

- The full command: {{command}}
- The wall time of a full run: {{time}}
- The command for one test file: {{command}}
- What a failure that is not a real failure looks like: {{fill this in
  the first time one appears. A flake, a skipped case, a missing
  fixture. A session that cannot tell a flake from a defect reads a
  baseline wrong.}}

## The end-to-end run

- What it is: {{the command that runs the real system, start to finish}}
- How long it takes: {{time}}
- What it covers that the suite does not: {{the answer to grill question
  4. This is why the run exists. A session that does not know it will
  skip the run under time pressure.}}
- Where it runs from: a worktree at the frame's closing commit, because
  the real system reads its own files at every start.

## Gitignore

Add these lines to `.gitignore` when the matching thing exists.

```
.gate-baseline.json
.gate.log
.claude/settings.local.json
.handover/
```

## Cost anchors

The grill prices each ends-when line from this section. Every row is
observed from the harness usage line under an agent result, never from
the agent's own report of what it used.

The rows below are **borrowed** from the project this workflow came
from. They were measured on a different codebase with a different file
size. Use them as a first estimate only. Replace each row with your own
number as soon as one of your frames measures it. Re-derive from the
last three frames whenever a frame that changes the workflow closes.

- Agent floors, one trivial task each: a general-purpose agent 38k, an
  implementer 11k, a reviewer 13k, a sweeper 9k. (borrowed)
- A reviewer with no tool call, a three-line answer: 10k. (borrowed)
- A reviewer pass, cold, six to eight numbered points with probes: 69k
  to 76k. On a worktree, five points: 61k. (borrowed)
- A design review on a scope report and a design record, before any
  code: 66k. (borrowed)
- A read-only probe of stored data, no worktree: 24k. (borrowed)
- An implementer pass, cold, two new files of about 300 lines and one
  suite run: 74k to 77k. (borrowed)
- An implementer pass, resumed: 7k for a docstring and three lines. 40k
  for six fixes and ten tests. 24k for five fixes and five tests.
  (borrowed)
- A full suite run read inside an agent as raw test output: about 25k.
  Through a gate: about 1k in the agent, and about 6k of the assistant's
  context per run. (borrowed)
- One frame in the assistant's own context, claim to close, two reviews
  and three implementer passes included: about 120k. (borrowed)
- A design record written by the assistant: about 8k of output. A status
  line: about 1k. (borrowed)

## The peers and the reserve

{{Other sessions of the assistant on this machine, and which model each
one runs. Fill this the first time you hand a frame off.}}

A peer's name changes when its session restarts. A session id does not.
So address a peer by the session id, and record the name only so that a
person can find the window.

The harness peer list covers the machine and not the project. It shows a
name and a reference, and never a working directory. A session in another
repository answers "clean standby" truthfully in its own sense. On
2026-09-20 a frame from one project was handed to a session working in
another, and the sender could not have seen the difference. The join it
needed is `~/.claude/sessions/<pid>.json`, which carries the name, the
session id and the working directory together. The reserve avoids the
question: it lives in this checkout, so a sender never sees a session
from another project.

The reserve lives in `.handover/` at the repository root, and a worktree
shares the same one. It is machine state, not a record, and `.gitignore`
holds it. `python tools/handover.py peers` prints it. The record of a
hand-off is the status line in the stack.

The context hook enrols every session that sends a prompt, in
`.handover/sessions/`, with its peer name and its context estimate. So a
session the Principal only pasted into is still reachable by a message,
and `peers` can show which standby is the cleanest. An unread claim
returns to the queue as a vacancy after fifteen minutes. So a session
that wakes and cannot act does not hold a frame still. The mechanism is
proved, and the fifteen minute value is not: a destination proved
RECLAIMED with the clock shortened to three seconds, so nothing yet has
waited out the default on real work. (observed: a destination's
acceptance run, 2026-09-20)

Two facts about the harness decide the whole mechanism. Both were read
from one machine's own transcripts, and both should be re-read on yours
before anyone writes a rule about them.

- An idle session does receive a message, and fast. Of 248 cross-session
  messages, none was lost. 57 that landed in sessions idle for over five
  minutes drained in a median of 0.010 seconds, one across 35.8 hours.
  (observed: the transcripts of five projects)
- A session parked mid-turn drains nothing. One session held its inbound
  messages for six hours while it waited on a tool decision. A permission
  prompt parks a session the same way. (observed: the same corpus)

Five assertions that felt sound and were never run, all on 2026-09-20,
in the same week the rule against them was written down. Keep the list.
The shape repeats and the cost is always a rule that gates.

- "Session messaging did not carry it." Written into a record and a
  commit message from one hand-off that arrived four minutes late. The
  message had arrived. (observed: the transcripts, 2026-09-20)
- "The kit update is not installed in that project." A check run before
  the update landed, quoted afterwards as current, then broadcast to four
  sessions as a rule that would have stopped a session at 400k holding a
  frame it could have handed. The receiving session caught it in minutes.
  (observed: the peer's reply and the installed commit, 2026-09-20)
- "That reclaim hazard is reachable from ordinary operation." Asserted
  from reading the code, then disproved by the first test written for it.
  A re-armed watcher reads the waiting claim on its first poll.
  (observed: the failing test, 2026-09-20)
- "Our two glob implementations disagree on 30 cases, then on 171, then
  on 80." Three faults in the comparison and none in either
  implementation. On the third, every trivial case passed and the result
  was still wrong, because a trivial case tests the matchers and never
  tests the reading of the table. The comparison count caught it. The
  fourth run found 5 real ones. (observed: a destination's own report,
  2026-09-20)
- "That destination's hook carries local edits, so merge by hand." Written
  into this kit's own update procedure about a file in a project nobody
  here had read. The diff removed two upstream lines and nothing local, so
  the safe move was to replace the file whole. The instruction sent an
  installer down the riskier path, by hand, through four functions.
  (observed: the destination's diff, 2026-09-20)

  This one spread, and the spreading is the lesson. The destination copied
  the claim into its own `CLAUDE.md` and into a frame, neither of which
  diffed the file either, and carried it for two days. One unrun claim
  then had three homes and read as three records agreeing. A destination
  that repeats an upstream assertion in its own words does not check it by
  repeating it. (observed: the destination's own report, 2026-09-20)

Three things a message cannot do, which is why the hand-off uses a file.
Each one cost a real hand-off.

- It cannot carry a session id. A peer is addressed by name, a name is
  recycled between sessions, and one session answered to two names on two
  days. A sender once broadcast a frame with the words "claim it only if
  your session id is 4286e076". (observed)
- It cannot prove it landed. Four sends to a listed but closed session
  returned success and reached nobody. One receiver woke in 68
  milliseconds after 15.7 hours and spent its whole turn on a usage-limit
  notice. (observed)
- It is not free for the receiver. A one-line liveness probe made a
  standby answer and then read the git log and the stack unprompted, in
  the same turn. The probe spends the asset it is measuring. (observed)

Numbers this project should measure once, with the borrowed values from
the machine the tool was built on:

- The context count is a count, not an estimate. The hook reads the last
  assistant turn's own usage from the transcript: fresh tokens, plus
  tokens written to cache, plus tokens read from cache. Where a
  transcript carries no usage the hook scales its bytes by 0.65, measured
  on 2026-09-20 against a 4.7 MB transcript whose last turn reported
  771,959 tokens. The kit shipped 0.6 until then, which read 8 percent
  low, and low is the dangerous direction for a rule that decides whether
  a session can finish a frame. (observed: this repository's own
  transcript, 2026-09-20)
- One word carries two meanings and stays that way, ruled by the
  Principal on 2026-09-20. A `claim` is the file a sender writes, and to
  claim a frame is to write your session id in its heading. A rename
  would touch about sixty places across the kit and two destinations'
  records, for an ambiguity that context resolves every time. Recorded so
  the next reviewer finds the ruling instead of the defect.
- The wake: the time from the claim file appearing to the standby's first
  turn. 6 seconds, and no longer borrowed. Measured here once, then
  measured twice more in a second project on its first two real hand-offs,
  6 seconds each time. (observed: three projects, 2026-09-20)
- The cost of waiting: nothing. A process blocks, and the model spends no
  tokens until it wakes. (borrowed)
- The cost of arming a standby: one command and one line of reply.
  {{measure it, and write the number here}}
- The cost of a re-arm when the wait runs out: one turn per standby per
  `--wait`. At the 28800 default that is one turn per session per eight
  hours. Observed: two standbys ran out at 10:37 and re-armed four and
  seven seconds later with no person present, and both were still at
  about 20k after twelve and a half hours in the reserve. (observed:
  a destination's hand-off log, 2026-09-20)
- How long the harness lets a background process live. A heartbeat beat
  150 times over 49.7 minutes here and then ended on its own clock, with
  no interruption, across idle turns and busy ones. The longest gap
  between two beats was 22 seconds against a 20 second interval. The
  ceiling is above 50 minutes and is otherwise unknown. {{measure your
  own, then set `--wait` below it}}

## Decisions by the assistant

{{A decision the assistant made because the Principal was not in the
session. Each one carries its date and its reason. The Principal can
reverse any of them at any time. Keep this list separate from the
Principal's rulings, so that a later reader can tell which is which.}}

## Rulings that are facts

{{A ruling by the Principal that a session must know before it acts.
Each one carries its date. A ruling that shapes the design belongs in
`plans/composition.md` instead.}}
