<!-- cspell:disable -->

# Phiên chạy tự động 2026-09-04 (Asia/Saigon)

Bắt đầu 01:44. Cây xuất phát: `main` = `41621c0` (chưa push). Luật: mỗi việc một commit, `just check`
xanh trước khi commit, không push, không đăng gì lên upstream, không container sót. Worker Opus viết
code, Fable review gối đầu; nghiên cứu mục 3 chạy song song bằng subagent.

## Trạng thái trước phiên

- Mục 1 của prompt (prediction mode trên dự đoán thật) đã xong trước phiên này: `a3bac13`
  (trường nguồn + file dự đoán khóa theo vị trí), `dfb0c96` (SELECT trần không làm sập run),
  `41621c0` (report `measurement-260904-0046-prediction-mode-on-real-predictions.md`, artifact,
  README, register A16 đến A20, NOTICE). Gate lúc đó: 541 test + 20 sandbox.

## Mục 0: upstream (chỉ đọc)

01:45: `gh issue view` trên mini_dev #38 (comment của mình 2026-09-03T17:44:08Z là comment duy
nhất), mini_dev #39, mini_dev #40 và SpotIt-plus #1: cả bốn OPEN, chưa có phản hồi của maintainer.
Không có gì để chép vào register, không commit `docs(register)`.

04:05: đọc lại cả bốn thread (`gh issue view --json state,comments,updatedAt`): vẫn OPEN, updatedAt
không đổi từ 2026-09-03T17:44Z, 0 phản hồi ngoài comment của mình trên #38.

## Commit trong phiên (một dòng mỗi commit: hash, việc, số liệu, giờ)

| Giờ | Hash | Việc | Số liệu |
|---|---|---|--- |
| 02:01 | `bc74ccf` | Mục 2.1: `existing_tables` đọc `pg_catalog` + `has_table_privilege`, trả `TableLookup(present, unreadable)`; summary có `fixture.unreadable_tables`; sandbox thêm bảng `public.sealed` bị REVOKE và câu 900003 | 12 file, +265/-67; test 541 -> 543, sandbox 20 -> 22; gate xanh |
| 02:12 | `64bf96a` | Mục 3: report nghiên cứu `research-260904-next-postgres-targets.md` (92 dòng) + mở run log + 2 từ cspell | 5 tìm kiếm; BIRD-CRITIC pg 390/556 câu parse (70.1 %), flash 144/211; BIRD-Interact, LiveSQLBench 0 gold công khai; Spider 2.0 không có PostgreSQL |
| 02:15 | `efd9d00` | Mục 2.2: mọi lần chạy `SET LOCAL max_parallel_workers_per_gather = 0` + read-back (ReadBackDrift nếu lệch); ghi `server_version`, gather của session; summary có khối `parser` (validator, postgast 0.1.0, grammar 170007) | 9 file, +232/-27; test 543 -> 547, sandbox 22 -> 23; gate xanh; boundary test thêm 1 ngoại lệ đúng đường dẫn cho `importlib.metadata` |
| 02:29 | `e203cf2` | Mục 2.3: khóa advisory cấp session giữ suốt run (`pg_advisory_lock` trước khi tạo bản sao, `pg_advisory_unlock` trong finally của drop, chờ tối đa `LOCK_WAIT_SECONDS = 60` rồi refuse); bỏ `pg_advisory_xact_lock`; README + register A11 và non-claim cập nhật | 5 file, +261/-30; test 547 -> 552, sandbox 23 -> 24; gate xanh |
| 02:41 | `9e4627d` | Mục 2.4: chạy lại cùng `--out` xóa `summary.json` và mọi `q<số>/` của lần trước ngay sau khi tạo thư mục; `fixture.json` giữ nguyên; README + docstring nói thư mục là bằng chứng của một lần chạy | test 552 -> 554, sandbox 24; gate xanh |
| 02:50 | `ab12e79` | Mục 4: ADR-0014 Proposed (SQLite backend sau cùng một evidence record), dòng index, script kiểm kê phụ thuộc PostgreSQL, run log | 115 dòng ADR; 6,498 dòng src trong 21 file, khoảng 220 dòng gọi thẳng PostgreSQL: `postgres.py` 860 + `statements.py` 465 tách, khoảng 4,000 dòng giữ nguyên |
| 02:53 | `8a80e14` | Mục 2.5: cache fixture có tín hiệu nội dung (`content_signal`: relfilenode + n_tup_ins/upd/del + n_live_tup từ `pg_class` và `pg_stat_user_tables`, đo mới mỗi lần chạy, lệch là miss); `CACHE_FORMAT` .../2 | test 554 -> 557, sandbox 24 -> 25; gate xanh |
| 03:05 | `5570b10` | Mục 2.6: giữ và nối `source_file`: cờ `--data-file`, `--data-origin`, `--data-date`; băm một lần mỗi run; summary `fixture.source` (null khi không nêu file); record `source_file_sha256` được điền; ba hàm nhận `source_digest: str` thay vì `Path` | 6 file, +212/-19; gate xanh |
| 03:12 | `0580e49` | Sửa nhỏ sau review 2.6: khóa `fixture.source.sha256` đổi thành `digest` cho giống hai khối `questions`/`predictions` (điều phối tự sửa, 2 file) | test 557 -> 563, sandbox 25; gate xanh |
| 03:46 | `d3d6cb6` | Mục 2.8: tên bảng là cặp (schema, relation) từ parser đến catalogue; sửa 4 lỗi tái hiện được (alias mất schema nên smell đọc `public.y` thay `Quoted.y`; `_qualify` cắt `"a.b"`; hai schema cùng tên bare đè một bản sao scratch; bảng qualified bị khai là shuffle đã phủ); sandbox thêm schema `"Quoted"` + 2 câu | test 563 -> 572, sandbox 25 -> 29; gate xanh |
| 04:02 | `7b2f595` | Mục 2.9: NaN là một giá trị (như PostgreSQL gộp và sắp), định nghĩa ở một chỗ: `typed_value`/`typed_row` trong `evidence/serialize.py`; replay, tie detector, float-order-only dùng chung; `smells._typed` bỏ; ADR-0004 + README ghi luật. Sửa tiền đề brief: `hash(Decimal('NaN'))` không raise trên 3.11/3.13, hai NaN chỉ bị coi là khác nhau (NOT_EQUAL âm thầm) | test 572 -> 583, sandbox 29; gate xanh |
| 04:16 | `0b0da6e` | Mục 2.10: `session_settings` cache trong backend như `identity`, `run_audit` đọc một lần và truyền xuống; gold parse một lần trước khi đo fixture rồi truyền `ParsedStatement` xuống `record_statement`/`compare_statements` (tham số `parsed`, `gold_parsed`, `second_parsed`, `session_settings`); `smells._typed` đã bỏ ở 2.9 | test 583 -> 586, sandbox 29; gate xanh |
| 04:25 | `7c2a5f5` | Đóng run log lần đầu (bảng commit, quyết định, kết thúc) | docs + repocheck xanh |
| 04:15 | `d8ac6c7` | Đo lại toàn bộ mục 1 ở HEAD: artifact `remeasure-at-head/`, register A21 và A22, mục "Đo lại" trong report này | `just check` xanh 586 + 29; commit cuối cùng là bản cập nhật report này |

