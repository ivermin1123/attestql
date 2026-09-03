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
- Chủ cần làm: đọc report, `git push` (15 commit từ `41621c0`, kể cả commit report cuối), quyết mục 2.7
  và ADR-0014.

Status: DONE_WITH_CONCERNS (2.7 không làm được nếu không đảo quyết định thiết kế; ADR-0014 chỉ là
đề xuất; số liệu README đo ở `41621c0`, đo lại ở HEAD lệch đúng q1473 và q707 như trên).
