"""Condense the per-gold typing_<set>.json (task 4b) into a small summary safe
to check into the report directory: aggregate counts plus the question_id
lists for timeouts/errors and any type-mixing incidents (there were none, but
the script still reports the check rather than assuming it).
"""

import json

W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"


def summarize(set_name, expected_total):
    with open(f"{W}/typing_{set_name}.json") as f:
        rows = json.load(f)
    ok = [r for r in rows if r["status"] == "ok"]
    timeouts = [r["question_id"] for r in rows if r["status"] == "timeout"]
    errors = [
        {"question_id": r["question_id"], "db_id": r["db_id"], "detail": r.get("detail", "")}
        for r in rows
        if r["status"] not in ("ok", "timeout")
    ]
    mix_int_real = []
    mix_text_num = []
    py_smaller = []
    for r in ok:
        for i, s in enumerate(r.get("col_type_sets", [])):
            s = set(s)
            if "int" in s and "float" in s:
                mix_int_real.append({"question_id": r["question_id"], "col": i})
            if "str" in s and ("int" in s or "float" in s):
                mix_text_num.append({"question_id": r["question_id"], "col": i})
        if r.get("python_set_smaller"):
            py_smaller.append(r["question_id"])
    return {
        "set": set_name,
        "expected_total": expected_total,
        "covered": len(rows),
        "ok": len(ok),
        "timeouts": len(timeouts),
        "timeout_question_ids": timeouts,
        "errors": errors,
        "columns_mixing_int_and_real": mix_int_real,
        "columns_mixing_text_and_number": mix_text_num,
        "golds_where_python_set_merges_types": py_smaller,
    }


if __name__ == "__main__":
    out = {}
    out["minidev_hf"] = summarize("minidev_hf", 500)
    try:
        out["bird_dev"] = summarize("bird_dev", 1534)
    except FileNotFoundError:
        out["bird_dev"] = {
            "set": "bird_dev",
            "expected_total": 1534,
            "covered": 0,
            "note": "not yet run",
        }
    with open(f"{W}/typing_summary.json", "w") as f:
        json.dump(out, f, indent=1)
    for k, v in out.items():
        print(
            k,
            v.get("covered"),
            "/",
            v.get("expected_total"),
            "ok=",
            v.get("ok"),
            "timeouts=",
            v.get("timeouts"),
        )
