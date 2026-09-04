"""The fixture digest: measured on the server, cached for the run, never assumed.

The cache is a speed decision and never an evidence decision, so the tests that matter
are that a hit returns what was measured, that the schema digest and the content signal
are taken from the server every time, and that data which moved under an unchanged schema
is measured again rather than served. A cache that cannot be read is replaced rather than
obeyed.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestql.audit.backend import Backend, PlannerStatistics, TableName
from attestql.audit.fixture import CACHE_FILE, CACHE_FORMAT, file_digest, fixture_digest
from tests.audit_fakes import FakeBackend

DRIVERS = TableName("", "drivers")
RESULTS = TableName("", "results")
TABLES = (DRIVERS, RESULTS)
COUNTS = {"drivers": 3, "results": 7}
"""The counts a backend answers with, keyed the way a backend keys them: by the name it
resolved, which for these two bare names is the name itself."""


def _backend() -> FakeBackend:
    return FakeBackend({}, row_counts=COUNTS)


def test_a_digest_states_the_schema_and_the_exact_counts_of_the_tables_it_was_given(
    tmp_path: Path,
) -> None:
    backend: Backend = _backend()
    digest = fixture_digest(backend, TABLES, directory=tmp_path)
    assert digest.schema_digest == "sha256:fake-schema-digest"
    assert dict(digest.row_counts) == COUNTS
    assert dict(digest.content_digests) == {}
    assert digest.source_file_sha256 == ""


def test_the_tables_are_measured_once_each_whatever_order_they_were_named_in(
    tmp_path: Path,
) -> None:
    """Two statements naming the same tables in another order are one measurement."""
    backend = _backend()
    fixture_digest(backend, (RESULTS, DRIVERS, RESULTS), directory=tmp_path)
    assert backend.row_count_calls == [(DRIVERS, RESULTS)]


def test_content_digests_are_taken_only_when_they_are_asked_for(tmp_path: Path) -> None:
    backend = _backend()
    without = fixture_digest(backend, TABLES, directory=tmp_path)
    assert backend.content_digest_calls == []
    assert dict(without.content_digests) == {}
    with_content = fixture_digest(backend, TABLES, directory=tmp_path, with_content_digests=True)
    assert backend.content_digest_calls == [(DRIVERS, RESULTS)]
    assert dict(with_content.content_digests) == {
        "drivers": "md5:drivers",
        "results": "md5:results",
    }


def test_the_measurement_is_written_to_the_cache_and_read_back_from_it(tmp_path: Path) -> None:
    backend = _backend()
    first = fixture_digest(backend, TABLES, directory=tmp_path)
    cache = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))
    assert cache["format"] == CACHE_FORMAT
    assert len(cache["entries"]) == 1

    second = fixture_digest(backend, TABLES, directory=tmp_path)
    assert second == first
    assert backend.row_count_calls == [(DRIVERS, RESULTS)], "the counts were counted twice"
    assert len(backend.schema_digest_calls) == 2, "the schema is read from the server every time"
    assert len(backend.content_signal_calls) == 2, "the signal is read from the server every time"


def _statistics(modified: int) -> dict[TableName, PlannerStatistics]:
    """The planner's statistics for both tables, alike but for how far the rows have moved."""
    return {
        name: PlannerStatistics(
            last_analyze="2026-09-04 09:00:00+00",
            last_autoanalyze=None,
            n_mod_since_analyze=modified,
        )
        for name in TABLES
    }


def test_an_entry_measured_before_an_analyze_is_a_miss_after_it(tmp_path: Path) -> None:
    """The signal carries the planner's statistics, because the shuffle probe reruns a gold
    with the plan they were chosen from: an entry measured under other statistics describes a
    database that can answer that probe differently."""
    before = FakeBackend({}, row_counts=COUNTS, planner_statistics=_statistics(0))
    fixture_digest(before, TABLES, directory=tmp_path)
    after = FakeBackend({}, row_counts=COUNTS, planner_statistics=_statistics(41))

    digest = fixture_digest(after, TABLES, directory=tmp_path)

    assert dict(digest.row_counts) == COUNTS
    assert after.row_count_calls == [(DRIVERS, RESULTS)], "the entry was served rather than missed"


