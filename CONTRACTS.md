# The four tools

The kit ships the sweep and the hand-off, and it describes the gate and
the map. A gate welds to a test runner and a map welds to a language, so a
copied one would carry another project's shape into yours. The sweep welds
to neither, because it reads bytes. The hand-off welds to neither, because
it moves files and watches a clock.

This file states what each tool must do and when to build it. Build the
gate and the map on their own triggers, and not before.

Three of the four exist for the same reason: the assistant's context is
the scarce resource, and each tool turns a large amount of output into a
small amount of output. The hand-off exists to protect the same resource
in another session: it lets a reserve session wait for hours and spend
nothing.

Keep this file until the gate and the map exist. Delete it then.

## The gate

**What it is.** One command that runs the whole suite and prints five
lines.

**The trigger to build it.** Build it when a plain test run costs more
than about 6k of the assistant's context, or when the failures you have
decided to live with pass about twenty. Below that, a plain test command
serves, and a gate is waste.

**Why it exists.** Raw test output read inside an agent costs about 25k.
The same run through a gate costs about 1k in the agent and about 6k of
the assistant's context. The gate also answers the question that raw
output cannot: is this failure new.

**The five lines, in order.**

1. `suite: <this run's counts> (baseline: <the stored counts>)`
2. `new failures (N): <ids, or none>`
3. `failures gone (N): <ids, or none>`
4. `not measured (N): <ids>`, or a line saying why the set is empty
5. `time: <seconds>s, <any setting that changes the result>, baseline
   <commit> <when>`

A note may follow a line: the baseline was stored, the tree moved past
the baseline, the baseline was taken on an uncommitted tree, the pass
count fell from X to Y. A new failure adds one traceback block and the
exit code stays non-zero.

**The five capabilities behind those lines.**

1. Run one fixed test tree as a child process and capture the counts.
2. Produce a stable, machine-readable set of failing test ids for the
   run. Most test runners already write one.
3. Persist one baseline record in a gitignored file at the repository
   root: the commit, a dirty flag, the time, the summary, the failing
   set, and the not-measured set.
4. Produce a "not measured" set. A project whose tests are all
   deterministic returns an empty set, and line 4 reads `not measured
   (0): none` with no loss. Line 4 exists for a project that replays
   recordings, where a test with no recording renders exactly like a
   failure and is not one.
5. Refuse to overwrite a baseline that did not parse. Refuse to report
   green when the child process did not run.

**The two rules that go in the briefs.** An agent never takes the
baseline, because the assistant owns it. An agent never reads the log
file, because the five lines are the whole interface.

## The map

**What it is.** One command that answers where a name lives, in a few
lines instead of a file.

**The trigger to build it.** Build it when one file in the project
passes a few thousand lines. Below that, grep is fine.

**Why it exists.** A scope agent once made 96 tool calls, and most of
them were to find where things were, because one file held 8993 lines.
The map turns that search into one call.

**The two queries that port to any project.**

- `fn <name>`: the definition's file and line span, and its callers by
  bare name, with a cap on the list.
- `file <path or bare name>`: the top-level definitions with their line
  spans. It answers a bare name, or lists the ambiguity when the name
  matches more than one file.

**A third query, if the project has one data layer.** `table <name>`:
the schema file and line, the columns, and the writers and readers, each
marked by how it writes. This one needs a single schema file and a
single write path. A project with an ORM answers it differently or drops
it.

**Do not add a fourth query for a domain concept.** That is where the
original map welded itself to its project.

**The rule that goes in the briefs.** Ask the map before you grep. Grep
only for what the map does not answer.

## The sweep

**What it is.** One command that applies one mechanical edit across many
tracked files.

**It ships with the kit**, at `meta/tools/sweep.py`, with 114 tests and
a frozen reference table in `meta/tools/glob_reference.json`. Copy all
three. The list below is what it already does, kept so that a port to
another language has a specification.

**The trigger to use it.** Use it at the first change that is the same
edit in more than three files.

