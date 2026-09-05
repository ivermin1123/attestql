"""A record names the engine it ran on, and the engine decides which settings it may state.

The five named settings are PostgreSQL's session. An engine that has no session has no
value for them, and the rule here is what keeps the two apart: on PostgreSQL all five are
required, on SQLite all five are absent, and an engine nobody stated a rule for is refused
rather than admitted with whichever of the five the caller happened to pass.
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

THE_FIVE = (
    "time_zone",
    "date_style",
    "interval_style",
    "extra_float_digits",
    "database_collation",
)

POSTGRESQL_VALUES = {
    "time_zone": "UTC",
    "date_style": "ISO, MDY",
    "interval_style": "postgres",
    "extra_float_digits": "1",
    "database_collation": "en_US.UTF-8",
}


def _postgresql(**overrides: object) -> SessionSettings:
    values: dict[str, object] = {**POSTGRESQL_VALUES, **overrides}
    return SessionSettings(engine=ENGINE_POSTGRESQL, recorded=RECORDED, **values)  # pyright: ignore[reportArgumentType]  # the overrides are what each test varies


def test_postgresql_states_all_five_settings() -> None:
    settings = _postgresql()
    assert settings.engine == ENGINE_POSTGRESQL
    assert [getattr(settings, name) for name in THE_FIVE] == list(POSTGRESQL_VALUES.values())


@pytest.mark.parametrize("missing", THE_FIVE)
@pytest.mark.parametrize("absent", [None, ""])
def test_postgresql_refuses_a_setting_nobody_read_back(missing: str, absent: str | None) -> None:
    """Absent and empty are the same refusal: neither is a value the server reported."""
    with pytest.raises(ValueError, match=f"{missing} is required on {ENGINE_POSTGRESQL}"):
        _postgresql(**{missing: absent})


def test_sqlite_states_none_of_them() -> None:
    settings = SessionSettings(
        engine=ENGINE_SQLITE,
        time_zone=None,
        date_style=None,
        interval_style=None,
        extra_float_digits=None,
        database_collation=None,
        recorded={"journal_mode": "delete"},
    )
    assert settings.engine == ENGINE_SQLITE
    assert [getattr(settings, name) for name in THE_FIVE] == [None] * len(THE_FIVE)


@pytest.mark.parametrize("stated", THE_FIVE)
def test_sqlite_refuses_a_setting_it_has_no_session_to_hold(stated: str) -> None:
    """A value here would be this tool's own invention, not something a file reported."""
    absent: dict[str, str | None] = dict.fromkeys(THE_FIVE)
    absent[stated] = POSTGRESQL_VALUES[stated]
    with pytest.raises(ValueError, match=f"no session to precondition, so \\['{stated}'\\]"):
        SessionSettings(engine=ENGINE_SQLITE, recorded=RECORDED, **absent)


@pytest.mark.parametrize("engine", ["", "postgres", "PostgreSQL", "duckdb", "mysql"])
def test_an_engine_nobody_stated_a_rule_for_is_refused(engine: str) -> None:
    """Including a spelling of an engine that is here: the name is read, not guessed at."""
    assert engine not in ENGINES
    with pytest.raises(ValueError, match="engine must be one of"):
        SessionSettings(engine=engine, recorded=RECORDED, **POSTGRESQL_VALUES)
