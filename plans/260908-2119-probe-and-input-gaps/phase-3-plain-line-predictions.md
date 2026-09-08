# Phase 3: a predictions file with one statement per line

## Context

Register A44: of the 21 licensed BIRD dev prediction files L3 measured, 12 ship as one SQL statement
per line, and the tool reads only a JSON object. The lane wrapped them into the BIRD shape in a
measurement script, which is work every reader of those files has to repeat. The shape is generic
and belongs in the tool; the dataset-specific edits that lane also made do not.

## Requirements

- `--predictions-format json|lines`, `json` by default, so no existing command line changes meaning.
- Under `lines`, the file is read as one statement per line in file order, and line `i` is the
  prediction at position `i`. A blank line, or a line that is empty once the BIRD suffix is off, is
  read as the file's own statement that the model produced nothing, exactly as the number `0` and
  the empty string are read under `json`.
- Position keying is what pairs those predictions with questions, so `lines` with
  `--predictions-keyed-by id` is refused before anything runs, with a message that says why.
- The BIRD tab suffix is stripped as it is under `json`, because it is the same file family.
- Out of scope, and stated in the flag's help: a comment cut such as DAIL-SQL's `/*`, and a database
  name appended to the statement such as ATLAS's. A file that needs those is prepared outside.

## Files

- `src/attestql/audit/cli.py`: the flag, `read_predictions` taking the format, the refusal of the
  keying combination, and the module docstring's paragraph on which prediction answers which
  question. The run's summary already records `predictions_origin` and the keying; the format joins
  them so a reader knows how the file was read.
- `tests/test_audit_command_runs_over_a_question_file.py` or the nearest existing test module: a
  lines file audits, a blank line is a question with no prediction, the keying combination is
  refused, and a `json` run is unchanged.
- `docs/audit-command.md`: the flag and one example.

## Steps

1. Add the format flag and the reader, keeping one function per shape and one pairing step.
2. Tests, including that the summary states the format the file was read under.
3. Run the gate.
4. Prove it on the data that found the gap: read one of the 12 plain-line files from the cached
   inputs and audit a handful of its questions, with the file left where it is.
5. Commit, then the register row.

## Validation

- A plain-line file audits with `--predictions-format lines --predictions-keyed-by position`.
- The same file under `json` is refused with the message it already gives.
- `just check` green.

## Risk

A line-oriented reader that silently accepted a JSON file would pair statements with the wrong
questions. The refusal is therefore explicit: `lines` reads every line as SQL, and a first line of
`{` is a statement that fails to parse, which is a per-question error and not a silent pairing.

## Rollback

One commit, one flag with a default that preserves today's behaviour.
