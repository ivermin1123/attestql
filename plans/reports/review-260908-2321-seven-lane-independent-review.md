<!-- cspell:disable -->
# Review độc lập AttestQL bởi bảy lane Codex, 2026-09-08 23:21

**Đã xử lý từ báo cáo này, tính tới 2026-09-10:** toàn bộ Nhóm A trong action plan
(commit `6b40707` tới `075bbbe`, cộng phần cấu hình repo trên GitHub), và `LOGIC-01`
ở commit `1eea1c2`. Phần còn lại của Nhóm B và toàn bộ Nhóm C vẫn đúng như viết dưới
đây. Báo cáo giữ nguyên nội dung của ngày nó mang.

Review độc lập bởi bảy agent Codex chạy trên GLM song song trong Orca run `run_b2c2824c3333`. Mỗi lane đóng vai reviewer chưa từng thấy codebase, đọc code thật và chạy lệnh lấy bằng chứng, không sửa một file nào trong repo. Sau đó Claude tự mở lại từng dòng được trích để xác nhận, tự chạy lại các reproduction quan trọng, hạ hoặc giữ severity, và loại bỏ những gì không chứng minh được.

Trích dẫn số dòng trong báo cáo này tính theo commit `511822c`, tức bản phát hành 0.3.0. Cần lưu ý: anh commit 12 lần vào `main` trong lúc review chạy, chạm 9 file nguồn mà báo cáo trích, nên tôi đã chạy lại toàn bộ reproduction và dò lại từng số dòng. Không finding nào biến mất, chỉ số dòng dịch.

**Ba lỗi High ở mục 3 hiện đã nằm trong bản 0.3.0 trên PyPI.** Commit phát hành chỉ chạm `pyproject.toml` và claims register, nên `LOGIC-01`, `LOGIC-02` và `LOGIC-03` đi nguyên vào bản mà người dùng cài được từ hôm nay.

## Tóm tắt

Repo này ở trạng thái tốt hơn phần lớn dự án open source cùng quy mô. Gate `just check` xanh trong 35.51 giây và bao trọn lint, pyright strict, 1,087 test, sandbox PostgreSQL trên Docker và sandbox SQLite. Demo trong README khớp byte-for-byte với output thật. Hàng rào chặn SQL độc hại, cách ly engine và escaping HTML đều được chứng minh bằng reproduction chứ không phải bằng lời. `LICENSE` khớp byte-for-byte với văn bản Apache-2.0 chính thức.

Ba vấn đề lớn nhất:

1. **Một giá trị số hợp lệ làm sập cả run.** `Decimal('1E+100')` ném `InvalidOperation` không ai bắt, giết audit giữa chừng, thoát 1 với traceback và không ghi `summary.json`.
2. **Ghi công giấy phép thiếu ở hai nơi.** Gold SQL của Spider 1.0 dev nằm nguyên văn trong repo nhưng `NOTICE` không nhắc Spider lần nào, trong khi chính claims register ghi nguồn đó là CC BY-SA 4.0. Và không trang nào trong 673 trang của site công khai nêu tên bộ dữ liệu hay giấy phép, dù site chính là nơi phân phối lại rộng nhất.
3. **NaN trong R-SET thành ERROR thay vì verdict.** So sánh trả EQUAL rồi bước băm kết quả từ chối số không hữu hạn, trái với chính điều ADR-0004 quy định.

Kế đó là một báo động giả có thể tái hiện trong probe `arbitrary-cut` trên SQLite, một công cụ maintainer xoá đệ quy thư mục tuỳ ý, và một lời hứa trong README bị chính tài liệu tham chiếu phá: sáu flag có thật không được mô tả ở đâu cả.

Điểm yếu nhất không nằm trong code mà ở vận hành open source. Nhánh `main` không có bảo vệ nào, không có kênh báo lỗi bảo mật riêng, không có Dependabot, và bảy GitHub Action đều ghim theo tag di động trong khi workflow phát hành đang giữ quyền publish lên PyPI.

## Bảng đếm finding theo severity

Số sau khi verify, tức đã hạ severity ở những chỗ bằng chứng chỉ chạm tới đường maintainer chứ không phải đường sản phẩm.

| Lane | Phạm vi | Critical | High | Medium | Low | Nit | Tổng |
|---|---|---|---|---|---|---|---|
| L1 | audit core (mục 1, 2, 3) | 0 | 3 | 3 | 7 | 0 | 13 |
| L2 | CLI và evidence (mục 1, 2, 3) | 0 | 1 | 4 | 8 | 1 | 14 |
| L3 | renderer, site, tools (mục 1, 2, 3) | 0 | 0 | 5 | 6 | 0 | 11 |
| L4 | docs đối chiếu code, test, perf (mục 4, 7, 8) | 0 | 1 | 5 | 5 | 0 | 11 |
| L5 | security, deps, CI, metadata (mục 6, 9, 13, 14) | 0 | 0 | 4 | 13 | 1 | 18 |
| L6 | hygiene, legal, docs, khác (mục 10, 11, 12, 15) | 0 | 2 | 4 | 9 | 7 | 22 |
| L7 | UI/UX (mục 5) | 0 | 0 | 3 | 4 | 0 | 7 |
| **Tổng** | | **0** | **7** | **28** | **52** | **9** | **96** |

Không có Critical nào sống sót qua verify. Codex gắn nhãn Critical cho ba finding; cả ba đều là vấn đề thật nhưng tôi hạ xuống Medium hoặc chuyển sang nhóm chờ anh quyết, lý do ghi ngay tại từng dòng.

**Kết quả verify: 95 finding đứng vững, 1 bị bác một phần, 0 finding nào tôi phải loại hoàn toàn.** Tôi hạ severity 11 finding, không nâng cái nào, và bổ sung 1 finding mà bảy lane bỏ sót. Chỗ bị bác nằm trong LEGAL-01: L6 cho rằng 21 file prediction của bên thứ ba được chép nguyên vào repo, nhưng tôi mở cả 42 file ở thư mục đó và không file nào chứa một câu SELECT; chúng chỉ giữ kết quả đo.

## Mục 1: Code quality

Lint sạch trên toàn bộ scope: `ruff check`, `ruff format --check` và `pyright` strict đều thoát 0 ở cả ba lane. Không có TODO, FIXME, XXX, print debug, breakpoint hay code bị comment lại nào trong `src` và `tools`. `vulture --min-confidence 80` không báo dead code.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| CQ-L1-01 | Low | `src/attestql/audit/engines.py:103` | `"password" in target.lower()` từ chối mọi DSN chứa chuỗi này, nên `dbname=password_history` bị chặn dù không mang credential. | Parse danh sách keyword libpq và chỉ từ chối khoá `password`; vẫn từ chối mọi dạng URI trước khi parse. | S |
| CQ-L2-01 | Low | `src/attestql/audit/cli.py` (1,998 dòng) | Một module gộp argument grammar, validation, orchestration, vòng đời thư mục output, schema summary, demo và report. `_summary_json` 143 dòng, `build_parser` 169. | Tách theo ranh giới sẵn có thành `cli/parser.py`, `cli/inputs.py`, `cli/run.py`, `cli/summary.py`, giữ `main` làm facade. | M |
| CQ-L3-01 | Low | `src/attestql/report/render.py` (1,865 dòng), `tools/site/build.py` (1,109 dòng) | Cùng loại với trên: một module gánh nhiều trục thay đổi khác nhau. Hàm dài nhất 79 dòng nên chưa tới mức khó đọc. | Tách renderer theo ranh giới sẵn có, giữ `render_report` làm facade công khai. | M |
| CQ-L3-02 | Low | `tools/site/build.py:1103`, `tools/site-select/select.py:950-954`, `src/attestql/report/render.py:1763-1767` | Ba bản sao gần giống của cùng một hàm đọc số nguyên từ JSON, nhưng chỉ bản trong site builder từ chối số âm. Selector có thể ghi một count âm mà site builder sau đó từ chối. | Đưa một hàm parse count không âm dùng chung, giữ nguyên message riêng của từng caller. | S |
| CQ-L2-02 | Low | `src/attestql/audit/cli.py:1608`, `src/attestql/__init__.py:1`, `pyproject.toml:8` | Mô tả subcommand nói "against one PostgreSQL database" trong khi `--engine {postgresql,sqlite}` tồn tại. Chuỗi này còn là description của package trên PyPI và là câu mở đầu của trang chủ attestql.com. | Sửa một câu ở ba nơi thành "against one PostgreSQL or SQLite database". | S |
| CQ-L2-03 | Low | `src/attestql/audit/cli.py` (31 lần `cast(`), `src/attestql/evidence/render.py:34` | `Json = dict[str, Any]` và 31 cast đẩy giả định về JSON dị dạng ra sau assertion thay vì chứng minh tại biên. Đây là nơi vài lỗi loader đã lọt qua. | Định nghĩa alias JSON đệ quy và narrow bằng helper trả về view đã có kiểu. | M |
| CQ-L3-03 | Low | `tools/site/build.py:20`, `tools/site/README.md:49-51` | Docstring của `--help` vẫn nói `tools/site/data/` rỗng và mọi trang mang banner sandbox, trong khi repo đã publish 121 run và banner không còn xuất hiện. README ngay bên cạnh nói đúng. | Viết lại docstring theo hành vi có điều kiện hiện tại. | S |
| CQ-L3-04 | Low | `tools/report-stress/build.py:340-342` so với `:379-386` và `:234-237` | Comment khẳng định hàng dữ liệu thêm nằm ở bảng không câu hỏi nào đọc, nhưng nó được chèn vào `sequence`, đúng bảng mà câu NOT_COMPARABLE đọc. | Sửa comment cho đúng cơ chế: fixture digest khác nhau nên so sánh bị từ chối trước khi tới kết quả. | S |
| CQ-L3-05 | Low | `tools/site-select/select.py`, `tools/site-select/manifest.py:67-70` | Tên file trùng module `select` của thư viện chuẩn. Repo đã phải mang hai chỗ giải thích cách né va chạm này, và test dữ liệu site từ chối import script vì lý do đó. | Đổi tên thành `select_questions.py` và cập nhật ba chỗ gọi. Mở khoá luôn cho TEST-01 bên dưới. | S |
| CQ-L2-04 | Nit | `src/attestql/contract/__init__.py:1` | Docstring liệt kê "metric registry, schema" mà ADR-0013 đã xoá; package chỉ còn `clock.py`. | Sửa câu docstring. | S |

