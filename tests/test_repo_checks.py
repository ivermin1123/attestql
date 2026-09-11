"""The repository checks under tools/ must fail on deliberately bad input and pass on
good input. A checker never seen to fail is not known to work."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

import check_adr_index
import check_commit_message
import check_doc_links
import check_typography

EM_DASH = "\u2014"
EN_DASH = "\u2013"
NUMERO = "\u2116"

Check = Callable[[Sequence[str] | None], int]


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(check: Check, root: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    status = check(["--root", str(root)])
    captured = capsys.readouterr()
    return status, captured.out + captured.err


# check_typography


def test_typography_fails_on_an_em_dash_naming_file_line_and_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "docs" / "note.md", f"fine\nbad {EM_DASH} here\n")
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert "docs/note.md:2:5: U+2014 em dash" in output


def test_typography_flags_en_dash_and_numero_sign_in_python(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "src" / "module.py", f"# range 1{EN_DASH}2\n# {NUMERO} 3\n")
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert "src/module.py:1:10: U+2013 en dash" in output
    assert "src/module.py:2:3: U+2116 numero sign" in output


def test_typography_passes_on_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "README.md", "plain hyphen - and nothing else\n")
    write(tmp_path / "src" / "module.py", "x = 1  # hyphen-minus only\n")
    assert run(check_typography.main, tmp_path, capsys) == (0, "check_typography: ok\n")


def test_typography_exempts_blockquote_lines_including_lazy_continuation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        tmp_path / "q.md",
        f"> quoted {EM_DASH} text\ncontinued {EM_DASH} lazily\n\nafter {EM_DASH} the blank line\n",
    )
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert output.count("U+2014") == 1, output
    assert "q.md:4:7: U+2014 em dash" in output


def test_typography_new_block_ends_the_blockquote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "q.md", f"> quoted {EM_DASH} text\n# heading {EM_DASH} dash\n")
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert output.count("U+2014") == 1, output
    assert "q.md:2:" in output


def test_typography_marker_inside_fenced_code_is_not_a_blockquote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "c.md", f"```text\n> looks quoted {EM_DASH} but is code\n```\n")
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert "c.md:2:" in output


def test_typography_skips_hidden_and_cache_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / ".cache" / "x.md", EM_DASH)
    write(tmp_path / "node_modules" / "y.md", EM_DASH)
    write(tmp_path / "pkg.egg-info" / "z.py", f"# {EM_DASH}")
    assert run(check_typography.main, tmp_path, capsys)[0] == 0


def test_no_document_is_exempt_from_the_typography_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exemption set is empty, so a file that once held one is checked like any other."""
    assert not check_typography.VERBATIM_FILES
    write(tmp_path / "docs" / "v29-review.md", f"# Review {EM_DASH} verbatim\n")
    status, output = run(check_typography.main, tmp_path, capsys)
    assert status == 1
    assert "docs/v29-review.md:1:" in output


# check_doc_links


def test_doc_links_fails_on_a_missing_target_naming_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "README.md", "intro\nsee [the plan](docs/missing.md)\n")
    status, output = run(check_doc_links.main, tmp_path, capsys)
    assert status == 1
    assert "README.md:2: broken link 'docs/missing.md'" in output


def test_doc_links_pass_when_targets_exist_and_absolute_urls_and_anchors_are_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "README.md", "[a](docs/a.md) [b](docs/b.md#part 'title') ![img](docs/a.md)\n")
    write(
        tmp_path / "docs" / "a.md",
        "[up](../README.md#section) [web](https://example.com/x.md) [mail](mailto:a@b.c)\n"
        "[anchor](#local) [ref]\n\n[ref]: b.md\n",
    )
    write(tmp_path / "docs" / "b.md", "[root](/README.md)\n")
    assert run(check_doc_links.main, tmp_path, capsys) == (0, "check_doc_links: ok\n")


def test_doc_links_resolve_relative_to_the_linking_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "docs" / "a.md", "top\n")
    write(tmp_path / "docs" / "sub" / "c.md", "[ok](../a.md)\n[bad](a.md)\n")
    status, output = run(check_doc_links.main, tmp_path, capsys)
    assert status == 1
    assert "docs/sub/c.md:2: broken link 'a.md'" in output
    assert "c.md:1:" not in output


