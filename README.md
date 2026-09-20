# Adopt this workflow

## For the person installing this

Run this in the destination repository:

```
git clone --depth 1 https://github.com/Balibaloo/claude-stack-workflow.git meta
rm -rf meta/.git
```

Then say to the assistant there: "Read `meta/README.md` and adopt the
workflow."

If that repository already runs this workflow and you are updating it,
clone the kit again the same way and say instead: "Read the 'Update an
installation' section of `meta/README.md` and apply it." The adoption
steps would overwrite records that the project has already earned.

Everything below this section is addressed to that assistant, not to
you. The assistant grills you before it writes any file, so keep about
twenty minutes for the questions.

You are the assistant in a repository that does not yet run this
workflow. Someone copied this `meta/` directory into your repository so
that you can adopt the workflow yourself. This README is your
instruction. Read it whole before you write anything.

**If this repository already runs the workflow, stop and read "Update an
installation" below instead.** The numbered steps after it are for a
first adoption. They would overwrite records that a running project has
already earned.

The workflow was built in another project, a Python repository called
rota. Every rota fact is out of these files. What is left is the method.

## Update an installation

Read this only when the repository already runs the workflow. The
Principal will say that the kit is updated. `meta/` was deleted at the
end of the adoption, so it is back now only because somebody cloned it
again.

Nothing here replaces a record. `plans/` is yours and this kit never
touches it. The five artifacts are yours too, and the edits below are
paragraph edits, never file copies.

Do the steps in this order. The order matters, because step 1 stops step
3 from parking a session.

1. **The permission rule, first.** Add this to `.claude/settings.json`
   under `permissions.allow`, with your own interpreter in place of
   `python`:

   ```
   "Bash(python tools/handover.py:*)"
   ```

   Do this before anything arms a watcher. A permission prompt parks a
   session in the middle of a turn, and a parked session receives nothing
   at all, not a message and not a task notification. One session held its
   inbound messages for six hours that way. Merge into the rules that are
   already there. Never replace the block.

2. **The tool.** Copy `meta/tools/handover.py` to `tools/handover.py` and
   `meta/tools/test_handover.py` beside your other tests. Run them once:
   38 tests, a few seconds. Add `.handover/` to `.gitignore`.

3. **The hook.** Diff before you merge. Run

   ```
   git diff --no-index --ignore-cr-at-eol .claude/hooks/context_count.py meta/hooks/context_count.py
   ```

   and read what it removes. If it removes only lines the new file
   rewrites, this destination has no local content in that hook and you
   replace the file whole. Merge by hand only what the diff proves is
   local. A destination followed an earlier version of this step, which
   asserted local edits, and merged four functions by hand where the diff
   showed two upstream lines and nothing else. The riskier path was the
   one this file told it to take.

   What the new file adds, when you do have to merge: `repo_root`,
   `enrol`, `peer_name`, `waiting`, and the four lines in `main` that
   call them. Then check the hook by hand:

   ```
   echo '{"session_id":"test1234","transcript_path":"","cwd":"<this repo>"}' | python .claude/hooks/context_count.py
   ```

   It must print one JSON object and exit 0. A hook that raises breaks
   the prompt of every session in the repository, so test it before you
   trust it.

4. **The brief.** Your `CLAUDE.md` holds the old hand-off rule. It tells a
   session to list its peers and send each one a liveness probe. That rule
   cannot work and its stated reason was wrong, so replace it:

   - Replace the whole `400k:` bullet with the `400k:` bullet from
     `meta/brief.md`.
   - Replace the `300k:` bullet with the one from `meta/brief.md`, which
     adds one command.
   - Add the `# Standby duty` section from `meta/brief.md`, whole.
   - Add step 1 of the `On wake:` list from `meta/brief.md`, and renumber
     the steps that follow.
   - Replace every `{{slot}}` in the text you moved.

5. **The records.** Add the three blocks from the "The peers and the
   reserve" section of `meta/operating-facts.md` to your
   `plans/operating-facts.md`: the two harness facts, the three things a
   message cannot do, and the numbers to measure. They are measurements,
   so they belong in the records and not in the brief.

6. **The command, if your harness has slash commands.** Copy
   `meta/commands/standby.md` to `.claude/commands/standby.md`, replace
   all four `{{interpreter}}` slots, and delete the comment block it
   names. The file holds five, and the fifth is inside that block.
   Then a new session joins the reserve with one word instead of a paste.

