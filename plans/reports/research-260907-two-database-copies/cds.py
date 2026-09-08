"""Measure the California CDS joins on both copies and, when supplied, CDE's directory."""

import csv
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DEV = WORK / "data/dev/dev_databases/california_schools/california_schools.sqlite"
MINIDEV = (
    WORK / "data/zip/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite"
)


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    return connection


def one(connection: sqlite3.Connection, statement: str) -> tuple[object, ...]:
    return connection.execute(statement).fetchone()


def internal(path: Path) -> dict:
    connection = connect(path)
    sats_total, sats_13, sats_14 = one(
        connection,
        "select count(*), sum(length(cds) = 13), sum(length(cds) = 14) from satscores",
    )
    sats_school = one(
        connection,
        "select count(*) from satscores as s "
        "where exists (select 1 from schools as h where h.CDSCode = s.cds)",
    )[0]
    frpm_total, frpm_13 = one(
        connection,
        "select count(*), sum(length(CDSCode) = 13) from frpm",
    )
    frpm_school = one(
        connection,
        "select count(*) from frpm as f "
        "where exists (select 1 from schools as h where h.CDSCode = f.CDSCode)",
    )[0]
    frpm_satscores = one(
        connection,
        "select count(*) from frpm as f "
        "where exists (select 1 from satscores as s where s.cds = f.CDSCode)",
    )[0]
    missing = [
        row[0]
        for row in connection.execute(
            "select cds from satscores where length(cds) = 13 order by cds"
        )
    ]
    connection.close()
    return {
        "satscores": {
            "rows": sats_total,
            "thirteen_character_codes": sats_13,
            "fourteen_character_codes": sats_14,
            "join_schools": sats_school,
            "do_not_join_schools": sats_total - sats_school,
        },
        "frpm": {
            "rows": frpm_total,
            "thirteen_character_codes": frpm_13,
            "join_schools": frpm_school,
            "do_not_join_schools": frpm_total - frpm_school,
            "join_satscores_cds": frpm_satscores,
        },
        "satscores_thirteen_character_codes": missing,
    }


def public(path: Path | None, url: str) -> dict:
    result = {
        "landing_url": "https://www.cde.ca.gov/ds/si/ds/pubschls.asp",
        "attempted": True,
        "downloaded": False,
        "reason": "the CDE site answered curl with a Web Application Firewall redirect loop",
    }
    if path is None:
        return result
    data = path.read_bytes()
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    rows = list(reader)
    field = next((name for name in reader.fieldnames or [] if "cds" in name.lower()), None)
    public_codes = {row[field].strip() for row in rows if field and row.get(field)}
    dev = internal(DEV)
    padded = ["0" + code for code in dev["satscores_thirteen_character_codes"]]
    matched = [code for code in padded if code in public_codes]
    result.update(
        {
            "downloaded": True,
            "reason": "",
            "url": url,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "field": field,
            "rows": len(rows),
            "checked_zero_padded_codes": len(padded),
            "matched": len(matched),
            "unmatched": len(padded) - len(matched),
            "unmatched_examples": [code for code in padded if code not in public_codes][:10],
        }
    )
    return result


def main() -> None:
    if len(sys.argv) not in (1, 3):
        raise SystemExit("usage: cds.py [<downloaded.tsv> <download-url>]")
    dev, minidev = internal(DEV), internal(MINIDEV)
    if (
        dev["satscores"]["thirteen_character_codes"] != 211
        or dev["satscores"]["join_schools"] != 2058
        or minidev["satscores"]["thirteen_character_codes"] != 0
        or minidev["satscores"]["fourteen_character_codes"] != 2269
        or minidev["satscores"]["join_schools"] != 2269
        or dev["frpm"]["join_satscores_cds"] - minidev["frpm"]["join_satscores_cds"] != -162
    ):
        raise SystemExit("the internal CDS join counts are not what the earlier finding states")
    document = {
        "reading": (
            "CDS codes are 14 digits. The dev copy lost the leading zero on 211 satscores "
            "rows; those rows do not join schools. Mini-Dev's copy keeps all 14 digits."
        ),
        "dev": dev,
        "minidev": minidev,
        "verdict": "Mini-Dev's california_schools copy carries the codes that join schools",
        "public_directory": public(
            Path(sys.argv[1]) if len(sys.argv) == 3 else None,
            sys.argv[2] if len(sys.argv) == 3 else "",
        ),
    }
    target = WORK / "out" / "cds.json"
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"CDS: dev {dev['satscores']['join_schools']}/"
        f"{dev['satscores']['rows']}, minidev {minidev['satscores']['join_schools']}/"
        f"{minidev['satscores']['rows']}, downloaded "
        f"{document['public_directory']['downloaded']}"
    )


if __name__ == "__main__":
    main()