def test_doc_links_ignore_links_inside_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        tmp_path / "docs" / "a.md",
        "```md\n[fenced](nope.md)\n```\nprose `[span](nope.md)` prose\n",
    )
    assert run(check_doc_links.main, tmp_path, capsys)[0] == 0


def test_doc_links_only_check_readme_and_docs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "plans" / "p.md", "[elsewhere](nope.md)\n")
    write(tmp_path / "README.md", "no links\n")
    assert run(check_doc_links.main, tmp_path, capsys)[0] == 0


# check_adr_index


def test_adr_index_reports_both_directions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    adr = tmp_path / "docs" / "adr"
    write(adr / "0001-first.md", "# 1\n")
    write(adr / "0002-unlisted.md", "# 2\n")
    write(
        adr / "0000-index.md", "# ADRs\n\n| [0001](0001-first.md) |\n| [0003](0003-missing.md) |\n"
    )
    status, output = run(check_adr_index.main, tmp_path, capsys)
    assert status == 1
    assert "docs/adr/0002-unlisted.md is not linked from docs/adr/0000-index.md" in output
    assert "docs/adr/0000-index.md:4: links 0003-missing.md, which does not exist" in output
    assert "0001-first.md" not in output


def test_adr_index_passes_when_consistent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    adr = tmp_path / "docs" / "adr"
    write(adr / "0001-first.md", "# 1\n")
    write(adr / "0002-second.md", "# 2\n")
    write(
        adr / "0000-index.md",
        "[0001](/docs/adr/0001-first.md) [0002](./0002-second.md#context) "
        "[reg](../claims-register.md)\n",
    )
    assert run(check_adr_index.main, tmp_path, capsys) == (0, "check_adr_index: ok\n")


def test_adr_index_fails_when_the_index_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "docs" / "adr" / "0001-first.md", "# 1\n")
    status, output = run(check_adr_index.main, tmp_path, capsys)
    assert status == 1
    assert "docs/adr/0000-index.md: missing" in output


# check_commit_message


def message(path: Path, text: str) -> list[str]:
    """A message file and the argument list a commit-msg hook would be given for it."""
    path.write_text(text, encoding="utf-8")
    return [str(path)]


def test_commit_message_refuses_a_trailer_crediting_an_assistant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = message(
        tmp_path / "COMMIT_EDITMSG",
        "fix(audit): refuse a catalogue name that did not decode\n"
        "\n"
        "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n",
    )
    status = check_commit_message.main(argv)
    captured = capsys.readouterr()

    assert status == 1
    assert ":3:" in captured.err, "the finding names the line the trailer is on"
    assert "claude" in captured.err.lower()


def test_commit_message_refuses_a_vendor_address_without_a_known_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = message(
        tmp_path / "COMMIT_EDITMSG",
        "docs: a line\n\nco-authored-by: Some Assistant <noreply@openai.com>\n",
    )
    status = check_commit_message.main(argv)

    assert status == 1
    assert "noreply@openai.com" in capsys.readouterr().err


def test_commit_message_refuses_the_generated_with_marker_and_the_robot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = message(
        tmp_path / "COMMIT_EDITMSG",
        "docs: a line\n\n\N{ROBOT FACE} Generated with [Claude Code](https://claude.com/)\n",
    )
    status = check_commit_message.main(argv)
    captured = capsys.readouterr()

    assert status == 1
    assert "generated-with marker" in captured.err
    assert "robot emoji" in captured.err


def test_commit_message_passes_a_message_that_credits_nobody(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = message(
        tmp_path / "COMMIT_EDITMSG",
        "fix(serialize): size a numeric's rendering room by its magnitude\n"
        "\n"
        "Precision was set by significant digits rather than by the exponent.\n"
        "\n"
        "Co-authored-by: A Person <person@example.com>\n",
    )
    status = check_commit_message.main(argv)

    assert status == 0
    assert "ok" in capsys.readouterr().out


def test_commit_message_allows_prose_about_an_assistant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rule is about who a commit claims wrote it, not about what it is about."""
    argv = message(
        tmp_path / "COMMIT_EDITMSG",
        "docs(plans): record what the Claude and codex workers measured\n"
        "\n"
        "The GPT-4 prediction files are the ones BIRD publishes.\n",
    )

    assert check_commit_message.main(argv) == 0
    assert "ok" in capsys.readouterr().out