**Why it exists.** Two measured hazards, not neatness. A Bash heredoc
eats backslashes, which corrupted a patch twenty-three times. A
`read_text` followed by `write_text` turns every LF into CRLF on
Windows, which rewrites a whole file and hides the real change.

**What it must do.**

1. Select tracked files by a glob. Never touch an untracked file, and
   never touch itself.
2. Apply a regex with a literal replacement. A separate flag turns on
   backreferences, so that a replacement holding a dollar sign or a
   backslash is safe by default.
3. Accept a transform file instead of a regex, for an edit a regex
   cannot express. The transform takes the file's text and its path and
   returns the new text.
4. Keep each file's own line ending. Read bytes and write bytes.
5. Check its own writes. Read each file back and compare.
6. Print the touched files and a diff stat.
7. Offer a dry run.
8. Return a distinct exit code for a write mismatch and for a skipped
   file, so the caller knows which happened without reading the output.

**The rule that goes in the briefs.** A change that is the same edit in
more than three files is a script, and the script runs through the
sweep. Read the diff once, for the judgement cases only.

## The hand-off

**What it is.** One command that moves a frame from a full session to a
fresh one. It lands while the fresh session sits idle at its prompt.

**It ships with the kit**, at `meta/tools/handover.py`, with 45 tests.
Copy both, and copy `meta/commands/standby.md` with them. The enrolment
in requirement 17 lives in `meta/hooks/context_count.py`, so copy that
too. The list below is what it already does, kept so that a port to
another language has a specification.

**The trigger to use it.** Use it at the first day two sessions run on
one project. Before that, copy it anyway, because the day it matters is
the day you have no context left to write it.

**Why it exists.** Not because messages fail to arrive. They arrive. In
one machine's history 248 cross-session messages were enqueued and none
was lost. Of those, 57 landed in sessions idle for over five minutes.
They drained in a median of 0.010 seconds, one across 35.8 hours of idle.
Read those numbers before you build anything here. The first version of
this contract said the opposite, and it was wrong.

A message fails at three other things, each measured in that same
history. It cannot be addressed: a peer is addressed by a name, the name
is recycled between sessions, and the Principal names a session id that
no peer list shows. It cannot be proved. Four sends to a listed but closed
session returned success and reached nobody. One receiver woke in 68
milliseconds after 15.7 hours, then spent its whole turn on a usage-limit
notice. It is not free. A liveness probe spends the clean context
that made the standby worth handing to. One probed standby answered in
one line, then read the git log and the stack unprompted.

Two cases defeat a message outright. A session that was never prompted
holds no transcript and nothing can reach it. A session parked mid-turn on
a tool decision or a dialog does not drain its queue at all. One such
session held messages for six hours.

A file and a process do arrive. A standby blocks a background process on
a claim file. The sender writes the file. The process exits, and the
harness wakes the standby, because a background task that exits
re-invokes its session. Measured on Windows 10 with harness 2.1.258: the
wake came 6 seconds after an outside process wrote the file, and the
waiting before it cost the standby no tokens.

**What it must do.**

1. Register a standby, then block. The blocking must cost the model
   nothing. A process waits. A model that polls on a timer spends its
   context, and its context is the asset being protected.
2. Write a heartbeat while it blocks, so liveness is a fact on disk and
   not a question sent to a session that cannot answer.
3. Wake exactly one standby per hand-off. The others must not learn that
   a hand-off happened, so that their context stays clean.
4. Arbitrate two senders that hand off in the same second. An exclusive
   create gives one winner. A sender that loses the race moves to the
   next standby.
5. Never report success on its own write. Wait for the receiver's own
   state to say it holds the frame, and return a distinct exit code when
   that never comes.
6. Survive a drought. A hand-off that finds no standby waits on disk. The
   next session to arm takes it before it blocks. A rename makes that
   take atomic.
7. Tell a session that arms nothing. A session started for other work
   must still learn that a hand-off waits. So the notice rides on the
   context hook that every session fires.
8. Return a distinct exit code for each of: took the frame, claim unread,
   no standby, left the reserve. The caller writes a status line from the
   code and never from a guess.
