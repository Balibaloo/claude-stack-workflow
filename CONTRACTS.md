# The three tools

The kit ships the sweep and describes the gate and the map. A gate welds
to a test runner and a map welds to a language, so a copied one would
carry another project's shape into yours. The sweep welds to neither,
because it reads bytes.

This file states what each tool must do and when to build it. Build the
gate and the map on their own triggers, and not before.

Every one of the three exists for the same reason: the assistant's
context is the scarce resource, and each tool turns a large amount of
output into a small amount of output.

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

**It ships with the kit**, at `meta/tools/sweep.py`, with 25 tests. Copy
both. The list below is what it already does, kept so that a port to
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
