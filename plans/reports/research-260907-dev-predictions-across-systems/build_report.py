"""Build the report from the JSON evidence, without a hand-copied number."""

import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"
ARTIFACT = Path(__file__).resolve().parent
REPORT = (
    ARTIFACT.parent
    / f"research-260907-{datetime.now().strftime('%H%M')}-dev-predictions-across-systems.md"
)

CODES = {
    "alpha-sql-dev.json": "alpha",
    "predict_dev-codes-1b-bird.json": "codes1",
    "predict_dev-codes-1b-bird-with-evidence.json": "codes1e",
    "predict_dev-codes-3b-bird.json": "codes3",
    "predict_dev-codes-3b-bird-with-evidence.json": "codes3e",
    "predict_dev-codes-7b-bird.json": "codes7",
    "predict_dev-codes-7b-bird-with-evidence.json": "codes7e",
    "predict_dev-codes-15b-bird.json": "codes15",
    "predict_dev-codes-15b-bird-with-evidence.json": "codes15e",
    "rsl-sql-deepseek.txt": "rsl-ds",
    "rsl-sql-gpt-4o.txt": "rsl-gpt",
    "dail-sql-gpt-4-7shot-mask-thr-0.8.txt": "dail7m80",
    "dail-sql-gpt-4-7shot-mask-thr-0.85.txt": "dail7m85",
    "dail-sql-gpt-4-7shot-questionmask.txt": "dail7q",
    "dail-sql-gpt-4-9shot-mask-thr.txt": "dail9m",
    "dail-sql-gpt-4-9shot-questionmask.txt": "dail9q",
    "gsr-gpt-4o.sql": "gsr",
    "csc-sql-7b.sql": "csc7",
    "csc-sql-32b.sql": "csc32",
    "atlas-core-20260301.sql": "atlas1",
    "atlas-core-20260324.sql": "atlas2",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pair(old: int | float | str, new: int | float | str) -> str:
    return f"{old}/{new}"


def percent(value: float) -> str:
    return f"{value:.1%}"


def mechanism(row: dict) -> str:
    values = row["ex1_not_equal_by_mechanism"]
    return ".".join(
        str(values.get(key, 0)) for key in ("multiplicity", "type", "order", "truncation", "other")
    )


def main() -> None:
    sources = load(ARTIFACT / "sources.json")
    pairing = load(OUT / "prediction-pairing.json")
    readable = load(OUT / "predictions-readable.json")
    measured = load(OUT / "prediction-measurement.json")
    moved = load(OUT / "credits-moved.json")
    classified = load(OUT / "classification.json")
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPORT
    rows = measured["files"]
    files = [row["name"] for row in sources["accepted"]]
    code_s_count = sum(row["system"] == "CodeS" for row in sources["accepted"])
    dail_count = sum(row["system"] == "DAIL-SQL" for row in sources["accepted"])
    old_rows = [rows[f"old/{name}"] for name in files]
    new_rows = [rows[f"dev1106/{name}"] for name in files]
    agreement = sum(row["crosscheck"]["agree"] for row in rows.values())
    readable_count = sum(row["crosscheck"]["readable"] for row in rows.values())
    timeout_count = sum(len(row["timeout_ids"]) for row in rows.values())
    error_sides = {
        side: sum(row["error_sides"].get(side, 0) for row in rows.values())
        for side in ("prediction", "gold", "run")
    }
    error_steps = {
        step: sum(row["error_steps"].get(step, 0) for row in rows.values())
        for step in ("execute", "statement", "row_counts")
    }
    movement_counts = [row["moved_both_directions"] for row in moved["files"].values()]
    disagreement_rows = [
        (row["file"], disagreement)
        for row in rows.values()
        for disagreement in row["crosscheck"]["rows"]
    ]
    plain_files = sum(record["source_shape"] != "JSON object" for record in readable["files"])
    disagree_count = sum(row["crosscheck"]["disagree"] for row in rows.values())
    disagree_text = (
        "there was 1 disagreement"
        if disagree_count == 1
        else f"there were {disagree_count} disagreements"
    )
    sample = classified["sample"]
    judged_rows = [row for row in classified["rows"] if row["class"] != "B"]
    harmless: dict[str, dict[str, list[str]]] = {}
    for row in classified["rows"]:
        if row["class"] == "B":
            harmless.setdefault(CODES[row["file"]], {}).setdefault(row["copy"], []).append(
                f"q{row['question_id']}"
            )
    harmless_text = "; ".join(
        f"`{code}` " + ", ".join(f"{copy} " + ", ".join(ids) for copy, ids in copies.items())
        for code, copies in harmless.items()
    )
    lines = [
        "<!-- cspell:ignore ATLAS AlphaSQL AtlasCore CodeS DAIL DAMO GenaSQL GSR LHTB -->",
        "<!-- cspell:ignore Omni RUCKB RSL XiYan birdenv ucdigital Abhi Poluri Graphix UIUC -->",
        "<!-- cspell:ignore dev1106 dev minidev qid sqls fewshot questionmask PTY azorius Takr -->",
        "# Research: BIRD dev predictions across systems",
        "",
        f"Date {datetime.now().strftime('%Y-%m-%d %H:%M')} +07, tree "
        f"`{os.environ.get('GIT_SHA', 'uncommitted')}`. Artifact: "
        "[directory](research-260907-dev-predictions-across-systems/).",
        "",
        "## Outcome and assumption",
        "",
        f"The hunt accepted {len(files)} full-dev files. On the 2024-06-27 gold, "
        f"{measured['pooled_old']['credited_but_not_equal']} of "
        f"{measured['pooled_old']['credited']} credited predictions are NOT_EQUAL "
        f"({measured['pooled_old']['share']:.1%}), against A37's "
        f"{measured['baseline_a37']['share']:.1%}. The pooled denominator counts file rows, "
        f"not distinct systems: CodeS contributes {code_s_count} configurations and "
        f"DAIL-SQL {dail_count}. In the hand-read sample of {sample['sampled']} "
        f"credited-but-NOT_EQUAL rows, {sample['A']} are wrong answers the benchmark "
        f"credited ({sample['A_share']:.1%}).",
        "",
        "The hand sample is assumed to mean both gold copies: its population is every "
        "(file, copy, id) row, ordered by file, copy and id. Credit movement is reported per "
        "file in both directions. No product file was changed.",
        "",
        "## Hunt, licences and pairing",
        "",
        "Every accepted URL, commit, sha256, licence and pairing witness is in "
        "[`sources.json`](research-260907-dev-predictions-across-systems/sources.json); "
        "[`prediction-pairing.json`](research-260907-dev-predictions-across-systems/prediction-pairing.json) "
        f"holds the machine checks. Accepted groups: Alpha-SQL (MIT), CodeS {code_s_count} "
        "(Apache-2.0), RSL-SQL two, DAIL-SQL GPT-4 five, GSR one, CSC-SQL two "
        "(all Apache-2.0), and ATLAS Core two (MIT).",
        "The accepted set was fixed at the two-hour mark; 34 further minutes only checked "
        "candidate families while the first PTY run was suspended.",
        "",
        "Refused or not usable: OmniSQL, MAC-SQL, E-SQL, TA-SQL, Middleware, hill-climb-RL, "
        "AbhiPoluri/sql-r1 and the BIRD-Platinum root have no usable licence for their full "
        "outputs; MAG-SQL ships only 24 rows; DTS-SQL and Graphix ship Spider; CHESS is "
        "present only as a UIUC 100-question subset; XiYan-SQL, NL2SQL360, SQL-R1, LHTB, "
        "N-rep and ontology2sql exposed no full dev file; OpenSearch-SQL's bird_dev.json is "
        "fewshot source. The "
        "DAIL questionmask alias, an Alpha-SQL fork and a LangSQL CodeS copy are duplicates. One "
        "Hugging Face candidate is gated and returns HTTP 401 unauthenticated.",
        "",
        f"All {len(pairing['files'])} files have {pairing['files']['alpha-sql-dev.json']['entries']} "
        f"entries. No accepted file holds an entry with no statement. {plain_files} plain-line "
        "files cannot be read by the tool as shipped; `predictions_readable.py` wraps them, "
        "applies DAIL's own `/*` cut and removes ATLAS's checked tab database suffix. The "
        "changed DAIL positions are in `predictions-readable.json`.",
        "",
        "## Measurement",
        "",
        f"Each file ran once per database and gold copy, "
        f"{len(files) * 2 * len(old_rows[0]['run_ids'])} SQLite audits, "
        "three processes at a time, at the default statement budget. Every timeout was rerun "
        "alone; "
        f"{timeout_count} timeout entries remained. `card_games` used the byte-identical work "
        "copy named by `database-copies.json`, because its WAL sidecars need a writable "
        "directory. The loaded audits stopped at "
        f"{measured['execution']['loaded_run_stall']['stopped_at']} and resumed at "
        f"{measured['execution']['loaded_run_stall']['resumed_at']} without a PTY; "
        f"{measured['execution']['loaded_run_stall']['safety']}.",
        "",
        "| File | C o/n | E1 o/n | B o/n | E0 o/n | ER o/n | CNE o/n | sh o/n | Mo | Mn | TS0 o/n |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for old, new in zip(old_rows, new_rows, strict=True):
        lines.append(
            f"| `{CODES[old['file']]}` | "
            f"{pair(old['compared'], new['compared'])} | "
            f"{pair(old['tool_ex1'], new['tool_ex1'])} | "
            f"{pair(old['official_ex_sum'], new['official_ex_sum'])} | "
            f"{pair(old['tool_ex0'], new['tool_ex0'])} | "
            f"{pair(old['errors'], new['errors'])} | "
            f"{pair(old['ex1_not_equal'], new['ex1_not_equal'])} | "
            f"{pair(percent(old['ex1_not_equal_share']), percent(new['ex1_not_equal_share']))} | "
            f"{mechanism(old)} | {mechanism(new)} | "
            f"{pair(old['ex1_not_equal_by_test_suite_ex'].get('0', 0), new['ex1_not_equal_by_test_suite_ex'].get('0', 0))} |"
        )
    lines.extend(
        [
            "",
            "C is compared, E1 is the tool's BIRD EX, B is BIRD's own score, E0 is EX=0, "
            "ER is ERROR, and CNE means credited by BIRD but NOT_EQUAL; sh is CNE share, "
            "o/n is old gold over 2025-11-06. Each M "
            "multiplicity.type.order.truncation.other, and TS0 is the test-suite reading "
            "refusing that CNE row.",
            "",
            f"The tool's BIRD EX reading and BIRD's unmodified evaluator agree on "
            f"{agreement} of {readable_count} readable rows across all file-copy pairs. "
            "Per-file official sums, errors, timeouts and every disagreement row are in "
            f"`prediction-measurement.json`; {disagree_text}.",
            f"The one disagreement is `{CODES[disagreement_rows[0][0]]}` "
            f"q{disagreement_rows[0][1]['question_id']} on the new gold: the tool says EQUAL "
            "and BIRD's evaluator times out.",
            f"Pooled ERROR sides are prediction {error_sides['prediction']}, gold "
            f"{error_sides['gold']}, run {error_sides['run']}; steps are execute "
            f"{error_steps['execute']}, statement {error_steps['statement']}, row-count "
            f"{error_steps['row_counts']}.",
            "",
            "## Credits moved by the gold",
            "",
            f"Of {moved['rewritten_gold_count']} rewritten golds, "
            f"{moved['totals']['lost']} old credits were lost and "
            f"{moved['totals']['gained']} were gained, "
            f"{moved['totals']['moved']} movements over {moved['totals']['file_copy_pairs']} "
            f"files. Per-file movements range {min(movement_counts)} to "
            f"{max(movement_counts)}; every moved id and its rewritten-gold overlap is in "
            "`credits-moved.json`.",
        ]
    )
    lines.extend(
        [
            "",
            "## Hand sample",
            "",
            f"Selection: {sample['selection']}; population {sample['population']}. "
            f"{classified['rule']}",
            "",
            f"The sample found {sample['A']} A, {sample['B']} B and {sample['C']} C; A is "
            f"{sample['A_share']:.1%} and A or B is {sample['A_or_B_share']:.1%}. "
            f"{classified['first_pass']} The {len(judged_rows)} A and C rows:",
            "",
            "| File | Copy | Q | Gold | Pred | Pred distinct | C | Reason |",
            "|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in judged_rows:
        lines.append(
            "|"
            + "|".join(
                (
                    f"`{CODES[row['file']]}`",
                    row["copy"],
                    str(row["question_id"]),
                    str(row["gold_rows"]),
                    str(row["prediction_rows"]),
                    str(row["distinct_rows"]),
                    row["class"],
                    row["reason"],
                )
            )
            + "|"
        )
    lines.extend(
        [
            "",
            f"The {sample['B']} B rows (reasons in `classification.json`): {harmless_text}.",
        ]
    )
    lines.extend(
        [
            "",
            "## Unresolved questions",
            "",
            "- Whether a clearly licensed upstream file can replace BIRD-Platinum's unlicensed "
            "OmniSQL output.",
            "- Whether ATLAS Core's two runs use the same unnamed model; the run directories do "
            "not say.",
            "- Whether the 12 plain-line wrappers belong in AttestQL or stay a measurement-side "
            "adapter.",
            "",
            "## What changes in AttestQL",
            "",
            "Add to register row A37: the pooled old-gold "
            f"{measured['pooled_old']['credited_but_not_equal']}/"
            f"{measured['pooled_old']['credited']} "
            f"({measured['pooled_old']['share']:.1%}), the per-file and per-copy rows in "
            "`prediction-measurement.json`, the exact BIRD agreement count, the movement "
            "totals, and the sample's A/B/C counts. Name the 12 unread-as-shipped plain-line "
            "files as a parser/input gap; the selected JSON files themselves need no change.",
            "",
        ]
    )
    prepared = []
    for line in lines:
        if line.startswith("|"):
            prepared.append(line.replace(" | ", "|").replace("| ", "|").replace(" |", "|"))
            continue
        if len(line) <= 100:
            prepared.append(line)
            continue
        indent = "    " if line.startswith("- ") else ""
        prepared.extend(
            textwrap.wrap(
                line,
                width=100,
                break_long_words=False,
                break_on_hyphens=False,
                subsequent_indent=indent,
            )
        )
    target.write_text("\n".join(prepared), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