## Còn mở (thấy trong lúc làm, không làm)

- Mục 2.7 (NOT_COMPARABLE chạm được từ CLI): không tái hiện, bằng chứng: `compare_statements`
  (`src/attestql/audit/compare.py` 356 đến 400) dựng cả hai record từ cùng một `settings`, cùng
  một `fixture` (đo trên hợp của bảng hai câu) và đóng dấu `rule`/`ordering` của gold lên record
  dự đoán; `_incomparable` (`src/attestql/evidence/replay.py` 137 đến 173) chỉ so fixture, năm
  setting phiên, rule, serialization, ordering. Trong một phiên, SET là giao dịch và bị rollback,
  nên không câu SELECT nào trong sandbox đổi được precondition giữa hai lần chạy. Đường duy nhất là
  để record dự đoán khai rule/ordering thật của nó (dự đoán không ORDER BY khi gold có -> R-SET
  vs R-ORD -> NOT_COMPARABLE), tức đảo quyết định "gold quyết định rule" mà số liệu README và
  register A16 đến A20 đang dựa vào. Không tự đảo; chủ quyết: (A) record khai thật, chấp nhận
  đổi số; (B) giữ, và bỏ chữ NOT_COMPARABLE khỏi dòng tổng kết CLI vì không bao giờ xảy ra.
  Chủ chọn B (Phiên 2).

- Smell `not-a-function-of-the-data` đổi giữa hai run cùng input (3/498 câu tại HEAD): plan đổi
  theo thống kê; cân nhắc `ANALYZE` trước khi đo hoặc ghi `last_analyze` vào tín hiệu fixture.
- `float-aggregate-order` giờ hiếm bật vì mọi lần chạy đều gather = 0; nếu muốn tool vẫn cảnh báo
  gold nhạy với cộng song song (đúng cái làm script BIRD lệch), cần một biến thể plan bật gather.
- README vẫn nêu số đo ở `41621c0` (1,240 EX=1); tại HEAD là 1,245/1,246 do q1473; sửa khi phát hành.
- `pyproject.toml` vẫn `version = "0.1.2"`: không tự nâng lên 0.1.3 vì đó là quyết định phát hành
  (kèm tag và PyPI, đều là việc của chủ).

## Quyết định tự đưa (kèm lý do)

- Thứ tự commit theo đúng thứ tự danh sách; worker chạy gối đầu (Opus viết mục N+1 trong khi
  Fable review mục N) thay vì nhiều worktree song song, vì các mục 1, 2, 3, 8, 10 cùng đụng
  `postgres.py` và 3, 4, 6, 7, 10 cùng đụng `cli.py`; chỉ chạy hai worker cùng lúc khi file
  không giao nhau. Lý do: tránh xung đột merge phải giải bằng tay giữa phiên không ai duyệt.
- Dòng report của việc N được ghi ngay sau khi commit N (cần hash), nên nó đi cùng commit của
  việc N+1; lần sửa report cuối cùng là một commit `docs(report)` riêng. Lý do: không amend,
  không commit đôi cho mỗi việc.