## Mục 2: Architecture

Ranh giới kiến trúc là thật và có test canh: `src/attestql/report` không import engine, đồ thị import không có chu trình, hai backend nằm sau cùng một protocol. Site builder tách khỏi report renderer là đúng chứ không phải trùng lặp, vì nó còn chạy demo SQLite và đọc hằng số method từ module engine.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| ARCH-01 | Low | `src/attestql/audit/backend.py:100`, `src/attestql/audit/cli.py` | `Backend` mở kết nối server và file nhưng không có `close` và `connect_and_audit` không giải phóng trong `finally`. CLI sống sót nhờ process thoát; test fixture để lại 86 ResourceWarning. | Thêm `Backend.close()` cho cả hai engine, dùng context manager trong `connect_and_audit`, cho fixture test `yield` rồi đóng. | S |
| ARCH-02 | Low | `src/attestql/audit/engines.py:120` | `Engine` mang `parser` tách rời khỏi `parse`, không gì bảo đảm hai thứ khớp nhau, đúng thứ drift mà docstring của chính nó nói phải không bao giờ xảy ra. | Kiểm tra tại lúc dựng registry rằng `engine.parse("SELECT 1").parser == engine.parser`. | S |
| ARCH-03 | Low | `src/attestql/kernel/ports.py`, `src/attestql/audit/compare.py:684-688` | `QueryExecutor`, `SqlValidator` và `ExecutionContext` không nằm trên đường audit. Code gọi `admit()` sau khi đã chạy statement, với một width proof mà docstring của chính nó nói "không phải là width proof". ADR-0013 đã tuyên bố `kernel/` nằm ngoài đường sản phẩm. | Cần chủ repo quyết: bỏ hẳn cụm port và nghi thức admit, hay giữ như legacy có tài liệu. | L |

## Mục 3: Thuật toán và logic

Đây là nơi tập trung mọi finding nghiêm trọng. Mỗi finding dưới đây đều có reproduction chạy được, không có cái nào suy đoán.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| LOGIC-01 | High | `src/attestql/evidence/serialize.py:162` | Precision được đặt theo số chữ số có nghĩa thay vì theo số mũ, nên `Decimal('1E+100')` ném `InvalidOperation`, và `sided()` không bắt exception này. Một câu `SELECT 1e100` hợp lệ giết cả run, thoát 1 kèm traceback, không ghi summary. Tôi chạy lại: `1E+16` render đúng, `1E+100` và `9.99E+100` ném exception. | Tính precision theo `value.adjusted()`, và bọc lỗi `quantize` thành `UnsupportedValue` để nó thành ERROR một câu hỏi thay vì sập run. | S |
| LOGIC-02 | High | `src/attestql/audit/compare.py:935-936`, `src/attestql/evidence/serialize.py:156` | Cả hai kết quả bị băm cho mọi rule, mà bước băm từ chối số không hữu hạn. Một kết quả R-SET chứa NaN vì thế thành ERROR thay vì nhận verdict, trong khi ADR-0004:110-116 chỉ nói R-ORD mới "không có byte để so sánh". Đây là đường sản phẩm vì cột float PostgreSQL đi qua `NumericFromFloatText`. | Cho digest một biểu diễn nhận biết kiểu cho sentinel không hữu hạn, hoặc tách khoá so sánh khỏi rendering của record. | M |
| LOGIC-03 | High | `src/attestql/audit/sqlite_statements.py:179-208`, `src/attestql/audit/smells.py:510` | Rewrite giữ DISTINCT rồi thêm khoá ORDER BY vào select list. Trên SQLite điều đó nới grain khử trùng lặp, nên `arbitrary-cut` báo động giả trên một kết quả đã chứa đủ mọi hàng distinct. Reproduction: `SELECT DISTINCT x FROM t ORDER BY y LIMIT 2` trả 2 hàng, bản rewrite trả 3, smell bắn `tie-at-the-cut`. Test hiện có chỉ phủ trường hợp khoá đã nằm trong projection. | Chỉ thêm khoá khi statement gốc đã project một biểu thức tương đương; nếu không thì đánh dấu smell không áp dụng kèm lý do. | M |
| LOGIC-04 | Medium | `src/attestql/audit/postgres.py:241`, `:521` | Bảng không nêu schema được đo và quy về `public`, nhưng envelope thực thi không đặt `search_path`, nên statement lại resolve theo search_path mà session tình cờ đang có. Fixture digest có thể mô tả `public.results` trong khi cả gold lẫn prediction đọc `other.results`. Giảm nhẹ: `search_path` có nằm trong `RECORDED_SETTINGS` nên người đọc record thấy được. `execute_shuffled` đã pin đúng cách. | Thêm `SET LOCAL search_path` vào envelope và đọc lại cùng các setting khác. Lưu ý điều này đổi session settings mà mọi record ghi ra. | M |
| LOGIC-05 | Medium | `src/attestql/audit/smells.py:480`, `:614` | `applicable=False` chỉ khi chưa hề chuẩn bị bản sao xáo trộn. Khi đã có bản sao nhưng không bảng nào của statement này được phủ, rerun vẫn chạy trên bảng gốc và báo `applicable=True`, EQUAL. Đúng thứ mà contract của `Backend` nói smell không được làm. | Tính giao giữa bảng của statement và bảng đã sao chép; rỗng thì trả không áp dụng và không chạy rerun. | S |
| LOGIC-06 | Medium | `src/attestql/report/render.py:929`, `:1669` | Hàng trên trang index chỉ đến từ thư mục câu hỏi cộng danh sách `errors`; id trong summary không bao giờ được đối chiếu. Một audit hỏng một phần render ra báo cáo trông đầy đủ, nêu đúng tổng số câu đã audit nhưng thiếu hẳn câu bị mất. Reproduction xoá `q879` khỏi demo: render ra 5 câu trong khi summary nói 6. | Đối chiếu id của summary với thư mục cộng id lỗi, và từ chối khoảng trống không giải thích được. | M |
| LOGIC-07 | Medium | `src/attestql/report/render.py:656` so với `:697` | Rerun xoá trang, summary, thư mục câu hỏi, static và filter, nhưng không xoá `classification.json` và `classification-source.json` đã copy lần trước. Bằng chứng phân loại thủ công cũ đọng lại trong output đã publish. | Thêm hai tên file vào vòng dọn dẹp và cập nhật `MARKER_TEXT`. | S |
| LOGIC-08 | Medium | `src/attestql/audit/cli.py:652` | Với keying theo question id, prediction có id không tồn tại trong file câu hỏi bị bỏ im lặng. `positions_unused` chỉ dùng cho keying theo vị trí. Một lỗi gõ trong id cho ra kết quả GOLD-ONLY mà người vận hành tưởng đã audit prediction. | Từ chối id lạ trước khi chạy, hoặc thêm `ids_unused` vào summary và đếm nó trên dòng tổng kết. | S |
| LOGIC-09 | Medium | `tools/site-select/select.py:210` và `:664` | `--out` đi thẳng vào `_clear()` xoá đệ quy mọi thứ trừ `README.md`, không chốt chặn repo, không marker sở hữu, và đi theo symlink. Reproduction xoá được file `keep/irreplaceable.txt`. Codex gắn Critical; tôi hạ xuống Medium vì đây là công cụ maintainer và giá trị mặc định của `--out` an toàn. | Resolve `--out`, từ chối repo và mọi thư mục tổ tiên, và chỉ ghi vào thư mục rỗng hoặc thư mục mang marker riêng, theo đúng cách site builder đã làm. | S |
| LOGIC-10 | Medium | `tools/site-select/audits.sh:28`, `:194`, `:206`, `:209` | Script đặt `set -uo pipefail` không có `-e`, giới hạn job bằng `wait -n` rồi vứt trạng thái bằng `wait` trần. Mọi audit hỏng vẫn in `SQLITE_DONE` và thoát 0. Reproduction: 0 summary được ghi, exit vẫn 0. Comment ở `:176-177` còn nói hỗ trợ bash 3.2 trong khi `wait -n` cần 4.3. | Bắt PID từng job và `wait "$pid"`, cộng dồn trạng thái hỏng, và thay `wait -n` bằng cách chia lô tương thích. | M |
| LOGIC-11 | Medium | `tools/site-select/release.sh:76-77` | Lệnh tạo release luôn truyền `--notes-file "$ASSETS/notes.md"` nhưng không đường code nào tạo file đó. `git grep` chỉ ra đúng một lần xuất hiện. Hiện chưa nổ vì release v0.2.2 đã tồn tại nên nhánh tạo mới bị bỏ qua; tag mới tiếp theo sẽ hỏng. | Sinh notes từ manifest và truyền `--notes`, hoặc tạo và kiểm tra file trước khi gọi; đồng thời kiểm tra mã trả về của `archives` và `manifest`. | S |
| LOGIC-12 | Low | `src/attestql/audit/cli.py:481`, `src/attestql/evidence/render.py:72` | Id câu hỏi là số nguyên không giới hạn, thành tên thư mục `q<id>`, và `write_json` gọi `mkdir` không kiểm tra độ dài tên. Một id 300 chữ số cho traceback `OSError` và thoát 1, trong khi README:80 và `docs/audit-command.md:97` hứa thoát 2 cho lỗi công cụ. | Từ chối id ngoài khoảng hợp lệ của BIRD trước khi mở backend, và chuyển lỗi ghi output muộn thành `ToolError`. | S |
| LOGIC-13 | Low | `src/attestql/audit/cli.py:481` | Các trường bị ép kiểu thay vì từ chối: JSON `true` thành id 1, `null` thành chuỗi `"None"`. Input dị dạng được audit dưới một danh tính sai. | Yêu cầu đúng `int` cho `question_id` và đúng `str` cho các trường còn lại, báo `ToolError` kèm tên trường. | S |
| LOGIC-14 | Low | `src/attestql/audit/cli.py:163` | Id âm được chấp nhận và ghi vào `q-1`, nhưng regex dọn dẹp là `q\d+` nên rerun không xoá thư mục đó, phá đúng cam kết "một thư mục là một run" ở `docs/audit-command.md:123-125`. | Từ chối id âm, hoặc thay việc nhận diện theo tên bằng manifest các file mà run này đã ghi. | S |
| LOGIC-15 | Low | `src/attestql/audit/fixture.py:138` | Cache được khoá theo schema digest vừa đo, nhưng giá trị trả về lấy từ trường `schema_digest` trong file cache. Một `fixture.json` bị sửa tay khiến mọi record mới khai một danh tính fixture sai, tức một điều kiện tiên quyết của replay. | Trả về giá trị vừa đo thay vì giá trị đọc từ cache. | S |
| LOGIC-16 | Low | `src/attestql/evidence/render.py:72`, `src/attestql/audit/fixture.py:175` | Ghi thẳng vào đường dẫn cuối, không temp file rồi rename. Một lần ngắt giữa chừng để lại thư mục câu hỏi dở dang mà không có summary. Marker rerun sẽ dọn ở lần chạy sau, nên rủi ro là người đọc tin vào một thư mục dở. | Ghi ra file tạm rồi `os.replace`, và chuyển lỗi ghi thành `ToolError` ở mức run. | M |
| LOGIC-17 | Low | `src/attestql/evidence/render.py:127` | `_multiset` khoá theo `(tag, value)` chứ không qua `typed_row`, nên hai hàng NaN được đếm là khác nhau. Chỉ lộ ra sau khi LOGIC-02 được sửa. | Đổi sang `Counter(typed_row(row) for row in rows)`. | S |
| LOGIC-18 | Low | `src/attestql/audit/sqlite.py:924` | `except BackendRefused: return False` biến mọi lỗi, kể cả database hỏng, thành kết luận "quan hệ không có rowid", làm giảm độ phủ probe một cách im lặng. | Chỉ coi lỗi "no such column: rowid" là kết quả view hoặc WITHOUT ROWID; ném lại phần còn lại. | S |
| LOGIC-19 | Low | `src/attestql/audit/sqlite.py:1117` | Khôi phục `automatic_index = 1` cứng thay vì trả về giá trị trước đó, và pragma này không nằm trong `RECORDED_PRAGMAS`. Chỉ khác biệt trên build không dùng mặc định. | Đọc và lưu giá trị hiện tại, khôi phục đúng nó, và ghi pragma này vào record. | S |
| LOGIC-20 | Low | `tools/audit-sandbox/run.sh:47-53` | Chốt chặn "output phải nằm ngoài repo" dùng `cd && pwd` nên là đường dẫn logic; một symlink trỏ ngược vào repo vượt qua được. `render.py:618-620` cùng loại kiểm tra thì dùng `Path.resolve()`. | Đổi sang `cd -P` và từ chối khi `out` chính là symlink. | S |
| LOGIC-21 | Low | `src/attestql/audit/compare.py:481-521` | Tìm kiếm hoán vị cột được cắt tỉa bằng tập giá trị nên bình thường rất nhanh, nhưng một kết quả rộng bệnh lý với các cột trùng tập giá trị vẫn là giai thừa. Đây là bản mô phỏng có chủ ý của evaluator tham chiếu. | Cần chủ repo quyết, vì đặt ngân sách node sẽ đổi độ trung thực với evaluator gốc. | M |
| LOGIC-22 | Cần quyết | `src/attestql/audit/statements.py:150`, `docs/adr/0004...md:25-26` | Quy tắc gán R-ORD là cú pháp thuần: có ORDER BY ở cấp cao nhất thì là R-ORD. `docs/audit-command.md:163` mô tả đúng như vậy, nhưng ADR-0004 lại đòi "total deterministic ordering with ties broken by a unique key". Một gold có ORDER BY bị hoà sẽ cho NOT_EQUAL với mechanism `order`. Đây là điều repo đã ghi nhận là "documented non-claim". | Hai lựa chọn cho chủ repo: sửa lời văn ADR-0004 cho khớp quy tắc cú pháp, hoặc đo tính toàn phần của thứ tự và ghi một outcome riêng. Tôi nghiêng về phương án đầu trước mắt. | M |

