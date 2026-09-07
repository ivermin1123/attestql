"""Copy every owned measurement output into the committed artifact."""

import json
import shutil
from pathlib import Path

WORK = Path(__import__("os").environ["MEASURE_WORK"])
ARTIFACT = Path(__file__).parent
MODELS = [
    line.split()[0] for line in (ARTIFACT / "SHA256SUMS.predictions").read_text().splitlines()
]
DATABASES = [
    "california_schools",
    "european_football_2",
    "formula_1",
    "thrombosis_prediction",
    "toxicology",
]


def copy_json(source: str, target: str) -> None:
    document = json.loads((WORK / source).read_text())
    destination = ARTIFACT / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    owned = [
        "tables.json",
        "replay/pairs-dev-20240627.json",
        "replay/pairs-dev-20251106.json",
        "replay/pairs-minidev-hf.json",
        "smells-by-copy.json",
        "score-flips.json",
        "cds.json",
        "column-golds.json",
    ]
    for name in owned:
        copy_json(f"out/{name}", name)
    for copy in ("dev", "minidev"):
        for db in DATABASES:
            source = WORK / "out" / "tool" / copy / db / "summary.json"
            target = ARTIFACT / "tool" / copy / db / "summary.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for copy in ("dev", "minidev"):
        for model in MODELS:
            copy_json(f"out/official/{copy}/{model}.json", f"official/{copy}/{model}.json")
    print(f"artifact built: {len(owned)} owned outputs, 10 summaries, {len(MODELS) * 2} scores")


if __name__ == "__main__":
    main()