- Sandbox của `just check` dùng cổng cố định 5497, nên chỉ một worker chạy gate tại một thời
  điểm; reviewer chỉ đọc nên chạy song song được. Nghiên cứu mục 3 (subagent `researcher`) đã
  khởi động 01:52, song song, không đụng file code.
- Mục 3 khép lại trước mục 2.2 vì subagent nghiên cứu xong sớm; kết luận của nó (BIRD-CRITIC là
  bộ duy nhất có SQL PostgreSQL công khai, gold vẫn phải xin qua email) ghi trong report, không
  gửi email (luật chỉ đọc).
- Report tiếng Việt này đặt `<!-- cspell:disable -->` ở đầu file thay vì sửa `cspell.json`,
  vì gate docs quét toàn bộ `plans/**` và từ tiếng Việt không thuộc từ điển dự án.
- Reviewer cho từng commit là chính phiên điều phối này (đang chạy Fable), đọc diff bằng
  `git show`; không mở worker Fable riêng vì cùng bậc model, tốn thêm mà không thêm mắt.
- Mục 4 (ADR-0014, SQLite) do chính phiên điều phối soạn (việc kiến trúc thuộc Fable theo
  luật routing); số dòng phụ thuộc PostgreSQL đo bằng script commit kèm
  `plans/reports/session-260904-autonomous-run/pg_dependency_inventory.py`. Bài học: file ADR
  chưa link trong `0000-index.md` làm hook pre-commit của worker mục 2.5 từ chối commit (check
  chạy trên cả worktree), nên dòng index được thêm ngay và worker được trả lời để commit lại.
- Mục 2.1: hợp đồng `existing_tables` đổi sang `TableLookup(present, unreadable)` thay vì giữ
  tuple, vì hai nguyên nhân (bảng không có, bảng không được GRANT) sửa ở hai chỗ khác nhau và
  summary phải gọi đúng tên.
- Mục 2.2: gather = 0 đặt cho MỌI lần chạy (gold, dự đoán, shuffle, plan variant) chứ không
  riêng baseline, vì so sánh baseline với rerun song song sẽ đổ lỗi thứ tự cộng cho shuffle.
- Mục 2.3: chờ khóa tối đa 60 giây rồi refuse (shuffle "không chạy"), thay vì chờ vô hạn một
  run khác đang giữ schema.
- Mục 2.5: tín hiệu nội dung là relfilenode + bốn bộ đếm tuple (một câu hỏi catalogue), là bộ
  vô hiệu cache chứ không phải bằng chứng; docstring nói rõ giới hạn (reset stats, tạo lại DB).
- Mục 2.6: giữ `source_file` và nối thành nguồn thứ ba (`--data-file/--data-origin/--data-date`)
  thay vì bỏ, vì chạy trên bản dump lệch là đúng lỗ hổng chủ vừa dính; băm một lần mỗi run
  (phương án A của worker), khóa summary là `digest` cho giống hai khối kia.
- Mục 2.9: luật NaN đặt ở `evidence/serialize.py` (một chỗ cho replay và smells) nên phần
  "`smells._typed` dùng `replay._typed_row`" của 2.10 hoàn thành ngay tại 2.9.
- Mục 2.10: chọn phương án B (backend cache + truyền `session_settings` và `ParsedStatement`
  xuống) để summary và mọi record cùng nêu một đối tượng, thay vì chỉ cache ở backend.

## Đo lại toàn bộ mục 1 ở HEAD (04:00 đến 04:08)

Chạy lại `reproduce.sh` (đã commit ở `41621c0`) với `attestql` ở `7c2a5f5`, cùng dump, cùng
file dự đoán, container mới rồi xóa. Artifact:
`plans/reports/session-260904-autonomous-run/remeasure-at-head/` (`compare-head.txt`,
`aggregate-at-head.json`, `official-flips.json`, `compare_head.py`). Kết quả:

- Số chính giữ nguyên: 170 hàng EX=1 mà NOT_EQUAL, lớp tay 69/74/27, 4 "0 oan", số câu riêng.
- 13 verdict đổi, giải thích hết: q1473 NOT_EQUAL -> EQUAL ở 11 cặp file-gold (mục 2.2: gather = 0
  xóa lệch thứ tự cộng float; EX=1 tăng 1,240 -> 1,245 trên HF, 1,246 trên zip, dòng q1473 biến khỏi
  bảng zip-khác-HF); q707 (meta-llama-3-70b) NOT_EQUAL -> ERROR trên cả hai gold vì plan tuần tự
  vượt statement timeout (lỗi 1,721 -> 1,722). Chủ cân nhắc nâng timeout mặc định hoặc ghi rõ.
- Script chấm của BIRD tự nó không ổn định: chạy hai lần trên cùng server (gather mặc định 2 của
  container), EX của q1473 đổi ở 5/18 cặp (4 lần 1 -> 0, 1 lần 0 -> 1). Đây là bằng chứng trực tiếp
  cho mục 2.2; register A22.
- Smell đổi 49 dòng: `float-aggregate-order` tắt ở 13 chỗ (hệ quả của gather = 0: biến thể plan
  không còn đổi thứ tự cộng); `not-a-function-of-the-data` bật/tắt 8/7 mỗi gold và khác nhau giữa
  hai run cùng input tại HEAD (zip vs zip-by-id: q847, q1482, q1529). Tức smell này phụ thuộc
  thống kê planner (autovacuum/analyze sau khi nạp dump), không phải code. Ghi "còn mở".

