"""Copy generated JSON evidence into the committed artifact without copying inputs."""

import json
import os
import shutil
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"

ROOT_FILES = [
    "database-copies.json",
    "prediction-pairing.json",
    "predictions-readable.json",
    "prediction-measurement.json",
    "credits-moved.json",
    "classification.json",
]
DATABASES = {
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
}


def main() -> None:
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    for name in ROOT_FILES:
        source = OUT / name
        if source.exists():
            shutil.copyfile(source, HERE / name)
    tool = HERE / "tool"
    tool.mkdir(exist_ok=True)
    for summary in (OUT / "tool-predictions").glob("*/*/*/summary.json"):
        relative = summary.relative_to(OUT / "tool-predictions")
        if relative.parts[2] not in DATABASES:
            continue
        target = tool / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(summary, target)
    official = HERE / "official"
    official.mkdir(exist_ok=True)
    for result in (OUT / "official").glob("*/*.json"):
        if ".under-load" in result.name or ".alone" in result.name:
            continue
        target = official / result.relative_to(OUT / "official")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result, target)
    sums = []
    for line in (WORK / "SHA256SUMS.predictions").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(None, 1)
        if Path(name).name in {"alpha-sql-dev.json", "gsr-gpt-4o.sql"} or any(
            Path(name).match(pattern)
            for pattern in (
                "predict_dev-codes-*.json",
                "rsl-sql-*.txt",
                "dail-sql-*.txt",
                "csc-sql-*.sql",
                "atlas-core-*.sql",
            )
        ):
            sums.append(f"{digest}  {Path(name).name}")
    (HERE / "SHA256SUMS.predictions").write_text("\n".join(sorted(sums)) + "\n", encoding="utf-8")
    if len(sums) != len(sources["accepted"]):
        raise SystemExit("the copied prediction digest list is not one per accepted file")
    print(f"copied {sum(1 for _ in tool.glob('*/*/*/summary.json'))} tool summaries")


if __name__ == "__main__":
    main()
