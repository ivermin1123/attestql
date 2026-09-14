"""Building the pages and writing them out: the templates, the output directory, the copy.

What the models above become: a question page from a counterexample and its two records, a run
page from a summary, and the files a render leaves on disk. The output directory's lifecycle is
here because what a rerun may empty is part of what a render is.
"""

from __future__ import annotations

import difflib
import json
import shutil
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from attestql.contract.document import JsonObject, JsonValue
from attestql.evidence.load import LoadedRecord, load_record
from attestql.report.figures import question_figure
from attestql.report.render.errors import ReportRefused
from attestql.report.render.indexes import (
    FILTER_DIRECTORIES,
    credited,
    data_file,
    mechanism_counts,
    probe_fired,
)
from attestql.report.render.load import (
    CLASSIFICATION_FILE,
    CLASSIFICATION_SOURCE_FILE,
    COUNTEREXAMPLE_FILE,
    GOLD_RECORD_FILE,
    QUESTION_DIRECTORY,
    SECOND_RECORD_FILE,
    SMELLS_FILE,
    SUMMARY_FILE,
    Beside,
    array_at,
    array_of,
    as_text,
    beside_the_run,
    cell_text,
    facts_of,
    integer_at,
    listed_directories,
    object_at,
    object_of,
    object_or_none,
    objects_at,
    optional_integer,
    optional_text,
    origin_of,
    read_document,
    strings_at,
    text_at,
)
from attestql.report.render.models import (
    ALWAYS_TAGGED,
    BIRD_READING,
    GOLD,
    GOLD_GLYPH,
    GOLD_ONLY,
    ROWS_ON_A_PAGE,
    SECOND,
    SECOND_GLYPH,
    SQL_TOKEN,
    TEST_SUITE_READING,
    Cell,
    Column,
    Crumb,
    Difference,
    Entry,
    Fact,
    Hash,
    Mechanism,
    Probe,
    Projection,
    Published,
    QuestionPage,
    Reading,
    Record,
    Report,
    Row,
    Rows,
    RunPage,
    Side,
    Source,
    Token,
    count_in_words,
)

TEMPLATES = Path(__file__).parent.parent / "templates"
STATIC = Path(__file__).parent.parent / "static"
"""Both are the report package's own, one directory above this one since the split of
2026-09-14: the templates a page is rendered from and the stylesheet every page links."""
"""Where the templates and the stylesheet are, found beside this file.

``importlib`` is forbidden repository-wide outside package metadata
(``tests/test_boundary.py``), and a package directory that ships its templates is a
directory this file can point at."""

PAGE_COMMAND = "attestql audit"
"""What wrote the directory this command reads, as a refusal names it."""

PAGE_FILE = "index.html"
STATIC_DIRECTORY = "static"
OUT_SUFFIX = "-report"
"""What the default ``--out`` appends to the audit directory's own name. A sibling and
never a child: a rerun of the audit clears its own directory, and a report written inside
one would be left there, stale, beside a fresh run. A ``--out`` that names the audit
directory or a directory under it is refused for that reason, rather than half written and
then abandoned where the audit's own cleanup will meet it."""

MARKER_FILE = ".attestql-report"
"""What says an output directory is a render's own and may be cleared by the next one."""

CLEARED_FILES: tuple[str, ...] = (
    PAGE_FILE,
    SUMMARY_FILE,
    CLASSIFICATION_FILE,
    CLASSIFICATION_SOURCE_FILE,
)
"""Every file a render writes at the root of its output directory, and so every file the
rerun before this one has to remove.

The two classification files were missing from this list until 2026-09-13, and a rerun of a
directory whose audit no longer has them left the copies the render before it made: a
maintainer's own reading of some other run's questions, standing beside a summary that says
nothing about it, in output that had already been published. ``MARKER_TEXT`` says what is
removed, so the two are stated there as well."""

MARKER_TEXT = (
    "written by attestql report: every rerun into this directory removes index.html, "
    "summary.json, classification.json, classification-source.json, the q<id>/ directories, "
    "not-equal/, by-mechanism/, by-probe/ and static/\n"
)
"""The one line the marker holds, so a reader who opens it learns why it is there."""


def default_out(audit_directory: Path) -> Path:
    """Where a report goes when the command line does not say: the audit's own sibling."""
    resolved = audit_directory.resolve()
    return resolved.parent / f"{resolved.name}{OUT_SUFFIX}"