## Mục 4: Tính năng đối chiếu README và docs

Đối chiếu từng khẳng định trong README, `docs/audit-command.md`, `docs/claims-register.md`, bốn ADR và hai README của site với code thật. Demo trong README khớp byte-for-byte: 830 byte, `cmp` thoát 0. Các claim A1 đến A4, A11, A13, A14, A20, A24, A39, A40 khớp với code và test được trích dẫn. Các claim còn lại là đo đạc có ngày tháng trên dữ liệu BIRD và Spider bên ngoài nên lane không chạy lại.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| FEAT-01 | High | `docs/audit-command.md:4-5` | Trang này tự nhận là tài liệu tham chiếu cho mọi flag, nhưng `--plan-variant`, `--shuffle-seed`, `--shuffle-row-limit` và `--data-as-of` không xuất hiện ở bất kỳ đâu trong README hay docs, còn `--fixture-digest` chỉ có trong một ADR. CLI định nghĩa 23 flag. | Thêm mục tham chiếu cho từng flag còn thiếu kèm giá trị mặc định và khác biệt giữa hai engine. | S |
| FEAT-02 | Medium | `docs/audit-command.md:102-103` | Tài liệu nói mọi `audit/q<id>/` chứa bốn file, nhưng một câu gold-only chỉ ghi `evidence-gold.json` và `smells.json`. Kiểm chứng trên demo: `q900001` có hai file, `q879` có bốn. | Sửa tài liệu: thư mục có so sánh chứa bốn file, thư mục gold-only chứa hai. Không nên bịa record thứ hai. | S |
| FEAT-03 | Medium | `docs/audit-command.md:97` so với `src/attestql/audit/cli.py:1336` | Tài liệu nói "chỉ một run không trả lời câu nào mới thoát 2", nhưng một file câu hỏi rỗng thoát 0. Code cố ý như vậy và nói rõ trong docstring. Exit code là hợp đồng cho automation. | Sửa tài liệu cho khớp code, vì hành vi hiện tại là quyết định có chủ đích. Đổi exit code là lựa chọn khác và thuộc nhóm đổi hành vi. | S |
| FEAT-04 | Medium | `docs/audit-command.md:110-115` so với `src/attestql/audit/cli.py:925` | Tài liệu liệt kê năm cơ chế trên dòng tổng kết gồm cả `other`, code chỉ in bốn. Khi một ca `other` xuất hiện, tổng trên dòng đó lớn hơn tổng các thành phần hiển thị. | Hoặc in thêm `other`, hoặc nói rõ trong tài liệu rằng `other` chỉ có trong `summary.json`. Phương án đầu đổi khối output mà README trích nguyên văn. | S |
| FEAT-05 | Low | `docs/adr/0003...md:59`, `docs/adr/0014...md:62-63` | Hai ADR vẫn ở trạng thái Accepted và nói đồng hồ cố định là trường bắt buộc của evidence record, trong khi ADR-0013 đã bỏ trường đó và `record.py:8-15` xác nhận. `docs/adr/0000-index.md:21` còn nói "ba ADR được giữ" trong khi bảng có bốn dòng. | Thêm ghi chú bị thay thế một phần vào ADR-0003 và ADR-0014, sửa câu đếm trong index. | S |
| FEAT-06 | Low | `docs/developer-environment.md:83-84`, `:119-120` | Tài liệu nêu hai file test không còn tồn tại và nói `just check` kết thúc ở pytest, trong khi `justfile:58` còn chạy tiếp hai sandbox. Người mới không biết Docker và cổng 5497 nằm trong merge gate. | Cập nhật mục 5 theo recipe hiện tại và viết lại mục 3 thành phần lịch sử. | S |

## Mục 5: UI/UX của site công khai và báo cáo cục bộ

Kiểm bằng cách build thật: site ra 673 trang HTML, báo cáo demo ra 13 trang. Những phần đạt: mọi trang có viewport meta, chỉ có breakpoint 768 và 1280 đúng chủ đích, bảng rộng và SQL dài đều nằm trong vùng cuộn riêng, 11,532 ô tiêu đề bảng đều có `scope`, mỗi trang đúng một `h1` và không nhảy cấp, SVG sinh ra có `role="img"` kèm `title`, focus ring rõ, có nhánh `prefers-reduced-motion`, `html-validate` thoát 0, và trình duyệt kiểm 686 trang không có link nội bộ gãy. Ba phông tự host tổng cộng 60,788 byte, dùng `font-display: swap`.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| UI-01 | Medium | `src/attestql/report/templates/base.html:22`, `tools/site/build.py:775-793` | Toàn bộ 673 trang đã deploy chỉ có charset, viewport, title và stylesheet trong `head`. Không description, không canonical, không thẻ mạng xã hội, và bản build không có `robots.txt`, `sitemap.xml`, `404.html` hay favicon. Trang gốc `site/index.html` có sẵn description tốt nhưng không được deploy. | Thêm description và canonical theo từng trang vào model trang, phát sinh bốn file kia, và thêm thẻ Open Graph cho trang landing, method và run. | M |
| UI-02 | Medium | `src/attestql/report/render.py:427` | Title trang câu hỏi chỉ là id cộng verdict, nên cùng một câu hỏi dưới nhiều prediction run có title trùng nhau. Đo trên bản build: 673 trang, 584 title duy nhất, riêng `q1435 NOT_EQUAL` lặp 17 lần. | Đưa benchmark và tên nhóm prediction vào title, giữ độ dài dưới khoảng 60 ký tự. | M |
| UI-03 | Medium | `src/attestql/report/templates/_record.html:30`, `tools/site/build.py:138` | Toàn bộ kết quả của record được nhúng thẳng vào mỗi trang câu hỏi. Hai trang `q1088` nặng 1,806 KB với 16,616 thẻ hàng. Ngân sách 2 MiB mỗi trang vẫn đạt và nén còn 38 KB, nên vấn đề là kích thước DOM chứ không phải băng thông. | Render một phần xem trước có giới hạn trong khối gấp, và liên kết tới file JSON bằng chứng đã copy sẵn. | L |
| UI-04 | Low | `src/attestql/report/templates/question.html:133`, `run.html:115-130` | Trên site, trang câu hỏi chỉ liên kết tới run của nó, và trang run không có đường lên nhóm hay benchmark. Trang group và benchmark thì đã có. Người vào từ link chia sẻ mất ngữ cảnh. | Thêm một breadcrumb tuỳ chọn vào model trang run và để trống với báo cáo cục bộ. | M |
| UI-05 | Low | `src/attestql/report/templates/_index.html:21` | Báo cáo không có câu hỏi nào render ra `tbody` rỗng, không có câu trạng thái rỗng, trong khi bảng hàng bên cạnh đã có sẵn dòng `no rows`. | Thêm nhánh `{% else %}` in một dòng "no questions". | S |
| UI-06 | Low | `_strip.html:22`, `static/report.js:22` | Khi tắt JavaScript, chip cơ chế vẫn là nút bật được nhưng không có handler và không có trạng thái `aria-pressed`. Phần còn lại của báo cáo suy biến tốt vì mọi nội dung đều render sẵn. | Đặt `aria-pressed` trong markup ban đầu và ẩn chip bằng `noscript`. | S |
| UI-07 | Low | `pyproject.toml:8`, `tools/site/build.py:751` | Câu mở đầu trang chủ lấy từ description của package nên chỉ nói PostgreSQL, trong khi chính site đó publish 99 run SQLite. | Sửa description để nêu cả hai engine. Cùng một chuỗi với CQ-L2-02. | S |

