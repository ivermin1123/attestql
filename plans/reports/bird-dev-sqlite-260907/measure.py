"""Read the gold-only runs over both copies of BIRD dev and count what the report states.

Inputs, under the work directory:
  out/tool/<copy>/<db_id>/{stdout.txt,summary.json}     (run_tool.sh, then rerun_timeouts.sh)
  data/dev/dev_20240627/dev.json                        the 2024-06-27 copy
  data/hf/dev_20251106-00000-of-00001.json              the 2025-11-06 pass
Outputs:
  out/measurement.json   every count and every listed id
  out/manual-rows.md     the unchanged golds a probe fired on, for classification by hand

A dev question file names eleven databases and ``--dsn`` takes one SQLite file, so one copy is
eleven runs. The merge rule, stated once here and once in the report: the counts of the eleven
summaries are summed (questions audited, smells, errors, elapsed seconds), the per-question lines
are concatenated, and the eleven run ids are listed. Nothing is averaged and nothing is
deduplicated: no question id appears in two of the eleven, because a question names one database.

The recall the report leads with is computed against BIRD's own rewrite, not against a list of
defects: R-C split the 1,534 questions by comparing the two copies' golds under one normalisation
(whitespace collapsed, trailing semicolon and case dropped), giving 399 whose SQL BIRD rewrote,
172 that differ only in question or evidence text, and 963 it left alone. The split is recomputed
here from the two files rather than read from R-C's list, and the two are asserted equal, so that
a moved dataset shows up as a failure instead of a silently different denominator.
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"
COPIES = ("old", "dev1106")
DATABASES = [
    "california_schools",
    "card_games",
    "codebase_community",
    "debit_card_specializing",
    "european_football_2",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]
LINE = re.compile(r"^q(\d+)\s+(\S+)\s+(\S*)\s+GOLD-ONLY\s+smells=(\S+)")
TIMEOUT = re.compile(r"timeout|timed out", re.IGNORECASE)
NORMALISE = re.compile(r"\s+")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(sql: str) -> str:
    """R-C's normalisation, reproduced: whitespace collapsed, trailing semicolon and case gone."""
    return NORMALISE.sub(" ", sql.strip().rstrip(";")).lower()


def read_copy(copy: str) -> dict:
    """The eleven runs of one copy, merged into one."""
    questions: dict[int, dict] = {}
    merged = {
        "audited": 0,
        "smells": Counter(),
        "errors": [],
        "elapsed_seconds": Counter(),
        "run_ids": [],
        "timeout_lines": [],
    }
    for db in DATABASES:
        run = OUT / "tool" / copy / db
        summary = load(run / "summary.json")
        merged["audited"] += summary["verdicts"].get("GOLD-ONLY", 0)
        merged["smells"].update(summary["smells"])
        merged["errors"].extend(summary["errors"])
        merged["elapsed_seconds"].update(summary["elapsed_seconds"])
        merged["run_ids"].append(summary["run_id"])
        for number, text in enumerate(run.joinpath("stdout.txt").read_text().splitlines(), 1):
            if TIMEOUT.search(text):
                merged["timeout_lines"].append({"copy": copy, "db": db, "line": number})
            found = LINE.match(text)
            if found is None:
                continue
            questions[int(found.group(1))] = {
                "db": found.group(2),
                "rule": found.group(3),
                "smells": [] if found.group(4) == "none" else found.group(4).split(","),
            }
    by_probe: dict[str, list[int]] = {}
    for question_id, question in sorted(questions.items()):
        for smell in question["smells"]:
            by_probe.setdefault(smell, []).append(question_id)
    return {
        "audited": merged["audited"],
        "questions": questions,
        "smells": dict(merged["smells"]),
        "by_probe": by_probe,
        "questions_with_a_smell": sorted(i for i, q in questions.items() if q["smells"]),
        "errors": merged["errors"],
        "elapsed_seconds": dict(merged["elapsed_seconds"]),
        "run_ids": merged["run_ids"],
        "timeout_lines": merged["timeout_lines"],
    }


def split(old: list[dict], new: list[dict]) -> dict[str, list[int]]:
    """The 399 / 172 / rest split, recomputed from the two files."""
    new_by_id = {entry["question_id"]: entry for entry in new}
    groups: dict[str, list[int]] = {"sql_rewritten": [], "text_only": [], "unchanged": []}
    for entry in old:
        question_id = entry["question_id"]
        other = new_by_id[question_id]
        if norm(entry["SQL"]) != norm(other["SQL"]):
            groups["sql_rewritten"].append(question_id)
        elif (
            entry["question"].strip() != other["question"].strip()
            or entry.get("evidence", "").strip() != other.get("evidence", "").strip()
        ):
            groups["text_only"].append(question_id)
        else:
            groups["unchanged"].append(question_id)
    return {name: sorted(ids) for name, ids in groups.items()}