7. **Prove it, then say so.** Run acceptance lines 7 to 13 at the end of
   this README. Report which ones held. Push a frame for anything that did
   not, and never report an untested line as done.

If your `plans/` records say that peer messaging is broken, that sentence
is false and it was measured false. Correct it with a dated line, and say
in the correction that a message does arrive and is the wrong carrier for
other reasons. `meta/CONTRACTS.md` carries the numbers.

Delete `meta/` again when these steps are done.

## What the workflow is

One strong model holds one long context beside one person. The person is
the Principal. They hold intent and shape, they rule, and they declare
the work finished. You are the partner. You hold the structure, you keep
the records, and you run the agents.

Four beliefs drive every rule below.

1. The Principal's attention is the scarcest budget. Never spend it on
   what the records already answer.
2. Nothing accumulates in a conversation. Everything accumulates in
   records. A fresh session reads the records and continues.
3. Work that was never priced is work that was never understood. Every
   unit of work carries a token price and the behaviour the price buys.
4. A prediction never gates. Only a fact or a ruling gates.

## Before you start: what the kit assumes

Check these three before step 1. Each one is a thing the kit needs and
cannot supply.

1. **An interpreter for the context hook.** The hook is 260 lines of
   Python 3. `meta/settings.json` calls it by the bare name `python`.
   Run `python --version` in the project's shell. If no Python is there,
   you have two choices: install one, or port the hook to a language
   this project already has. The hook reads a JSON object from stdin,
   counts the bytes of a JSONL file, and prints one JSON object. Any
   language does it. Do not skip the hook. The wake steps need the
   session id that only the hook supplies, and the hand-off needs the
   enrolment that the hook writes.
2. **A background process that outlives a turn.** The hand-off wakes a
   fresh session by exiting a process that the session started. Check two
   things in your harness: it can start a command in the background, and
   it tells the session when that command exits. On the machine this kit
   was built on, 109 of 142 such notifications woke a session that was
   already idle, after up to 73.8 minutes of silence. If your harness has
   no such background process, read the degraded path at the end of
   `meta/CONTRACTS.md` and cut the standby section from the brief.

   Peer messaging is not the thing to check. It works, and the hand-off
   still does not use it as its first route. `meta/CONTRACTS.md` says why,
   with the numbers.
3. **A way to run a sub-agent.** The rule that the writer never reviews
   its own diff needs a second context. If your harness has no
   sub-agents, that rule needs a different shape, and you should raise
   it with the Principal at step 1.

## Step 0: push the adoption as a frame

The adoption is work. Work that was never priced was never understood.

Write nothing else yet. Create `plans/stack.md` from `meta/stack.md`,
and push one frame: the adoption itself. Price each line. This frame is
the first thing you close, and closing it is the proof that the workflow
runs.

A worked shape, which you adjust:

```
### 1. Adopt the workflow (<date>) [<your session id>]

- Meta workflow. A `meta/` kit arrived in this repository. Adopt it.
- Ends when, each line priced:
  1. The grill is recorded in `plans/archive/grill-<date>.md`: 10k.
     Buys: every later record quotes the Principal, not my guess.
  2. The five boot artifacts exist with no slot left unreplaced: 25k.
     Buys: a fresh session wakes and finds its own instructions.
  3. `plans/operating-facts.md` holds the machine, the suite and the
     borrowed anchors: 10k. Buys: the next grill can price a line.
  4. The acceptance list of `meta/README.md` is run and recorded: 5k.
     Buys: the gaps are known, not assumed absent.
- Waits on: nothing.
- Reasoning: `meta/README.md`.
- Status <date> (<peer name>): pushed and claimed.
```

## Step 1: grill your Principal

The workflow fails when you install another project's assumptions. Ask
these questions one at a time. Give a recommended answer with each one.
Wait for the answer before the next question.

**Write every answer to `plans/archive/grill-<date>.md` as you get it.**
That file is the record. The composition page and the operating facts
quote from it. An unchecked inference is never a record.

### About the work

1. **What is this project for, in one sentence?** The sentence goes at
   the top of the composition page. It is the test that every frame must
   pass.
2. **What is the destination?** Describe the end state as something a
   person can observe. "A careful person does X and gets Y" is the form.
   This becomes the bottom frame of the stack, and it never closes until
   the Principal says so.
3. **What must the Principal approve before work starts, and what is
   opt-in after that?** Recommended: approval of intent is required, and
   every later sign-off is opt-in, merges included. The reason is
   question 1's budget.
