# Making the runs the site publishes

Five audits become 121 runs, a selection of their questions becomes the site's data, and the runs
whole become a release's assets. Each script's header says what that script does; this says the
order they go in, because two of them read what another wrote.

```text
audits.sh            the five audits, into a work directory outside the repository
select_questions.py  which questions the site publishes, copied under tools/site/data/
release.sh           the runs whole as one archive per run or group, on a release
manifest.py          what each archive holds, read by the two below
notes.py             the notes a release created by release.sh carries
question_ids.py      the question ids of one database, which audits.sh passes to --ids
```

## The order, when every run is made again

1. `audits.sh inputs`, then `audits.sh sqlite` and `audits.sh postgres`. A directory holding a
   `summary.json` is a run that finished and is not made again, so an interrupted pass is resumed
   by running the same command.
2. `select_questions.py --dry-run` and read the table. It states what the selection would cost per
   benchmark, and a benchmark with 0 questions there is a benchmark whose run pages would have no
   question page under them. That is what to look at when a new probe fires on many questions.
3. `select_questions.py`, which empties `tools/site/data/` and writes the selection into it. This
   removes every run's `published.json`, because that file names a release asset and the assets for
   these runs do not exist yet.
4. `release.sh archives`, then `release.sh manifest <tag>`.
5. `select_questions.py --published <the manifest>`, which writes each run's `published.json` back.
   Until this runs, the data is a selection whose pages cannot say where the whole run is, and the
   tests that read the published data fail.
6. `uv run python tools/site/build.py`, which prints the file count and the total against the
   budget, and `just check`.
7. Commit the data, tag the release, and `release.sh upload <tag>` once the tag is pushed. The
   release workflow creates the GitHub release for the tag with generated notes, so `upload` finds
   one there and uploads the archives to it; the notes are then worth replacing with something that
   says what the release is.

## What a refresh moves that is easy to miss

A record states the layout it was written under, and a refresh leaves no record on the site written
under an earlier one. `tests/records-from-earlier-releases/` is where the records an earlier release
wrote are kept for the test that needs them; its README says why.

The run archives are named after the run or group they hold, and an asset that is not one of those
is not in the manifest and not in the notes: `release.sh` builds archives out of `runs/` alone, so
a measurement kept elsewhere in the work directory is archived by hand and its digest stated in the
report that rests on it.
