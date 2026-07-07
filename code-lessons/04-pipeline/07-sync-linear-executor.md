# #04 · Mẩu 07: `SyncLinearExecutor` — chạy chuỗi stage tuyến tính, dừng ở lỗi đầu tiên

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/runtime/sync_linear_executor.py` ·
tầng **runtime** · đây là "người lái" chuỗi stage: đẩy 1 packet qua từng stage theo thứ tự.

## 2. Cần biết trước
- Mẩu 01 (`StageStatus`/`StageResult`) + mẩu 02 (`ExecutionResult` + `from_stage_result`/`processed`) + mẩu 04 (`IStage`) — đọc trước.
- [pipeline](../../knowledge-base/00-GLOSSARY.md#pipeline-dây-chuyền-xử-lý) ·
  [stage](../../knowledge-base/00-GLOSSARY.md#stage-bước-xử-lý)
- Context manager (`__enter__`/`__exit__`) → tách sang mẩu 08.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/runtime/sync_linear_executor.py
class SyncLinearExecutor:
    """Run packet through stages linearly. Stop on first non-SUCCESS."""

    def __init__(self, stages: list[IStage]):
        self._stages = list(stages)
        self._setup_done: list[IStage] = []   # R3: chỉ teardown stage đã setup THÀNH CÔNG

    def setup_all(self) -> None:
        """Setup tuần tự. Nếu 1 stage setup LỖI → rollback (teardown ngược các stage đã setup) rồi raise."""
        self._setup_done = []
        for s in self._stages:
            try:
                s.setup()
            except Exception:
                # R3 (ERRATA E-16): setup lỗi nửa chừng → dọn các stage đã mở rồi mới ném lên.
                self.teardown_all()
                raise
            self._setup_done.append(s)

    def teardown_all(self) -> None:
        # R3: chỉ teardown các stage ĐÃ setup (tránh gọi teardown lên stage chưa khởi tạo).
        for s in reversed(self._setup_done):
            try:
                s.teardown()
            except Exception:
                pass
        self._setup_done = []
    # ... (context manager __enter__/__exit__ → xem mẩu 08)

    def execute(self, packet: MediaPacket) -> ExecutionResult:
        """Drive packet qua chuỗi stage. Giữ đầy đủ trạng thái (PROCESSED/SKIPPED/ERROR/CANCELLED)."""
        current = packet
        for stage in self._stages:
            result = stage.process(current)
            if result.status == StageStatus.SUCCESS:
                current = result.packet
            else:
                return ExecutionResult.from_stage_result(result)
        return ExecutionResult.processed(current)
```

## 4. Giải thích từng phần nhỏ nhất
- `class SyncLinearExecutor:` → chạy **đồng bộ** (sync, không đa luồng) + **tuyến tính** (linear, lần lượt).
- `__init__(self, stages)` → `self._stages = list(stages)`: **copy** danh sách stage (tạo list mới) → người ngoài đổi list gốc không ảnh hưởng executor.
- `setup_all()` → gọi `setup()` từng stage theo thứ tự xuôi; ghi vào `_setup_done` sau mỗi stage thành công. **R3 (E-16):** nếu 1 stage `setup()` lỗi → `teardown_all()` (rollback các stage đã mở) rồi `raise` → không để tài nguyên mở dở dang.
- `teardown_all()` → gọi `teardown()` theo **`reversed(_setup_done)` — thứ tự NGƯỢC**, **CHỈ trên stage đã setup thành công** (R3: không gọi teardown lên stage chưa khởi tạo). Mỗi `teardown` bọc `try/except: pass` → 1 stage dọn lỗi không chặn stage khác; xong thì clear `_setup_done`.
- `execute(self, packet) -> ExecutionResult`:
  - `current = packet` → giữ packet "hiện hành" đang chạy qua chuỗi.
  - `for stage in self._stages:` → lần lượt từng stage.
  - `result = stage.process(current)` → chạy stage (trả `StageResult`, mẩu 01).
  - `if result.status == SUCCESS: current = result.packet` → xuôi thì lấy packet mới làm đầu vào stage sau.
  - `else: return ExecutionResult.from_stage_result(result)` → **dừng NGAY** ở stage non-SUCCESS đầu tiên, map thành `ExecutionResult` (mẩu 02).
  - hết vòng lặp (mọi stage SUCCESS) → `return ExecutionResult.processed(current)` (SUCCESS toàn pipeline).

## 5. Là gì (1–2 câu)
`SyncLinearExecutor` là bộ chạy pipeline tuyến tính: đẩy packet qua từng stage, dừng ngay ở kết cục
non-SUCCESS đầu tiên, và trả `ExecutionResult` mang status cuối cùng.

