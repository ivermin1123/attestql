#!/usr/bin/env bash
# Fetch only what is absent, verify every digest, and regenerate the measurement.
#
# MEASURE_WORK and ATTESTQL_INPUTS come from the environment. No BIRD file is written inside
# this repository; the fixed hand readings are validated, not replaced by this script.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK}"
: "${ATTESTQL_INPUTS:?set ATTESTQL_INPUTS}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
ATTESTQL_INPUTS="$(cd "$ATTESTQL_INPUTS" && pwd)"
export MEASURE_WORK
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "work directory is inside the repository" >&2; exit 2;; esac
mkdir -p "$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases" "$MEASURE_WORK/data/dev" \
  "$MEASURE_WORK/data/hf" "$MEASURE_WORK/tmp"

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }
fetch() { # fetch <url> <output>
  [ -s "$2" ] && return 0
  for _ in $(seq 1 200); do
    curl -sSL -C - --speed-time 20 --speed-limit 10240 --max-time 600 "$1" -o "$2" && return 0
  done
  return 1
}

DEV_URL="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"
DEV_SHA="cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630"
NEW_URL="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json"
NEW_SHA="ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb"
fetch "$DEV_URL" "$ATTESTQL_INPUTS/dev.zip"
verify "$ATTESTQL_INPUTS/dev.zip" "$DEV_SHA"
[ -s "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json" ] \
  || unzip -p "$ATTESTQL_INPUTS/dev.zip" dev_20240627/dev.json \
       > "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json"
verify "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json" \
  630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06
fetch "$NEW_URL" "$ATTESTQL_INPUTS/dev_20251106.json"
verify "$ATTESTQL_INPUTS/dev_20251106.json" "$NEW_SHA"

DATABASES=(
  california_schools:986817d793479801ed55133e55aa27e335422c0cd3866b54a3d6317b7c5f09c1
  card_games:c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227
  codebase_community:92101be6d2a9f6adceea59d38f6d1c556087f9eea1432432a21268cb1348036d
  debit_card_specializing:b3d149ad05746dbbe5116e229e17e18f09c39db43cf117d9ef3441753608b691
  european_football_2:e4d361dbeec6591a4b315877c0c481da05c8ff5a3d389b34d6e17b6f15bee4e0
  financial:d15d89cdb068a202b6f2b99342af44dffc1d52545b39ceaf62efdc0ba570101e
  formula_1:17185981cd747f6cdc374cb02a6096db3130e6ec2ddc582fe1686a28fb4c4c8a
  student_club:eb89bcfe97eefa386a27904ec5aa15159811a7eac894ec659a36e48fa9f76b77
  superhero:75e94a2c3236ee3bb2c01fb97a1c4b4c1c269bcefd4eab1d04be323d2d0825b1
  thrombosis_prediction:e7e16d74b4731b4b8d33fdbe8c29cd5622620788ce8d1f335631f65fc7cf1db9
  toxicology:f5fa7f21af1ad878ff8fef1b0582b8cb2d7ed63dbac65ff16d2ba05667650c5b
)
unzip -p "$ATTESTQL_INPUTS/dev.zip" dev_20240627/dev_databases.zip > "$MEASURE_WORK/tmp/dev_databases.zip"
for item in "${DATABASES[@]}"; do
  db="${item%%:*}"; want="${item#*:}"
  target="$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases/$db/$db.sqlite"
  mkdir -p "$(dirname "$target")"
  [ -s "$target" ] || unzip -p "$MEASURE_WORK/tmp/dev_databases.zip" "dev_databases/$db/$db.sqlite" > "$target"
  verify "$target" "$want"
done

ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627" "$MEASURE_WORK/data/dev/dev_20240627"
ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases" "$MEASURE_WORK/data/dev/dev_databases"
ln -sfn "$ATTESTQL_INPUTS/dev_20251106.json" "$MEASURE_WORK/data/hf/dev_20251106-00000-of-00001.json"

[ -x "$MEASURE_WORK/venv/bin/attestql" ] || {
  uv venv "$MEASURE_WORK/venv" --python 3.13
  uv pip install --python "$MEASURE_WORK/venv/bin/python" "$repo"
}
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"
python3 "$here/split.py"
python3 "$here/prepare_database.py"
bash "$here/run_rewrites.sh"
bash "$here/rerun_timeouts.sh"
python3 "$here/measure.py"
"$MEASURE_WORK/venv/bin/python" "$here/ast_diff.py"
python3 "$here/crosstab.py"
python3 "$here/sample.py"
python3 "$here/validate_readings.py"
echo "done: $here"
