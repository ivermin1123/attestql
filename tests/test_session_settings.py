"""A record names the engine it ran on, and the engine decides which settings it may state.

The seven named settings are PostgreSQL's session. An engine that has no session has no
value for them, and the rule here is what keeps the two apart: on PostgreSQL all seven are
required, on SQLite all seven are absent, and an engine nobody stated a rule for is refused
rather than admitted with whichever of the seven the caller happened to pass.
"""

from __future__ import annotations

import pytest

from attestql.evidence.types import (
    ENGINE_POSTGRESQL,
    ENGINE_SQLITE,
    ENGINES,
    SessionSettings,
)

RECORDED = {"statement_timeout": "30000", "server_version_num": "160004"}

THE_SEVEN = (
    "time_zone",
    "date_style",
    "interval_style",
    "extra_float_digits",
    "database_collation",
    "work_mem",
    "hash_mem_multiplier",
)

POSTGRESQL_VALUES = {
    "time_zone": "UTC",
    "date_style": "ISO, MDY",
    "interval_style": "postgres",
    "extra_float_digits": "1",
    "database_collation": "en_US.UTF-8",
    "work_mem": "4096",
    "hash_mem_multiplier": "2",
}


def _postgresql(**overrides: object) -> SessionSettings:
    values: dict[str, object] = {**POSTGRESQL_VALUES, **overrides}
    return SessionSettings(engine=ENGINE_POSTGRESQL, recorded=RECORDED, **values)  # pyright: ignore[reportArgumentType]  # the overrides are what each test varies


def test_postgresql_states_all_seven_settings() -> None:
    settings = _postgresql()
    assert settings.engine == ENGINE_POSTGRESQL
    assert [getattr(settings, name) for name in THE_SEVEN] == list(POSTGRESQL_VALUES.values())


@pytest.mark.parametrize("missing", THE_SEVEN)
@pytest.mark.parametrize("absent", [None, ""])
def test_postgresql_refuses_a_setting_nobody_read_back(missing: str, absent: str | None) -> None:
    """Absent and empty are the same refusal: neither is a value the server reported."""
    with pytest.raises(ValueError, match=f"{missing} is required on {ENGINE_POSTGRESQL}"):
        _postgresql(**{missing: absent})


def test_sqlite_states_none_of_them() -> None:
    settings = SessionSettings(
        engine=ENGINE_SQLITE, recorded={"journal_mode": "delete"}, **dict.fromkeys(THE_SEVEN)
    )
    assert settings.engine == ENGINE_SQLITE
    assert [getattr(settings, name) for name in THE_SEVEN] == [None] * len(THE_SEVEN)


@pytest.mark.parametrize("stated", THE_SEVEN)
def test_sqlite_refuses_a_setting_it_has_no_session_to_hold(stated: str) -> None:
    """A value here would be this tool's own invention, not something a file reported."""
    absent: dict[str, str | None] = dict.fromkeys(THE_SEVEN)
    absent[stated] = POSTGRESQL_VALUES[stated]
    with pytest.raises(ValueError, match=f"no session to precondition, so \\['{stated}'\\]"):
        SessionSettings(engine=ENGINE_SQLITE, recorded=RECORDED, **absent)


@pytest.mark.parametrize("engine", [ENGINE_POSTGRESQL, ENGINE_SQLITE])
def test_either_engine_states_what_its_session_reported(engine: str) -> None:
    """An engine that preconditions nothing still says what it is, so an empty mapping is
    refused on both: a session nobody asked anything else about is one nobody looked at."""
    stated: dict[str, str | None] = dict.fromkeys(THE_SEVEN)
    if engine == ENGINE_POSTGRESQL:
        stated.update(POSTGRESQL_VALUES)
    with pytest.raises(ValueError, match="recorded must state the other settings"):
        SessionSettings(engine=engine, recorded={}, **stated)


@pytest.mark.parametrize("engine", ["", "postgres", "PostgreSQL", "duckdb", "mysql"])
def test_an_engine_nobody_stated_a_rule_for_is_refused(engine: str) -> None:
    """Including a spelling of an engine that is here: the name is read, not guessed at."""
    assert engine not in ENGINES
    with pytest.raises(ValueError, match="engine must be one of"):
        SessionSettings(engine=engine, recorded=RECORDED, **POSTGRESQL_VALUES)
