"""Rerun alone every run whose stdout holds a timeout line.

usage: MEASURE_WORK=<work-directory> ATTESTQL=<attestql> python3 rerun_timeouts.py

Moving a timed-out run aside makes its summary absent. The matching run script then reuses every
other finished summary and starts only the moved run, so the rerun is serial. The under-load
directory is kept beside it, and a timeout that survives is final.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ["MEASURE_WORK"]).resolve()
OUT = WORK / "out"


def rerun_script(mode: str) -> None:
    script = HERE / ("run_tool.sh" if mode == "tool" else "run_predictions.sh")
    environment = os.environ.copy()
    environment["MEASURE_WORK"] = str(WORK)
    subprocess.run(["/bin/bash", str(script)], check=True, env=environment)  # noqa: S603


def main() -> None:
    rows = []
    for stdout in sorted(OUT.glob("tool*/*/*/stdout.txt")):
        run = stdout.parent
        summary = json.loads(run.joinpath("summary.json").read_text(encoding="utf-8"))
        if not (summary["timed_out"]["gold"] or summary["timed_out"]["prediction"]):
            continue
        if run.name.endswith(".under-load") or run.with_name(run.name + ".under-load").exists():
            continue
        parts = run.relative_to(OUT).parts
        if parts[0] == "tool":
            mode, pass_name, db = "tool", parts[1], parts[2]
        else:
            mode, pass_name, db = "predictions", parts[1], parts[2]
        under_load = run.with_name(run.name + ".under-load")
        shutil.rmtree(under_load, ignore_errors=True)
        run.rename(under_load)
        rerun_script(mode)
        rerun_summary = json.loads(run.joinpath("summary.json").read_text(encoding="utf-8"))
        survived = bool(
            rerun_summary["timed_out"]["gold"] or rerun_summary["timed_out"]["prediction"]
        )
        rows.append(
            {
                "mode": mode,
                "pass": pass_name,
                "db": db,
                "under_load": str(under_load.relative_to(WORK)),
                "serial": str(run.relative_to(WORK)),
                "timeout_survived_alone": survived,
            }
        )
    document = {
        "rule": "one serial rerun per run whose summary holds a timed-out statement; a survivor is final",
        "runs_with_a_timed_out_statement": len(rows),
        "survivors": sum(row["timeout_survived_alone"] for row in rows),
        "rows": rows,
    }
    (OUT / "timeout-reruns.json").write_text(json.dumps(document, indent=1) + "\n")
    print(f"timed-out statements under load: {len(rows)}; survivors alone: {document['survivors']}")


if __name__ == "__main__":
    main()