## Kết thúc

- Test: 541 + 20 sandbox (trước phiên) -> 586 + 29 sandbox (`0b0da6e`); `just check` xanh ở từng
  commit; không container nào còn chạy (`docker ps` không có container audit); mọi terminal
  worker của phiên đã release.
- Chưa làm: mục 2.7 (xem "Còn mở"); không có việc nào bỏ dở, cây làm việc sạch ngoài report này.
- Chủ cần làm: đọc report, `git push` (18 commit từ `41621c0`, kể cả ba commit bổ sung sau review), quyết mục 2.7
  và ADR-0014.

## Bổ sung sau review của chủ (2026-09-04, sau khi report được đọc)

Reviewer đọc thẳng 15 commit và đưa ba việc, mỗi việc một commit, gate xanh; hai ghi nhận
"không cần làm" của reviewer (main() không gọi backend.close(); khoá advisory tự nhả khi
process kết thúc) được giữ nguyên, không sửa.

| Hash | Việc | Số liệu | Giờ |
|---|---|---|--- |
| `38fb01b` | `_clear_previous_run` chỉ xoá khi `--out` có file đánh dấu `.attestql-run`; thư mục không rỗng, không có marker thì ToolError và không đụng gì; README sửa câu rerun | test 588 + 29 sandbox | 11:31 |
| `f120c01` | Docstring `content_signal` và `fixture.py` nêu cửa sổ pg_stat_user_tables công bố trễ sau commit (UPDATE/DELETE không đổi relfilenode); register thêm một hàng non-claim | test 588 + 29 sandbox | 11:33 |
| commit chứa mục này | README thêm `fixture.unreadable_tables` (cạnh `fixture.missing_tables`, README trước đó không nhắc) và `predictions.positions_unused`; report thêm mục này | test 588 + 29 sandbox | 11:34 |

Sau ba commit này main đi trước `41621c0` 18 commit, chưa push.

## Phiên 2 (2026-09-04 chiều): quyết định của chủ, Batch A trên main, Batch B trên nhánh `sqlite-backend`

Chủ quyết: mục 2.7 theo phương án B (gold quyết định rule, bỏ NOT_COMPARABLE khỏi dòng tổng kết);
ADR-0014 chấp nhận với ba chốt (R-SET so cùng storage class; bird_ex trên SQLite là script chấm
của BIRD nhập nguyên văn; BIRD dev trước, Spider sau). Luật push: main không push; nhánh
`sqlite-backend` push sau mỗi phase để CI chạy.

| Hash | Việc | Số liệu | Giờ |
|---|---|---|--- |
| `8b67992` | A1: bỏ NOT_COMPARABLE khỏi dòng tổng kết; README nêu vì sao trong một run không xảy ra | test 588 + 29 sandbox | 15:50 |
| `ed40955` | Script đo: mở stdout.txt sau khi tool chạy (luật marker mới từ chối thư mục có file lạ) | không đổi test | 15:57 |
| `824e98b` | A3: NOT_EQUAL có lớp cơ chế (multiplicity/type/order/truncation/other) trong counterexample; summary đếm "BIRD cho 1 mà NOT_EQUAL" theo lớp; dòng ERROR nêu bên lỗi (gold/prediction/run) | test 597 + 29 sandbox | 16:03 |
| `f141734` | A2: bird_ex đọc float4/float8 thành float Python như psycopg2 (numeric giữ Decimal); typed verdict không đổi | test 601 + 29 sandbox | 16:10 |
| `cf0b033` | A4: backend.planner_statistics (last_analyze, last_autoanalyze, n_mod_since_analyze) vào evidence của smell shuffle, vào tín hiệu cache (fixture-cache/3) và khối planner_statistics của summary; register thêm non-claim | test 604 + 30 sandbox | 20:02 |
| `6456bc7` | A5: README nêu `--statement-timeout`, timeout trong record và summary có test; giữ mặc định 30 s; artifact `q707-timeouts/` | test 605 + 30 sandbox | 20:07 |
| `1e5927a` | A6: README ghi số đo ở `cf0b033` (4.478/4.482; 1.239; 164 = 138 + 26; 69/74/21); register A16, A17, A19, A23 và header; ghi chú ngày trong report đo; version 0.1.3 (không tag); artifact `remeasure-at-cf0b033/` | test 605 + 30 sandbox | 20:38 |
| commit chứa dòng này | A7: draft upstream thứ năm `plans/reports/upstream-drafts-260904.md` (script chấm BIRD không ổn định ở q1473: 5 lần chạy gold cho 3 giá trị với gather = 2, 1 giá trị với gather = 0; đề xuất SET trong evaluation_utils); chủ gửi | docs | sau A6 |