## Mục 6: Security

Không có secret nào trong cây làm việc và trong lịch sử. `gitleaks` quét 150 commit và báo 4 hit, tất cả đều là trường JSON `"keys"` mô tả hình dạng báo cáo, không phải khoá. Tôi tự xác nhận ba lớp hàng rào chặn SQL độc hại: parser chỉ chấp nhận đúng một SELECT, PostgreSQL chạy trong `BEGIN READ ONLY` với statement timeout và login sandbox chỉ có `GRANT SELECT` cùng `default_transaction_read_only = on`, SQLite mở file bằng `mode=ro` kèm `PRAGMA query_only`. Lane chạy chín prediction độc hại thật trên SQLite: `DROP`, `ATTACH`, `load_extension`, đa câu lệnh, `PRAGMA` ghi, `writefile` và `readfile` đều bị từ chối, hash fixture không đổi, không file nào được tạo trong `/tmp`. DSN không lọt vào record, summary hay report. Traversal đường dẫn bất khả thi vì id là số nguyên. Jinja bật autoescape với `StrictUndefined`, chỉ một chỗ dùng `|safe` và nội dung đó do `figures.py` sinh ra với escape đầy đủ.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| SEC-01 | Medium | 18 dòng `uses:` trong `.github/workflows/` | Cả 7 action đều ghim theo tag di động chứ không theo commit SHA, kể cả trong workflow phát hành đang giữ `id-token: write`. Một tag bị trỏ lại biến rò rỉ token thành một lần publish PyPI bị đầu độc. | Ghim từng action theo SHA đầy đủ, để lại version trong comment cho Dependabot cập nhật. | S |
| SEC-02 | Low | `.github/workflows/site.yml:58`, `justfile:7-8` | Ba công cụ Node được tải lúc chạy qua `npx --yes`, có ghim version nhưng không lockfile và không integrity hash, trong đó wrangler chạy trong job đang giữ token Cloudflare. | Cần chủ repo quyết, vì thêm lockfile Node vào một repo Python là chi phí thật. | M |
| SEC-03 | Low | `.github/workflows/ci.yml`, `release.yml` job check và build | Không khai `permissions:`, nên dựa vào mặc định của repo. Tôi kiểm tra: mặc định hiện là `read`, nên đây là phòng thủ theo chiều sâu chứ không phải lỗ hổng. | Thêm `permissions: contents: read` ở cấp workflow. | S |
| SEC-04 | Cần quyết | `.github/workflows/site.yml:55` | Bước deploy in ra độ dài token sau khi cắt khoảng trắng. Chính anh vừa thêm dòng này lúc 21:52 hôm nay ở commit `90c8176`, sau khi phép kiểm tra hình dạng chặn nhầm token 53 ký tự. Tôi không đề xuất revert một quyết định mới ra. | Nếu muốn kín hơn thì chỉ in trạng thái có hoặc không có, và để Cloudflare tự từ chối token sai. | S |

## Mục 7: Tests

Gate chạy đủ và xanh: `just check` hết 35.51 giây với 1,087 test qua, 33 test sandbox PostgreSQL qua trên Docker, 105 test sandbox SQLite qua. Toàn bộ 33 test bị skip trong lần chạy thường đều skip vì đúng một lý do đã ghi rõ. Lane kiểm tra tính thật của test bằng năm phép thử xoá tính năng và cả năm đều làm test đỏ. Coverage 94% được đo một lần làm thông tin, không phải để đề xuất thành gate. CI chạy `just check` trên Python 3.11 và 3.13, nên sandbox Docker nằm trong merge gate chứ không chỉ chạy cục bộ.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| TEST-01 | Medium | `tools/site-select/select.py`, `manifest.py`, `question_ids.py` | Ba script quyết định nội dung publish lên attestql.com và nội dung release asset đều không có test trực tiếp nào. Test dữ liệu site cố ý không import script vì tên trùng thư viện chuẩn. | Đổi tên module theo CQ-L3-05 rồi thêm test cho các hàm chọn thuần, cho phần đọc manifest và cho việc trích id. | M |

## Mục 8: Performance

Đo thật chứ không suy đoán: demo chạy 0.41 giây, audit fixture SQLite 0.31 giây, render báo cáo 0.35 giây, build site 5.10 giây cho 2,218 file. Một kết quả 200,000 hàng audit hết 3.23 giây. Không có cache toàn cục hay `lru_cache` nào rò rỉ. Một statement PostgreSQL tốn chín lượt round trip cho envelope, không có EXPLAIN thừa. Gold được parse một lần cho cả run.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| PERF-01 | Medium | `src/attestql/audit/postgres.py:528`, `src/attestql/audit/sqlite.py:1137`, `src/attestql/evidence/render.py:235` | Cả hai backend `fetchall` toàn bộ, `truncated` luôn là false, và record giữ mọi hàng. Một prediction `SELECT *` trên bảng lớn làm bộ nhớ tăng theo cỡ kết quả mà không có ERROR ở mức câu hỏi. | Cần chủ repo quyết, vì bất biến "không cắt xén im lặng" là quyết định thiết kế trong ADR-0013; đặt ngân sách hàng sẽ đổi hành vi. | L |
| PERF-02 | Low | `src/attestql/evidence/replay.py:264`, `src/attestql/audit/compare.py:935-936`, `src/attestql/evidence/render.py:270` | Với R-ORD, mỗi kết quả bị serialize một lần cho verdict rồi băm lại cho Comparison, và băm lần ba khi ghi record. Chi phí thực đo được là vừa phải. | Tính digest một lần rồi tái sử dụng. | M |
| PERF-03 | Low | `src/attestql/audit/compare.py:829` và `:897`, `src/attestql/audit/postgres.py:433` | Vai trò database được đọc lại bằng `SELECT current_user` cho từng record và từng so sánh, dù `cli.py:849` đã đọc một lần và vai trò không thể đổi trong một kết nối. Trên server ở xa, chi phí này nhân với số câu hỏi. | Truyền vai trò đã đọc vào, hoặc cache trên backend theo vòng đời kết nối. | S |

## Mục 9: Dependencies

Lockfile nhất quán: `uv lock --check` thoát 0. Không có dependency thừa và không thiếu khai báo: quét AST toàn bộ `src`, `tools`, `tests` chỉ ra đúng năm thư viện bên ngoài và cả năm đều đã khai báo. `pip-audit` không tìm thấy lỗ hổng đã biết. Ba công cụ Node được ghim đều có 0 advisory. Chiến lược ghim được biện luận đúng: ghim tuyệt đối hai parser vì chúng quyết định replay rule, để khoảng cho driver và template engine vì chúng không quyết định record nào.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| DEP-01 | Low | `uv.lock`, `.github/dependabot.yml` không tồn tại | Bảy gói lạc hậu, gồm psycopg 3.3.4 lên 3.3.5 và ruff 0.16.4 lên 0.16.6, và không cơ chế nào nhắc cập nhật. | Thêm cấu hình Dependabot ở CI-01 và merge các bản vá đang chờ. | S |
| DEP-02 | Low | `.github/workflows/ci.yml:18`, `justfile:7-8`, `site.yml:58` | `astral-sh/setup-uv@v7` trong khi bản mới nhất là v10.0.1, tức chậm ba major; cspell 10.1.1 so với 10.3.0; wrangler 4.129.0 so với 4.129.1. | Nâng setup-uv trong cùng đợt ghim SHA, và để Dependabot lo phần còn lại. | S |
| DEP-03 | Low | `.pre-commit-config.yaml:14`, `pyproject.toml:90` | Hook pre-commit ghim `v0.16.4` còn dev group chỉ đặt sàn `ruff>=0.16.4`. Hôm nay hai bên trùng nhau do may mắn; lần `uv lock --upgrade` đầu tiên sẽ tách chúng ra và người đóng góp sẽ qua hook nhưng đỏ gate. | Ghim tuyệt đối `ruff==0.16.4` trong dev group, hoặc thêm một test so hai giá trị. | S |
| DEP-04 | Low | `pyproject.toml:20`, `.github/workflows/ci.yml:15` | Package quảng cáo hỗ trợ Python 3.12 nhưng CI chỉ chạy 3.11 và 3.13. Một hồi quy chỉ xảy ra trên 3.12 sẽ phát hành dưới một classifier mà người dùng PyPI tin. | Thêm 3.12 vào ma trận, hoặc bỏ classifier đó. | S |

## Mục 10: Repo hygiene

