# Draft: correction to `ai-ar-research/SpotIt-plus` issue 1 (U4), for the owner to post

<!-- cspell:ignore atremante ivermin -->

Written 2026-09-04 by the coordinating session; not posted. ADR-0013 point 9: sessions draft,
the owner reviews and files under their own identity. Evidence: the raw LICENSE of the
repository (only commit `fbf5460`, 2026-02-15, unchanged at HEAD `abee2ba`, sha256 `687ee88a…`),
re-read from both URLs, which are one repository (`atremante26/SpotItPlus` redirects). Its first
sentence reserves all rights; its second paragraph grants study, modification and redistribution
under the modified-BSD text reproduced below it. Issue 1 says the file "grants nothing", which is
wrong, and the issue is open with no reply as of 2026-09-04 21:25 (Asia/Saigon).

## Comment text

```text
Correction from the reporter: I misread the LICENSE file, sorry for the noise. Its first
sentence reserves all rights, but the paragraph that follows grants the right to study, modify
and redistribute the code under the modified BSD licence reproduced below it (commit fbf5460,
unchanged). So the file does state a licence, and my question is answered by the file itself.
Closing. If you want to spare other readers the same misreading, a `license` field in the package
metadata pointing at that file would make it explicit.
```

## How to post, as the owner

Both URLs are one repository; the issue lives under `ai-ar-research/SpotIt-plus`. The personal
account is the one that opened it.

```text
gh auth switch -u ivermin1123
gh auth status
gh issue close 1 --repo ai-ar-research/SpotIt-plus --comment "$(sed -n '/^```text$/,/^```$/p' plans/reports/upstream-260904-2125-u4-licence-correction.md | sed '1d;$d')"
```

Then record the date in `docs/claims-register.md`, row U4, under "Replies received".