4. **Which change is risky enough to need an end-to-end run of the real
   system before its frame closes?** Name the surface. In rota it was
   the write pipeline and the agent briefs. Every project has one. If
   the Principal cannot name one, ask which past change broke something
   the tests did not catch. Ask also what that end-to-end run is: the
   exact command, and how long it takes.

### About the machine

5. **What is the test command, and how long does a full run take?** You
   need the exact command, the command for one test file, and the wall
   time of a full run. All three go in the operating facts.
6. **What runs a repository script here?** Name the interpreter and how
   to call it. A project with a virtual environment or a pinned
   toolchain calls it by a path, not by a bare name. This answer fills
   four slots in the agent briefs, and it decides whether the context
   hook runs at all.
7. **What is the shell, the operating system, and the working branch?**
   Three short answers. Every agent brief needs all three, and a wrong
   shell makes every command in them fail.
8. **What is the commit standard?** Recommended: Conventional Commits, a
   summary line and a prose body, no footer.

### About how we work

9. **What do I call you?** The brief names the Principal in nine places.
   Ask for the name they want in the records.
10. **Does all prose follow Simplified Technical English?**
    Recommended: yes. Short sentences, the active voice, one topic per
    sentence, one word for one thing. The reason is that the Principal
    reads everything and reads it once. The rules are in `meta/brief.md`.
11. **What are the context thresholds and which model runs which seat?**
    Recommended: keep the numbers in `meta/brief.md`. They were
    measured, not guessed. Change them only when this project measures
    its own.
12. **When you are not here, do I decide or do I block?** Recommended: I
    decide, and I mark the decision as mine in
    `plans/operating-facts.md`. A decision of mine is reversible by you
    at any time. A blocked frame costs you a day.

Before you leave step 1, check whether the repository already holds a
`CLAUDE.md`, a `.claude/settings.json` or a `CONTRIBUTING.md`. Merge
into what is there. Never overwrite another person's file, and show the
Principal the result.

## Step 2: write the five artifacts that boot the workflow

Nothing works before these five exist. Write them in this order.

1. **The brief.** Copy `meta/brief.md` into the first section of your
   repository's `CLAUDE.md`. Start at the line after the `---`. The wake
   steps live here, so nothing else can be read first.
2. **The composition page.** Copy `meta/composition.md` to
   `plans/composition.md`. Fill the Purpose from question 1 and the
   destination from question 2. Leave the rest thin. The page is low
   resolution on purpose, and the grill fills it over weeks.
3. **The stack.** You created it at step 0. Now push the bottom frame:
   the destination from question 2. It sits below the adoption frame and
   waits on everything.
4. **The commit standard.** Copy `meta/CONTRIBUTING.md` to
   `CONTRIBUTING.md`, or merge its Commits section into the file that is
   already there. The brief links to this file, so a missing file
   installs a dead link into the one document every session reads first.
5. **The context hook.** Copy `meta/hooks/context_count.py` to
   `.claude/hooks/context_count.py`. Copy `meta/settings.json` to
   `.claude/settings.json`, or merge its two hooks into the file you
   already have. Change the interpreter name from `python` to the
   answer of question 6 if they differ. The hook prints your session id
   at every wake, and the wake procedure needs that id to claim a frame.
   Keep the `permissions.allow` entry in that file as well. It is not a
   convenience, and step 5 of this README says what it prevents.

Create `plans/archive/` now. A closed frame moves there, and so do the
grill record, every scope report, and every design record.

**Replace every slot.** The table below lists all of them. A slot left
in an installed file is a defect, because the file is an instruction
that a session obeys literally.

