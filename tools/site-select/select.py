#!/usr/bin/env python3
"""Choose the question directories the site publishes, and copy them under `tools/site/data/`.

`audits.sh` makes the five audits whole, in a work directory outside the repository. The whole
of them is a release asset; what a page is made of is the selection this script makes, which is
the questions the site is about:

- every question BIRD's own check credited and this comparison called NOT_EQUAL, in each of the
  prediction runs. `summary.json` counts them and does not name them, so they are read off the
  question directories: a directory whose `counterexample.json` carries a mechanism, which a
  comparison has when and only when it is a NOT_EQUAL, and whose `bird_ex.value` is 1;
- every gold a probe fired on, in every run;
- every question a maintainer read by hand and recorded in one of the two classifications;
- the unjust zeros and unjust ones the prediction-mode aggregate names for the GitHub zip copy.

A question that errored or reached the statement bound has no directory to publish -- the audit
writes one only for a disagreement or a fired probe -- and is a row of the run page read out of
the summary. That is the rule the plan's red-team pass confirmed, and this script does not work
around it.

The site has a file and a byte budget, and the evidence records hold every row of their results,
so a question directory ranges from kilobytes to megabytes. The dry run states what the selection
would cost, per benchmark and in total; a selection over the budget leaves out whole questions,
largest first, and never one a maintainer read by hand or one the aggregate names as unjust.
Nothing is trimmed inside a record: a record's hash covers its content, so a shortened copy of
one is not the record.

    tools/site-select/select.py --dry-run          what the selection would cost
    tools/site-select/select.py                    make it, under the budget
    tools/site-select/select.py --published <file> write the release-asset lines, after upload
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent.parent
DATA = REPOSITORY / "tools" / "site" / "data"
REPORTS = REPOSITORY / "plans" / "reports"
DEFAULT_WORK = Path("/tmp/attestql-runs")  # noqa: S108

SUMMARY_FILE = "summary.json"
COUNTEREXAMPLE_FILE = "counterexample.json"
SMELLS_FILE = "smells.json"
QUESTIONS_FILE = "questions.json"
CLASSIFICATION_FILE = "classification.json"
CLASSIFICATION_SOURCE_FILE = "classification-source.json"
PUBLISHED_FILE = "published.json"
AGGREGATE_FILE = "aggregate.json"
SELECTION_FILE = "selection.json"
LEFT_OUT_FILE = "left-out.json"
QUESTION_DIRECTORY = re.compile(r"^q(\d+)$")
REPORT_DATE = re.compile(r"^Date:?\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)

MAX_FILES = 8_000
MAX_BYTES = 40 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
"""The three budgets `tools/site/build.py` refuses a build over, repeated here because this is
where a selection can still be made smaller. The build measures what was written and is the
authority; this predicts the same three numbers so that a selection is made once."""

PAGE_OVERHEAD_BYTES = 9_000
PAGE_BYTES_PER_DATA_BYTE = 1.15
"""How a question's page is predicted from the JSON it renders: a fixed head, a strip, a foot
and the rest in proportion to the rows. Measured over the six questions of the packaged sandbox,
where the rendered pages run from 1.43 to 1.71 times their JSON and this model is at or above
every one of them. It is used to keep a page under `MAX_PAGE_BYTES` and to predict the site's
total; both are checked afterwards by the build, which measures rather than predicts."""

RUN_RESERVE_BYTES = 40_000
RUN_RESERVE_FILES = 8
SITE_RESERVE_BYTES = 900_000
SITE_RESERVE_FILES = 80
"""What a run costs the built site beyond its questions -- its own page, its summary, the
pre-rendered filters of its index and the marker -- and what the site costs beyond its runs: the
landing, the method page, the two indexes, the group pages, the shared static directory and the
packaged sandbox the build always renders.