Không có rác kinh điển nào bị track: không `node_modules`, không `dist`, không `build`, không `.env`, không `.DS_Store`, không `.pyc`, không log, không cache, không database lạc. Line ending đồng nhất, không file nào CRLF hay lẫn lộn, không BOM, mọi file text đều UTF-8, không thư mục rỗng. Khoảng trắng cuối dòng chỉ còn đúng một dòng và nó nằm trong `OFL.txt`, tức văn bản giấy phép bên thứ ba không được sửa. Khoảng trống trong đánh số ADR đã được `docs/adr/0000-index.md` giải thích.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| HYG-01 | Medium | `plans/` (1,489 file, 53.6 MB), `tools/site/data/` (1,653 file, 23.1 MB), `.git` 55 MB | Trong 3,277 file được track chỉ khoảng 135 là source, config và docs; phần còn lại là dữ liệu đo và dữ liệu publish, trong đó có một file 11.1 MB. Mỗi người clone tải 55 MB, và tìm kiếm code trên GitHub lọt thỏm giữa hàng nghìn file JSON. Một commit publish dữ liệu chạm hàng trăm file, ví dụ `245ce84` chạm 1,526 file. | Tách hai cây ra mà quyết riêng. `tools/site/data/` có lý do chính đáng để ở lại vì workflow build site chạy thẳng từ checkout và tài liệu nói build không chạm mạng. Với `plans/`, cách rẻ nhất là cắt: giữ báo cáo dạng văn bản và các summary nhỏ, bỏ track output thô và file 11.1 MB vốn đã có script tái tạo. | M |
| HYG-02 | Medium | `.gitignore`, `README.md:11` | `.gitignore` không có `demo/` và `*.sqlite`, trong khi lệnh mở đầu README chính là `attestql demo --out demo` và nó ghi ra một file SQLite cùng hàng chục file JSON ngay tại gốc repo. Cũng thiếu `.DS_Store`, `.idea/`, `.vscode/`, `node_modules/`, `.coverage`, `htmlcov/`. Ngược lại `.mypy_cache/` còn nằm đó dù `docs/developer-environment.md:40` đã bác mypy dứt khoát. Tôi tự xác nhận `demo/` và `.coverage` không được ignore. | Thay khối hiện tại bằng danh sách tường minh; L6 đã soạn sẵn nội dung đầy đủ. Bỏ `.mypy_cache/`, giữ `.claude/worktrees/` và `.wrangler/`. | S |
| HYG-03 | Low | `site/index.html`, `tools/site/build.py:89`, `.github/workflows/site.yml` | Có hai trang chủ viết tay. Workflow deploy bản dựng từ `tools/site/`, còn trang gốc `site/index.html` không được phục vụ nữa nhưng vẫn bị build đọc làm nguồn liên kết. Xoá nó thì build từ chối chạy, sửa tay thì nó trôi khỏi trang thật. | Chuyển ba đích liên kết vào template của landing rồi ngừng đọc trang gốc, và xoá nó khi đã chắc attestql.com phục vụ bản dựng. | S |
| HYG-04 | Low | `plans/reports/**` (997 file), tổng cộng 1,001 file | Đường dẫn tuyệt đối `/Users/hoangle/...` xuất hiện trong 1,001 file được track, hầu hết trong trường `backend_identity` của các summary. Điều này công bố bố cục máy cá nhân hàng nghìn lần và trái với chính chính sách repo tự đặt ra trong `tools/site/README.md`, nơi nói sandbox dùng đường dẫn cố định để "không nêu tên người dùng, repo hay vị trí build". Tôi xác nhận: 997 file dưới `plans/reports`, 0 file dưới `tools/site/data`, 0 file trong `src`, `tools`, `docs`. | Với đo đạc về sau, chạy từ một gốc trung tính như site tooling đang làm. Với dữ liệu đã track, hoặc để nguyên như lịch sử bất biến, hoặc chuẩn hoá tiền tố đường dẫn trong một lần chạy script nếu các báo cáo được sinh lại. | M |
| HYG-05 | Low | `refs/heads/*`, `refs/tags/*` | Cả ba nhánh ngoài `main` đều đã merge hết và không còn việc: `research-260904`, `sqlite-backend` và `ivermin1123/web-ui`, cùng `origin/ivermin1123/web-ui`. Tag không nhất quán về kiểu: v0.1.1 đến v0.2.0 là annotated, còn v0.2.1 và v0.2.2 là lightweight nên không mang tagger, ngày hay message. Tôi xác nhận cả hai. | Xoá ba nhánh sau khi gỡ worktree web-ui, và chọn một kiểu tag rồi ghi vào tài liệu phát hành. Annotated là mặc định tốt hơn cho release. | S |
| HYG-06 | Nit | git history, `tests/`, `tools/` | Không tài liệu nào ghi quy ước đặt tên, nên các phong cách đang trôi: test phần lớn đặt tên thành câu nhưng có bốn ngoại lệ ngắn, `tools/` trộn thư mục kebab-case với script snake_case, và tiêu đề commit dài, 113 trên 160 vượt 72 ký tự cùng vài loại ngoài chuẩn. | Thêm mục "Conventions" vào CONTRIBUTING.md. | S |
| HYG-07 | Nit | `plans/reports/**`, `src/attestql/report/static/fonts/` | Có file kết thúc không có dòng trống cuối, trái `.editorconfig`. L6 đếm 48; tôi đếm lại được 119, gồm 115 file JSON đo đạc do script ghi, ba phông woff2 nhị phân và `OFL.txt`. Nghĩa là không file nguồn văn bản nào của repo bị ảnh hưởng, nên còn nhẹ hơn L6 mô tả. | Để nguyên phông và `OFL.txt`. Nếu các báo cáo được sinh lại thì cho script ghi thêm dòng trống cuối. | S |
| HYG-08 | Nit | `.gitignore:13` | `.claude/worktrees/` được ignore cho một công cụ điều phối không tạo đường dẫn đó trong checkout này, nên không rõ còn cần hay không. | Giữ lại nhưng mở rộng comment để nêu tên công cụ và đường dẫn nó tạo. | S |
| HYG-09 | Low | ba commit `246a354`, `74594d0`, `04d2170` | Đây là phần tôi bổ sung và không đồng ý với L6. Ba commit đã publish mang trailer `Co-Authored-By: Claude Opus 5`. L6 nhìn thấy chúng nhưng gạt đi là "ghi công chứ không phải nhiễu". Quy tắc phát triển của chính anh nói commit dùng conventional format và không nhắc AI, nên đây là vi phạm quy tắc anh tự đặt, trên một repo công khai. | Cần anh quyết. Gỡ chúng đồng nghĩa viết lại lịch sử đã đẩy, mà đó lại là điều quy tắc thường trực của anh cấm. Lựa chọn thực tế là chấp nhận ba commit này như lịch sử và siết quy trình cho các commit sau. | S |

Một dữ kiện vận hành tôi phát hiện khi kiểm: **`main` đang đi trước `origin/main` 9 commit và chưa được đẩy.**

## Mục 11: Pháp lý và giấy phép

Phần lớn hồ sơ pháp lý ở đây làm tốt hơn mức trung bình. `LICENSE` khớp byte-for-byte với văn bản Apache-2.0 chính thức; tôi tự kiểm bằng `curl` cộng `diff` và kết quả rỗng. Dòng `Copyright [yyyy]` trong phụ lục là một phần của văn bản gốc chứ không phải chỗ trống bị bỏ quên, và dòng bản quyền thật nằm ở `NOTICE:2`, đúng thông lệ Apache. Không còn gói GPL nào trong cây phụ thuộc. Phông IBM Plex có đủ `OFL.txt` và một file provenance nêu đúng gói npm, sha256 và khẳng định các file được chép nguyên vẹn, nên quy tắc Reserved Font Name được tôn trọng. Site không thu thập dữ liệu người dùng nên không cần chính sách riêng tư. Không có logo hay wordmark của bên thứ ba.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| LEGAL-01 | High | `NOTICE:57-58`, `plans/reports/research-260907-spider-dev-sqlite/corrections.json` | `NOTICE` liệt kê rất kỹ tài liệu BIRD Mini-Dev, BIRD dev và phông chữ, rồi kết bằng câu bao trùm rằng mọi file khác là công sức của repo này. Câu đó sai với một tập tài liệu: gold SQL của Spider 1.0 dev nằm nguyên văn trong `corrections.json` với 28 cặp `before_sql` và `after_sql`, trong khi từ "Spider" không xuất hiện lần nào trong `NOTICE`. Chính `docs/claims-register.md:61` ghi nguồn Spider là CC BY-SA 4.0, tức giấy phép đòi ghi công khi phân phối lại. | Thêm một mục cho Spider vào `NOTICE` theo đúng văn phong các mục sẵn có: tên bộ dữ liệu, các file mang gold SQL và hàng kết quả của nó, giấy phép CC BY-SA 4.0 kèm link, và những thay đổi đã thực hiện. Sau khi danh sách đầy đủ thì đổi câu bao trùm thành "mọi file không nêu ở trên". | S |
| LEGAL-02 | Medium | `tools/site/templates/*.html`, `tools/site/data/README.md` | Site công khai đăng lại câu hỏi, gold SQL, prediction và hàng kết quả của BIRD, nhưng không trang nào nêu tên bộ dữ liệu, giấy phép hay link. Tôi kiểm cả năm template và cả 673 trang đã build: 0 trang nhắc `creativecommons` hay `CC BY`. Ghi công chỉ tồn tại trong `NOTICE` của repo, thứ mà người đọc trang web không bao giờ thấy. CC BY-SA đòi ghi công ở nơi tác phẩm được phân phối lại, và site chính là bề mặt phân phối rộng nhất. | Thêm một khối "Data and credit" vào chân trang: tên BIRD Mini-Dev và BIRD dev, link kho gốc, link giấy phép, và câu nói rõ đã thay đổi gì. Lặp lại một câu trong `tools/site/data/README.md`. | S |
| LEGAL-03 | Low | `README.md:152-155` | Mục giấy phép nêu `postgast`, `psycopg` và `sqlglot` nhưng bỏ sót Jinja2 (BSD-3-Clause). Apache-2.0 không đòi liệt kê phụ thuộc và wheel không nhúng chúng, nên đây là thiếu sót tài liệu chứ không phải vi phạm. | Thêm một câu nêu Jinja2, hoặc chuyển cả bảng giấy phép phụ thuộc vào `NOTICE` như phần thông tin. | S |

