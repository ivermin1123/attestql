<!-- cspell:disable -->
# Báo cáo phiên: nghiên cứu độc lập bốn đề tài, 2026-09-04 15:53 đến 2026-09-05 10:55

Phiên điều phối (Fable), chỉ đọc và đo, không sửa code sản phẩm. Toàn bộ sản phẩm nằm trên nhánh
`research-260904` tại worktree `../attestql-research`, đã rebase lên main `c4eb03d`, chưa push,
chưa merge: 9 commit, 91 file, gate docs, ruff, doc links, ADR index xanh trên cả nhánh.
`just sandbox` không chạy vì không đổi code.

## Sản phẩm

| Commit | Nội dung |
|---|---|
| `4a0381d` | R-C: errata gold đã công bố cho BIRD dev, Mini-Dev, Spider 1.0; ma trận trùng lặp theo id |
| `5544a99` | R-A: cách đọc kết quả của 9 evaluator, 6 cách áp lên 170 hàng EX=1 mà NOT_EQUAL |
| `ff1bf8a` | R-D: SQLite trước khi làm backend: sqlglot, census, evaluator BIRD, storage class |
| `36e8a70` | R-B: mọi GUC và yếu tố môi trường PostgreSQL 16 đổi byte, hàng, thứ tự; đo từng cái |
| `6244dc5` | bỏ mật khẩu throwaway khỏi DSN trong script R-A; libpq đọc `PGPASSWORD` |
| `96a0967` | summary 59 dòng, xếp theo mức lật verdict, ba việc nên làm ngay |
| `8455871` | sửa cách đọc licence SpotIt+ ở N3, U4, đoạn ngữ cảnh ADR-0013, báo cáo mechanism |
| `5c7fd0b` | ghi U4 đã rút và đóng với bình luận đính chính |
| `a99f4fa` | file draft giữ bình luận một dòng như GitHub hiển thị |

Mỗi report dưới 150 dòng, kết thúc bằng mục "What changes in AttestQL", mọi số đo có script và
output trong thư mục cùng tên; script qua ruff check và format vì pre-commit lint cả `plans/`.

## Phát hiện chính

- `work_mem` một mình đổi giá trị 3 trong 9 gold float (q1473, q1476, q1482) dù gather đã tắt;
  chưa ghi, chưa là tiền đề. Provider và version collation (`datlocprovider`, `daticulocale`,
  `datcollversion`, `server_encoding`) chưa ghi; 0/11 gold ORDER BY text đổi trên corpus này.
- `result_eq` của test-suite khác `bird_ex` ở 37/170 hàng (46 % lớp A); Spider 2.0 từ chối
  143/170 chỉ vì multiplicity; 40,6 % của A17 là số tương đối theo `bird_ex`.
- LICENSE của SpotIt+ là modified-BSD có cấp quyền; ADR-0013, N3 và issue U4 đọc sai. Đã đính
  chính trong repo và đóng issue upstream ngày 2026-09-05 (chủ repo ra lệnh "đóng thôi").
- BIRD đã công bố `bird_sql_dev_20251106`: 399/1.534 gold dev viết lại, sửa q1029, giữ q879,
  thay q207. Mini-Dev id là BIRD dev id (496/500 trùng text).
- sqlglot 30.18.0 parse 100 % BIRD dev và Mini-Dev SQLite; libpg_query từ chối 127/45/46, toàn
  bộ do backtick và `LIMIT x,y`; 0/806 cột lưu và 0/2.034 cột kết quả trộn storage class.

## Sự cố và cách xử lý

1. Docker engine kẹt khoảng 17:50, bốn researcher treo (watchdog 600 giây). Khởi động lại Docker
   Desktop (quit mềm thất bại, phải KILL backend), dựng lại container `attestql-research-pg`
   cổng 5499 với `bird`, `bird_c`, `bird_icu`; nối lại từng agent từ file dở dang.
2. Máy thrash (swap 13/14 GB, load 47) do tiến trình quét đĩa của phiên khác; hai agent treo lần
   nữa; nối lại tuần tự với hướng dẫn ghi report theo từng đoạn ngắn.
3. Cache pre-commit bị xoá trước 20:27; khi cài lại hook, git 2.51 + pre-commit 4.6.2 rò
   `GIT_INDEX_FILE` nên index của worktree bị ghi đè bằng checkout `markdownlint-cli2` (796 entry,
   368 object "thiếu" theo fsck). Object store không hỏng; xoá file index của worktree và dựng lại
   từ HEAD; index của checkout main không bị ảnh hưởng.
4. Bình luận đính chính U4 đăng nguyên văn từ draft ngắt 100 cột nên GitHub hiển thị vỡ dòng; sửa
   tại chỗ thành một đoạn (10:54), ghi quy tắc vào memory: văn bản rời khỏi repo không ngắt dòng.

## Dọn dẹp

Container đã xoá, cổng 5499 trống, watchdog Docker đã dừng. Còn lại: worktree
`../attestql-research`, venv `/tmp/attestql-research-venv`, và 3,9 GB dữ liệu tạm trong scratchpad
của phiên (minidev.zip, dump, 11 file SQLite, BIRD dev.zip, kết quả trung gian), xoá được.

## Chưa làm, chờ chủ repo

- `work_mem` trong envelope và ghi thêm collation provider/version (`audit/postgres.py`, A9, A2a).
- `test_suite_ex` cạnh `bird_ex` (`audit/compare.py`), A17 ghi rõ tương đối theo `bird_ex`, câu N2.
- Sửa ADR-0014 theo số đo R-D; quyết định mục tiêu với `bird_sql_dev_20251106`.
- Merge `research-260904` vào main rồi `git worktree remove`.

## Chưa đo được

Drift collation giữa hai host (chỉ một máy); hai thread comment GitHub (hết quota API ẩn danh);
`synchronize_seqscans` dưới tải đồng thời; `jit` trên nền tảng khác arm64.