def test_a_cache_written_against_another_schema_is_not_a_hit(tmp_path: Path) -> None:
    """The key holds the schema digest, so a schema that changed is a new measurement."""
    fixture_digest(_backend(), TABLES, directory=tmp_path)
    moved = FakeBackend({}, row_counts={"drivers": 4, "results": 7}, schema_digest="sha256:other")
    digest = fixture_digest(moved, TABLES, directory=tmp_path)
    assert digest.schema_digest == "sha256:other"
    assert dict(digest.row_counts) == {"drivers": 4, "results": 7}
    entries = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 2


def test_a_cache_written_by_another_server_is_not_a_hit(tmp_path: Path) -> None:
    fixture_digest(_backend(), TABLES, directory=tmp_path)
    elsewhere = FakeBackend({}, row_counts=COUNTS, identity="FakeSQL 1.0 | server=other | db")
    fixture_digest(elsewhere, TABLES, directory=tmp_path)
    assert elsewhere.row_count_calls == [(DRIVERS, RESULTS)]


def test_a_cache_that_cannot_be_read_is_replaced_rather_than_obeyed(tmp_path: Path) -> None:
    (tmp_path / CACHE_FILE).write_text("{not json at all", encoding="utf-8")
    backend = _backend()
    digest = fixture_digest(backend, TABLES, directory=tmp_path)
    assert dict(digest.row_counts) == COUNTS
    cache = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))
    assert cache["format"] == CACHE_FORMAT


def test_a_cache_entry_of_the_wrong_shape_is_a_miss(tmp_path: Path) -> None:
    backend = _backend()
    fixture_digest(backend, TABLES, directory=tmp_path)
    document = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))
    key = next(iter(document["entries"]))
    document["entries"][key] = {"schema_digest": "sha256:fake-schema-digest"}
    (tmp_path / CACHE_FILE).write_text(json.dumps(document), encoding="utf-8")
    digest = fixture_digest(backend, TABLES, directory=tmp_path)
    assert dict(digest.row_counts) == COUNTS
    assert len(backend.row_count_calls) == 2


def test_the_source_digest_is_recorded_when_one_is_given_and_is_empty_when_none_is(
    tmp_path: Path,
) -> None:
    dump = tmp_path / "dump.sql"
    dump.write_text("CREATE TABLE t (x int);\n", encoding="utf-8")
    given = file_digest(dump)
    with_file = fixture_digest(_backend(), TABLES, directory=tmp_path, source_digest=given)
    assert with_file.source_file_sha256 == given
    assert with_file.source_file_sha256.startswith("sha256:")
    assert fixture_digest(_backend(), TABLES, directory=tmp_path).source_file_sha256 == ""


def test_the_source_digest_is_never_served_from_the_cache(tmp_path: Path) -> None:
    """It describes a file this run was given, not the server the entry was measured on."""
    dump = tmp_path / "dump.sql"
    dump.write_text("one", encoding="utf-8")
    first = fixture_digest(_backend(), TABLES, directory=tmp_path, source_digest=file_digest(dump))
    dump.write_text("another", encoding="utf-8")
    second = fixture_digest(_backend(), TABLES, directory=tmp_path, source_digest=file_digest(dump))
    assert second.source_file_sha256 != first.source_file_sha256
    assert second.row_counts == first.row_counts


def test_data_that_changed_under_the_same_schema_is_measured_again(tmp_path: Path) -> None:
    """A schema digest is a statement about columns, so it cannot notice a reload."""
    first = fixture_digest(_backend(), TABLES, directory=tmp_path, with_content_digests=True)
    reloaded = FakeBackend(
        {},
        row_counts={"drivers": 30, "results": 70},
        content_digests={"drivers": "md5:other-drivers", "results": "md5:other-results"},
    )
    second = fixture_digest(reloaded, TABLES, directory=tmp_path, with_content_digests=True)

    assert second.schema_digest == first.schema_digest
    assert dict(second.row_counts) == {"drivers": 30, "results": 70}
    assert dict(second.content_digests) == {
        "drivers": "md5:other-drivers",
        "results": "md5:other-results",
    }
    entries = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 1, "the stale entry was kept beside the one that replaced it"