Reserved rather than measured, because the selection is made before the build. Calibrated
against the build of 2026-09-08, which over 121 runs wrote 612 files and 5,179,098 bytes that
were not a published question's, against the 1,048 files and 5,740,000 bytes reserved here: the
byte reserve, which is the binding one, is 11 % above what it cost, and the file reserve is
generous because files are nowhere near their budget. The build measures rather than predicts
and is the authority; the reconciliation report states both numbers."""


class SelectionRefused(Exception):
    """The selection cannot be made, and the message says what is over or what is missing."""


@dataclass(frozen=True)
class Run:
    """One invocation of `attestql audit` in the work directory, and where it is published.

    `group` is the level a SQLite benchmark has and a PostgreSQL one does not: `--dsn` is one
    file there, so one prediction file is eleven runs, and the group is that prediction file.
    """

    benchmark: str
    group: str
    name: str
    audit: Path
    summary: Mapping[str, object]

    @property
    def slug(self) -> str:
        return "/".join(part for part in (self.benchmark, self.group, self.name) if part)

    @property
    def archive(self) -> str:
        """The release asset this run's whole audit is in: its group's, where it has one."""
        return f"{self.benchmark}-{self.group or self.name}.tar.gz"


@dataclass(frozen=True)
class Question:
    """One question directory of one run, why it was selected, and what it costs."""

    run: Run
    directory: Path
    question_id: str
    files: tuple[str, ...]
    data_bytes: int
    reasons: frozenset[str]

    @property
    def protected(self) -> bool:
        """A row a maintainer read by hand, or one the aggregate names as unjust, stays.

        The budget is met by leaving out whole questions, largest first, and these are the
        questions the site exists to show: leaving one out to fit would be leaving out the
        finding rather than the evidence for it.
        """
        return bool(self.reasons & {"hand", "unjust"})

    @property
    def page_bytes(self) -> int:
        return PAGE_OVERHEAD_BYTES + int(PAGE_BYTES_PER_DATA_BYTE * self.data_bytes)

    @property
    def built_bytes(self) -> int:
        """What this question costs the built site: its JSON, copied, and its page."""
        return self.data_bytes + self.page_bytes

    @property
    def built_files(self) -> int:
        return len(self.files) + 1


@dataclass(frozen=True)
class Classification:
    """One hand classification: the file, the date its report states, and how it joins."""

    benchmark: str
    source: Path
    date: str
    shape: str
    reason_field: str
    keys: str
    document: Mapping[str, object]

    @property
    def relative(self) -> str:
        return self.source.relative_to(REPOSITORY).as_posix()


@dataclass
class Measured:
    """What one benchmark's selection costs, as the dry run states it."""

    questions: int = 0
    data_files: int = 0
    data_bytes: int = 0
    built_files: int = 0
    built_bytes: int = 0
    runs: int = 0

    def add(self, question: Question) -> None:
        self.questions += 1
        self.data_files += len(question.files)
        self.data_bytes += question.data_bytes
        self.built_files += question.built_files
        self.built_bytes += question.built_bytes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK, help="where audits.sh ran")
    parser.add_argument("--out", type=Path, default=DATA, help="where the selection is written")
    parser.add_argument("--dry-run", action="store_true", help="state the cost, copy nothing")
    parser.add_argument(
        "--published",
        type=Path,
        default=None,
        help=f"a manifest of uploaded release assets; writes {PUBLISHED_FILE} and nothing else",
    )
    parsed = parser.parse_args(argv)
    work = cast("Path", parsed.work)
    out = cast("Path", parsed.out)
    try:
        published = cast("Path | None", parsed.published)
        if published is not None:
            return write_published(out, published)
        return select(work, out, dry_run=bool(parsed.dry_run))
    except SelectionRefused as refused:
        print(f"site-select: {refused}", file=sys.stderr)
        return 2


def select(work: Path, out: Path, *, dry_run: bool) -> int:
    """Read the runs, choose the questions, state the cost, and copy where asked to."""
    runs = discover(work / "runs")
    if not runs:
        raise SelectionRefused(f"{work / 'runs'} holds no run: `audits.sh` writes them there")
    classifications = {found.benchmark: found for found in read_classifications()}
    unjust = read_unjust()
    questions = [
        question
        for run in runs
        for question in questions_of(run, classifications.get(run.benchmark), unjust)
    ]
    kept, dropped = trim(runs, questions)
    report(runs, kept, dropped)
    if dry_run:
        return 0
    write(out, runs, kept, dropped, classifications, work)
    print(f"written to {out}")
    return 0


