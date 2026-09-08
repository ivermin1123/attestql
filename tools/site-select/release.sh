#!/usr/bin/env bash
# The whole of every published run, as one archive per run or group, on the release of the tag
# the audits were made with.
#
#   tools/site-select/release.sh archives           make them and list their digests
#   tools/site-select/release.sh upload <tag>       create the release if there is none, upload
#
# What the site shows of a run is a selection of its questions, chosen against a file and a
# byte budget. This is the rest: every question directory the run wrote, its stdout and its
# stderr with them, so that nothing is lost by the selection and a reader who wants the run
# whole has it.
#
# One archive per run on an engine where one invocation answers a whole question set, and one
# per group where a connection is one database file and a prediction file is eleven runs.
# Built with COPYFILE_DISABLE=1 so that macOS writes no `._*` member, and from inside the work
# directory so that no absolute path is inside one.
#
# The crowded answer a rerun kept beside it is not in an archive: `<name>.under-load` is the
# run the statement bound stopped under three processes, kept in the work directory so that the
# reconciliation can state both, and what is published is the rerun.
set -uo pipefail
RUNS_WORK="${RUNS_WORK:-/tmp/attestql-runs}"
RUNS_WORK="$(cd "$RUNS_WORK" && pwd)"
ASSETS="$RUNS_WORK/assets"
MANIFEST="$RUNS_WORK/assets/manifest.json"
REPOSITORY="${ATTESTQL_REPOSITORY:-ivermin1123/attestql}"

archives() {
  cd "$RUNS_WORK"
  mkdir -p "$ASSETS"
  local benchmark group name path archive
  : > "$ASSETS/SHA256SUMS"
  for benchmark in runs/*/; do
    benchmark="$(basename "$benchmark")"
    for path in "runs/$benchmark"/*/; do
      name="$(basename "$path")"
      case "$name" in *.under-load) continue;; esac
      # A directory holding a summary is a run; one holding runs is a group. Either way it is
      # one archive, because a group is what one prediction file was audited as.
      [ -f "$path/summary.json" ] || [ -n "$(find "$path" -maxdepth 2 -name summary.json -print -quit)" ] || continue
      archive="$ASSETS/$benchmark-$name.tar.gz"
      if [ ! -f "$archive" ]; then
        # Checked, because this script runs without `set -e`: a tar that failed would leave
        # part of an archive or none, and the shasum and the byte count below would then be
        # taken of a file nobody can unpack, or of one that is not there.
        if ! COPYFILE_DISABLE=1 tar --exclude='*.under-load' -czf "$archive" "runs/$benchmark/$name"; then
          rm -f "$archive"
          echo "could not archive runs/$benchmark/$name" >&2
          return 1
        fi
      fi
      ( cd "$ASSETS" && shasum -a 256 "$benchmark-$name.tar.gz" >> SHA256SUMS )
      echo "$(basename "$archive") $(wc -c < "$archive" | tr -d ' ') bytes"
    done
  done
  echo "archives in $ASSETS"
}

# The manifest select.py reads to write each run's published.json: what each asset is called,
# where it is, how large it is and what it hashes to.
manifest() {  # manifest <tag>
  local tag="$1"
  python3 - "$ASSETS" "$tag" "$REPOSITORY" > "$MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

assets, tag, repository = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
found = []
for archive in sorted(assets.glob("*.tar.gz")):
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    found.append(
        {
            "name": archive.name,
            "url": f"https://github.com/{repository}/releases/download/{tag}/{archive.name}",
            "bytes": archive.stat().st_size,
            "sha256": digest,
        }
    )
json.dump({"tag": tag, "assets": found}, sys.stdout, indent=1)
print()
PY
  echo "manifest: $MANIFEST"
}

upload() {  # upload <tag>
  local tag="${1:?the tag the audits were made with}"
  archives
  manifest "$tag"
  ( cd "$ASSETS" && shasum -a 256 ./*.tar.gz > SHA256SUMS )
  gh auth status >/dev/null 2>&1 || { echo "gh is not logged in" >&2; return 1; }
  if ! gh release view "$tag" --repo "$REPOSITORY" >/dev/null 2>&1; then
    gh release create "$tag" --repo "$REPOSITORY" --verify-tag \
      --title "attestql ${tag#v}" --notes-file "$ASSETS/notes.md" || return 1
  fi
  gh release upload "$tag" --repo "$REPOSITORY" --clobber "$ASSETS"/*.tar.gz "$ASSETS/SHA256SUMS"
}

case "${1:-}" in
  archives) archives ;;
  manifest) manifest "${2:?the tag}" ;;
  upload) upload "${2:-}" ;;
  *) sed -n '2,20p' "$0"; exit 2 ;;
esac