| Slot | What it is | Where it appears | Rota's value, as an example |
| --- | --- | --- | --- |
| `{{principal}}` | The Principal's name. | brief, composition | Roman |
| `{{project}}` | The name of the thing being built. It names the second workflow in every record. | brief, implementer | the rota workflow, the seats |
| `{{repository path}}` | The absolute path of the checkout. | implementer, sweeper | `D:/repos/rota` |
| `{{branch}}` | The working branch. | implementer | `rota/foundation` |
| `{{shell}}` | The shell an agent's commands run in. | implementer | Git Bash |
| `{{interpreter}}` | The exact command that runs a repository script. | brief, implementer, reviewer, standby command | `.venv/Scripts/python.exe` |
| `{{builder model}}` | The model an implementer or a sweeper runs on. | brief, implementer, sweeper | Opus |
| `{{judge model}}` | The model of the session that holds the frame. | brief | Fable |
| `{{test command for one file}}` | How an agent runs one test file. | implementer, reviewer, sweeper | `python -m pytest tests/x.py -q` |
| `{{gate command}}` | The one command that runs the whole suite. Use the plain test command until a gate exists. | brief, implementer, reviewer | `python -m rota.tools.gate` |
| `{{wall time}}` | How long a full suite run takes. | implementer, reviewer | eight minutes |
| `{{map command}}` | The command that answers where a name lives. Cut the line until a map exists. | brief, all three agents | `python -m rota.tools.map` |
| `{{sweep command}}` | The command that edits many files at once. | sweeper | `python tools/sweep.py` |
| `{{risky surface}}` | The part of the system the tests do not fully cover. | brief | the seats, the briefs, the write pipeline or a predicate |
| `{{end-to-end run}}` | One run of the real system, start to finish, with its command. | brief | a full night on a lineage repository |
| `{{commit standard}}` | The commit format. | brief, implementer, sweeper, CONTRIBUTING | Conventional Commits, a summary line and a prose body, no footer |
| `{{date}}` | Today's date, from the clock and never from memory. | composition, stack | 2026-09-18 |

### When the Principal is not in the session

The Principal may be away while you adopt. Do not stop.

- Write `Status: written <date>, not yet ratified.` at the top of
  `plans/composition.md`.
- Push a frame blocked on the Principal: "Ratify the composition page",
  with your reading as the recommended answer.
- Record every decision you made in their place under "Decisions by the
  assistant" in `plans/operating-facts.md`.

When the Principal is in the session, show them the five files and ask
whether the composition page says what they meant. That is the one
checkpoint that is not opt-in.

## Step 3: write the operating facts

Copy `meta/operating-facts.md` to `plans/operating-facts.md`. It is a
skeleton. Fill the machine, the repository, the suite and the
end-to-end run from the grill.

The cost anchors section holds the token prices that the grill uses.
Rota's measured anchors are there, each marked borrowed. Use them as a
first estimate. Replace each one with your own number as soon as a frame
of yours measures it, and re-derive from the last three frames whenever
a frame that changes the workflow closes.

Add the gitignore lines the skeleton names.

## Step 4: the agents, when you need them

Do not install an agent before its first use. Each agent brief is a file
under `meta/agents/`. Copy everything below its "COPY FROM HERE" line
into `.claude/agents/`, and **replace every slot in it**. Each brief
carries between five and eleven slots, so read the whole file. Do not
assume the suite section is the only part that changes.

- **`reviewer.md`**: install it before the first frame that changes
  code. It needs no tooling, and it enforces the rule that the writer
  never reviews its own diff.
- **`implementer.md`**: install it at the first frame that writes code.
- **`sweeper.md`**: install it only after a sweep tool exists. Read
  `meta/CONTRACTS.md` first.

## Step 5: the tools, each on its own trigger

The kit ships two tools and describes two. Code welds to a language and
a layout, so a copied gate or map would carry another project's shape
into yours. `meta/CONTRACTS.md` states what each of those two must
supply and when to build it. Read it when a trigger fires, and not
before.

**The sweep ships, because its two hazards are platform facts and not
project facts.** Copy `meta/tools/sweep.py` to `tools/sweep.py` and
`meta/tools/test_sweep.py` beside your other tests. It is Python, and it
reads bytes, so it sweeps a repository written in any language. Run its
tests once to prove git behaves as it expects:

```
python -m pytest tools/test_sweep.py -q
```

**The hand-off ships, because the defect it repairs is in the harness and
not in a project.** Copy `meta/tools/handover.py` to `tools/handover.py`,
`meta/tools/test_handover.py` beside your other tests, and
`meta/commands/standby.md` to `.claude/commands/standby.md`. Replace the
`{{interpreter}}` slot in the command file. Run its tests once:

```
python -m pytest tools/test_handover.py -q
```

**Keep the permission rule that `meta/settings.json` carries**, and match
its interpreter to your answer to question 6. The rule is
`Bash(python tools/handover.py:*)`, and it is not a convenience. A
permission prompt parks a session mid-turn, and a parked session drains
nothing. One session held its messages for six hours that way. So a
standby that must ask permission to arm its own watcher can never be
woken at all, and the Principal cannot see why.