Quyết định A5 (coordinator, từ số đo): giữ mặc định 30 s. q707: gold 50 ms; prediction của
meta-llama-3-70b 0,22 s khi có 2 worker song song, 41 s (cache ấm) đến 105 s (cache lạnh) khi
chạy tuần tự như tool đang chạy từ `efd9d00`; toàn bộ phép đo ở `7c2a5f5` chỉ có 4/4,482 slot
timeout (q707 và q694, mỗi câu hai gold). Nâng mặc định lên 120 s để cứu 4 slot thì mọi
prediction chạy hỏng của mọi người dùng chờ gấp bốn; dòng ERROR đã nêu bên và record đã ghi
timeout, nên README chỉ cách đặt `--statement-timeout`, q707 là ví dụ. Số đo trong
`plans/reports/session-260904-autonomous-run/q707-timeouts/`.

Đo lại ở `cf0b033` (coordinator, 20:00 đến 21:30; artifact `remeasure-at-cf0b033/`): tool 164 = 138 + 26
"BIRD cho 1 mà NOT_EQUAL" (sáu hàng float8 giờ BIRD-reading = 0), lớp tay 69/74/21, 4 "0 oan" giữ;
khớp script BIRD 4.478/4.482 trên HF (còn lệch: q1473 ×4), 4.473 trên zip (q1473 ×6, q212 ×2, q1476 ×1);
script BIRD tự đổi 10 EX so với lần chấm đã commit (q1473 ×7, q212 ×2, q1476 ×1). Lần chấm đầu chạy 6 file
song song bị bỏ: server hết worker, 110 EX đổi thành cụm id liên tiếp; lần dùng là 3 file song song.
Mục mở mới: q212 gold có `LIMIT 1` trên COUNT hoà trong derived table mà probe cắt tuỳ ý không bật.

Nhánh `sqlite-backend` (Batch B):

