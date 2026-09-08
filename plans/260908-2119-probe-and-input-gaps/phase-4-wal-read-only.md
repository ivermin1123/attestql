# Phase 4: a WAL database on read-only media

## Context

L1 and L3 both met it: `card_games` of BIRD dev ships with WAL sidecars, and SQLite needs to write
the `-shm` and `-wal` files to read such a database. On the read-only input cache the open fails,
and both lanes worked around it by copying the file into their own work directory. L1 left the
question open: a private copy is safe but costs 262 MB, while `immutable=1` assumes the file cannot
change under the run.

## Requirements

- An audit of a WAL SQLite file whose directory is read-only opens a private byte-identical copy
  and reads that, rather than failing at connect.
- The copy is made only when the read-only open fails and the file has a `-wal` sidecar. Nothing is
  copied otherwise.
- The copy is announced on stderr when it is made, with its size, because it costs disk.
- The run's own output names the file that was read and the file it was copied from, so a reader is
  never told a copy was the original.
- The copy is removed at the end of the run, including when the run fails.
- `immutable=1` is rejected in the ADR sense of a recorded alternative: it makes the run assume
  something about the file that the run cannot check.

## Files

- `src/attestql/audit/sqlite.py`: the fallback in `connect`, the copy, its cleanup and the module
  docstring's "Read-only is the file".
- `src/attestql/audit/cli.py`: the line the run prints and the field the summary states.
- `tests/test_audit_audits_a_sqlite_file.py`: a WAL file in a read-only directory audits, the copy
  is named in the output, and it is gone when the run ends.
- `docs/audit-command.md`: what a WAL database costs and where the copy goes.

## Steps

1. Reproduce first: build a small WAL database in a temporary directory, `chmod a-w` the directory,
   and watch the connect fail. That failure is the test.
2. Add the fallback, the announcement and the cleanup.
3. Tests, including that a run whose audit raises still removes the copy.
4. Run the gate, then commit and add the register row.

## Validation

- The reproduction fails before the change and passes after it.
- The temporary directory is empty after both a green and a failing run.
- `just check` green.

## Risk

A copy of a database is a second file that can be read as if it were the original. The output naming
both is what keeps a record honest. Disk is the other risk: a 262 MB copy per run, announced rather
than silent, and removed at the end.

## Rollback

One commit. Without it the tool refuses the file the way it does today, which is a run that cannot
start rather than a wrong answer.