def discover(root: Path) -> list[Run]:
    """Every audit directory under the work directory, as a run with its place in the site.

    A directory holding a `summary.json` is a run. One two levels under a benchmark is a run
    of a group, which is what a SQLite benchmark has: `--dsn` is one file there, so a
    prediction file is eleven runs and the group is the prediction file.
    """
    found: list[Run] = []
    for benchmark in sorted(path for path in _directories(root)):
        for first in sorted(_directories(benchmark)):
            if (first / SUMMARY_FILE).is_file():
                found.append(_run(benchmark.name, "", first))
                continue
            for second in sorted(_directories(first)):
                if (second / SUMMARY_FILE).is_file():
                    found.append(_run(benchmark.name, first.name, second))
    return found


def _run(benchmark: str, group: str, audit: Path) -> Run:
    return Run(
        benchmark=benchmark,
        group=group,
        name=audit.name,
        audit=audit,
        summary=_document(audit / SUMMARY_FILE),
    )


def _directories(root: Path) -> list[Path]:
    """Directories, with the crowded answer a rerun kept beside its own left out.

    `audits.sh` moves a run that reported a timeout under load to `<name>.under-load` and runs
    it again alone. What the site publishes is the rerun; the other stays in the work directory
    so that a reader of the reconciliation can see both.
    """
    if not root.is_dir():
        return []
    return [
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.endswith(".under-load") and not path.name.startswith(".")
    ]


def questions_of(
    run: Run,
    classification: Classification | None,
    unjust: Mapping[tuple[str, str], frozenset[str]],
) -> list[Question]:
    """Every question directory of one run that the selection names, with why it was named."""
    hand = _hand_rows(classification, run)
    named = unjust.get((run.benchmark, run.group or run.name), frozenset())
    found: list[Question] = []
    for directory in sorted(
        (path for path in _directories(run.audit) if QUESTION_DIRECTORY.match(path.name)),
        key=lambda path: int(path.name[1:]),
    ):
        question_id = directory.name[1:]
        reasons: set[str] = set()
        if _credited(directory):
            reasons.add("credited")
        if _probe_fired(directory):
            reasons.add("probe")
        if question_id in hand:
            reasons.add("hand")
        if question_id in named:
            reasons.add("unjust")
        if not reasons:
            continue
        files = tuple(sorted(path.name for path in directory.iterdir() if path.is_file()))
        found.append(
            Question(
                run=run,
                directory=directory,
                question_id=question_id,
                files=files,
                data_bytes=sum((directory / name).stat().st_size for name in files),
                reasons=frozenset(reasons),
            )
        )
    return found


def _credited(directory: Path) -> bool:
    """BIRD's own check credited this pair and this comparison called it NOT_EQUAL.

    Read off the two fields the counterexample states rather than off `summary.json`, which
    counts these and does not name them. A comparison carries a mechanism when and only when
    it is a NOT_EQUAL, which is the same test `cli.py` counts them by.
    """
    counterexample = directory / COUNTEREXAMPLE_FILE
    if not counterexample.is_file():
        return False
    stated = _document(counterexample)
    if stated.get("mechanism") is None:
        return False
    bird = stated.get("bird_ex")
    return isinstance(bird, dict) and cast("Mapping[str, object]", bird).get("value") == 1


def _probe_fired(directory: Path) -> bool:
    """Any probe fired on this question's gold."""
    smells = directory / SMELLS_FILE
    if not smells.is_file():
        return False
    stated = _document(smells)
    return any(
        isinstance(probe, dict) and cast("Mapping[str, object]", probe).get("fired") is True
        for probe in _list(stated, "smells")
    )


