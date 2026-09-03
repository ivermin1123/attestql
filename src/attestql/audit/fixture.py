"""The fixture digest: what the data was, measured on the server, cached for the run.

ADR-0013 point 6. Per referenced table, the schema digest and the exact row count, always;
a digest of the table's contents when the caller asks for one, because that reads every
row of every table and on Mini-Dev costs fourteen seconds against half a second for the
other two. The digest of the file the data was loaded from is recorded when the caller
names one and is never a precondition; the caller takes it once for the whole run, because
a gigabyte dump costs seconds a pass and every question would ask for the same answer.

The cache exists because an audit asks the same question of the same tables once per
question and the answer cannot change under it: the executor only ever reads. The key is
the backend's identity and the schema digest, so a cache written against one server is
never read against another, and a schema that changed is a new key rather than a stale
hit. The schema digest is therefore always taken from the server, and only the counts and
the content digests are ever served from the file.

The file outlives the run that wrote it, and a schema digest is a statement about columns
and types and not about rows, so the key alone would serve yesterday's counts for data
reloaded under the same schema today. Every entry therefore also carries the content
signal its measurement was taken under, and an entry whose signal is not the one this run
reads from the server is a miss. What the signal is: the counters the server already keeps
per table, taken fresh on every run at the cost of one question. What it is not: evidence,
or a proof that the data is the same. Counters can be reset and a database of the same
name can be made again, and then a signal that did not move is a signal that missed a
reload. The evidence is the digests, which are measured on the server whenever the signal
does not vouch for what the file holds.

A cache file this module cannot read is replaced rather than obeyed. It is not evidence:
everything in it can be recomputed from the server, which is the only thing here that is.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from attestql.audit.backend import Backend
from attestql.evidence.types import FixtureDigest

CACHE_FILE = "fixture.json"
"""The cache, under the output directory the audit writes to."""

CACHE_FORMAT = "attestql/audit/fixture-cache/2"
"""What the layout below is. A file that does not say this is not read."""

_BLOCK = 1 << 22


def file_digest(path: Path) -> str:
    """The sha256 of a file, read in blocks so a gigabyte dump need not fit in memory."""
    if not path.is_file():
        raise ValueError(f"{path} is not a file")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_BLOCK), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def fixture_digest(
    backend: Backend,
    tables: Sequence[str],
    *,
    directory: Path,
    with_content_digests: bool = False,
    source_digest: str = "",
) -> FixtureDigest:
    """The digest of the data those tables hold, from the cache when it holds it.

    ``source_digest`` is what the caller measured of the file the data was loaded from, or
    the empty string when no file was named. It is recorded and never measured here: the
    file is the caller's and is hashed once for a run rather than once a question.
    """
    wanted = tuple(sorted(set(tables)))
    schema_digest = backend.schema_digest(wanted)
    signal = dict(backend.content_signal(wanted))
    key = _key(
        backend.identity(), schema_digest, with_content_digests=with_content_digests, tables=wanted
    )
    cached = _read_cache(directory)
    hit = _entry(cached.get(key), signal, source_digest)
    if hit is not None:
        return hit
    digest = FixtureDigest(
        schema_digest=schema_digest,
        row_counts=backend.row_counts(wanted),
        content_digests=backend.content_digests(wanted) if with_content_digests else {},
        source_file_sha256=source_digest,
    )
    cached[key] = {
        "schema_digest": digest.schema_digest,
        "row_counts": dict(digest.row_counts),
        "content_digests": dict(digest.content_digests),
        "content_signal": signal,
    }
    _write_cache(directory, cached)
    return digest


def _key(
    identity: str, schema_digest: str, *, with_content_digests: bool, tables: Sequence[str]
) -> str:
    """One line naming the server, the schema, the tables and how deep the measurement went."""
    depth = "content" if with_content_digests else "counts"
    return "\n".join((identity, schema_digest, depth, ",".join(tables)))


def _entry(payload: object, signal: Mapping[str, str], source_digest: str) -> FixtureDigest | None:
    """A cached measurement as a digest, or ``None`` when the file does not hold one.

    ``signal`` is what the server says about those tables now. An entry measured under
    another one describes data this run does not have, so it is a miss and not a hit whose
    counts happen to be old.

    The source file's digest is not read from the cache. It describes a file this run was
    given rather than the server the rest of the entry was measured on, so it is the
    caller's and the cached entry never gets to state it.
    """
    if not isinstance(payload, dict):
        return None
    # The isinstance check proves this is a mapping; the cast states the types this
    # format writes, and every value is converted below where a wrong one raises.
    entry = cast("dict[str, Any]", payload)
    try:
        measured = {str(key): str(value) for key, value in entry["content_signal"].items()}
        if measured != dict(signal):
            return None
        return FixtureDigest(
            schema_digest=str(entry["schema_digest"]),
            row_counts={str(key): int(value) for key, value in entry["row_counts"].items()},
            content_digests={
                str(key): str(value) for key, value in entry["content_digests"].items()
            },
            source_file_sha256=source_digest,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        # A malformed entry is a cache miss and nothing more: everything it holds is
        # about to be measured again from the server.
        return None


def _read_cache(directory: Path) -> dict[str, Any]:
    """The cache file's entries, or an empty mapping when there is nothing to read.

    The values are whatever the file held, which is what ``Any`` says here; ``_entry``
    converts every one of them and treats a value it cannot convert as a miss.
    """
    path = directory / CACHE_FILE
    if not path.is_file():
        return {}
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    document = cast("dict[str, Any]", decoded)
    if document.get("format") != CACHE_FORMAT:
        return {}
    entries: object = document.get("entries")
    if not isinstance(entries, dict):
        return {}
    return {str(key): value for key, value in cast("dict[str, Any]", entries).items()}


def _write_cache(directory: Path, entries: Mapping[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    document = {"format": CACHE_FORMAT, "entries": dict(entries)}
    (directory / CACHE_FILE).write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = ["CACHE_FILE", "CACHE_FORMAT", "file_digest", "fixture_digest"]
