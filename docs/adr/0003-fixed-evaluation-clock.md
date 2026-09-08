# ADR-0003: All relative time windows resolve against a fixed evaluation clock

**Status:** Accepted. **Date:** 2026-08-25. **Amended:** 2026-08-30, the Open question below is
answered by ADR-0011 (in the private history before publication), which fixes Q13's lower
bound at the phrase `"the last 12 complete months"`; Q15 already carried one through its cohort
window.
**Amended:** 2026-08-31, the sentence above is left standing as a record and no longer describes
the contract: a cohort window is never a trend's lower bound, Q15 now declares
`trend_lower_bound_phrase="the last 12 complete months"` beside the cohort window it keeps, and
the rule, that the bound is read from `trend_lower_bound_phrase` only and must decompose at the
trend's grain, is ADR-0011 (in the private history before publication)'s.
**Amended:** 2026-09-09, recording what ADR-0013 did on 2026-09-02. That record leaves this one
standing, and says so in its point 7, but it partly supersedes it: the evidence record was re-cut
for a benchmark comparison and the evaluation clock went with the product path it served, so the
sentence under Decision that says the clock is recorded in every evidence record, and the second
bullet under Consequences, are left standing as a record and no longer describe the contract.
`src/attestql/evidence/record.py` states the twenty-one fields that replaced the old set and holds
no clock among them; what a record now states about the data it read is `fixture` and
`data_as_of`. `contract/clock.py` is still here and still what this record decided, off the
audit's path by ADR-0013 point 7.

## Context

Most of the canonical questions contain a relative window: "last 30 days", "last month", "current
month", "last quarter", "last 12 weeks". Resolved against wall-clock time at execution, the same
question has a different correct answer every day.

That makes the question set untestable. A golden expected result would expire overnight, a
regression could not be distinguished from the calendar advancing, and a reviewer re-running an
evidence record a week later would get a different number and could not tell whether that was a bug.

## Decision

**Evaluation clock: `2026-07-15T00:00:00Z`.** Every relative window in the canonical question set
resolves against this fixed instant, never against wall-clock time at execution.

The resolution is a table, not an algorithm to be inferred. Each phrase maps to explicit half-open
UTC bounds (start inclusive, end exclusive). A phrase not in the table raises `UnknownWindow`; the
resolver never guesses.

Three rules follow. Golden expected results are generated under the same clock and are invalid under
any other. The clock is recorded in every evidence record. Partial periods are never silently mixed
with complete ones: a per-month trend excludes the incomplete month containing the clock.

Questions whose window is absolute do not use the clock at all. Q8 was rewritten from "active in
January ... still active in July" to name 2025 explicitly, so it is independent of the clock
entirely.

The synthetic fixture spans 2025-01-01 through the clock, so every window in the table and both
absolute months of Q8 fall inside complete data.

## Alternatives considered

**Wall-clock with a tolerance band.** Rejected. A tolerance turns an exact test into a fuzzy one,
and the size of the band becomes a second thing to argue about.

**Relative windows resolved at fixture-generation time.** Rejected. It couples the clock to the
fixture, so regenerating the fixture silently changes what every question means.

**Let each question carry its own absolute dates.** Rejected for most questions: it would remove the
relative-phrase interpretation problem, which is precisely one of the things Slice 1 must handle.
Adopted for Q8 only, where the question is naturally absolute.

## Consequences

- `contract/clock.py` is real, tested code rather than a stub, and it is the one piece of milestone
  M0 that every later milestone depends on being correct.
- The clock is a required field of the evidence record and a precondition of replay comparability.
- When the fixture span is eventually extended, the clock is a deliberate, versioned change that
  invalidates existing goldens. It is not a configuration knob.

## Open questions

The lower bound for per-month trend questions (Q13, Q15). The brief's table states a grain and an
exclusive end but no start, so `resolve_window` returns a `TrendRule` carrying no lower bound rather
than encoding a guess. This must be decided before M2.

**Answered on 2026-08-30 and left standing above rather than rewritten.**
ADR-0011 (in the private history before publication) decides Q13's bound is the phrase
`"the last 12 complete months"`, and the contract now refuses to construct a trend question that
declares no lower bound. `resolve_window` still returns a `TrendRule` carrying no start, which is
what the paragraph above records; what changed is that the question must now supply the start
itself. This note first named `"the last year"`; that phrase is not month aligned, so
`Window.periods` refuses it, and ADR-0011's first decision was amended the same day to name the
month-aligned phrase instead.
