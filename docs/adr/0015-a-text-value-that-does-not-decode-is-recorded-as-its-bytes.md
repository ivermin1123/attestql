# ADR-0015: A text value that does not decode is recorded as its bytes

**Status:** Accepted, 2026-09-08.

## Context

Spider 1.0 dev holds two golds, q455 and q456 on `wta_1`, that this tool cannot audit
(`docs/claims-register.md`, A43). A TEXT column of that database holds bytes that are not valid
UTF-8. Python's `sqlite3` decodes every TEXT value on the way out and raises there, so the failure
is not one cell but the whole statement, and with it the 26 predictions written for those two
questions.

The bytes are what the database holds. A reader that refuses the row refuses the data; a reader
that decodes it with replacement characters renders two different values alike, and a comparison
over that rendering would call two results equal that are not. The canonical serialization has no
rendering for bytes on purpose: it refuses a value nobody stated a rule for rather than inventing
one (`src/attestql/evidence/serialize.py`). So a rule has to be stated.

Two versions are in play and they mean different things. `FORMAT_IDENTITY`
(`attestql/canonical-serialization/1`) names the line grammar: cells separated by a tab, a
document terminated per line, each cell a type tag and a payload. `SerializationDescriptor.version`
(`attestql/audit/2`) is what a reader compares two records' layout under. A record is verified by
re-rendering it and re-taking its hashes, and the re-rendering uses the version the record itself
states, so which of the two moves decides whether every record ever written still verifies.

## Decision

A TEXT value whose bytes are not valid text in the encoding it was read under is recorded as those
bytes, under a type tag of its own.

1. `UndecodedText` is a `bytes` subclass declared beside the serialization. The SQLite connection's
   `text_factory` answers with `str` when the value decodes and with `UndecodedText` when it does
   not.
2. Its canonical tag is `text-bytes` and its payload is the lowercase hex of the bytes. The JSON
   record holds `{"type": "text-bytes", "value": "<hex>"}`, and the loader reads it back to the
   same bytes.
3. It stays a TEXT cell. Its storage class is TEXT, not BLOB; it is never equal to text that
   decoded, because the comparison keys a value by its tag; and it is never equal to a BLOB holding
   the same bytes, because a BLOB has no tag here at all.
4. `FORMAT_IDENTITY` does not move. The grammar did not change, and a record written earlier
   re-renders to the bytes it was written with, which is what its stored hashes are taken over.
5. `SerializationDescriptor.version` moves to `attestql/audit/3`. It is what a reader compares
   layouts under, and the set of value types a record can hold is part of that. A record states the
   version it was written under and is verified under that one, so records written under `2` still
   re-hash to what they state.

A BLOB stays refused, at the value, with its length named. This decision is about the gap that was
measured and not about binary results, which no gold in any corpus this tool has run has returned.

## Alternatives considered

**Decode with a replacement character, or with Python's surrogate escaping.** Replacement loses the
bytes and makes two different values render alike. Surrogate escaping round-trips in Python but
cannot be encoded back to UTF-8, so the canonical rendering, whose last step is an encode, would
raise on exactly the values this exists for.

**Move `FORMAT_IDENTITY` to `/2` instead.** The first line of the rendering is inside what the
stored hashes are taken over, and the re-rendering that verifies a record uses the constant rather
than the record's own line. Every record ever written would report a hash mismatch, which is the
one thing the recomputed line exists to rule out.

**Keep refusing, and leave the two golds unaudited.** It is the smallest change and it is what was
shipped until now. It also means the tool cannot audit a database whose text is not text, which is
a property of real data and not of a corpus.

**Give bytes one tag for every storage class.** A BLOB and a TEXT cell holding the same bytes would
then render alike and compare equal, which contradicts ADR-0004: a value only meets a value of its
own type.

## Consequences

- Records written from now on state `attestql/audit/3`. A reader that knows only `2` is told so by
  the record rather than by a hash that does not match.
- Two Spider golds and the predictions written for them can be compared.
- The content digest of a table qualifies the class of such a cell (`TEXT-undecoded:<hex>`), so a
  table holding the byte `0xff` and one holding the text `ff` never digest alike.
- The numeric-text census over a column holding one is refused rather than answered. The driver
  decodes the argument of a user-defined function itself and raises there, whatever the connection
  answers for a result, so the probe records the refusal and stays quiet on that column.
- PostgreSQL is unaffected: its driver returns `str` for text, and nothing here changes what that
  backend produces.

## Open questions

- Whether a BLOB should become recordable under a tag of its own. Nothing measured needs it yet.
- Whether a text value that decodes under the file's own encoding but not under UTF-8 exists in
  practice. SQLite hands a TEXT value to the driver as UTF-8 whatever the file's encoding is, so
  this reader has not met one.
