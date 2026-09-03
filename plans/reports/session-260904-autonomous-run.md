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