def read_classifications() -> list[Classification]:
    """The two hand classifications, each with the date its own measurement report states."""
    return [
        Classification(
            benchmark="minidev-pg",
            source=REPORTS / "prediction-mode-260904-real-predictions" / CLASSIFICATION_FILE,
            date=_report_date(
                REPORTS / "measurement-260904-0046-prediction-mode-on-real-predictions.md"
            ),
            shape="per_file",
            reason_field="reason",
            keys="per_file[<prediction file>].rows[], joined by the run name and question_id",
            document=_document(
                REPORTS / "prediction-mode-260904-real-predictions" / CLASSIFICATION_FILE
            ),
        ),
        Classification(
            benchmark="bird-dev-sqlite",
            source=REPORTS / "bird-dev-sqlite-260907" / CLASSIFICATION_FILE,
            date=_report_date(REPORTS / "measurement-260907-1435-bird-dev-sqlite.md"),
            shape="rows",
            reason_field="why",
            keys="rows[], joined by question_id and db",
            document=_document(REPORTS / "bird-dev-sqlite-260907" / CLASSIFICATION_FILE),
        ),
    ]


def _report_date(report: Path) -> str:
    """The date the measurement report states on its own Date line, and never a typed one."""
    found = REPORT_DATE.search(report.read_text(encoding="utf-8"))
    if found is None:
        raise SelectionRefused(
            f"{report} states no Date line to read the classification's date from"
        )
    return found.group(1)


def _hand_rows(classification: Classification | None, run: Run) -> Mapping[str, Mapping[str, str]]:
    """The rows of one classification that belong to one run, by question id.

    The two files join differently and each says so in the `classification-source.json` written
    beside it: the prediction-mode file is keyed by the prediction file, which is the run or the
    group, and the BIRD dev file names the database each row was read on.
    """
    if classification is None:
        return {}
    if classification.shape == "per_file":
        files = _mapping(classification.document, "per_file")
        stated = files.get(run.group or run.name)
        if not isinstance(stated, dict):
            return {}
        rows = _list(cast("Mapping[str, object]", stated), "rows")
    else:
        rows = [
            row for row in _list(classification.document, "rows") if _text(row, "db") == run.name
        ]
    return {
        _text(row, "question_id"): {
            "class": _text(row, "class"),
            "reason": _text(row, classification.reason_field),
        }
        for row in rows
        if isinstance(row, dict)
    }


def read_unjust() -> Mapping[tuple[str, str], frozenset[str]]:
    """The unjust zeros and unjust ones the prediction-mode aggregate names, for the zip copy.

    Both lists name a prediction file and a question; the zeros also name the gold copy, and
    only the rows against the GitHub zip are read, because that is the copy `minidev-pg` is
    audited against. The site publishes the question directories of those pairs where the audit
    wrote one: a pair the tool called EQUAL and no probe fired on has none, by the same rule
    that leaves an errored question a row of the run page.
    """
    aggregate = _document(REPORTS / "prediction-mode-260904-real-predictions" / AGGREGATE_FILE)
    named: dict[tuple[str, str], set[str]] = {}
    for key in ("unjust_zero", "unjust_one"):
        for entry in _list(aggregate, key):
            row = cast("Sequence[object]", entry)
            if len(row) < 3 or str(row[2]) != "zip":
                continue
            named.setdefault(("minidev-pg", str(row[0])), set()).add(str(row[1]))
    return {pair: frozenset(ids) for pair, ids in named.items()}


