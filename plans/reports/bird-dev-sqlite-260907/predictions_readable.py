"""Write a copy of a BIRD dev prediction file this tool can read, and say what was changed.

    predictions_readable.py <predict_dev.json> <out.json> <changed.json>

BIRD's two `predict_dev.json` files record a prediction the model did not produce as the JSON
number ``0``, not as a string: 14 of 1,534 in `turbo_output_kg`, 54 in `turbo_output`. This tool
refuses the whole file for one of those (`audit/cli.py`: "is int and a prediction is SQL"), so
the file cannot be measured as it ships; the refusal is a gap this measurement found and the
report names it.

The substitution here is upstream's own. `evaluation/evaluation_utils.py` `package_sqls` reads
the same files and replaces a non-string with a single space, which then fails to execute and is
scored 0. Writing that same single space keeps the tool and BIRD's evaluator on the same input:
the tool cannot parse it either, so it becomes that question's error line and no comparison. The
positions changed are written out and the report states their count, so nothing is silent.
"""

import json
import sys
from pathlib import Path

UPSTREAM_SUBSTITUTE = " "
"""What ``package_sqls`` puts in place of a non-string prediction."""


def main() -> None:
    source, target, changed_at = (Path(argument) for argument in sys.argv[1:4])
    document = json.loads(source.read_text())
    changed = sorted(
        (key for key, value in document.items() if not isinstance(value, str)), key=int
    )
    out = {
        key: (value if isinstance(value, str) else UPSTREAM_SUBSTITUTE)
        for key, value in document.items()
    }
    target.write_text(json.dumps(out, indent=1))
    changed_at.write_text(
        json.dumps(
            {
                "source": source.name,
                "entries": len(document),
                "not_a_string": len(changed),
                "positions": changed,
                "substitute": UPSTREAM_SUBSTITUTE,
                "why": (
                    "upstream's package_sqls replaces a non-string prediction with a single "
                    "space; this tool refuses the file instead, so the same substitution is made "
                    "here before the run"
                ),
            },
            indent=1,
        )
        + "\n"
    )
    print(f"{source.name}: {len(changed)} of {len(document)} entries were not a string")


if __name__ == "__main__":
    main()