> 📊 **Sơ đồ luồng executor → ExecutionResult** (nguồn: [`diagrams/pipeline-flow.drawio`](diagrams/pipeline-flow.drawio) → Export SVG ra `diagrams/pipeline-flow.svg`). _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (tách "khung chạy" khỏi "bước")
- **Tách trách nhiệm:** stage lo *logic 1 bước*; executor lo *trình tự chạy + dừng đúng lúc + dọn*. Thêm/bớt stage KHÔNG đụng executor.
- **Dừng ở lỗi đầu tiên (fail-fast):** non-SUCCESS thì dừng → không chạy tiếp trên dữ liệu đã sai/đã bỏ.
- **Teardown thứ tự NGƯỢC — fix tận gốc:** tài nguyên thường phụ thuộc nhau theo thứ tự mở. Dọn xuôi có thể đóng cái mà stage sau còn cần → lỗi. `reversed` đảm bảo đối xứng mở/đóng (LIFO). (Review #04 từng nghi "teardown xuôi" — đã kiểm code: thực tế là `reversed`, đúng.)
- **Giữ đủ status (result-object):** trả `ExecutionResult` thay `Optional` → phân biệt SUCCESS/SKIPPED/ERROR (mẩu 02).

## 7. Dùng ở đâu trong project (cụ thể)
- `demo_pipeline` (mẩu 09): `executor = SyncLinearExecutor([BrightnessStage(), DarkFilterStage(...)])` rồi `executor.execute(packet)` mỗi frame.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_executor_runs_stages_in_order`: chạy đủ chuỗi → `SUCCESS`, `is_processed`, `brightness ≈ 200`.
  - `test_executor_stops_on_skip`: dừng ở DarkFilter → `SKIPPED`, `packet is None`, `failed_stage == "dark_filter"`.
  - `test_executor_stops_on_error`: dừng ở lỗi → `ERROR`, `failed_stage == "dark_filter"`.
  - `test_executor_skip_and_error_are_distinguishable`: skip status ≠ error status.
  - `test_executor_idempotent_setup`: gọi `setup_all`/`teardown_all` 2 lần không vỡ.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Viết vòng lặp gọi stage rải rác trong code nghiệp vụ: trùng lặp + dễ quên dừng đúng lúc + quên teardown.
- Teardown xuôi (không reversed): đóng tài nguyên sai thứ tự → stage sau dọn lúc thứ nó cần đã bị đóng → lỗi/rò.
- Không bọc `try/except` quanh teardown: 1 stage dọn lỗi làm các stage sau KHÔNG được dọn → rò tài nguyên.

## 9. Ví von đời thường
`SyncLinearExecutor` như **quản đốc dây chuyền**: chuyền sản phẩm qua từng trạm, gặp trạm "loại/hỏng"
thì dừng và ghi kết luận. Cuối ca **tắt máy theo thứ tự ngược** lúc bật (bật A→B→C, tắt C→B→A).

## 10. Liên kết bức tranh lớn
Executor là "khung chạy" (ổn định) tiêu thụ `IStage` (mẩu 04) + sinh `ExecutionResult` (mẩu 02) từ
`StageResult` (mẩu 01). `teardown_all` reversed là nền cho context manager (mẩu 08) đảm bảo luôn dọn.

## 11. Cạm bẫy / lỗi thường gặp
- Quên gọi `setup_all`/`teardown_all` (nếu không dùng `with`) → stage chưa mở / không được dọn. → mẩu 08 giải quyết bằng context manager.
- Không copy list (`self._stages = stages`) → người ngoài sửa list gốc làm hỏng executor. Code chủ ý `list(stages)`.
- Đổi `teardown_all` thành xuôi "cho gọn" → tái sinh bug thứ tự dọn. Giữ `reversed`.
- Tiếp tục chạy sau non-SUCCESS → xử lý trên dữ liệu sai/đã bỏ.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `execute` dừng khi nào? trả gì khi dừng vs khi chạy hết?
- Tình huống: vì sao `teardown_all` chạy `reversed`? cho 1 ví dụ tài nguyên phụ thuộc thứ tự.
- Giải thích lại bằng LỜI MÌNH: "Executor lái chuỗi bằng cách ... ; dừng ở ... ; dọn theo thứ tự ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại vòng lặp execute + điều kiện dừng | 1 tuần → tự viết executor đơn giản | 1 tháng → giải thích vì sao teardown reversed + try/except.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/runtime/sync_linear_executor.py` (đã ĐỌC nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm 5 test executor trích ở §7). · Độ chắc: **cao**.