def trim(
    runs: Sequence[Run], questions: Sequence[Question]
) -> tuple[list[Question], list[Question]]:
    """The selection cut to the budget: whole questions, largest first, protected ones kept.

    Two cuts, in this order. A question whose page would be over `MAX_PAGE_BYTES` cannot be
    published at any budget, so it goes first and its being protected does not save it -- the
    build would refuse the site. Then the largest of the rest, until the file count and the
    total fit. A selection that does not fit with the protected questions alone is refused
    rather than made smaller by dropping one of them.
    """
    dropped: list[Question] = []
    kept = list(questions)
    over = [question for question in kept if question.page_bytes > MAX_PAGE_BYTES]
    if over:
        kept = [question for question in kept if question.page_bytes <= MAX_PAGE_BYTES]
        dropped.extend(
            replace(question, reasons=question.reasons | {"over-page"}) for question in over
        )
    files = SITE_RESERVE_FILES + RUN_RESERVE_FILES * len(runs)
    total = SITE_RESERVE_BYTES + RUN_RESERVE_BYTES * len(runs)
    floor_files = files + sum(question.built_files for question in kept if question.protected)
    floor_bytes = total + sum(question.built_bytes for question in kept if question.protected)
    if floor_files > MAX_FILES or floor_bytes > MAX_BYTES:
        raise SelectionRefused(
            f"the questions read by hand and named as unjust do not fit on their own: "
            f"{floor_files:,} files of {MAX_FILES:,} and {floor_bytes:,} bytes of {MAX_BYTES:,}"
        )
    order = sorted(kept, key=lambda question: (question.protected, -question.built_bytes))
    running_files = files + sum(question.built_files for question in kept)
    running_bytes = total + sum(question.built_bytes for question in kept)
    survivors = {id(question) for question in kept}
    for question in order:
        if running_files <= MAX_FILES and running_bytes <= MAX_BYTES:
            break
        if question.protected:
            break
        survivors.discard(id(question))
        running_files -= question.built_files
        running_bytes -= question.built_bytes
        dropped.append(replace(question, reasons=question.reasons | {"over-budget"}))
    return [question for question in kept if id(question) in survivors], dropped


def report(runs: Sequence[Run], kept: Sequence[Question], dropped: Sequence[Question]) -> None:
    """What the selection costs, per benchmark and in total, before anything is copied."""
    per: dict[str, Measured] = {}
    for run in runs:
        per.setdefault(run.benchmark, Measured()).runs += 1
    for question in kept:
        per.setdefault(question.run.benchmark, Measured()).add(question)
    print(
        f"{'benchmark':<22} {'runs':>5} {'questions':>10} {'files':>7} {'bytes':>12} {'built':>12}"
    )
    for name in sorted(per):
        measured = per[name]
        print(
            f"{name:<22} {measured.runs:>5} {measured.questions:>10} {measured.data_files:>7} "
            f"{measured.data_bytes:>12,} {measured.built_bytes:>12,}"
        )
    questions = sum(measured.questions for measured in per.values())
    data_files = sum(measured.data_files for measured in per.values())
    data_bytes = sum(measured.data_bytes for measured in per.values())
    built_files = (
        SITE_RESERVE_FILES
        + RUN_RESERVE_FILES * len(runs)
        + sum(measured.built_files for measured in per.values())
    )
    built_bytes = (
        SITE_RESERVE_BYTES
        + RUN_RESERVE_BYTES * len(runs)
        + sum(measured.built_bytes for measured in per.values())
    )
    print(
        f"{'all':<22} {len(runs):>5} {questions:>10} {data_files:>7} {data_bytes:>12,} "
        f"{built_bytes:>12,}"
    )
    print(
        f"predicted for the built site: {built_files:,} files of {MAX_FILES:,}, "
        f"{built_bytes:,} bytes of {MAX_BYTES:,}"
    )
    print(f"left out: {len(dropped)} questions, {sum(q.data_bytes for q in dropped):,} bytes")


def write(
    out: Path,
    runs: Sequence[Run],
    kept: Sequence[Question],
    dropped: Sequence[Question],
    classifications: Mapping[str, Classification],
    work: Path,
) -> None:
    """The selection copied under `data/`, with everything a page reads beside it."""
    _clear(out)
    by_run: dict[str, list[Question]] = {}
    for question in kept:
        by_run.setdefault(question.run.slug, []).append(question)
    for run in runs:
        destination = out / run.slug
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run.audit / SUMMARY_FILE, destination / SUMMARY_FILE)
        for question in by_run.get(run.slug, ()):
            beside = destination / question.directory.name
            beside.mkdir(parents=True, exist_ok=True)
            for name in question.files:
                shutil.copyfile(question.directory / name, beside / name)
        _write_json(destination / QUESTIONS_FILE, _questions_of(run, work))
        classification = classifications.get(run.benchmark)
        if classification is not None:
            shutil.copyfile(classification.source, destination / CLASSIFICATION_FILE)
            _write_json(destination / CLASSIFICATION_SOURCE_FILE, _source_of(classification, run))
    for benchmark, classification in classifications.items():
        if not (out / benchmark).is_dir():
            continue
        shutil.copyfile(classification.source, out / benchmark / CLASSIFICATION_FILE)
        _write_json(out / benchmark / CLASSIFICATION_SOURCE_FILE, _source_of(classification, None))
    _write_json(out / AGGREGATE_FILE, _aggregate(runs, kept, classifications))
    _write_json(out / SELECTION_FILE, _selection(runs, kept))
    _write_json(out / LEFT_OUT_FILE, _left_out(dropped))


