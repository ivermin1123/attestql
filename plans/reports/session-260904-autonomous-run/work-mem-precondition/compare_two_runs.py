"""Do the two audit runs state the same answer for each of the nine golds?

Reads the gold record each run wrote per question, rebuilds it as an ``EvidenceRecord``,
and asks the library the question a reader of two records would ask: the rule the record
declares, by name, and ``compare_results`` on the two results under it. The canonical bytes are recomputed here from the rebuilt result
rather than trusted from the document, so that the ``result_hash`` each run wrote is
checked against a rendering made in this process.

Two invocations per role state, because gold-only mode writes a question's directory only
where a smell fired: the nine records come from the run with a non-answer beside each gold,
and every question the gold-only run of the same role state did write is checked to hold
the same ``result_hash``, which is what says the second invocation ran the gold the same
way.

The control files ``control_raw_statements.py`` wrote are counted beside them: the same
nine statements without the envelope, once under each role state.

Writes ``comparison.json``. The rows themselves are not copied into it: what a reader
needs is the hashes, the verdicts and the settings each record states.
"""

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from attestql.audit.compare import GOLD_RECORD_FILE
from attestql.evidence.record import EvidenceRecord, ValidationOutcome
from attestql.evidence.render import result_digest
from attestql.evidence.replay import compare_r_ord, compare_r_set, compare_results
from attestql.evidence.serialize import SerializationDescriptor, canonical_serialize
from attestql.evidence.types import (
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
    StatementSource,
)
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

HERE = Path(__file__).resolve().parent
IDS = [1473, 1476, 1482, 1529, 1531, 1380, 1390, 1410, 955]


def _value(cell: dict[str, Any]) -> object:
    """One cell back from the document, under the type tag the record wrote for it."""
    tag, payload = cell["type"], cell["value"]
    if tag == "null":
        return None
    if tag in {"bool", "int", "str"}:
        return payload
    if tag == "dec":
        return Decimal(str(payload))
    if tag == "date":
        return date.fromisoformat(str(payload))
    if tag == "timestamp":
        return datetime.fromisoformat(str(payload))
    raise ValueError(f"no reader for the type tag {tag!r}")


def _record(document: dict[str, Any]) -> EvidenceRecord:
    settings = document["session_settings_in_force"]
    result = document["result"]
    return EvidenceRecord(
        question_as_asked=document["question_as_asked"],
        question=QuestionMetadata(**document["question"]),
        question_set_version=document["question_set_version"],
        statement_source=StatementSource(**document["statement_source"]),
        executed_sql=document["executed_sql"],
        bound_parameters=(),
        validation_outcome=ValidationOutcome(
            checks_run=tuple(document["validation_outcome"]["checks_run"]),
            all_passed=document["validation_outcome"]["all_passed"],
        ),
        validator_version=document["validator_version"],
        effective_database_role=document["effective_database_role"],
        backend_identity_at_checkout=document["backend_identity_at_checkout"],
        session_settings_in_force=SessionSettings(
            time_zone=settings["time_zone"],
            date_style=settings["date_style"],
            interval_style=settings["interval_style"],
            extra_float_digits=settings["extra_float_digits"],
            database_collation=settings["database_collation"],
            work_mem=settings["work_mem"],
            hash_mem_multiplier=settings["hash_mem_multiplier"],
            recorded=settings["recorded"],
        ),
        result=ExecutionResult(
            columns=tuple(ColumnType(**column) for column in result["columns"]),
            rows=tuple(tuple(_value(cell) for cell in row) for row in result["rows"]),
            backend_identity=result["backend_identity"],
            limits_in_force=ExecutionLimits(statement_timeout_ms=result["statement_timeout_ms"]),
            truncated=result["truncated"],
        ),
        row_count=document["row_count"],
        canonical_ordering=tuple(SortKey(**key) for key in document["canonical_ordering"]),
        serialization=SerializationDescriptor(**document["serialization"]),
        replay_rule=ReplayRule(document["replay_rule"]),
        fixture=FixtureDigest(
            schema_digest=document["fixture"]["schema_digest"],
            row_counts=document["fixture"]["row_counts"],
            content_digests=document["fixture"]["content_digests"],
            source_file_sha256=document["fixture"]["source_file_sha256"],
        ),
        data_as_of=datetime.fromisoformat(document["data_as_of"]),
        executed_at=datetime.fromisoformat(document["executed_at"]),
        run_id=document["run_id"],
        rerun_instruction=document["rerun_instruction"],
    )