def refuse_an_out_inside_the_audit(audit_directory: Path, out: Path) -> None:
    """A report is written beside an audit and never into one.

    The audit's own rerun clears its directory, so a report written there is either removed
    by the next run or left stale beside it, and a report written *onto* it would copy the
    evidence over itself. Both resolved first, so a relative path, a symlink and a ``..``
    naming the same directory are the same answer.
    """
    inside = out.resolve()
    audit = audit_directory.resolve()
    if inside == audit or audit in inside.parents:
        raise ReportRefused(
            f"--out {out} is the audit directory {audit_directory} or a directory inside it, "
            f"and a report goes beside an audit: a rerun of the audit clears its own "
            f"directory, so nothing written in there survives it. Nothing was written."
        )


def clear_the_render_before_this_one(out: Path) -> None:
    """Everything a previous render wrote here, gone before this one writes anything.

    The same rule the audit's own output directory follows, for the same reason: a reader
    opens this directory and reads it as one report, so a question page the render before
    wrote and this one does not is a page about a question that is not in this run.

    Only a directory this command wrote to is cleared, which is what ``MARKER_FILE`` says.
    One that is empty is taken over and marked, one that holds the marker is cleared and
    keeps it, and one that holds anything else is refused untouched: ``--out`` named a
    directory of the reader's own, and deleting from it would cost them files this command
    never wrote.
    """
    try:
        out.mkdir(parents=True, exist_ok=True)
        entries = sorted(out.iterdir())
    except OSError as unusable:
        raise ReportRefused(
            f"the output directory {out} cannot be made or read: {unusable}"
        ) from unusable
    if entries and not (out / MARKER_FILE).is_file():
        raise ReportRefused(
            f"the output directory {out} is not empty and holds no {MARKER_FILE}, the file "
            f"a report leaves in a directory of its own: nothing in it was removed. A render "
            f"writes into a directory that is empty, that is not there yet, or that an "
            f"earlier report wrote to."
        )
    try:
        for name in CLEARED_FILES:
            (out / name).unlink(missing_ok=True)
        for child in entries:
            if child.is_dir() and (
                QUESTION_DIRECTORY.match(child.name)
                or child.name == STATIC_DIRECTORY
                or child.name in FILTER_DIRECTORIES
            ):
                shutil.rmtree(child)
        (out / MARKER_FILE).write_text(MARKER_TEXT, encoding="utf-8")
    except OSError as unwritable:
        raise ReportRefused(
            f"the output directory {out} cannot be cleared of the render before it: {unwritable}"
        ) from unwritable


def write_pages(
    out: Path,
    run: RunPage,
    questions: Sequence[QuestionPage],
    audit_directory: Path,
    directories: Sequence[Path],
    banner: str,
    static_root: str = "",
    address: str = "",
    icon: str = "",
) -> Report:
    """The pages, the stylesheet and the script, and the JSON copied beside each page.

    ``address`` is where this report's own root is served, with a trailing slash, or the
    empty string for one nobody publishes: every page below states its own address under it.
    """
    environment = _environment()
    pages: list[Path] = [
        _page(
            out / PAGE_FILE,
            environment,
            "run.html",
            page=run,
            root="",
            banner=banner,
            static_root=static_root,
            canonical=address,
            icon=icon,
        )
    ]
    files: list[Path] = [_copy(audit_directory / SUMMARY_FILE, out / SUMMARY_FILE)]
    files.extend(
        _copy(audit_directory / name, out / name)
        for name in (CLASSIFICATION_FILE, CLASSIFICATION_SOURCE_FILE)
        if (audit_directory / name).is_file()
    )
    for question, directory in zip(questions, directories, strict=True):
        beside = out / question.slug
        pages.append(
            _page(
                beside / PAGE_FILE,
                environment,
                "question.html",
                page=question,
                root="../",
                banner=banner,
                static_root=static_root,
                canonical=f"{address}{question.slug}/" if address else "",
                icon=icon,
            )
        )
        files.extend(
            _copy(directory / stated.name, beside / stated.name) for stated in question.files
        )
    filters = [
        _page(
            out / view.slug / PAGE_FILE,
            environment,
            "filter.html",
            page=view,
            root=view.root,
            banner=banner,
            static_root=static_root,
            canonical=f"{address}{view.slug}/" if address else "",
            icon=icon,
        )
        for view in run.filters
    ]
    if not static_root:
        for static in sorted(path for path in STATIC.rglob("*") if path.is_file()):
            # The whole tree, because the fonts are under a directory of their own: a stylesheet
            # copied without them would ask a reader's browser for a file that is not there.
            files.append(_copy(static, out / STATIC_DIRECTORY / static.relative_to(STATIC)))
    return Report(out=out, pages=tuple(pages), files=tuple(files), filters=tuple(filters))