Một phần của LEGAL-01 tôi phải bác. L6 còn cáo buộc rằng 21 file prediction của bên thứ ba được chép nguyên vào `plans/reports/research-260907-dev-predictions-across-systems/official/`, kéo theo nghĩa vụ giữ thông báo giấy phép MIT và Apache. Tôi mở toàn bộ 42 file được track ở đó: **không file nào chứa một câu SELECT nào.** Chúng chỉ giữ kết quả đo gồm `positions`, `ex_sum`, `errors`, `timeouts` và tên file nguồn. Repo không phân phối lại câu lệnh của bên thứ ba ở đó, nên nghĩa vụ kèm thông báo không phát sinh. Đây là false positive duy nhất của cả bảy lane.

## Mục 12: Documentation

Bốn cổng kiểm tài liệu đều xanh: ADR index, doc link, typography, markdownlint và cspell, tổng cộng 59 file không lỗi. Trạng thái ADR nhất quán. L6 đối chiếu năm dòng của claims register với code và cả năm đều khớp. Comment trong code không lỗi thời: các chuỗi ngày tháng đều là provenance hợp lệ, và các docstring dài được lấy mẫu đều mô tả đúng code bên dưới.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| DOC-01 | High | `README.md:82`, `docs/audit-command.md:5` | README hứa "mọi flag, mọi dòng output và mọi khoá của `summary.json` đều được mô tả" trong trang tham chiếu, nhưng sáu flag có thật không xuất hiện ở đó. Tôi đếm trực tiếp: `--data-as-of`, `--fixture-digest`, `--plan-variant`, `--shuffle-row-limit`, `--shuffle-seed` và `--version` đều bằng 0 lần, trong khi `--dsn`, `--engine`, `--ids` thì có. Bốn trong sáu flag này đổi thứ mà một lần chạy đo và ghi lại. Đây cùng gốc với FEAT-01 của lane L4, và L6 đếm đầy đủ hơn. | Thêm bảng flag vào `docs/audit-command.md` với giá trị mặc định và ảnh hưởng lên `summary.json` cùng evidence record. | S |
| DOC-02 | Medium | `README.md` | README không hề nhắc attestql.com, chính site mà repo này dựng và deploy, và cũng không có lối vào cho người muốn đóng góp: 0 lần nhắc `attestql.com` hay `contribut`, 0 link tới `docs/developer-environment.md`. | Thêm hai mục ngắn: một dòng về site đã publish, một dòng về cách chạy `just check` và trỏ tới tài liệu môi trường. | S |
| DOC-03 | Low | `docs/developer-environment.md:132-134` | Tài liệu vẫn nói "khi chưa có benchmark nào được publish dưới `tools/site/data/`, build sẽ audit sandbox và hiện banner", trong khi thư mục đó đã có dữ liệu publish từ 2026-09-08 và `tools/site/README.md` nói ngược lại. | Cập nhật câu đó, và tách ảnh chụp trạng thái ngày 2026-08-25 ở mục 1 thành phần "History" để lần đổi trạng thái sau có chỗ rõ ràng. | S |
| DOC-04 | Low | gốc repo, `.github/` | Thiếu CONTRIBUTING.md, SECURITY.md và CITATION.cff. L6 lập luận đúng về mức cần thiết: gate của repo này nghiêm và không được mô tả ở đâu ngoài tài liệu môi trường; công cụ chạy SQL lên database của người dùng nên cần kênh báo lỗi riêng; và đây là công cụ nghiên cứu có số liệu được trích dẫn nên đáng có file citation. CHANGELOG là tuỳ chọn vì claims register và tag đã ghi lại thay đổi. | Thêm ba file tối thiểu và liên kết chúng từ README. Trùng một phần với META-02. | S |
| DOC-05 | Low | `plans/` (1,489 file, không README) | `plans/` công khai và được README trỏ vào như nơi giữ bằng chứng cho các claim, nhưng không có README nào nói cái gì là tài liệu bền, cái gì là ghi chép phiên làm việc, và cái gì người đọc có thể bỏ qua. Nó chiếm 45% số file của repo. | Thêm `plans/README.md` khoảng 15 dòng giải thích ba loại nội dung và trỏ tới claims register như chỉ mục cho biết báo cáo nào là chịu lực. | S |
| DOC-06 | Nit | `README.md` | Không câu nào nói CLI là bề mặt công khai duy nhất và các module Python là nội bộ, nên người dùng import chúng không có tín hiệu nào rằng chữ ký có thể đổi giữa các bản 0.x. | Thêm một câu vào README. | S |

## Mục 13: CI/CD và release

Gate CI rộng và xanh: 15 run gần nhất đều xanh ở workflow `ci`, ba run đỏ đều thuộc `site` và đều do secret Cloudflare bị dán kèm chữ thừa, đã sửa và các run sau đều xanh. Workflow phát hành có chốt chặn tốt: cài wheel rồi bắt buộc version khớp tag, chạy demo và kiểm chính xác dòng tổng kết trước khi publish; `id-token: write` chỉ nằm ở job publish trong environment `pypi`. Version trong pyproject, tag và PyPI đều là 0.2.2.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| CI-01 | Medium | `.github/dependabot.yml` không tồn tại | Không Dependabot cũng không Renovate, trong khi có ba bề mặt cần cập nhật: dependency uv, bảy action, ba công cụ Node. Đây đúng là loại rủi ro chậm mà PR tự động bắt được. | Thêm file cấu hình với hai ecosystem `uv` và `github-actions`, lịch hàng tuần. | S |
| CI-02 | Medium | 7 tag nhưng 1 GitHub release, `CHANGELOG.md` không tồn tại | Chỉ v0.2.2 có GitHub release. Sau lần phát hành hôm nay tình hình xấu đi: PyPI đã có 0.3.0 với 15 commit `feat` bên trong, nhưng không có release note nào ở bất kỳ đâu, vì `release.yml` chỉ publish lên PyPI chứ không tạo GitHub release. Người dùng cài 0.3.0 không có cách nào biết nó đổi gì ngoài việc tự diff tag. | Tạo release kèm notes cho các tag còn lại hoặc đánh dấu rõ chúng là tiền phát hành, và thêm URL Changelog. | S |
| CI-03 | Cần quyết | `git log v0.1.2..v0.1.3`, `v0.2.1..v0.2.2` | Tính năng mới từng phát hành trong bản vá: v0.1.3 chứa ba commit `feat` và v0.2.2 thêm hẳn lệnh `attestql demo`. Phần hướng tới tương lai anh đã tự xử lý: v0.3.0 mang 15 commit `feat` và được bump minor, đúng semver. Chỉ còn phần lịch sử. | Chọn một trong hai: theo quy tắc feat lên minor, hoặc tuyên bố rõ rằng nhánh 0.x đang Alpha nên bản vá có thể mang tính năng. | S |
| CI-04 | Low | `.github/workflows/ci.yml`, `release.yml` | Chỉ `site.yml` khai `concurrency`. Mỗi lần đẩy liên tiếp lên main xếp hàng thêm một gate đầy đủ gồm cả việc kéo image PostgreSQL. | Thêm nhóm concurrency theo ref cho ci.yml và theo tag cho release.yml. | S |
| CI-05 | Low | `justfile:58`, `.github/workflows/release.yml:36` | `uv build` chỉ chạy trong workflow theo tag. Một hồi quy đóng gói lộ ra lúc đã đẩy tag trông như một bản phát hành, thay vì lộ ra trên PR gây ra nó. | Thêm một bước build và cài thử wheel vào một nhánh của ma trận CI. | S |

## Mục 14: Metadata và mức sẵn sàng open source

Các trường lõi đều đúng: tên, version, description, readme, SPDX `license = "Apache-2.0"` kèm `license-files` trỏ tới hai file có thật, `requires-python`, bộ classifier mạch lạc, bốn dependency, ba URL và entry point. README đã có sẵn cảnh báo bảo mật trung thực rằng công cụ chạy dưới vai trò được cấp nên hãy cấp vai trò chỉ đọc.

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| META-01 | Medium | Nhánh `main` trên GitHub | Không branch protection và không ruleset; tôi kiểm tra trực tiếp và nhận 404 cùng danh sách ruleset rỗng. Release build thẳng từ tag trên nhánh này, nên đây là bước rẻ nhất biến một token rò rỉ thành một bản publish bị đầu độc. | Cần chủ repo quyết nội dung ruleset. Mức tối thiểu hợp lý: yêu cầu `ci` xanh, chặn force push và chặn xoá nhánh. | S |
| META-02 | Medium | `SECURITY.md` không tồn tại, private vulnerability reporting đang tắt | Công cụ chạy SQL không tin cậy theo thiết kế, nhưng người phát hiện lỗ hổng không có kênh riêng nào ngoài issue công khai. | Bật private vulnerability reporting và thêm `SECURITY.md` ngắn, trích lại đúng câu cảnh báo README đã có. | S |
| META-03 | Low | `pyproject.toml:5-24`, `:71-74`, không có `py.typed` | Thiếu `authors`, `keywords`, URL Documentation và Changelog, và không có marker `py.typed` dù code đã strict-typed hoàn toàn, nên type checker phía người dùng bỏ qua kiểu. Lane từ chối đúng đề nghị thêm classifier OSI vì package đã dùng PEP 639. | Thêm các trường trên và commit một file `src/attestql/py.typed` rỗng, khai trong package-data. | S |
| META-04 | Low | Cấu hình repo trên GitHub | Homepage để trống dù attestql.com đang chạy, không có topic, wiki đang bật và trống, không có template issue hay PR. | Đặt homepage, thêm topic, tắt wiki, thêm một template báo lỗi và một checklist PR ngắn. | S |
| META-05 | Nit | `README.md:1` | Không có badge nào. | Thêm bốn badge: phiên bản PyPI, trạng thái CI, giấy phép, phiên bản Python. | S |

## Mục 15: Những thứ khác chưa sạch

