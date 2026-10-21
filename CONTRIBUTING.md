<a id="contributing-to-civicmeetings"></a>

# Contributing to Townlight Meetings

Townlight Meetings is a planned Townlight module. The first contribution
priority is disciplined MVP delivery: docs, tests, UX evidence, then
code.

## Before opening a PR

Run:

```bash
bash scripts/verify-docs.sh
```

If frontend code is added in the future, include browser screenshots or
console evidence for desktop and mobile.

## Scope discipline

Keep PRs narrow. Do not mix roadmap changes, architecture decisions, and
runtime implementation unless the PR explicitly declares that scope.