def _environment() -> Environment:
    """Autoescaping on for every template, and an undefined name a template cannot swallow.

    SQL, engine messages and column names are untrusted text: they come from a question
    file, a prediction file and a server, and every one of them reaches a page. Escaping is
    therefore not a per-template decision. ``StrictUndefined`` is the same argument about
    the model: a template that reads a field the model does not have raises here rather
    than rendering an empty region nobody notices.
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _page(
    path: Path,
    environment: Environment,
    template: str,
    *,
    page: object,
    root: str,
    banner: str = "",
    static_root: str = "",
    canonical: str = "",
    icon: str = "",
) -> Path:
    """One page, with where the other pages are and where the stylesheet is told apart.

    ``root`` reaches this report's own root from this page; ``static`` reaches the directory
    holding ``static/``, which is that same root for a report that carries its own copy and a
    directory above the whole report for a site that shares one.

    ``canonical`` is the address this page is served at, and ``icon`` the path of the site's
    own icon under ``static``. Both are the publisher's: a report on somebody's disk has no
    address to state and nothing to point a search engine at.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = environment.get_template(template).render(
        page=page,
        root=root,
        banner=banner,
        static=root + static_root,
        canonical=canonical,
        icon=icon,
    )
    path.write_text(rendered, encoding="utf-8")
    return path