def _clear(out: Path) -> None:
    """Everything a selection before this one wrote, gone, and the README kept.

    The directory's own README states what a benchmark and a run are and is not written here;
    everything else under it is this script's output and is made again from the work directory.
    """
    if not out.is_dir():
        out.mkdir(parents=True)
        return
    for path in out.iterdir():
        if path.name == "README.md":
            continue
        shutil.rmtree(path) if path.is_dir() else path.unlink()


def _questions_of(run: Run, work: Path) -> list[Mapping[str, object]]:
    """The question id, the database and the question text of every question this run audited.

    The database a question is about reaches no file the audit writes, and the run page and the
    question page both name it, so it is read here out of the question file the run's own
    summary names and written beside that summary. Restricted to the ids the run audited, which
    on SQLite is the one database's own.
    """
    question_set = _mapping(run.summary, "question_set")
    path = work / _text(question_set, "path")
    if not path.is_file():
        raise SelectionRefused(
            f"{run.slug} names {path}, which is not there: the question file a run states is "
            f"where the database of each of its questions is read from"
        )
    wanted = {str(found) for found in _list(question_set, "ids")}
    entries = cast("list[Mapping[str, object]]", json.loads(path.read_text(encoding="utf-8")))
    return [
        {
            "question_id": str(entry["question_id"]),
            "db_id": str(entry["db_id"]),
            "question": str(entry["question"]),
        }
        for entry in entries
        if not wanted or str(entry["question_id"]) in wanted
    ]


def _source_of(classification: Classification, run: Run | None) -> Mapping[str, object]:
    """Where a hand classification came from, what date it carries, and how a page joins it."""
    stated: dict[str, object] = {
        "source": classification.relative,
        "date": classification.date,
        "shape": classification.shape,
        "reason_field": classification.reason_field,
        "keys": classification.keys,
    }
    if run is not None:
        stated["key"] = run.group or run.name if classification.shape == "per_file" else run.name
    return stated


def _aggregate(
    runs: Sequence[Run],
    kept: Sequence[Question],
    classifications: Mapping[str, Classification],
) -> Mapping[str, object]:
    """The three numbers the landing page reads, each with the file it was read out of.

    `credited_but_not_equal` is the count every `minidev-pg` run's own summary states, added
    up; the two hand numbers are the rows of the two classifications that join to a question
    those runs credited, so that the part is a part of the whole the bar draws it inside.
    """
    prediction_runs = [run for run in runs if run.benchmark == "minidev-pg"]
    credited = 0
    for run in prediction_runs:
        stated = run.summary.get("credited_but_not_equal")
        if not isinstance(stated, dict):
            raise SelectionRefused(f"{run.slug} states no credited_but_not_equal to add up")
        credited += _integer(cast("Mapping[str, object]", stated), "total")
    return {
        "credited_but_not_equal": {
            "value": credited,
            "source": (
                "minidev-pg/<run>/summary.json, credited_but_not_equal.total over the "
                f"{len(prediction_runs)} runs"
            ),
        },
        "classified_by_hand": {
            "value": _classified(kept, classifications, "minidev-pg", "A"),
            "source": f"minidev-pg/{CLASSIFICATION_FILE}",
        },
        "bird_dev_classified_by_hand": {
            "value": _classified(kept, classifications, "bird-dev-sqlite", "wrong"),
            "source": f"bird-dev-sqlite/{CLASSIFICATION_FILE}",
        },
    }