Copy it at adoption, even with one session open. The day a hand-off
matters is the day the sender has no context left to write a tool.

The short version of all four:

- A **gate** runs the suite and prints five lines, so that a full run
  costs a few thousand tokens of your context instead of tens of
  thousands. Build it when a plain test run costs more than about 6k of
  your context, or when the known failures pass about twenty.
- A **map** answers where a name is defined and used, in a few lines.
  Build it when one file passes a few thousand lines.
- A **sweep** applies one mechanical edit across many tracked files and
  keeps each file's line endings. It ships with the kit. Use it at the
  first edit that touches more than three files.
- A **hand-off** moves a frame to a fresh session and wakes that session
  while it waits idle. It ships with the kit. It uses a file and not a
  message, because a file is addressed by session id, proved by the
  receiver's own state, and free for a standby that is still waiting.

Until a tool exists, the brief's line that names it is false. Cut that
line from your brief. Then record what you cut, in a section of
`CLAUDE.md` called "Tools not built yet", with the trigger for each.
Without that record a later session cannot put the line back, because
`meta/brief.md` is gone by then.

Search the brief for the tool's name as well as for its slot. In rota's
wording the judge paragraph says "the gate on the commit", which names
the gate and holds no slot.

## What not to copy

- **Another project's `settings.local.json`.** It holds permissions and
  paths from a different machine. Create yours empty.
- **Another project's memory directory.** Memory accretes from work. It
  cannot be installed.
- **Another project's cost anchors, permanently.** Borrow them once,
  then measure your own.

## What to delete, and when

Delete these when steps 0 to 3 are done. The records are the workflow
from then on.

```
meta/README.md
meta/brief.md
meta/composition.md
meta/stack.md
meta/operating-facts.md
meta/CONTRIBUTING.md
meta/settings.json
meta/hooks/
```

Keep `meta/agents/` until all three agents are installed. Keep
`meta/tools/` until you have copied the sweep and the hand-off. Keep
`meta/commands/` until you have copied the standby command. Keep
`meta/CONTRACTS.md` until the gate and the map exist. Delete `meta/`
itself when all four are empty.

## How you know the adoption worked

Run every line. Report the ones that do not hold, and the ones you could
not check.

1. A fresh session reads the brief, the composition page and the stack,
   and reports the open frames without being told where to look.
2. The hook prints a session id at the first prompt of that session.
3. The fresh session claims a frame by writing its session id in the
   frame's heading.
4. The adoption frame from step 0 closes with a dated status line, the
   actual beside the estimate, and a commit.
5. No installed file holds a `{{slot}}`, a stray tag, or a link to a
   file that does not exist. Grep for `{{` and check every markdown link
   in `CLAUDE.md`.
6. No prose in the repository names the project this kit came from. An
   absolute path that happens to carry another name is not a breach.
   Keep the true path and say so in one sentence.
7. A second session is told to stand by, by the slash command or by a
   paste. It replies with one line and stops. `python tools/handover.py
   peers` then lists it as free.
8. The first session hands that peer a frame. The standby wakes with no
   keystroke, and the sender prints `CONFIRMED`. Time it. The wake was 6
   seconds on the machine this tool was built on.
9. Three standbys wait and one frame is handed off. Exactly one wakes.
   The other two still answer `peers` as free, and neither shows a turn.
10. With no standby armed, a hand-off exits 5 and writes one file under
    `.handover/waiting/`. The next session told to stand by takes that
    frame before it blocks, and the file is gone. Release or wait out
    every standby first, and check that `peers` reads zero free. A
    destination ran this line with two standbys still armed, and a frame
    number that does not exist woke a live session and cost it a turn.
11. A session that arms no watcher still sees the waiting hand-off, in
    the hook's line at its first prompt.
12. `python tools/handover.py peers` names every session that sent a
    prompt and arms no watcher. The context hook enrols them, so this
    line proves the hook writes `.handover/sessions/`.
13. A claim that its receiver never takes comes back. Hand a frame to a
    standby, do not run the take, wait fifteen minutes, and run `peers`.
    It prints `RECLAIMED` and the frame waits as a vacancy again.

## The one rule that makes the rest work

The Principal says what they want. You do not build it yet. You grill
them, one question at a time, each question with your recommended
answer, until the work splits into frames. A frame has an observable
"ends when", a countable cost, and a named thing it waits on.

A goal that has not been grilled is not work. It is a wish.
