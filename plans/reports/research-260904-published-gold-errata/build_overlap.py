"""Builds errata-ids.json and overlap.json for the R-C report.

Inputs (paths as used in the research session; re-derivable from the cited URLs
and sha256 in the report):
- BIRD dev.json 2024-06-27: dev.zip, https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip,
  sha256 630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06
- BIRD Mini-Dev HF 2026-01-18: mini_dev_pg-00000-of-00001.json,
  https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/,
  sha256 7fa740ef9225389cff6c34432120e8325d0ca3008d73db1ae38731234bc10da7
- BIRD Mini-Dev zip: minidev.zip, https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip,
  sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f
- BIRD dev 2025-11-06 QC pass, published on HF 2026-01-18:
  https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/main/data/dev_20251106-00000-of-00001.json
- Wretblad et al. repo, commit 6930cf6f9abaf50a3407f96b9facbda11835eec2:
  https://github.com/niklaswretblad/the-effects-of-noise-in-text-to-SQL
- AttestQL: plans/reports/sweep-260902-gold-only-probes/fired.json,
  plans/reports/prediction-mode-260904-real-predictions/classification.json,
  plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md (class table, hand-copied)
"""

import csv
import json
import re
from pathlib import Path

D = Path(
    "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/"
    "51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
)
W = Path(
    "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/"
    "51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rc"
)
REPORT_DIR = Path(
    "/Users/hoangle/Desktop/code/attestql-research/plans/reports/research-260904-published-gold-errata"
)


def norm(s):
    return re.sub(r"\s+", " ", s.strip().rstrip(";")).lower()


def load_json(path):
    return json.loads(path.read_text())


def load_csv_rows(path):
    return list(csv.DictReader(path.read_text().splitlines()))


# --- AttestQL's own sets ---
attestql = {
    "measurement_A_11": [879, 115, 1029, 129, 1144, 906, 1002, 847, 37, 82, 694],
    "measurement_B_22": [
        1473,
        1476,
        1482,
        1529,
        1531,
        1380,
        1390,
        1410,
        955,
        1389,
        1168,
        1028,
        736,
        751,
        766,
        794,
        671,
        349,
        94,
        1135,
        1011,
        31,
    ],
    "measurement_X_3": [340, 346, 397],
    "corrected_golds_3": [1029, 879, 207],
}
cls = load_json(
    REPORT_DIR.parent / "prediction-mode-260904-real-predictions" / "classification.json"
)
qids56 = {}
for _, v in cls["per_file"].items():
    for r in v["rows"]:
        qids56.setdefault(r["question_id"], set()).add(r["class"])
attestql["classification_56"] = sorted(qids56)

# --- Wretblad et al. financial (all 106 financial questions annotated; flagged = nonblank category) ---
fin_rows = load_csv_rows(W / "wretblad-repo" / "annotations" / "financial_annotations.csv")
fin_rows = [r for r in fin_rows if r["Question ID"].strip()]
wretblad_financial_flagged = sorted(
    int(r["Question ID"]) for r in fin_rows if r["Error Category"].strip()
)

# --- Wretblad et al. sampled (20 each of 4 other domains; flagged = nonblank Annotation) ---
samp_rows = load_csv_rows(W / "wretblad-repo" / "annotations" / "sampled_annotations.csv")
wretblad_sampled_flagged = sorted(
    int(r.get("﻿question_id") or r["question_id"]) for r in samp_rows if r["Annotation"].strip()
)

# --- CIDR 2026 (Jin et al.) Table 2, BIRD Mini-Dev question ids, read from the PDF by hand ---
cidr_minidev = sorted(
    {92, 149, 12, 36, 40, 50, 17, 1376, 1378, 1403, 32, 46, 62, 862, 877, 881, 954, 1175}
)

# --- bird-bench/mini_dev issues naming a question id (from issue titles/bodies, cached in gh_cache/) ---
minidev_issues = {
    38: {"ids": [1029], "state": "open", "date": "2026-08-09"},
    39: {"ids": [207], "state": "open", "date": "2026-09-03"},
    24: {"ids": [879], "state": "closed", "date": "2025-09-13"},
    19: {"ids": [1322], "state": "closed", "date": "2025-03-17"},
    17: {"ids": [137, 138], "state": "closed", "date": "2025-01-03"},
    30: {"ids": [180], "state": "closed", "date": "2025-12-24"},
    18: {"ids": [563, 565], "state": "closed", "date": "2025-03-12"},
    31: {"ids": [336], "state": "open", "date": "2026-01-18"},
}
minidev_issue_ids = sorted({i for v in minidev_issues.values() for i in v["ids"]})