def _classified(
    kept: Sequence[Question],
    classifications: Mapping[str, Classification],
    benchmark: str,
    wanted: str,
) -> int:
    """The rows of one classification in one class that join to a published question."""
    classification = classifications.get(benchmark)
    if classification is None:
        return 0
    total = 0
    for question in kept:
        if question.run.benchmark != benchmark or "hand" not in question.reasons:
            continue
        row = _hand_rows(classification, question.run).get(question.question_id)
        if row is not None and row["class"] == wanted:
            total += 1
    return total


def _selection(runs: Sequence[Run], kept: Sequence[Question]) -> Mapping[str, object]:
    """One row per run for the reconciliation: what it counted and what the site shows of it."""
    by_run: dict[str, list[Question]] = {}
    for question in kept:
        by_run.setdefault(question.run.slug, []).append(question)
    return {
        "runs": [
            {
                "slug": run.slug,
                "benchmark": run.benchmark,
                "group": run.group,
                "run": run.name,
                "run_id": _text(run.summary, "run_id"),
                "audited": _integer(_mapping(run.summary, "question_set"), "audited"),
                "verdicts": _mapping(run.summary, "verdicts"),
                "smells_fired": run.summary.get("smells_fired"),
                "credited_but_not_equal": run.summary.get("credited_but_not_equal"),
                "errors": len(_list(run.summary, "errors")),
                "timed_out": run.summary.get("timed_out"),
                "elapsed_seconds": run.summary.get("elapsed_seconds"),
                "published_questions": len(by_run.get(run.slug, ())),
                "published_ids": sorted(
                    (question.question_id for question in by_run.get(run.slug, ())), key=int
                ),
                "archive": run.archive,
            }
            for run in runs
        ]
    }


def _left_out(dropped: Sequence[Question]) -> Mapping[str, object]:
    """Every question the budget left out, largest first, with its size and why."""
    return {
        "questions": [
            {
                "slug": question.run.slug,
                "question_id": question.question_id,
                "data_bytes": question.data_bytes,
                "page_bytes": question.page_bytes,
                "reasons": sorted(question.reasons),
            }
            for question in sorted(dropped, key=lambda found: -found.data_bytes)
        ]
    }


def write_published(out: Path, manifest: Path) -> int:
    """The release-asset line of each run or group, written after the assets are uploaded.

    The manifest is a list of `{name, url, bytes, sha256}` for the archives; every run whose
    archive is in it gets `published.json` beside its summary, and every group gets one of its
    own at the group's level, which is where a reader of the benchmark index is.
    """
    assets = {
        _text(asset, "name"): asset
        for asset in _list(_document(manifest), "assets")
        if isinstance(asset, dict)
    }
    written = 0
    for summary in sorted(out.rglob(SUMMARY_FILE)):
        run = summary.parent
        parts = run.relative_to(out).parts
        benchmark = parts[0]
        archive = f"{benchmark}-{parts[1] if len(parts) == 3 else parts[-1]}.tar.gz"
        asset = assets.get(archive)
        if asset is None:
            raise SelectionRefused(f"{manifest} names no asset {archive} for {run}")
        _write_json(run / PUBLISHED_FILE, asset)
        written += 1
        if len(parts) == 3:
            _write_json(run.parent / PUBLISHED_FILE, asset)
    print(f"{PUBLISHED_FILE} written for {written} runs")
    return 0


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _document(path: Path) -> Mapping[str, object]:
    try:
        stated = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as unreadable:
        raise SelectionRefused(f"{path} could not be read as JSON: {unreadable}") from unreadable
    if not isinstance(stated, dict):
        raise SelectionRefused(f"{path} holds {type(stated).__name__} where an object was expected")
    return cast("Mapping[str, object]", stated)


def _mapping(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise SelectionRefused(f"{key} is {type(value).__name__} where an object was expected")
    return cast("Mapping[str, object]", value)


def _list(document: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = document.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise SelectionRefused(f"{key} is {type(value).__name__} where a list was expected")
    return cast("list[Mapping[str, object]]", value)


def _text(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    return "" if value is None else str(value)


def _integer(document: Mapping[str, object], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SelectionRefused(f"{key} is {type(value).__name__} where a whole number was expected")
    return value


if __name__ == "__main__":
    sys.exit(main())
