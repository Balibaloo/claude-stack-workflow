# The task stack

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
7. Every conclusion carries a mark with a headline-long reason:
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
  4. A diff review on a worktree at the commit, its fixes in: 110k.
     Buys: the change is read by a context that never wrote it.
  Total: 350k in agents, about 120k in this context.
- Waits on: nothing.
- Reasoning: the grill of 2026-09-17.
- Status 2026-09-17 14:25 (peer-02): pushed. The scope agent is out,
  read-only, cap 60k.
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