def recall(fired: set[int], groups: dict[str, list[int]], by_probe: dict[str, list[int]]) -> dict:
    """How much of each group a probe fired on, per group and per probe."""
    out = {}
    for name, ids in groups.items():
        member = set(ids)
        hit = sorted(member & fired)
        out[name] = {
            "size": len(member),
            "fired": len(hit),
            "share": round(len(hit) / len(member), 4) if member else 0.0,
            "ids": hit,
            "by_probe": {
                probe: sorted(member.intersection(on)) for probe, on in sorted(by_probe.items())
            },
        }
    return out


def overlap(fired: set[int], lists: dict[str, list[int]], universe: set[int]) -> dict:
    """Fired-and-listed, fired-not-listed, listed-not-fired, per published list.

    ``universe`` is the 1,534 ids audited here: a list drawn from Mini-Dev names ids this run
    also audited (Mini-Dev's ids are dev ids, R-C measured that), so nothing is dropped, but a
    list that ever named an id outside the set would be counted as out of range rather than as a
    miss, which is why the field exists.
    """
    out = {}
    for name, ids in lists.items():
        listed = {i for i in ids if i in universe}
        out[name] = {
            "listed": len(ids),
            "listed_in_range": len(listed),
            "fired_and_listed": sorted(fired & listed),
            "listed_not_fired": sorted(listed - fired),
            "fired_not_listed": len(fired - listed),
        }
    return out


def main() -> None:
    old_file = load(WORK / "data/dev/dev_20240627/dev.json")
    new_file = load(WORK / "data/hf/dev_20251106-00000-of-00001.json")
    groups = split(old_file, new_file)
    errata = load(HERE.parent / "research-260904-published-gold-errata" / "errata-ids.json")
    for name, key in (
        ("sql_rewritten", "bird_dev1106_sql_diff_399"),
        ("text_only", "bird_dev1106_text_only_diff_172"),
    ):
        if groups[name] != sorted(errata[key]):
            raise SystemExit(f"{name} differs from R-C's {key}: the dataset moved, say so")
    copies = {copy: read_copy(copy) for copy in COPIES}
    old = copies["old"]
    fired = set(old["questions_with_a_smell"])
    universe = {entry["question_id"] for entry in old_file}
    document = {
        "reading": (
            "Gold-only probes over both copies of BIRD dev on SQLite. copies holds one merged "
            "row per copy; recall is measured on the 2024-06-27 copy against BIRD's own rewrite "
            "in the 2025-11-06 pass; overlap is against the published errata lists R-C collected."
        ),
        "copies": copies,
        "delta_old_to_dev1106": {
            "questions_that_stop_firing": sorted(
                set(old["questions_with_a_smell"])
                - set(copies["dev1106"]["questions_with_a_smell"])
            ),
            "questions_that_start_firing": sorted(
                set(copies["dev1106"]["questions_with_a_smell"])
                - set(old["questions_with_a_smell"])
            ),
            "by_probe": {
                probe: {
                    "old_only": sorted(
                        set(old["by_probe"].get(probe, ()))
                        - set(copies["dev1106"]["by_probe"].get(probe, ()))
                    ),
                    "dev1106_only": sorted(
                        set(copies["dev1106"]["by_probe"].get(probe, ()))
                        - set(old["by_probe"].get(probe, ()))
                    ),
                }
                for probe in sorted(set(old["by_probe"]) | set(copies["dev1106"]["by_probe"]))
            },
        },
        "split": {name: {"size": len(ids), "ids": ids} for name, ids in groups.items()},
        "recall_on_the_old_copy": recall(fired, groups, old["by_probe"]),
        "overlap": overlap(
            fired,
            {
                name: errata[name]
                for name in (
                    "wretblad_financial_flagged_52",
                    "wretblad_sampled_flagged_27",
                    "cidr2026_jin_minidev_table2_18",
                    "minidev_github_issues_ids",
                    "attestql_corrected_golds_3",
                )
            },
            universe,
        ),
    }
    OUT.joinpath("measurement.json").write_text(json.dumps(document, indent=1) + "\n")
    unchanged_fired = sorted(fired & set(groups["unchanged"]))
    rows = [
        "# Unchanged golds a probe fired on, for classification by hand",
        "",
        f"{len(unchanged_fired)} of the {len(groups['unchanged'])} golds BIRD left alone in the",
        "2025-11-06 pass. Class: wrong / harmless / rule.",
        "",
        "| id | db | probes |",
        "|---|---|---|",
    ]
    for question_id in unchanged_fired:
        question = old["questions"][question_id]
        rows.append(f"| {question_id} | {question['db']} | {', '.join(question['smells'])} |")
    OUT.joinpath("manual-rows.md").write_text("\n".join(rows) + "\n")
    print("audited:", {c: copies[c]["audited"] for c in COPIES}, file=sys.stderr)
    print("smells:", {c: copies[c]["smells"] for c in COPIES}, file=sys.stderr)
    print(
        "recall:",
        {k: (v["fired"], v["size"]) for k, v in document["recall_on_the_old_copy"].items()},
        file=sys.stderr,
    )
    print("unchanged and fired:", len(unchanged_fired), file=sys.stderr)


if __name__ == "__main__":
    main()
