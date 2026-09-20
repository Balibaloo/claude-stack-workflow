---
description: Join the reserve and wait for a hand-off, at no cost while waiting
allowed-tools: Bash
---

<!--
INSTALLER, READ THIS AND THEN DELETE THIS COMMENT BLOCK ONLY.

Copy this file to `.claude/commands/standby.md`. Replace both
`{{interpreter}}` slots with the command that runs a repository script.
Keep the four lines above, and keep the `---` that closes them. A command
with broken front matter does not run at all.

Delete from the line that opens this comment to the line that closes it.
Change nothing else.
-->

You are a standby in the reserve. Do these four things, and nothing else.

1. Read your session id from the hook line in this turn. It is the eight
   characters after the word `Session`.
2. Arm one watcher. Use the Bash tool with its background flag, so that
   the process outlives this turn:
   `{{interpreter}} tools/handover.py standby --sid <your session id>`
   Pass no name. You cannot know your own peer name without asking for a
   peer list, and a guessed name is unaddressable on the one route that
   needs it. The context hook reads the true name and writes it.
3. Run `{{interpreter}} tools/handover.py peers` in the foreground. Find
   your own session id in the table. A background command returns at once
   and can still fail, so this step turns a hope into a fact. Read your
   peer name from the name column of your own row.
4. Reply with one line: your session id, your peer name, and the word
   standby. Then stop.

Read nothing else. Do not read the composition page, the stack, or any
file. Do not plan any work. Every token you spend now is a token the
frame you receive will not have.

If step 3 does not list you, say so and stop. Do not arm a second
watcher. A session that is not in the table is not in the reserve, and no
frame reaches it.

If a permission prompt appears at step 2, answer nothing and say so. A
prompt parks this session mid-turn, and a parked session receives
nothing at all. The Principal must add the rule to
`.claude/settings.json` first.

## When your watcher exits

The harness wakes you, because a background task that exits re-invokes
its session. Read the task output, and act on the exit code.

- **0**: a hand-off arrived. Run
  `{{interpreter}} tools/handover.py take --sid <your session id>`, then
  follow the wake procedure in `CLAUDE.md`.
- **3**: the wait ran out and nothing arrived. Arm the watcher again,
  exactly as in step 2, and stop.
- **6**: the claim is there and will not open. Run the take command again
  in a minute. Do not take other work, and do not report that no
  hand-off waits. A frame is addressed to you.
- **1**: your registration is gone, so you left the reserve. Do not arm
  again. Say so and stop.
- **2**: you hold a frame already. Report which frame and stop.

## If step 2 says a hand-off was already waiting

The reserve was empty when a peer handed off, so the frame waited on disk
for you. That is the drought case, and it is why the command looks before
it blocks. The watcher has already exited with 0. Take the frame now, and
then follow the wake procedure in `CLAUDE.md`.

## If you wake with no task output

The harness can end a background process without a word, and a machine
that sleeps ends every watcher on it. You are then a session that nobody
can reach, and neither you nor the Principal can see it. So on any wake
where you cannot find your watcher's output, run
`{{interpreter}} tools/handover.py peers` and look for your own row.

- Your row is there, and its beat is a number of seconds: the watcher
  lives. Stop.
- Your row says STALE, or no row names you: the watcher is gone. Arm it
  again from step 2, and tell the Principal that a watcher died.