9. Make the take a receipt. The receiver moves the claim out of the
   mailbox in one step. So a take cannot happen twice, and a reclaim
   cannot race a session that is already working.
10. Give an unread claim back. A session can wake and fail to act. It
    was observed twice, both times a usage limit. So a claim with no
    receipt returns to the queue as a vacancy on a clock.
11. Refuse to make a working session a standby. A session that holds a
    frame must not rejoin the reserve, or it is handed a second frame.
12. Find one mailbox from anywhere in the checkout. `--show-toplevel`
    answers a worktree, and the brief reviews a diff in a worktree, so a
    second reserve appears there that no sender can see.
13. Time every deadline on a monotonic clock. A wall-clock step must not
    end a wait or extend it.
14. Scope the reserve to one repository. A peer list is machine-wide, and
    a session in another project answers a liveness probe truthfully in
    its own sense. Measured on 2026-09-20: a session probed its peers,
    two sessions from a different repository answered "clean standby",
    and a frame was handed to one of them. That session would have read
    its own `plans/stack.md` and looked for a frame number that belonged
    to another project. The mailbox at the repository root makes the
    error impossible, because a sender reads only the reserve of its own
    checkout.
15. Never let a row say something that stopped being true. Three faults
    in one day were one fault: a row derived from a stored field that no
    longer matched the world. A holder's watcher exits when it delivers
    the claim, so its heartbeat stops by design and the beat column read
    STALE on a session that was working. Clearing a frame wrote
    "standby" into a row with no watcher, and the same column then read
    as a session that died. And the frame column named what the mailbox
    delivered long after that frame closed.

    So derive what you print from a fact you can check when you print it,
    and where you cannot, name the field for what it actually holds. A
    claim file on disk makes a row `woken`. A state of holding with no
    frame makes it `spent`. A beat means nothing for a row whose watcher
    exited, so that row reads `held`. The column that names a delivered
    frame is called `handed` and not `frame`, and a command corrects it.
    All three were reported from live frames, and the third had already
    been edited by hand because no command existed.
16. Hand to the oldest session that can finish the frame. Oldest first
    spends one session before it spends a fresh one, which keeps the
    number of open windows down. A ceiling keeps that from handing a
    frame to a session that must stop mid-frame, and the brief already
    names the number: a session at 300k takes no new frame, so it is
    handed none. A session past the ceiling leaves the reserve instead
    of arming, because a seat nothing can use makes the reserve read
    larger than it is. An unknown estimate is eligible: a window armed
    on its first prompt has no transcript to measure and stays that way
    while it sits quiet, so unknown is the cleanest seat there is and
    never a risk.
17. Never ask a session for its own peer name. It cannot know one without
    asking for a peer list, and the message fallback addresses by name,
    so a guess is unaddressable. The hook reads the true name from the
    harness registry, and the hook wins over anything typed.
18. Print the reserve for a person, and keep the files for a script. A
    table is read by a human and its columns carry words chosen for
    them: a holder reads `held` in the beat column, and a watcher that
    parsed that column alone raised a false alarm on a session that was
    working. Anything automatic reads `.handover/peers/*.json`, which
    carries the state, the beat and the frame as fields. Say so, because
    the table is the surface a script reaches for first.
19. Enrol a session at no cost. The context hook writes the session id,
    the peer name and the context estimate on every prompt. So a session
    that arms no watcher is still reachable by a message. The sender can
    also prefer the cleanest standby.

**The rule that goes in the briefs.** Hand off with the command, and
write the status line from its exit code. A hand-off gives away the whole
stack and ends the sender's work, and it is never a way to give a task to
a peer while the sender keeps working. A tool that moves work between
sessions will be used to widen a seat unless its own documentation says
it continues one. A message is never the first
route and never the only route. Resuming a sub-agent by message is a
different thing and stays as it is.

**The degraded path.** A harness with no background process that outlives
a turn cannot be woken. Then a standby is not possible, and the hand-off
becomes a vacancy that waits for the next session to start: keep the
`hand` and `take` commands, keep the hook notice, and cut the standby
section from the brief. The frame still moves, and it moves when a person
opens a window instead of within seconds.
