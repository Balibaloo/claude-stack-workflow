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

## The peers

{{Other sessions of the assistant on this machine, and which model each
one runs. The hand-off rule in the brief needs this. Fill it the first
time you hand a frame off.}}

## Decisions by the assistant

{{A decision the assistant made because the Principal was not in the
session. Each one carries its date and its reason. The Principal can
reverse any of them at any time. Keep this list separate from the
Principal's rulings, so that a later reader can tell which is which.}}

## Rulings that are facts

{{A ruling by the Principal that a session must know before it acts.
Each one carries its date. A ruling that shapes the design belongs in
`plans/composition.md` instead.}}
