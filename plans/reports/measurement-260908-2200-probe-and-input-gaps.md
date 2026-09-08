<!-- cspell:ignore minidev dev1106 qid -->
# Measurement: one new probe and three input gaps

Date 2026-09-08 22:00 +07, tree `b003a3dde693e5cde9a4c2a096218c5fa6dbe20c`. Artifact:
[directory](probe-260908-duplicate-full-row/). Plan:
[260908-2119-probe-and-input-gaps](../260908-2119-probe-and-input-gaps/plan.md).

## Outcome

The GLM research batch of 2026-09-07 (register A41 to A44) ended with one probe worth building and
three gaps found in use. All four are built and measured here. The probe fires on 32 of the 498
Mini-Dev golds and on none of the 21 the three older probes fire on, so the golds a run flags go
from 21 to 53. Read by hand, 20 of the 32 are actionable, which is the 67 % the older probes
measured. The two Spider golds nobody could audit are audited. A prediction file that ships one
statement per line is read as it ships, and gives the verdicts the lane got by wrapping it. A WAL
database on read-only media is read through a private copy.

## The duplicate-row probe, measured before it is claimed

Gold-only over both published copies of the Mini-Dev SQLite golds, on dev.zip's own databases, at
this tree. 496 of 498 audited on each copy; the two misses are q518 and q701, which exceed the 30 s
budget (A33).

|Probe|minidev.zip|Hugging Face|
|---|---:|---:|
|`ordering-over-numeric-text`|2|1|
|`arbitrary-cut`|15|15|
|`not-a-function-of-the-data`|9|9|
|`float-aggregate-order`|0|0|
|`duplicate-full-row`|32|33|
|golds with at least one fire|53|53|

The three older probes fire exactly as A31 recorded them, 26 on the zip copy and 25 on Hugging
Face. The new probe fires on 32 and 33 golds and overlaps none of them: it is a class the shipped
probes could not see, which is what L1 measured from the other side (23 of BIRD's 399 rewrites are
a gold whose result repeats rows and whose rewrite adds DISTINCT, 22 of them beyond every other
probe) and what L3 measured on predictions (1,697 of 1,751 credited-but-unequal rows differ by
multiplicity alone).

Every fire on the zip copy was read by hand and is in
[`classification.json`](probe-260908-duplicate-full-row/classification.json), with the question, the
statement, the row and distinct-row counts, and one sentence. The rule: a fire is actionable when
the thing the question asks about comes back more than once, so a statement that returns it once
disagrees on multiplicity alone; it is noise when the gold's rows are those things, one each, and a
repeated row is a second thing sharing its values. Which of the two it is was measured on the
database and not read off the statement: for each gold the rows of the gold were counted against the
distinct entities the question names.

20 of 32 are actionable (62.5 %), against the 67 % A31 measured over the three older probes. The
shapes: a value returned once per row of a table that has many rows per thing (`q1500` returns 27
product descriptions as 976 rows, `q145` 799 account holders as 4,484, `q149` one account type as
461); a yes or no answered once per row of the thing asked about (`q1205` answers for one patient in
67 rows, `q1399` in 14, `q469` in 15 rows holding both YES and NO); and a single number answered in
16 rows (`q959`). The 12 that are noise are golds whose rows are the things: 387 heroes, 4,430
users, 1,165 schools, where two of them share a name.

## A text cell that is not valid UTF-8

Spider 1.0 dev q455 and q456 on `wta_1` were gold-side execution errors: a TEXT column holds bytes
Python's decoder refuses, and one cell failed the whole statement (A43). Both audit now. The gold's
result holds 20,662 rows and 41,324 cells, of which two are recorded under the tag `text-bytes`:
two player names whose bytes are broken in the file. The record states `attestql/audit/3`, and
records written under `attestql/audit/2` still re-hash to what they state, which the test suite
checks against the site's own recorded run. ADR-0015 records the decision and the four alternatives.

## A predictions file with one statement per line

Twelve of the 21 prediction files of A44 ship as one statement per line, which the lane wrapped into
BIRD's JSON shape in a script. `--predictions-format lines` reads one as it ships. On `toxicology`,
RSL-SQL's GPT-4o file (1,534 lines) gives 93 EQUAL and 52 NOT_EQUAL with 9 credited by BIRD but
NOT_EQUAL, every count identical to the lane's own run over the wrapped copy
([`proofs.json`](probe-260908-duplicate-full-row/proofs.json)). The one difference is four fired
smells against none, which is the new probe.

## A WAL database on read-only media

`card_games.sqlite` of dev.zip is 262 MB and its header says WAL, so SQLite must create two
sidecars before it can read a row and the read-only input cache refuses the open. Both lanes of
2026-09-07 worked around it by copying the file. The backend now answers that one refusal, and only
when the header says WAL, by reading a private copy: the identity, the size and the content signal
stay on the original, the copy is named in the session settings under `read_through_private_copy`,
announced on stderr with its size, and removed when the run ends. Every `card_games` run of the
sweep above read one.

## What changes in AttestQL

- Register rows for the four: the probe with its fire counts and its hand reading, the recorded
  text value with the version move, the line-oriented predictions file, and the private copy.
- `docs/audit-command.md` documents all four. ADR-0015 carries the one decision that moves a
  version.
- The measurement report of 2026-09-02 that states each probe's precision predates this probe, and
  says so where it is linked.

## Unresolved questions

- Whether the probe should stay quiet on a gold whose rows are the things it asks about, which is
  the 12 noise fires. It cannot be told from the statement alone; it needs the question, and every
  gold-only probe here reads no question text.
- Whether a BLOB should become recordable under a tag of its own, now that undecodable text is.
- Whether the 33rd fire on the Hugging Face copy, `q1322`, is a gold that copy changed or a
  difference in the data underneath it.