| Hash | Việc | Số liệu | Giờ |
|---|---|---|--- |
| `eacc778` | B0: ADR-0014 Accepted với ba chốt; ADR-0004 thêm luật storage class; index | docs; CI <https://github.com/ivermin1123/attestql/actions/runs/33883811118> | 21:24 |
| `930f165` | B1: `ColumnType.declared_type`; `SessionSettings.engine`, năm setting PostgreSQL vắng khi sqlite; version record/summary/counterexample/smells lên 2; bytes canonical không đổi (451 byte, sha256 ef5615ef… ghim bằng test) | test 637 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33943458181> | 11:01 |
| `befbe9e` | B2: ParsedStatement thành protocol (`audit/parse.py`), `PostgresStatement`; `Engine(name, connect, parse, parser)` trong `audit/engines.py`, cờ `--engine`; bằng chứng PostgreSQL không đổi (`b2-postgres-unchanged/`: 501 dòng chỉ lệch q94 do probe shuffle, đối chứng cùng lệch; 30 record giống nhau trừ run_id) | test 659 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33944486978> | 11:24 |
| commit chứa dòng này | Dừng Batch B tại `befbe9e` theo chỉ thị của chủ 11:29 (05/09, chuyển qua session attestql-fa): B3 chưa commit gì, cây sạch, không stash; report `parser-260905-sqlglot-sqlite-reading.md` của worker B3 ghi lại điều đã kiểm (sqlglot 30.18.0 MIT; đọc backtick đúng; token trong dấu nháy kép luôn thành identifier, khác SQLite; ba phương án) | docs | 05/09 12:xx |
| `575d516` | merge main (`f2563db`) vào nhánh; xung đột ở `evidence/types.py`, `evidence/replay.py`, `audit/cli.py`, `audit/compare.py`, `tests/test_replay_equality.py`: giữ dáng của nhánh (engine trước, các setting PostgreSQL cho phép None) và các trường của main (`work_mem`, `hash_mem_multiplier` thành tiền đề; `datlocprovider`, `daticulocale`, `datcollversion`, `server_encoding` được ghi) | test 685 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33947729860> | 12:38 |
| `5484ff5` | B0': ADR-0014 sửa theo R-D: sqlglot 100 % parse (1.534 và 500+500), libpg_query từ chối 127/45/46 toàn backtick hoặc `LIMIT offset, count`, 0/806 cột lưu và 0/2.034 cột kết quả trộn storage class, chín setting phiên SQLite được ghi, `PRAGMA query_only = 1` là bao ngoài và `mode=ro` là bảo đảm mức file, phương án 2 cho token trong nháy kép; register thêm dòng A26 | docs; test 685 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33947914832> | 12:42 |
| `a2a32ce` | B1': một khối SessionSettings cho cả hai engine (engine, bảy tiền đề PostgreSQL có thể vắng, recorded bắt buộc; SQLite ghi chín khoá); không đổi layout nên không bump version | test 687 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33948157031> | 12:48 |
| `62d224d` | B3a: backend SQLite (`audit/sqlite.py`) và parser sqlglot 30.18.0 (`audit/sqlite_statements.py`) sau cùng một bản ghi bằng chứng; engine `sqlite` trong registry, `--engine sqlite --dsn <file>`; REAL thành Decimal ngắn nhất round-trip, cột kết quả mang lớp lưu trữ quan sát được, BLOB bị từ chối; `mode=ro` + `PRAGMA query_only` đọc lại trước mỗi câu; bản sao xáo trộn là bảng TEMP trên kết nối thứ hai; cách đọc bird_ex chọn theo engine | test 778 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33949327275> | 13:15 |
| `7a8e3fd` | Khoá ORDER BY trong nháy kép: parse chỉ nêu tên (`unresolved_ordering_keys`), nơi có backend phân giải theo cột của các bảng câu lệnh đọc, chỉ từ chối khoá không trỏ cột nào; giữ được gold BIRD đúng mà vẫn chặn cách đọc sai; ADR-0014 (Context 4, Decision 3) và report parser sửa theo | test 782 + 30 sandbox; CI <https://github.com/ivermin1123/attestql/actions/runs/33949606380> | 13:21 |
| `c803934` | B3b: sandbox SQLite không container (`tools/audit-sandbox-sqlite/`, ba lỗi gold từ chính file SQLite của Mini-Dev, group_concat thay cho sum float); `just check` chạy cả hai sandbox; README, NOTICE, register A27 | test 800 + 30 sandbox + 11 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/33950199069> | 13:34 |
| `73ec41d` | B4: năm probe chạy trên SQLite; tập kiểu cộng phụ thuộc thứ tự do backend trả lời (PostgreSQL float4/float8, SQLite rỗng vì Kahan-Babuska-Neumaier từ 3.43.0, đo 28.000 multiset); NULL mặc định đứng đầu dưới ASC do parse điền; README, ADR-0014, register A28 | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/33951172921> | 13:56 |
| (không commit) | Máy khởi động lại 06/09 ~09:00, macOS xoá /private/tmp: lần đo B5 thứ nhất (114/220 run, 20 tiến trình song song, load 61, 19 timeout gold giả) và worker mất; đo lại từ đầu, dữ liệu và venv để ở `~/.cache/attestql-measure`, cap 3 tiến trình | | |
| `d640be1` | B5: đo lại Mini-Dev trên SQLite, 220 run (2 bản gold x 10 x 11 database) + 27 run gold sửa, cap 3 tiến trình, không container; 40 run có dòng timeout, chạy lại đơn lẻ giữ nguyên cả 40 (gold q518, q701 quá 30 s thật). HF: 3.501 so sánh, 1.650 EX=1, 981 lỗi, khớp evaluator BIRD 4.481/4.482 (chỗ lệch duy nhất q31 do REAL làm tròn 6 chữ số); 237/1.650 (14,4 %) EX=1 mà NOT_EQUAL (230 bội, 6 lớp lưu trữ, 1 thứ tự), mẫu 50 tay: 27 A / 22 B / 1 C. Gold-only 25 smell trên 20 gold (PostgreSQL 39 trên 29), 19 câu lệch giữa hai engine; report + artifact + register A29-A33 + README + NOTICE | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/34088637798> | 12:55 |
| `9c8b38c` | B5b: report SQLite về 118 dòng, danh sách id chuyển sang `differences.json`, hàng B5 ghi hash và CI thật | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/34089573285> | 13:09 |
| `6a43c01` | B5c: report wrap lại 100 cột, 119 dòng, giữ mọi bảng và số | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/34090142899> | 13:17 |
| `1f1feb6` | B6': BIRD dev 1.534 câu trên SQLite, hai bản gold (dev.json 2024-06-27 và bản rà 2025-11-06 của BIRD), 22 run gold-only + 44 run dự đoán, cap 3 tiến trình; 18/66 run có dòng timeout, chạy lại đơn lẻ giữ nguyên cả 18 (q518 38 s, q701 192 s, và bản viết lại của q1131 quá 30 s trong khi bản 2024 chạy 0,3 s). Số dẫn: **probe bắt 31/399 gold BIRD tự sửa (7,8 %)**, gấp ba mức nền 25/963 (2,6 %) trên gold BIRD không đụng, và 29 trong 31 tắt khi bản 2025-11-06 thay bản 2024. 25 gold BIRD để nguyên mà probe kêu: đọc tay cả 25, 23 sai / 1 vô hại / 1 luật của tool. Prediction mode trên hai file dự đoán dev của chính BIRD (DAMO-ConvAI, MIT): khớp evaluator dev của BIRD 6.136/6.136, 90/899 (10,0 %) EX=1 mà NOT_EQUAL. Phát hiện thêm: 5 trong 11 database khác nhau giữa `dev.zip` và `minidev.zip`, không tài liệu nào nói. Report + artifact + register A34-A38 + README | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/34096837188> | 14:42 |
| `f115a65` | B6'b: hàng B6' trong run report ghi hash và CI thật | test 807 + 30 sandbox + 17 sandbox_sqlite; CI <https://github.com/ivermin1123/attestql/actions/runs/34097167059> | 14:46 |

