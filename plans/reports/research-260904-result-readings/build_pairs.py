"""Build the 170 (model, question_id) pairs from the prediction-mode report's own artifacts.

Inputs (all read-only, none copied into this directory):
  R/classification.json     per_file[<model>].rows[i] = {question_id, class, mechanism, reason}
  R/verdicts-hf.json        [<model>][str(question_id)] = {verdict, rule, bird_ex, mechanism?}
  D/hf/mini_dev_pg-...json  gold: list of {question_id, db_id, question, evidence, SQL, difficulty}
  D/preds-by-id/predict_mini_dev_<model>_postgresql.json[str(question_id)] = "SQL\\t----- bird -----\\tdb_id"

Output: pairs.json in this directory (question ids and db ids only, no question text, no full
SQL copied verbatim beyond what is needed to run it, which stays out of the repository: the SQL
text itself is written to $W, not here).
"""

import json
import os
from pathlib import Path

SCRATCH = os.environ.get("MEASURE_WORK", ".")
"""The directory this run worked in, which held `data/` and `work-r*/`.

Read from the environment and not written here: the run of 2026-09-04 used a scratch
directory belonging to the session that made it, and one machine's layout is not something
this repository publishes. The default is what a rerun from that directory reads."""

R = Path(__file__).resolve().parents[1] / "prediction-mode-260904-real-predictions"
D = f"{SCRATCH}/data"
W = f"{SCRATCH}/work-ra"


def main():
    classification = json.loads((R / "classification.json").read_text())
    verdicts = json.loads((R / "verdicts-hf.json").read_text())
    gold_list = json.loads(Path(f"{D}/hf/mini_dev_pg-00000-of-00001.json").read_text())
    gold_by_id = {g["question_id"]: g for g in gold_list}

    pairs = []
    for model, entry in classification["per_file"].items():
        preds = json.loads(
            Path(f"{D}/preds-by-id/predict_mini_dev_{model}_postgresql.json").read_text()
        )
        for row in entry["rows"]:
            qid = row["question_id"]
            v = verdicts[model][str(qid)]
            gold = gold_by_id[qid]
            pred_raw = preds[str(qid)]
            pred_sql, _, _pred_db = pred_raw.partition("\t----- bird -----\t")
            pairs.append(
                {
                    "model": model,
                    "question_id": qid,
                    "db_id": gold["db_id"],
                    "class": row["class"],
                    "mechanism": row["mechanism"],
                    "rule": v["rule"],
                    "bird_ex": v["bird_ex"],
                }
            )
            # SQL text (third-party content) written only to the scratch dir, keyed the same way.
            os.makedirs(f"{W}/sql", exist_ok=True)
            with open(f"{W}/sql/{model}__q{qid}.json", "w") as f:
                json.dump(
                    {"gold_sql": gold["SQL"], "pred_sql": pred_sql, "question": gold["question"]}, f
                )

    if len(pairs) != 170:
        raise ValueError(f"expected 170 pairs, got {len(pairs)}")
    with open(f"{os.path.dirname(__file__)}/pairs.json", "w") as f:
        json.dump(pairs, f, indent=1)
    print(f"wrote {len(pairs)} pairs")


if __name__ == "__main__":
    main()
