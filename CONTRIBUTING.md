# Contributing

Copy this to `CONTRIBUTING.md` in the destination repository, or merge
the Commits section into the file that is already there. Replace every
`{{slot}}`. Delete this paragraph and the two rules below it.

The brief links to this file. A missing file installs a dead link into
the one document every session reads first.

---

## Commits

{{commit standard}}.

The recommended standard, which the workflow was built on:

- The summary line is `type(scope): summary`, in the imperative, at most
  72 characters. No full stop at the end.
- The types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`,
  `build`, `ci` and `chore`.
- A prose body follows a blank line. It says what changed and why. It
  does not list the files, because the diff lists the files.
- No footer of any kind. No author line. No co-author line. No tool
  attribution.
- The body follows the project's prose rules, the same as every other
  document.

## What a commit holds

- One commit holds one change.
- A commit that changes `plans/stack.md` changes nothing else. The
  stack's history is a record of decisions, and a code change in the
  same commit hides that record.
- A record commits when the conclusion forms, not at the end of the day.

## Before a commit

- Run the suite. Check that the summary line holds no failure.
- Read the diff of anything a script wrote.
- Never skip a hook and never bypass signing, unless the Principal asks
  for it in that instance.
