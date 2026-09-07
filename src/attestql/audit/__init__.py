"""The audit: two statements, one database, one verdict with the evidence behind it.

``parse`` says what an audit reads off a statement and ``statements`` is PostgreSQL's
answer to it, ``backend`` says what an audit needs from a database and ``postgres`` is
the first one that gives it, ``engines`` names one engine's answer to both, ``fixture``
measures the data both statements read, ``compare`` runs them and states what it found,
and ``smells`` asks the database the four questions that make a gold worth reading again.

``engines`` is not imported here either, and for the same reason as ``cli``: it names the
PostgreSQL backend, so importing it would pull the driver into every import of this
package.

``cli`` is deliberately not imported here. It builds the PostgreSQL backend, so importing
it would pull the driver into every import of this package, including the ones a test
makes to drive a scripted backend that reaches no server at all.
"""

from attestql.audit.backend import (
    Backend,
    BackendRefused,
    ReadBackDrift,
    ShuffledCopies,
    StatementTimedOut,
    TextCensus,
)
from attestql.audit.compare import (
    BirdEx,
    Comparison,
    RecordedStatement,
    TestSuiteEx,
    bird_ex,
    compare_statements,
    counterexample_json,
    record_statement,
    test_suite_ex,
    write_comparison,
)
from attestql.audit.fixture import fixture_digest
from attestql.audit.parse import (
    OrderingKey,
    ParsedStatement,
    ParserIdentity,
    StatementRefused,
)
from attestql.audit.smells import (
    QuestionText,
    Smell,
    SmellSettings,
    all_smells,
    smells_json,
)
from attestql.audit.statements import parse_statement

__all__ = [
    "Backend",
    "BackendRefused",
    "BirdEx",
    "Comparison",
    "OrderingKey",
    "ParsedStatement",
    "ParserIdentity",
    "QuestionText",
    "ReadBackDrift",
    "RecordedStatement",
    "ShuffledCopies",
    "Smell",
    "SmellSettings",
    "StatementRefused",
    "StatementTimedOut",
    "TestSuiteEx",
    "TextCensus",
    "all_smells",
    "bird_ex",
    "compare_statements",
    "counterexample_json",
    "fixture_digest",
    "parse_statement",
    "record_statement",
    "smells_json",
    "test_suite_ex",
    "write_comparison",
]