| ID | Sev | Vị trí | Vấn đề và hệ quả | Đề xuất fix | Effort |
|---|---|---|---|---|---|
| MISC-01 | Low | `cspell.json` | Từ điển chứa những từ không xuất hiện ở bất kỳ đâu trong repo ngoài chính file đó, và vài từ có hình dạng của lỗi gõ bị chấp nhận: `CREAT`, `ASSUM`, `unre`, `cdcd`, `arwd`, `oneline`, `colrows`. Tôi kiểm từng từ: cả bảy đều không xuất hiện ở file nào khác. Mỗi mục thừa nới rộng thứ mà cổng chính tả chấp nhận, và hai từ đầu trông đúng như `CREATE` và `ASSUME` bị cắt cụt. | Xoá các mục không dùng, và với tài liệu hiếm hoi cần trích SQL thô thì dùng comment `cspell:ignore` ngay tại dòng như một báo cáo đã làm. | S |
| MISC-02 | Nit | `.markdownlint.jsonc:2-3` | Comment nói lý do của từng ngoại lệ được ghi trong `plans/2026-08-25-slice1-mt-tooling.md`, nhưng file đó không tồn tại trong repo vì nó ở lại lịch sử riêng tư. Người đọc lần theo con trỏ sẽ hụt. | Viết thẳng ba lý do một dòng vào comment, hoặc trỏ sang `docs/developer-environment.md`, và bỏ đường dẫn treo. | S |
| MISC-03 | Nit | `.markdownlint-cli2.jsonc` | File config thứ hai chỉ chứa đúng một mục ignore `node_modules`, thứ mà markdownlint-cli2 vốn đã bỏ qua mặc định, và repo cũng không thể có `node_modules` vì không track `package.json` nào. | Xoá file, hoặc cho nó một ignore thật để nó xứng đáng tồn tại. | S |
| MISC-04 | Nit | `.pre-commit-config.yaml` | Hook chạy ruff, markdownlint và ba repo check nhưng không chạy cspell, trong khi recipe `docs` của justfile chạy cả hai. Phần đầu file chỉ giải thích những thứ bị bỏ vì chậm. Một commit có thể qua hết hook mà vẫn mang lỗi chính tả. | Thêm hook cspell nội bộ giống dòng trong justfile, hoặc nói rõ trong phần đầu rằng chính tả cố ý để dành cho gate. | S |

## Danh sách lệnh đã chạy

Bảy lane chạy tổng cộng hơn 150 lệnh; đây là những lệnh quyết định kết luận, kèm kết quả. Chi tiết đầy đủ nằm trong bảy báo cáo lane.

### Gate và test (lane L4, lane duy nhất được phép chiếm cổng Docker 5497)

| Lệnh | Kết quả |
|---|---|
| `just --time --timestamp check` | thoát 0 trong 35.51 giây; lint 0.25, typecheck 2.65, repocheck 0.29, docs 3.77, test 11.71, sandbox PostgreSQL 6.63, sandbox SQLite 9.32 |
| `uv run pytest -q --durations=15 -rs` | 1,087 qua, 33 skip, tất cả skip cùng một lý do đã ghi rõ |
| `uv run --with pytest-cov pytest -q --cov=attestql` | 94%, đo một lần làm thông tin |

### Lint và kiểu (ba lane, các đường dẫn khác nhau)

`ruff check`, `ruff format --check` và `pyright` đều thoát 0 trên `src/attestql/audit`, `src/attestql/report`, `tools`, `src/attestql/evidence`, `src/attestql/kernel`, `src/attestql/contract`. `uvx vulture --min-confidence 80` không báo dead code.

### Bảo mật

| Lệnh | Kết quả |
|---|---|
| `gitleaks git --no-banner -v --redact .` | thoát 1, 4 hit trên 150 commit; cả bốn là trường JSON `"keys"` mô tả hình dạng báo cáo, không phải khoá |
| Chín lần `attestql audit --engine sqlite` với prediction độc hại | mọi câu bị từ chối tại parser hoặc tại engine; hash fixture không đổi; không file nào được tạo trong `/tmp` |
| `uvx pip-audit --path .venv/.../site-packages --strict --desc` | không có lỗ hổng đã biết |
| `gh api "/advisories?ecosystem=npm&affects=<pkg>@<ver>"` cho ba công cụ Node | 0 advisory mỗi công cụ |
| `grep -rn -iE 'dsn\|password\|postgres://' OUT/demo` | không khớp gì, tức credential không lọt vào output |

### Reproduction do Claude tự chạy lại để xác nhận ba finding đầu bảng

| Reproduction | Kết quả |
|---|---|
| `_render_decimal(Decimal('1E+100'), 6)` | ném `InvalidOperation`; `1E+16` render đúng |
| R-SET trên hai kết quả NaN giống hệt | verdict `EQUAL`, rồi `result_digest` ném `UnsupportedValue`, còn `row_difference` báo 1 hàng khác nhau mỗi bên |
| Rewrite DISTINCT trên SQLite | câu gốc trả 2 hàng bằng đúng số giá trị distinct, bản rewrite trả 3 hàng vì DISTINCT áp lên cặp cột |

### Build và đo

| Lệnh | Kết quả |
|---|---|
| `uv run attestql demo --out <dir>` | thoát 1 đúng thiết kế, output khớp README byte-for-byte, 830 byte, `cmp` thoát 0 |
| `uv run python tools/site/build.py --out <dir>` | thoát 0, 2,218 file, 40,662,150 byte, 673 trang HTML, 5.10 giây |
| `npx html-validate` trên trang landing và trang report | thoát 0 |
| Trình kiểm link nội bộ trên 686 trang đã build | 0 link gãy |

### Trạng thái GitHub, đọc bằng tài khoản chủ repo, chỉ đọc

| Lệnh | Kết quả |
|---|---|
| `gh api .../branches/main/protection` | 404, nhánh không được bảo vệ |
| `gh api .../rulesets` | danh sách rỗng |
| `gh api .../private-vulnerability-reporting` | `enabled: false` |
| `gh api .../actions/permissions/workflow` | mặc định `read` |
| `gh run list --limit 15` | mọi run `ci` xanh; ba run `site` đỏ đều do secret bị dán kèm chữ thừa, đã sửa |
| `gh release list` so với `git tag` | 1 release trên 6 tag |
| `uv lock --check` | thoát 0, 28 gói |
| `uv pip list --outdated` | 7 gói lạc hậu |

## Action plan chia theo quyền quyết định

Chưa sửa gì cả. Ba nhóm dưới đây đúng theo yêu cầu của anh ở bước 2.

### Nhóm A: An toàn, không đổi hành vi. Gom một batch, đề nghị làm luôn

Toàn bộ nhóm này chỉ chạm docs, config, metadata và file mới. Không dòng nào đổi kết quả của một lần audit.

| Thứ tự | Việc | Finding gộp | Effort |
|---|---|---|---|
| 1 | Sửa một câu mô tả ở ba nơi để nêu cả PostgreSQL và SQLite: `pyproject.toml:8`, `src/attestql/__init__.py:1`, `src/attestql/audit/cli.py:1541`. Câu này còn là description trên PyPI và câu mở đầu attestql.com. | CQ-L2-02, UI-07 | S |
| 2 | Bổ sung `docs/audit-command.md` cho bốn flag còn thiếu, sửa đoạn nói về nội dung thư mục `q<id>/`, và sửa câu về exit code cho khớp code. | FEAT-01, FEAT-02, FEAT-03 | S |
| 3 | Thêm ghi chú bị thay thế một phần vào ADR-0003 và ADR-0014 về đồng hồ cố định, sửa câu đếm ADR trong `docs/adr/0000-index.md:21`. | FEAT-05, ARCH-02 của L2 | S |
| 4 | Cập nhật `docs/developer-environment.md`: bỏ hai tên file test không còn tồn tại, và nói đúng rằng `just check` còn chạy hai sandbox. | FEAT-06 | S |
| 5 | Sửa ba docstring và comment sai sự thật: `tools/site/build.py:20-23`, `tools/report-stress/build.py:340-342`, `src/attestql/contract/__init__.py:1`. | CQ-L3-03, CQ-L3-04, CQ-L2-04 | S |
| 6 | Thêm `.github/dependabot.yml` với hai ecosystem `uv` và `github-actions`, lịch hàng tuần. | CI-01, DEP-01 | S |
| 7 | Ghim bảy action theo commit SHA, giữ version trong comment, và nâng `astral-sh/setup-uv` lên major hiện tại. | SEC-01, DEP-02 | S |
| 8 | Thêm `permissions: contents: read` cho `ci.yml` và hai job của `release.yml`, thêm nhóm `concurrency` cho cả hai. | SEC-03, CI-04 | S |
| 9 | Bổ sung metadata gói: `authors`, `keywords`, URL Documentation và Changelog, cùng một file `src/attestql/py.typed` rỗng khai trong package-data. Giữ nguyên SPDX license expression. | META-03 | S |
| 10 | Thêm `SECURITY.md` ngắn và bật private vulnerability reporting trong cài đặt repo. | META-02 | S |
| 11 | Thêm bốn badge vào đầu README. | META-05 | S |
| 12 | Đặt homepage `https://attestql.com`, thêm topic, tắt wiki đang trống, thêm template issue và PR. | META-04 | S |
| 13 | Quyết một lần về Python 3.12: thêm vào ma trận CI hoặc bỏ classifier. | DEP-04 | S |
| 14 | Ghim `ruff` tuyệt đối trong dev group để hook pre-commit và gate không thể tách nhau. | DEP-03 | S |
| 15 | Thêm mục Spider vào `NOTICE` với giấy phép CC BY-SA 4.0, link và những thay đổi đã làm, rồi sửa câu bao trùm cuối file. Thêm một câu nêu Jinja2 vào mục giấy phép của README. | LEGAL-01, LEGAL-03 | S |
| 16 | Thêm khối "Data and credit" vào chân trang site: tên BIRD Mini-Dev và BIRD dev, link kho gốc, link giấy phép, và câu nói đã thay đổi gì. Lặp một câu trong `tools/site/data/README.md`. | LEGAL-02 | S |
| 17 | Bổ sung `.gitignore`: thêm `demo/`, `*.sqlite`, `.DS_Store`, `.idea/`, `.vscode/`, `node_modules/`, `.coverage`, `htmlcov/`, và bỏ `.mypy_cache/` vì mypy đã bị bác dứt khoát. | HYG-02 | S |
| 18 | Thêm `plans/README.md` khoảng 15 dòng giải thích ba loại nội dung trong đó và trỏ tới claims register. | DOC-05 | S |
| 19 | Thêm hai mục ngắn vào README: một dòng về attestql.com, một dòng về cách chạy gate và trỏ tới `docs/developer-environment.md`. Thêm một câu nói CLI là bề mặt công khai duy nhất. | DOC-02, DOC-06 | S |
| 20 | Cập nhật `docs/developer-environment.md:132-134` cho đúng trạng thái site đã có dữ liệu publish. | DOC-03 | S |
| 21 | Dọn `cspell.json`: xoá bảy từ không dùng, trong đó `CREAT` và `ASSUM` có hình dạng lỗi gõ. Sửa con trỏ treo trong `.markdownlint.jsonc` và quyết số phận `.markdownlint-cli2.jsonc`. Cân nhắc thêm hook cspell vào pre-commit. | MISC-01 đến MISC-04 | S |
| 22 | Xoá ba nhánh đã merge hết sau khi gỡ worktree web-ui, và chọn một kiểu tag rồi ghi vào tài liệu phát hành. | HYG-05 | S |