# --- Mini-Dev HF (2026-01-18) vs BIRD dev.json (2024-06-27): question/SQL text differences ---
dev = load_json(D / "dev" / "dev_20240627" / "dev.json")
hf = load_json(D / "hf" / "mini_dev_pg-00000-of-00001.json")
dev_by_id = {e["question_id"]: e for e in dev}
hf_by_id = {e["question_id"]: e for e in hf}
# Mini-Dev's SQL is a PostgreSQL-dialect rewrite of dev.json's SQLite-dialect gold, so SQL text
# always differs by dialect; only db_id + question text identify "the same question" here.
matched = 0
minidev_vs_devjson_diff = []
for row in hf:
    qid = row["question_id"]
    d = dev_by_id.get(qid)
    if d is None:
        continue
    if d["db_id"] == row["db_id"] and d["question"].strip() == row["question"].strip():
        matched += 1
    else:
        minidev_vs_devjson_diff.append(qid)
minidev_vs_devjson_diff.sort()

# --- BIRD dev 2025-11-06 QC pass vs dev.json 2024-06-27 ---
new = load_json(W / "hf-dev1106" / "dev_20251106.json")
new_by_id = {e["question_id"]: e for e in new}
dev1106_sql_diff = []
dev1106_text_only_diff = []
for qid, o in dev_by_id.items():
    n = new_by_id[qid]
    if norm(o["SQL"]) != norm(n["SQL"]):
        dev1106_sql_diff.append(qid)
    elif (
        o["question"].strip() != n["question"].strip()
        or o.get("evidence", "").strip() != n.get("evidence", "").strip()
    ):
        dev1106_text_only_diff.append(qid)
dev1106_sql_diff.sort()
dev1106_text_only_diff.sort()

sources = {
    "attestql_measurement_A_11": attestql["measurement_A_11"],
    "attestql_measurement_B_22": attestql["measurement_B_22"],
    "attestql_measurement_X_3": attestql["measurement_X_3"],
    "attestql_classification_56": attestql["classification_56"],
    "attestql_corrected_golds_3": attestql["corrected_golds_3"],
    "wretblad_financial_flagged_52": wretblad_financial_flagged,
    "wretblad_sampled_flagged_27": wretblad_sampled_flagged,
    "cidr2026_jin_minidev_table2_18": cidr_minidev,
    "minidev_github_issues_ids": minidev_issue_ids,
    "minidev_hf_vs_devjson_text_diff_4": minidev_vs_devjson_diff,
    "bird_dev1106_sql_diff_399": dev1106_sql_diff,
    "bird_dev1106_text_only_diff_172": dev1106_text_only_diff,
}
(REPORT_DIR / "errata-ids.json").write_text(json.dumps(sources, indent=1, sort_keys=True))

# --- overlap matrix ---
names = list(sources.keys())
overlap_counts = {}
overlap_ids = {}
for i, a in enumerate(names):
    for b in names[i + 1 :]:
        common = sorted(set(sources[a]) & set(sources[b]))
        if common:
            key = f"{a} x {b}"
            overlap_counts[key] = len(common)
            overlap_ids[key] = common

overlap = {
    "sizes": {k: len(v) for k, v in sources.items()},
    "overlap_counts": overlap_counts,
    "overlap_ids": overlap_ids,
}
(REPORT_DIR / "overlap.json").write_text(json.dumps(overlap, indent=1, sort_keys=True))

print("sizes:")
for k, v in sources.items():
    print(f"  {k}: {len(v)}")
print()
print("nonzero overlaps:")
for k, v in sorted(overlap_counts.items(), key=lambda kv: -kv[1]):
    print(f"  {k}: {v} -> {overlap_ids[k]}")
print()
print("minidev HF vs dev.json diff ids:", minidev_vs_devjson_diff)
print("dev1106 sql-substantive diff count:", len(dev1106_sql_diff))
print("dev1106 text-only diff count:", len(dev1106_text_only_diff))