def _gold(run: Path, question_id: int) -> dict[str, Any]:
    return json.loads((run / f"q{question_id}" / GOLD_RECORD_FILE).read_text())


def _gold_only_agrees(run: Path, question_id: int, result_hash: str) -> bool | None:
    """Whether the gold-only run of the same role state hashed this gold the same way.

    ``None`` where it wrote no directory for the question, which is what gold-only mode
    does when nothing smelled: not a disagreement, an absence.
    """
    directory = run / f"q{question_id}"
    if not directory.is_dir():
        return None
    return _gold(run, question_id)["result_hash"] == result_hash


RUNS = ("default-work-mem", "role-at-64kb")


def main(work: Path) -> None:
    per_question: dict[str, Any] = {}
    for question_id in IDS:
        documents = [_gold(work / run, question_id) for run in RUNS]
        a, b = (_record(document) for document in documents)
        bytes_a, bytes_b = (
            canonical_serialize(record.result, record.serialization) for record in (a, b)
        )
        rule = a.replay_rule
        by_rule = compare_r_ord if rule is ReplayRule.R_ORD else compare_r_set
        per_question[str(question_id)] = {
            "replay_rule": rule.value,
            "compare_results": compare_results(
                a.result, b.result, rule=rule, serialization=a.serialization
            ).result.name,
            f"compare_{'r_ord' if rule is ReplayRule.R_ORD else 'r_set'}": by_rule(
                a, b
            ).result.name,
            "result_hash_default": documents[0]["result_hash"],
            "result_hash_role_at_64kb": documents[1]["result_hash"],
            "result_hash_matches": documents[0]["result_hash"] == documents[1]["result_hash"],
            "result_hash_recomputed_here": [
                result_digest(record.result, record.serialization) == document["result_hash"]
                for record, document in zip((a, b), documents, strict=True)
            ],
            "canonical_bytes_match": bytes_a == bytes_b,
            "canonical_byte_length": len(bytes_a),
            "work_mem_stated": [
                document["session_settings_in_force"]["work_mem"] for document in documents
            ],
            "hash_mem_multiplier_stated": [
                document["session_settings_in_force"]["hash_mem_multiplier"]
                for document in documents
            ],
            "gold_only_run_agrees": [
                _gold_only_agrees(work / f"gold-only-{run}", question_id, document["result_hash"])
                for run, document in zip(RUNS, documents, strict=True)
            ],
        }
        print(question_id, per_question[str(question_id)]["compare_results"])

    raw = [json.loads((work / f"raw-{run}.json").read_text()) for run in RUNS]
    control = {
        "work_mem_the_role_gave_each_session": [
            answers["work_mem_the_role_gave_this_session"] for answers in raw
        ],
        "differs": sorted(
            int(question_id)
            for question_id in map(str, IDS)
            if raw[0][question_id] != raw[1][question_id]
        ),
        "same": sorted(
            int(question_id)
            for question_id in map(str, IDS)
            if raw[0][question_id] == raw[1][question_id]
        ),
    }
    document = {
        "questions": per_question,
        "verdicts": sorted({entry["compare_results"] for entry in per_question.values()}),
        "canonical_bytes_match_everywhere": all(
            entry["canonical_bytes_match"] for entry in per_question.values()
        ),
        "control_without_the_envelope": control,
        "settings_each_run_states": {
            run: {
                # Everything but the output directory, which is a path in whatever scratch
                # directory the run was given and says nothing about the measurement.
                name: value
                for name, value in json.loads((work / run / "summary.json").read_text())[
                    "settings"
                ].items()
                if name != "out"
            }
            for run in RUNS
        },
        "questions_the_gold_only_runs_wrote": {
            run: sorted(
                int(directory.name.removeprefix("q"))
                for directory in (work / f"gold-only-{run}").iterdir()
                if directory.is_dir()
            )
            for run in RUNS
        },
    }
    (HERE / "comparison.json").write_text(json.dumps(document, indent=1) + "\n")
    print("control differs on", control["differs"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
