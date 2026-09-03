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
|---|---|---|---|
| 02:01 | `bc74ccf` | Mục 2.1: `existing_tables` đọc `pg_catalog` + `has_table_privilege`, trả `TableLookup(present, unreadable)`; summary có `fixture.unreadable_tables`; sandbox thêm bảng `public.sealed` bị REVOKE và câu 900003 | 12 file, +265/-67; test 541 -> 543, sandbox 20 -> 22; gate xanh |

## Còn mở (thấy trong lúc làm, không làm)

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