def _copy(source: Path, destination: Path) -> Path:
    """One file beside the page that renders it, byte for byte and by copy, not by move.

    Never a link followed. ``shutil.copyfile`` reads through a symlink without a word, so a
    link inside an audit directory would put whatever it points at, from wherever that is,
    beside a published page.
    """
    if source.is_symlink():
        raise ReportRefused(
            f"{source} is a symlink, and everything beside a page is read out of the audit "
            f"directory: a link would publish whatever it points at, from wherever that is"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def question_page(directory: Path) -> QuestionPage:
    """One question directory as the model a template renders, for a page built elsewhere.

    The second of the accessors this package exposes for the site: the site's landing shows
    one question's differing rows through the same macro the question page shows them
    through, and the rows it shows have to be the ones this module reads out of that
    directory. A second reader of ``counterexample.json`` written over there would be a
    second answer to what those rows are.
    """
    return question_page_beside(directory, beside_the_run(directory.parent))


def question_page_beside(directory: Path, beside: Beside | None = None) -> QuestionPage:
    """One question directory as its page: a comparison when it holds one, a gold otherwise.

    The figure is attached here rather than inside the two builders because it is read off
    the finished page: the rows a slope chart draws are the rows the tables below it show.
    The database and a maintainer's reading come from beside the summary rather than from
    this directory, and are attached the same way and for the same reason.
    """
    counterexample = directory / COUNTEREXAMPLE_FILE
    smells = read_document(directory / SMELLS_FILE)
    page = (
        _comparison_page(directory, read_document(counterexample), smells)
        if counterexample.is_file()
        else _gold_only_page(directory, smells)
    )
    found = beside or Beside(databases={}, by_hand={}, published=None)
    return replace(
        page,
        figure=question_figure(page),
        db_id=found.databases.get(page.question_id, ""),
        by_hand=found.by_hand.get(page.question_id),
    )


def _comparison_page(
    directory: Path, counterexample: JsonObject, smells: JsonObject
) -> QuestionPage:
    """A question that had a prediction: both statements, what differs, and both records."""
    question = object_at(counterexample, "question")
    verdict = object_at(counterexample, "verdict")
    gold = object_at(counterexample, GOLD)
    second = object_at(counterexample, SECOND)
    records = [
        _record(directory / GOLD_RECORD_FILE, GOLD),
        _record(directory / SECOND_RECORD_FILE, SECOND),
    ]
    hashes = object_at(counterexample, "result_hashes")
    projection = object_or_none(counterexample, "projection_names_differ")
    marked_gold, marked_second = mark_differences(
        text_at(gold, "executed_sql"), text_at(second, "executed_sql")
    )
    return QuestionPage(
        slug=directory.name,
        question_id=text_at(question, "question_id"),
        question_set=text_at(question, "question_set"),
        question_text=text_at(question, "question_text"),
        evidence_text=text_at(question, "evidence_text"),
        replay_rule=text_at(counterexample, "replay_rule"),
        verdict=text_at(verdict, "result").upper(),
        verdict_reading=text_at(verdict, "reading"),
        mismatched=tuple(strings_at(verdict, "mismatched")),
        mechanism=_mechanism(object_or_none(counterexample, "mechanism")),
        projection=(
            None
            if projection is None
            else Projection(
                gold=tuple(strings_at(projection, GOLD)),
                second=tuple(strings_at(projection, SECOND)),
                reading=text_at(projection, "reading"),
            )
        ),
        backend_identity=text_at(counterexample, "backend_identity"),
        run_id=text_at(counterexample, "run_id"),
        sides=(
            _side(GOLD, GOLD_GLYPH, gold, marked_gold, text_at(hashes, GOLD), COUNTEREXAMPLE_FILE),
            _side(
                SECOND,
                SECOND_GLYPH,
                second,
                marked_second,
                text_at(hashes, SECOND),
                COUNTEREXAMPLE_FILE,
            ),
        ),
        differences=_differences(counterexample, records),
        readings=(
            _reading(BIRD_READING, object_at(counterexample, "bird_ex")),
            _reading(TEST_SUITE_READING, object_at(counterexample, "test_suite_ex")),
        ),
        probes=_probes(smells),
        probes_reading=text_at(smells, "reading"),
        records=tuple(record for record, _ in records),
        files=(
            Fact(COUNTEREXAMPLE_FILE, text_at(counterexample, "format")),
            Fact(GOLD_RECORD_FILE, "the gold's evidence record"),
            Fact(SECOND_RECORD_FILE, "the prediction's evidence record"),
            Fact(SMELLS_FILE, text_at(smells, "format")),
        ),
    )


def _gold_only_page(directory: Path, smells: JsonObject) -> QuestionPage:
    """A question with no prediction: the gold's own record is what the probes are about."""
    record, document = _record(directory / GOLD_RECORD_FILE, GOLD)
    question = object_at(document, "question")
    return QuestionPage(
        slug=directory.name,
        question_id=text_at(question, "question_id"),
        question_set=text_at(question, "question_set"),
        question_text=text_at(question, "question_text"),
        evidence_text=text_at(question, "evidence_text"),
        replay_rule=text_at(document, "replay_rule"),
        verdict=GOLD_ONLY,
        verdict_reading=(
            "This question was audited without a prediction beside it, so there is nothing "
            "to compare the gold with. The probes below read the gold alone."
        ),
        mismatched=(),
        mechanism=None,
        projection=None,
        backend_identity=text_at(document, "backend_identity_at_checkout"),
        run_id=text_at(document, "run_id"),
        sides=(_record_side(document, record),),
        differences=(),
        readings=(),
        probes=_probes(smells),
        probes_reading=text_at(smells, "reading"),
        records=(record,),
        files=(
            Fact(GOLD_RECORD_FILE, "the gold's evidence record"),
            Fact(SMELLS_FILE, text_at(smells, "format")),
        ),
    )


def _side(
    side: str,
    glyph: str,
    stated: JsonObject,
    tokens: tuple[Token, ...],
    result_hash: str,
    source: str,
) -> Side:
    """One statement of a counterexample: its SQL, its own ordering and its bounded result."""
    return Side(
        side=side,
        glyph=glyph,
        tokens=tokens,
        ordering=tuple(
            Fact(
                text_at(key, "expression"),
                "descending" if bool(key.get("descending")) else "ascending",
                f"nulls {text_at(key, 'nulls')}",
            )
            for key in objects_at(stated, "own_ordering")
        ),
        result=_result_rows(object_at(stated, "result"), source),
        result_hash=result_hash,
        record_file=text_at(stated, "record"),
    )


def _record_side(document: JsonObject, record: Record) -> Side:
    """The gold of a question that had no prediction, read from its record."""
    return Side(
        side=GOLD,
        glyph=GOLD_GLYPH,
        tokens=(Token(text=text_at(document, "executed_sql"), differs=False),),
        ordering=tuple(
            Fact(
                text_at(key, "column"), "descending" if bool(key.get("descending")) else "ascending"
            )
            for key in objects_at(document, "canonical_ordering")
        ),
        result=record.result,
        result_hash=record.hashes[0].stated,
        record_file=GOLD_RECORD_FILE,
    )


def _differences(
    counterexample: JsonObject, records: Sequence[tuple[Record, JsonObject]]
) -> tuple[Difference, ...]:
    """The two one-sided row differences, each under the columns of the side it came from."""
    stated = object_at(counterexample, "differing_rows")
    per_side = integer_at(stated, "rows_shown_per_side")
    sides = (
        (GOLD, GOLD_GLYPH, "in_gold_not_in_second", "in gold, not in the prediction"),
        (SECOND, SECOND_GLYPH, "in_second_not_in_gold", "in the prediction, not in gold"),
    )
    differences: list[Difference] = []
    for (label, glyph, key, heading), (record, _) in zip(sides, records, strict=True):
        groups = objects_at(stated, key)
        total = integer_at(stated, f"{key}_total")
        differences.append(
            Difference(
                label=label,
                glyph=glyph,
                heading=heading,
                rows=_grouped_rows(groups, record.result.columns, label, glyph, total, per_side),
                total=total,
                rows_shown_per_side=per_side,
            )
        )
    return tuple(differences)


def _grouped_rows(
    groups: Sequence[JsonObject],
    columns: tuple[Column, ...],
    label: str,
    glyph: str,
    total: int,
    per_side: int,
) -> Rows:
    """The rows of one side of a difference, each with the number of times it occurred."""
    rows = tuple(
        Row(
            cells=_cells(array_at(group, "row")),
            count=integer_at(group, "count"),
            label=label,
            glyph=glyph,
        )
        for group in groups
    )
    return _tagged(
        Rows(
            source=(
                f"from {COUNTEREXAMPLE_FILE}, {count_in_words(total)}, up to {per_side} shown per side"
            ),
            columns=columns,
            rows=rows,
            row_count=total,
            rows_shown=len(rows),
            truncated=False,
            counted=any((row.count or 0) > 1 for row in rows),
            labelled=True,
        )
    )


def _result_rows(result: JsonObject, source: str) -> Rows:
    """A result block as a table: its columns, a bounded reading of its rows, and the rest.

    Bounded since 2026-09-13. A record holds every row of its result and the page embedded
    all of them: two pages of the 2026-09-08 build weighed 1,806 kB with 16,616 row elements
    in them, which is a document a browser has to lay out however little of it a reader
    looks at. The bytes were never the problem, and the page is still inside its budget
    either way; the size of the document is, and the rows a reader actually reads are the
    first of them.

    Nothing is lost by the bound: the JSON these rows were read from is copied beside the
    page and the page links to it, and the row count on the table's own line is the whole
    count and not the shown one.
    """
    held = array_at(result, "rows")
    rows = tuple(
        Row(cells=_cells(array_of(row, "a row")), count=None, label="", glyph="")
        for row in held[:ROWS_ON_A_PAGE]
    )
    row_count = integer_at(result, "row_count")
    return _tagged(
        Rows(
            source=f"from {source}, {count_in_words(row_count)}",
            columns=tuple(
                Column(name=text_at(column, "name"), declared_type=text_at(column, "declared_type"))
                for column in objects_at(result, "columns")
            ),
            rows=rows,
            row_count=row_count,
            rows_shown=min(optional_integer(result, "rows_shown", len(held)), len(rows)),
            truncated=bool(result.get("truncated")),
            counted=False,
            labelled=False,
        )
    )


def _probe_rows(rows: Sequence[JsonValue]) -> Rows:
    """The rows a fired probe carries. The probe names no columns for them, so nor does this."""
    built = tuple(
        Row(cells=_cells(array_of(row, "a probe row")), count=None, label="", glyph="")
        for row in rows
    )
    return _tagged(
        Rows(
            source=f"from {SMELLS_FILE}, {count_in_words(len(built))}",
            columns=(),
            rows=built,
            row_count=len(built),
            rows_shown=len(built),
            truncated=False,
            counted=False,
            labelled=False,
        )
    )


def _cells(row: Sequence[JsonValue]) -> tuple[Cell, ...]:
    """One rendered row as its cells, each with the tag the value was written under."""
    return tuple(
        Cell(
            tag=text_at(cell, "type"),
            text=cell_text(cell),
            is_null=text_at(cell, "type") == "null",
            show_tag=False,
        )
        for cell in (object_of(value, "a cell") for value in row)
    )


def _tagged(rows: Rows) -> Rows:
    """The same table with a type tag on the cells of every column whose rows disagree.

    A column of a SQLite result holds whatever its cells came back as, so a page that
    showed only the declared type would state one type for a column holding two. The tag
    is put where the rows themselves disagree, which is where a reader has something to
    see, and nowhere else, with the exception of ``ALWAYS_TAGGED``: it is read off the rows
    and states nothing about the engine.
    """
    if not rows.rows:
        return rows
    width = max(len(row.cells) for row in rows.rows)
    mixed = [
        len({row.cells[index].tag for row in rows.rows if index < len(row.cells)}) > 1
        for index in range(width)
    ]
    return Rows(
        source=rows.source,
        columns=rows.columns,
        rows=tuple(
            Row(
                cells=tuple(
                    Cell(
                        tag=cell.tag,
                        text=cell.text,
                        is_null=cell.is_null,
                        show_tag=mixed[index] or cell.tag in ALWAYS_TAGGED,
                    )
                    for index, cell in enumerate(row.cells)
                ),
                count=row.count,
                label=row.label,
                glyph=row.glyph,
            )
            for row in rows.rows
        ),
        row_count=rows.row_count,
        rows_shown=rows.rows_shown,
        truncated=rows.truncated,
        counted=rows.counted,
        labelled=rows.labelled,
    )


def _record(path: Path, side: str) -> tuple[Record, JsonObject]:
    """One evidence record as a page states it, with its result and its two hashes retaken."""
    document = read_document(path)
    loaded: LoadedRecord = load_record(document)
    settings = object_at(document, "session_settings_in_force")
    result = object_at(document, "result")
    fixture = object_at(document, "fixture")
    source = object_at(document, "statement_source")
    validation = object_at(document, "validation_outcome")
    return (
        Record(
            file=path.name,
            side=side,
            executed_sql=text_at(document, "executed_sql"),
            source=Source(
                path=text_at(source, "path"),
                digest=text_at(source, "digest"),
                origin=optional_text(source, "origin"),
                date=optional_text(source, "date"),
            ),
            identity=(
                Fact("run", text_at(document, "run_id")),
                Fact("executed at", text_at(document, "executed_at")),
                Fact("data as of", text_at(document, "data_as_of")),
                Fact("backend at checkout", text_at(document, "backend_identity_at_checkout")),
                Fact("backend that answered", optional_text(result, "backend_identity")),
                Fact("database role", text_at(document, "effective_database_role")),
                Fact("replay rule", text_at(document, "replay_rule")),
                Fact("question set version", text_at(document, "question_set_version")),
                Fact("validator", text_at(document, "validator_version")),
                Fact("checks run", ", ".join(strings_at(validation, "checks_run"))),
                Fact("statement timeout", f"{optional_text(result, 'statement_timeout_ms')} ms"),
                Fact("rows", count_in_words(integer_at(document, "row_count"))),
            ),
            session=tuple(
                Fact(name, optional_text(settings, name, absent="not stated by this engine"))
                for name in settings
                if name != "recorded"
            ),
            recorded=facts_of(object_at(settings, "recorded")),
            serialization=facts_of(object_at(document, "serialization")),
            fixture=(
                Fact("schema digest", optional_text(fixture, "schema_digest")),
                Fact("source file sha256", optional_text(fixture, "source_file_sha256")),
                *(
                    Fact(f"rows in {name}", as_text(count))
                    for name, count in object_at(fixture, "row_counts").items()
                ),
            ),
            result=_result_rows(result, path.name),
            hashes=(
                Hash(
                    name="result_hash",
                    stated=loaded.result_hash.stated,
                    recomputed=loaded.result_hash.recomputed,
                    match=loaded.result_hash.match,
                ),
                Hash(
                    name="record_hash",
                    stated=loaded.record_hash.stated,
                    recomputed=loaded.record_hash.recomputed,
                    match=loaded.record_hash.match,
                ),
            ),
            rerun_instruction=text_at(document, "rerun_instruction"),
        ),
        document,
    )


def _mechanism(stated: JsonObject | None) -> Mechanism | None:
    if stated is None:
        return None
    return Mechanism(
        classification=text_at(stated, "class"),
        reading=text_at(stated, "reading"),
        facts=tuple(
            Fact(name, as_text(value))
            for name, value in stated.items()
            if name not in {"class", "reading"}
        ),
    )


def _reading(name: str, stated: JsonObject) -> Reading:
    """One evaluator's own answer about the same two results, as its document states it."""
    return Reading(
        name=name,
        value=integer_at(stated, "value"),
        equal=bool(stated.get("equal")),
        method=text_at(stated, "method"),
        source=text_at(stated, "source"),
        counts=tuple(
            Fact(key, as_text(value))
            for key, value in stated.items()
            if key not in {"value", "equal", "method", "source"}
        ),
    )


def _probes(smells: JsonObject) -> tuple[Probe, ...]:
    """Every probe that ran on this gold, fired, quiet and not applicable alike."""
    probes: list[Probe] = []
    for stated in objects_at(smells, "smells"):
        evidence = object_at(stated, "evidence")
        rows = array_at(stated, "counterexample_rows")
        probes.append(
            Probe(
                name=text_at(stated, "name"),
                fired=bool(stated.get("fired")),
                applicable=bool(stated.get("applicable")),
                means=optional_text(evidence, "means"),
                reason=optional_text(evidence, "reason"),
                evidence=json.dumps(
                    {key: value for key, value in evidence.items() if key != "means"},
                    indent=2,
                    ensure_ascii=False,
                ),
                rows=_probe_rows(rows) if rows else None,
            )
        )
    return tuple(probes)


def run_page(
    summary: JsonObject,
    questions: Sequence[QuestionPage],
    directories: Sequence[Path],
    published: Published | None = None,
    found: int = 0,
    *,
    within: str = "",
    breadcrumb: tuple[Crumb, ...] = (),
) -> RunPage:
    """``summary.json`` as the page a reader opens first: the counts, the run, the index."""
    question_set = object_at(summary, "question_set")
    predictions = object_or_none(summary, "predictions")
    fixture = object_at(summary, "fixture")
    settings = object_at(summary, "settings")
    shuffle = object_at(summary, "shuffle")
    session = object_at(summary, "session_settings")
    verdicts = object_at(summary, "verdicts")
    listed = listed_directories(summary)
    return RunPage(
        within=within,
        breadcrumb=breadcrumb,
        published=published,
        directories=found,
        wrote=None if listed is None else len(listed),
        run_id=text_at(summary, "run_id"),
        format=text_at(summary, "format"),
        exit_status=integer_at(summary, "exit_status"),
        questions_audited=integer_at(question_set, "audited"),
        counts=(
            Fact("questions audited", as_text(question_set.get("audited"))),
            *(Fact(name, as_text(count)) for name, count in verdicts.items()),
            Fact("probes fired", as_text(summary.get("smells_fired"))),
        ),
        verdict_counts=tuple(
            (name, value) for name, value in verdicts.items() if isinstance(value, int)
        ),
        mechanism_counts=mechanism_counts(questions),
        probe_counts=facts_of(object_at(summary, "smells")),
        probe_fired=probe_fired(object_at(summary, "smells")),
        credited=credited(object_or_none(summary, "credited_but_not_equal")),
        made_of=(
            Fact("run", text_at(summary, "run_id")),
            Fact("summary format", text_at(summary, "format")),
            Fact(
                "question file",
                text_at(question_set, "path"),
                origin_of(question_set, text_at(question_set, "digest")),
            ),
            Fact("questions in the file", as_text(question_set.get("entries"))),
            *(
                ()
                if predictions is None
                else (
                    Fact(
                        "prediction file",
                        text_at(predictions, "path"),
                        origin_of(predictions, text_at(predictions, "digest")),
                    ),
                    Fact("statements read", as_text(predictions.get("statements"))),
                    Fact("keyed by", text_at(predictions, "keyed_by")),
                )
            ),
            *data_file(object_or_none(fixture, "source")),
            Fact("server", text_at(summary, "backend_identity")),
            Fact("database role", text_at(summary, "effective_database_role")),
            Fact("engine", text_at(session, "engine")),
            Fact("parser", ", ".join(f"{k} {v}" for k, v in object_at(summary, "parser").items())),
            Fact("serialization", text_at(settings, "serialization")),
            Fact("statement timeout", f"{as_text(settings.get('statement_timeout_seconds'))} s"),
            Fact("fixture digest depth", text_at(fixture, "depth")),
            Fact("schema digest", optional_text(fixture, "schema_digest")),
            Fact(
                "data as of", text_at(summary, "data_as_of"), text_at(summary, "data_as_of_source")
            ),
            Fact(
                "shuffled copies",
                "prepared" if bool(shuffle.get("prepared")) else "not prepared",
                optional_text(shuffle, "reason"),
            ),
            Fact("shuffle seed", as_text(shuffle.get("seed"))),
            Fact("experimental probe", "on" if bool(settings.get("experimental_s2")) else "off"),
        ),
        session=facts_of(object_at(session, "recorded")),
        notes=_notes(summary, question_set, predictions, fixture, shuffle),
        entries=_entries(summary, questions, directories),
        files=(Fact(SUMMARY_FILE, text_at(summary, "format")),),
    )


def _notes(
    summary: JsonObject,
    question_set: JsonObject,
    predictions: JsonObject | None,
    fixture: JsonObject,
    shuffle: JsonObject,
) -> tuple[Fact, ...]:
    """The states of the run that are a row rather than a page, stated only when they occurred."""
    notes: list[Fact] = []
    duplicates = strings_at(question_set, "duplicate_ids")
    if duplicates:
        notes.append(Fact("ids the question file states twice", ", ".join(duplicates)))
    if predictions is not None:
        unused = strings_at(predictions, "positions_unused")
        if unused:
            notes.append(Fact("prediction positions not compared", ", ".join(unused)))
    for key, name in (
        ("missing_tables", "tables the catalogue does not hold"),
        ("unreadable_tables", "tables this role may not read"),
    ):
        tables = strings_at(fixture, key)
        if tables:
            notes.append(Fact(name, ", ".join(tables)))
    refused = optional_text(fixture, "refused")
    if refused:
        notes.append(Fact("the fixture measurement was refused", refused))
    for name, reason in object_at(shuffle, "not_reached_by_a_copy").items():
        notes.append(Fact(f"{name} was not reached by a shuffled copy", as_text(reason)))
    bound = as_text(object_at(summary, "settings").get("statement_timeout_seconds"))
    for side, ids in object_at(summary, "timed_out").items():
        stopped = [as_text(value) for value in array_of(ids, "timed_out")]
        if stopped:
            # The bound the run was given, beside the questions that reached it: the record of
            # a side that ran states the timeout it actually held, and a side that never
            # answered has none, so what a reader needs here is what the run asked for.
            notes.append(
                Fact(
                    f"stopped by the statement timeout, {side}",
                    ", ".join(stopped),
                    f"the run's bound was {bound} s",
                )
            )
    return tuple(notes)


def _entries(
    summary: JsonObject, questions: Sequence[QuestionPage], directories: Sequence[Path]
) -> tuple[Entry, ...]:
    """The question index: one row per directory, then the questions that wrote none.

    A question whose statement could not be run has no directory to open, so it is a row
    of this table read from the summary's own error list, with the side that failed, the
    step it failed at and the engine's message.
    """
    entries = [
        Entry(
            question_id=question.question_id,
            href=f"{directory.name}/{PAGE_FILE}",
            verdict=question.verdict,
            replay_rule=question.replay_rule,
            mechanism="" if question.mechanism is None else question.mechanism.classification,
            probes=tuple(probe.name for probe in question.probes if probe.fired),
            question_text=question.question_text,
            note="",
        )
        for question, directory in zip(questions, directories, strict=True)
    ]
    entries.extend(
        Entry(
            question_id=as_text(error.get("question_id")),
            href="",
            verdict="ERROR",
            replay_rule="",
            mechanism="",
            probes=(),
            question_text="",
            note=(
                f"{text_at(error, 'side')}: {text_at(error, 'step')}: {text_at(error, 'message')}"
            ),
        )
        for error in objects_at(summary, "errors")
    )
    return tuple(entries)


def mark_differences(left: str, right: str) -> tuple[tuple[Token, ...], tuple[Token, ...]]:
    """The two statements cut into tokens, with the tokens they differ in marked.

    A comparison of two texts and nothing more. It states nothing about either statement:
    two statements that differ nowhere are two spellings of one, and two that differ
    everywhere may still return the same rows, which is what the verdict above is for.
    """
    left_tokens = SQL_TOKEN.findall(left)
    right_tokens = SQL_TOKEN.findall(right)
    marked_left = [False] * len(left_tokens)
    marked_right = [False] * len(right_tokens)
    matcher = difflib.SequenceMatcher(a=left_tokens, b=right_tokens, autojunk=False)
    for tag, left_from, left_to, right_from, right_to in matcher.get_opcodes():
        if tag == "equal":
            continue
        for index in range(left_from, left_to):
            marked_left[index] = True
        for index in range(right_from, right_to):
            marked_right[index] = True
    return (
        tuple(Token(text, differs) for text, differs in zip(left_tokens, marked_left, strict=True)),
        tuple(
            Token(text, differs) for text, differs in zip(right_tokens, marked_right, strict=True)
        ),
    )