Hai việc cùng nhóm nhưng nặng hơn và nên làm sau: thêm bước `uv build` cộng cài thử wheel vào một nhánh ma trận CI (CI-05), và thêm test trực tiếp cho ba script trong `tools/site-select` (TEST-01, effort M, phụ thuộc việc đổi tên module ở nhóm B).

Một việc nằm ngoài mọi finding nhưng nên làm trước tiên: **`main` đang đi trước `origin/main` 9 commit và chưa đẩy.**

### Nhóm B: Đổi hành vi hoặc logic. Liệt kê để anh duyệt từng cái

Xếp theo mức độ đáng làm trước.

| Thứ tự | Finding | Đổi cái gì | Rủi ro nếu làm |
|---|---|---|---|
| 1 | LOGIC-01 | Một `Decimal` lớn hợp lệ chuyển từ làm sập run sang thành ERROR một câu hỏi. | Thấp. Đây là sửa một crash. |
| 2 | LOGIC-09 | `select.py --out` từ chối thư mục không rỗng và không mang marker. | Thấp. Có thể chặn một quy trình cũ của anh nếu anh vẫn trỏ vào thư mục có sẵn. |
| 3 | LOGIC-03 | `arbitrary-cut` ngừng bắn trên một lớp trường hợp DISTINCT. | Trung bình. Con số smell đã publish trên site sẽ đổi, nên cần đo lại và cập nhật claims register. |
| 4 | LOGIC-02 và LOGIC-17 | Kết quả chứa NaN nhận verdict thay vì ERROR, và hết báo hàng khác biệt giả. | Trung bình. Đổi cách ghi record cho giá trị không hữu hạn. |
| 5 | LOGIC-11, LOGIC-10 | `release.sh` tạo được release mới; `audits.sh` báo hỏng thay vì in `SQLITE_DONE`. | Thấp. Chỉ chạm công cụ maintainer. |
| 6 | LOGIC-06, LOGIC-07 | Report từ chối khoảng trống không giải thích được, và rerun dọn hai file phân loại cũ. | Thấp. |
| 7 | LOGIC-12, LOGIC-13, LOGIC-14 | File câu hỏi dị dạng bị từ chối sạch với exit 2 thay vì traceback hoặc audit dưới danh tính sai. | Thấp, nhưng là hợp đồng công khai của CLI. |
| 8 | LOGIC-08 | Prediction có id lạ bị từ chối hoặc được báo cáo thay vì bỏ im lặng. | Trung bình. Có thể làm đỏ một lần chạy vốn đang xanh. |
| 9 | LOGIC-04 | Envelope PostgreSQL pin `search_path`. | Trung bình. Đổi session settings mà mọi record ghi ra, nên byte của record đổi theo. |
| 10 | LOGIC-05, LOGIC-15, LOGIC-16, LOGIC-18, LOGIC-19, LOGIC-20 | Sáu chỗ siết chặt: độ phủ shuffle, digest fixture lấy giá trị vừa đo, ghi file nguyên tử, phân loại lỗi rowid, khôi phục pragma, và chốt symlink. | Thấp mỗi cái. |
| 11 | CQ-L1-01, ARCH-01, ARCH-02, CQ-L3-02 | DSN chứa chữ password được chấp nhận đúng cách; backend có `close`; parser identity được assert; ba hàm đọc count dùng chung. | Thấp. |
| 12 | CQ-L3-05 | Đổi tên `tools/site-select/select.py`, cập nhật ba chỗ gọi. | Thấp, nhưng chạm lệnh trong tài liệu. Mở khoá cho TEST-01. |
| 13 | FEAT-04 | Dòng tổng kết in thêm `other`. | Trung bình. README trích nguyên văn khối output nên phải sửa cả README và test. |
| 14 | UI-01 đến UI-06 | Site có metadata tìm kiếm, title phân biệt được, trang câu hỏi bớt nặng, có đường lên, có trạng thái rỗng, và chip cơ chế xử sự đúng khi tắt JavaScript. | Trung bình. UI-03 là việc lớn nhất trong nhóm. |
| 15 | PERF-02, PERF-03 | Digest tính một lần; vai trò database đọc một lần cho cả run. | Thấp. |
| 16 | HYG-03 | Chuyển ba liên kết vào template landing, ngừng đọc `site/index.html`, rồi xoá trang gốc. | Thấp, nhưng build sẽ từ chối chạy nếu xoá trang gốc trước khi chuyển liên kết. |
| 17 | HYG-01 | Bỏ track output thô và file 11.1 MB trong `plans/reports`, giữ báo cáo văn bản và summary nhỏ. | Trung bình. Cần chắc mọi thứ bỏ đi đều tái tạo được từ script và digest đã ghi. |

### Nhóm C: Cần anh quyết, tôi không tự chọn

| Vấn đề | Điều phải quyết |
|---|---|
| LOGIC-22, ngữ nghĩa R-ORD | ADR-0004 đòi thứ tự toàn phần với khoá phá hoà duy nhất, còn code gán R-ORD cho mọi ORDER BY ở cấp cao nhất và `docs/audit-command.md` mô tả đúng code. Anh muốn sửa lời văn ADR cho khớp code, hay muốn đo tính toàn phần và sinh một outcome riêng cho gold có thứ tự không đầy đủ? Đây chính là thứ memory của tôi ghi là "documented non-claim". |
| LOGIC-21, ngân sách hoán vị cột | Đặt trần tìm kiếm sẽ làm công cụ khác với evaluator tham chiếu mà nó cố ý mô phỏng. Chấp nhận khác biệt đó không? |
| PERF-01, ngân sách hàng kết quả | Bất biến "không cắt xén im lặng" là quyết định trong ADR-0013. Đặt trần hàng sẽ phá bất biến đó, không đặt thì một prediction xấu có thể ăn hết bộ nhớ. |
| ARCH-03, cụm kernel port | `QueryExecutor` và `SqlValidator` không nằm trên đường audit, và code gọi `admit()` sau khi đã chạy statement. Bỏ hẳn, hay giữ như legacy có tài liệu? |
| SEC-02, lockfile Node | Ba công cụ Node tải lúc chạy, trong đó wrangler chạy cùng token Cloudflare. Thêm lockfile Node vào một repo Python là chi phí thật. |
| SEC-04, log độ dài token | Chính anh vừa thêm dòng này hôm nay sau khi phép kiểm tra hình dạng chặn nhầm. Tôi không revert quyết định mới của anh. |
| META-01, ruleset cho `main` | Nhánh này đang không có bảo vệ nào. Anh muốn ruleset tới đâu, và có tự chặn chính mình không? |
| CI-03, semver cho nhánh 0.x | Tính năng đang ra trong bản vá. Đổi quy tắc, hay tuyên bố rõ rằng 0.x Alpha cho phép điều đó? |
| CQ-L2-01, CQ-L3-01, CQ-L2-03 | Ba đề nghị tái cấu trúc lớn: tách `cli.py` 1,998 dòng, tách `render.py` 1,865 dòng, và thay `dict[str, Any]` bằng kiểu JSON đệ quy. Đáng làm, nhưng là việc nhiều ngày và không sửa lỗi nào đang có. |
| HYG-09, ba commit mang trailer AI | Ba commit đã publish mang `Co-Authored-By: Claude Opus 5`, trái quy tắc anh tự đặt là commit không nhắc AI. Gỡ chúng đồng nghĩa viết lại lịch sử đã đẩy, mà quy tắc thường trực của anh lại cấm. Chấp nhận ba commit này như lịch sử và siết quy trình về sau, hay làm cách khác? |
| HYG-04, đường dẫn máy cá nhân | 1,001 file được track chứa `/Users/hoangle/...`, trái với chính chính sách repo đặt ra cho site tooling. Để nguyên như lịch sử bất biến, hay chuẩn hoá khi các báo cáo được sinh lại? |
| HYG-01, hai cây dữ liệu lớn | `plans/` chiếm 45% số file của repo và 53.6 MB. Giữ nguyên như thực hành bằng chứng công khai, cắt bớt, hay chuyển sang release asset? Mỗi lựa chọn có cái giá riêng đã ghi ở mục 10. |

## Câu hỏi còn treo

Tám điều ở nhóm C cần anh trả lời trước khi tôi động tới chúng. Ngoài ra có ba điều tôi không kiểm được và không muốn anh tưởng là đã kiểm:

- Không lane nào chạy lại các phép đo trên dữ liệu BIRD và Spider bên ngoài, nên các claim có ngày tháng trong `docs/claims-register.md` được coi là đã ghi đúng chứ không được đo lại.
- Không có reproduction nào chạy trên PostgreSQL thật vì sandbox Docker chỉ được lane L4 chiếm cổng, và lane bảo mật không được phép tự khởi động nó. Kết luận về PostgreSQL dựa trên đọc code và đọc script sandbox, còn lớp tương ứng bên SQLite thì đã chạy thật.
- Không đo Core Web Vitals thật vì không lane nào được mở trình duyệt; con số về trang nặng là đo DOM tĩnh.