Điểm dừng Batch B (05/09): B0, B1, B2 đã lên nhánh `sqlite-backend` và CI xanh; B3 dừng trước khi
commit theo chỉ thị mới của chủ (làm C0 đến C5 trên `main` trước, rồi B0', B1', B2 đến B5, B6'). Brief B2
và B3 nằm trong scratchpad của phiên (`specs/batch-b2.md`, `specs/batch-b3.md`); đầu vào cho B5/B6
(11 database SQLite của Mini-Dev, 9 file dự đoán SQLite, BIRD dev.zip 346 MB) đã tải về scratchpad.
Quyết định tự đưa: dừng theo chỉ thị chuyển qua session khác vì dừng là đảo được, còn hai session cùng
sửa một checkout thì không.

Kết thúc Batch B (07/09, 11:00 đến 16:00, session này, worker Opus viết, Fable duyệt): nhánh
`sqlite-backend` từ `c4eb03d` (main lúc tách) đến `f115a65`, 17 commit, CI xanh từng commit; test 605 + 30
sandbox lúc tách thành 807 + 30 sandbox + 17 sandbox_sqlite. Không merge vào main, không push main, không
đăng gì upstream. Đọc lại bốn thread upstream (chỉ đọc, 07/09 12:00): `mini_dev` #38, #39, #40 mở, chưa ai
trả lời; SpotIt-plus #1 chủ đã đóng 05/09. Không container sót, không tiến trình sót; Docker Desktop đang
chạy (worker bật cho gate). Thư mục đo `~/.cache/attestql-measure/minidev-sqlite` (6,7 GB) và
`bird-dev-sqlite` (4,1 GB) để lại, xoá được. Chờ chủ quyết: (1) merge `sqlite-backend` vào main và push;
(2) REAL render sáu chữ số thập phân làm q31 EQUAL trong khi BIRD cho 0 (hằng serialize dùng chung với
PostgreSQL, đổi là đổi mọi digest); (3) timeout không được đếm trong dòng tổng kết và `summary.json`, ba
gold BIRD dev (q518, q701, q1131 bản 2025) quá 30 s; (4) file dự đoán BIRD dev ghi số 0 cho câu thiếu và
tool từ chối cả file; (5) 5/11 database của dev.zip khác minidev.zip (A38, 211 mã CDS mất số 0 đầu); (6)
q879 vẫn sai trong bản dev 2025-11-06, q207 sửa join nhưng thêm `LIMIT` ngoài `GROUP_CONCAT`: chỉ ghi,
không gửi. Status Batch B: DONE (B0', B1', B2 đến B5, B6' đủ; B5 đo hai lần vì máy khởi động lại).

Status: DONE_WITH_CONCERNS (2.7 không làm được nếu không đảo quyết định thiết kế; ADR-0014 chỉ là
đề xuất; số liệu README đo ở `41621c0`, đo lại ở HEAD lệch đúng q1473 và q707 như trên).

## Phiên 3 (2026-09-05, 11:29 đến 12:45): merge nghiên cứu, C0 đến C5 trên main

Lệnh chủ 11:29: dừng Batch B, làm C0 đến C5 trên main, B tiếp tục trên `sqlite-backend` sau khi
merge main vào. Lệnh đến phiên điều phối nghiên cứu (`attestql-fa`); phiên Batch B (`attestql-c5`,
Orca run `run_17d55b8a90b4`) dừng B ở `8bd168f` (đã push; B1 và B2 hoàn tất; worker B3 dừng trước
khi commit; không có stash) và giữ B: sau khi main có tag, `c5` merge main vào `sqlite-backend` làm
bước đầu của B1'. C làm trong worktree `../attestql-research` chuyển sang main (checkout chính đang
ở `sqlite-backend`), C3 trong worktree `../attestql-c3` để hai worker Opus không đụng file; cả hai
worktree gỡ sau khi tag, nhánh `research-260904` giữ, nhánh `c3-test-suite-ex` xoá.

| Giờ | Hash | Việc | Số liệu |
|---|---|---|--- |
| 11:33 | `2ded756` | C0: merge `research-260904` (`--no-ff`, không squash); không xung đột vì nhánh đã rebase lên `c4eb03d` tối 04/09 | gate docs và repocheck xanh |
| 12:02 | `160e905` | C1: envelope giữ `work_mem = '4MB'` và `hash_mem_multiplier = 2` cạnh gather = 0, read-back trong giao dịch, hai giá trị thành tiền đề (bảy tiền đề); ADR-0013 điểm 6 ghi chú ngày; A9, A2a; chứng minh trên 9 gold float dưới role 4MB và role 64kB: 9/9 EQUAL, cùng `result_hash` và bytes; control không envelope lệch 3/9 (q1473, q1476, q1482) | test 605 -> 613, sandbox 30; artifact `work-mem-precondition/` |
| 12:06 | `7b91a3f` | C2: `datlocprovider`, `daticulocale` (đọc hàng `pg_database` dạng JSON nên chịu cả `datlocale` của PG17), `datcollversion`, `server_encoding` vào recorded, không chặn; A2a; hàng non-claim drift collation | test 617, sandbox 30 |
| 12:08 | `0963374` | C3: `test_suite_ex` cạnh `bird_ex` (multiset, dung hoán vị cột, giữ thứ tự khi gold có ORDER BY, không strip DISTINCT, ô đọc như psycopg2); `summary.json` có `by_test_suite_ex`; A17 thêm vế tương đối `bird_ex`, N2 thêm câu bốn hệ thống, A24; cherry-pick từ `c3-test-suite-ex` | test 625, sandbox 30; worker đối chiếu vi sai 40.000 cặp với `exec_eval.py` gốc, 0 lệch; full gate ở commit này xanh |
| 12:09 | `ceaa598` | C4: draft 5 thêm đoạn `work_mem` (459.95626421124274 ở 4MB, 459.956264211243 ở 64kB, gather = 0), đề xuất ba SET; body mỗi đoạn một dòng | docs |
| 12:45 | commit chứa mục này | C5: đo lại toàn bộ bằng `reproduce.sh` tại `0963374` (12:09 đến 12:26, cổng 5498, container xoá); README và register ghi số; A25; A24 có số | artifact `remeasure-at-0963374/` |

Số đo lại tại `0963374`, so với run đã commit ở `41621c0`: 25 move giống hệt lần đo ở `cf0b033`;
164 = 138 + 26 hàng "BIRD cho 1 mà NOT_EQUAL" trên cả hai gold; lớp tay 69/74/21; 52 câu riêng; 4
"0 oan" giữ. Tool và script BIRD khớp 4.476/4.482 (HF) và 4.479 (zip); toàn bộ bất đồng là q1473
(9 cặp), script BIRD tự lệch 4 cặp so với lần chấm đã commit, còn verdict và bytes q1473 của tool
giống nhau ở mọi cặp. `test_suite_ex`: từ chối 138/164 (đúng 138 hàng multiplicity), nhận 26 hàng
type; trên 170 cặp của R-A: 144 bị từ chối (A 64, B 74, C 6) so với 37 khi R-A strip DISTINCT rồi
chạy lại. Tức phần strip DISTINCT mới là thứ làm test-suite tha hàng trùng, không phải luật multiset.

Quyết định tự đưa: C chạy trong worktree research thay vì checkout chính (`c5` đang giữ), gỡ
worktree sau C5 thay vì ngay sau C0; merge `--no-ff` để lịch sử có điểm merge; hai worker Opus song
song, worker C3 bỏ sandbox (cổng 5497 do worker C1 dùng) và điều phối chạy full gate ở `0963374`;
không nâng format version khi thêm khoá (tiền lệ `824e98b`, `a3bac13`; `record_hash` đổi nhưng
không có test ghim); draft 5 body một dòng mỗi đoạn (bài học U4); hàng non-claim glibc 2.28 có link
wiki PostgreSQL. Sau commit này: push main, CI, tag `v0.1.3`, báo `c5`, gỡ hai worktree, xoá
container `attestql-research-pg` (cổng 5499).

Chưa làm, chờ chủ: gửi draft 5 (chủ đăng); B0', B1', B2 đến B6' do `c5` tiếp tục; drift collation
giữa hai host chưa đo.

## Review fixes before the merge, 2026-09-07

Ten review findings on `sqlite-backend`, one commit each, `just check` green before every commit
and the branch pushed after each. Tests before: 807 passed and 30 skipped under `just test`, 30
under `just sandbox`, 17 under `just sandbox-sqlite`. After: 821 passed and 30 skipped, both
sandboxes unchanged at 30 and 17. No measurement was rerun and no PostgreSQL number moved.

| Hash | What it did |
|---|---|
| `c4447f6` | S1: the SQLite file URI percent-escapes the path, so a `?`, `#` or `%` in it no longer ends the filename early and drops `mode=ro`; `urllib.parse` granted to that one module by exact path in the boundary test |
| `57ed9ed` | S2: the two credential refusals on `--dsn` move onto the engine record, so they are asked of PostgreSQL alone and a SQLite path holding `password` or `://` is accepted; the empty value is still refused for either engine |
| `782f669` | S3: `summary.json` states where the shuffled copies were made, read off a new `Backend.scratch` property (the schema on PostgreSQL, `temp` on SQLite) instead of echoing `--scratch-schema` |
| `58bb53c` | S4: `prepare_shuffled_copies` asks which names the file holds before counting rows, so one missing table is reported under `NOT_IN_THIS_FILE` and the others are still copied |
| `37c59c3` | S5: identifiers are folded over the ASCII letters through one helper beside the backend protocol, so `STRASSE` no longer resolves to a column or table named `straße` |
| `0cf0b6a` | S6: only SQLite's `interrupted` is reported as the statement timeout; every other driver error keeps the engine's own message however far the clock has moved |
| `1ef9d44` | S7: whether a declaration is text is the backend's answer, so SQLite applies the affinity rule (CHAR, CLOB, TEXT) and `VARCHAR(50)` fires `ordering-over-numeric-text`; PostgreSQL still matches its three catalogue names whole |
| `44d47d0` | S8: a test that `SELECT load_extension(...)` is refused when it runs, and one README sentence saying extension loading is never enabled |
| `85ffb26` | S9: the R-ORD and R-SET asymmetry over one pair of numbers recorded as a non-claim and as an ADR-0004 amendment; the README sentence about Mini-Dev q31 names the rule and the rendering |
| `bcd3c73` | S10: version `0.1.3` to `0.2.0` with `uv lock`, because two `feat!` commits behind this branch changed the record layout; no tag cut |

Decisions taken here: `urllib.parse` is permitted in `audit/sqlite.py` alone, with the positive
test the other exact-path permissions of `tests/test_boundary.py` carry, because the URI is how
`mode=ro` is stated and `urllib.request` stays forbidden; the `--dsn` rule became a field on
`Engine` rather than a branch on the engine name in `cli.py`, which that module's own rule forbids;
`PostgresBackend.scratch_schema` was renamed `scratch` so both engines answer the protocol under
one name (`connect(scratch_schema=...)` unchanged). Still open, seen while reading and not touched:
the register's non-claim "Any engine but PostgreSQL" still reads "nothing is built".
