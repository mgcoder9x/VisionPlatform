# #04 · Mẩu 02: `ExecutionResult` — result-object cho TOÀN pipeline (thay `Optional`)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` · tầng **kernel** ·
đây là "gói kết quả" của TOÀN BỘ pipeline cho 1 packet (executor trả về cái này).

## 2. Cần biết trước
- [result object](../../knowledge-base/00-GLOSSARY.md#result-object-đối-tượng-kết-quả) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue)
- Mẩu 01 (`StageStatus` + `StageResult`) — đọc trước; `ExecutionResult` map từ `StageResult`.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/stage_contract.py
@dataclass(frozen=True)
class ExecutionResult:
    """Outcome của TOÀN BỘ pipeline cho 1 packet (executor trả về cái này).

    Giữ ĐẦY ĐỦ trạng thái — KHÔNG bóp về Optional:
        - SUCCESS   → packet chạy hết chuỗi, `packet` là kết quả cuối.
        - SKIPPED   → 1 stage skip (filter chặn), `failed_stage` + `reason`.
        - ERROR     → 1 stage lỗi, `failed_stage` + error_type/message.
        - CANCELLED → pipeline bị huỷ giữa chừng.

    Vì sao result-object thay `Optional[MediaPacket]`? `None` không phân biệt "filter cố ý bỏ
    frame" (bình thường) với "stage lỗi" (cần alert). Result-object giữ status rõ ràng.
    """
    status: StageStatus
    packet: Optional[MediaPacket] = None
    failed_stage: str = ""
    reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    @property
    def is_processed(self) -> bool:
        return self.status == StageStatus.SUCCESS

    @classmethod
    def processed(cls, packet: MediaPacket) -> "ExecutionResult":
        return cls(status=StageStatus.SUCCESS, packet=packet)

    @classmethod
    def from_stage_result(cls, result: "StageResult") -> "ExecutionResult":
        """Map kết quả non-SUCCESS của 1 stage thành ExecutionResult của pipeline."""
        return cls(
            status=result.status,
            failed_stage=result.stage,
            reason=result.skip_reason,
            error_type=result.error_type,
            error_message=result.error_message,
            error_traceback=result.error_traceback,
        )
```

## 4. Giải thích từng phần nhỏ nhất
- `@dataclass(frozen=True) class ExecutionResult:` → kết quả bất biến của CẢ pipeline (khác `StageResult` là của 1 stage).
- Docstring nói thẳng 4 ca + lý do dùng result-object.
- Trường: `status` (bắt buộc) · `packet` (khi SUCCESS) · `failed_stage` (stage gây dừng) · `reason` (lý do skip) · `error_type`/`error_message` (chuỗi lỗi — vẫn KHÔNG giữ Exception, mẩu 01).
- `@property is_processed` → `True` chỉ khi `status == SUCCESS`. Lối tắt hỏi "packet đã chạy hết chuỗi chưa?".
- `processed(packet)` → factory tạo ExecutionResult SUCCESS.
- `from_stage_result(result)` → **map** một `StageResult` non-SUCCESS (skip/error của 1 stage) thành `ExecutionResult` của pipeline: chép `status`, `stage→failed_stage`, `skip_reason→reason`, error fields.

## 5. Là gì (1–2 câu)
`ExecutionResult` là result-object cho TOÀN pipeline: mang status cuối cùng (SUCCESS/SKIPPED/ERROR/CANCELLED)
+ thông tin kèm. Executor (mẩu 07) trả về nó thay vì trả `MediaPacket` hoặc `None`.

## 6. Tại sao tồn tại / vấn đề nó giải
Nếu pipeline trả `Optional[MediaPacket]` (`None` khi "không có kết quả"): `None` **gộp 2 ca khác hẳn nhau** —
*filter cố ý bỏ frame tối* (bình thường, không cần làm gì) và *một stage lỗi* (cần báo động/đếm). Xử lý
nhầm → hoặc spam alert cho frame bị bỏ, hoặc nuốt lỗi thật. `ExecutionResult` giữ **status tường minh** →
người gọi `if result.status == SKIPPED ... elif ERROR ...` xử lý đúng từng ca.

## 7. Dùng ở đâu trong project (cụ thể)
- `SyncLinearExecutor.execute()` (mẩu 07) trả `ExecutionResult`; `demo_pipeline` (mẩu 09) switch theo `result.status` để đếm processed/skipped/error.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_executor_stops_on_skip`: `result.status == SKIPPED`, `result.packet is None`, `failed_stage == "dark_filter"`, `"too_dark" in reason`.
  - `test_executor_stops_on_error`: `result.status == ERROR`, `failed_stage == "dark_filter"`, `error_message` là str chứa "brightness".
  - `test_executor_skip_and_error_are_distinguishable`: `skip_result.status != err_result.status` (SKIPPED ≠ ERROR).
  - `test_executor_runs_stages_in_order`: `result.is_processed` True + `artifacts["brightness"] ≈ 200`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Trả `Optional[MediaPacket]`: `None` mơ hồ → không phân biệt bỏ-cố-ý với lỗi → hoặc báo động sai, hoặc
nuốt lỗi. `ExecutionResult` là "bản chất" giải quyết: trạng thái hiện rõ, không suy đoán từ `None`.

## 9. Ví von đời thường
`ExecutionResult` như **kết luận cuối của cả dây chuyền** trên 1 sản phẩm: "Hoàn thành / Bị loại ở trạm X
(lý do) / Lỗi máy ở trạm X (mô tả)". Tờ kết luận trắng (None) thì quản lý không biết nên cho qua hay gọi thợ.

## 10. Liên kết bức tranh lớn
`StageResult` (mẩu 01) = kết quả 1 trạm; `ExecutionResult` = kết luận cả dây chuyền (executor map lên từ
stage dừng). Cùng triết lý result-object trạng-thái-tường-minh như `ReadResult` (#02). Executor (mẩu 07) là nơi sinh ra nó.

## 11. Cạm bẫy / lỗi thường gặp
- Bóp `ExecutionResult` về `Optional[MediaPacket]` "cho gọn" → tái sinh đúng bug "None mơ hồ". Cố ý giữ result-object.
- Quên xử lý nhánh ERROR (chỉ lo SUCCESS/SKIPPED) → nuốt lỗi thật.
- Nhầm `is_processed` với "có packet": `is_processed` = `status==SUCCESS` (chặt hơn).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao `None` không đủ cho kết quả pipeline? `from_stage_result` làm gì?
- Tình huống: frame tối bị DarkFilter bỏ vs stage lỗi thiếu artifact — `ExecutionResult` phân biệt 2 ca thế nào?
- Giải thích lại bằng LỜI MÌNH: "ExecutionResult để ... ; khác StageResult ở ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 4 status pipeline + vì sao không dùng None | 1 tuần → tự thiết kế result-object cho 1 quy trình | 1 tháng → giải thích skip ≠ error.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` (đã ĐỌC nguyên văn `ExecutionResult`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm 4 test trích ở §7). · Độ chắc: **cao**.
