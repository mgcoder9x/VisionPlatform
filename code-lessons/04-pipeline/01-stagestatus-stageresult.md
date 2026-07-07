# #04 · Mẩu 01: `StageStatus` + `StageResult` — kết quả 1 stage (KHÔNG giữ `Exception`)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` · tầng **kernel** ·
đây là "gói kết quả" của MỘT bước (stage) khi xử lý 1 packet.

## 2. Cần biết trước
- [Enum (enumeration)](../../knowledge-base/00-GLOSSARY.md#enum-enumeration) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [result object](../../knowledge-base/00-GLOSSARY.md#result-object-đối-tượng-kết-quả) ·
  [MediaPacket](../02-data-objects/08-mediapacket-immutable.md)
- `ExecutionResult` (kết quả TOÀN pipeline) → mẩu 02.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/stage_contract.py
class StageStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StageResult:
    """Outcome of stage processing 1 packet."""
    status: StageStatus
    packet: Optional[MediaPacket] = None
    skip_reason: Optional[str] = None
    error_type: Optional[str] = None        # type name only — no Exception ref
    error_message: Optional[str] = None     # str(exc) — no traceback ref
    error_traceback: Optional[str] = None   # format_exc() STRING — debug info, KHONG giu frame (E-16)
    stage: str = ""

    @classmethod
    def success(cls, packet: MediaPacket, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SUCCESS, packet=packet, stage=stage)

    @classmethod
    def skipped(cls, reason: str, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SKIPPED, skip_reason=reason, stage=stage)

    @classmethod
    def error(cls, error: Exception, stage: str = "",
              traceback_str: Optional[str] = None) -> "StageResult":
        """Build ERROR result without retaining exception reference (no traceback frames).

        `traceback_str` = traceback.format_exc() (CHUỖI thuần — giữ thông tin debug nhưng
        KHÔNG giữ tham chiếu frame/biến local → không rò RAM). Xem ERRATA E-16.
        """
        return cls(
            status=StageStatus.ERROR,
            error_type=type(error).__qualname__,
            error_message=str(error),
            error_traceback=traceback_str,
            stage=stage,
        )
```

## 4. Giải thích từng phần nhỏ nhất
- `class StageStatus(Enum):` → 4 kết cục của 1 stage: `SUCCESS` (ok), `SKIPPED` (bỏ frame cố ý), `ERROR` (lỗi), `CANCELLED` (bị huỷ).
- `@dataclass(frozen=True) class StageResult:` → gói kết quả **bất biến** của 1 stage.
  - `status: StageStatus` → bắt buộc: kết cục nào.
  - `packet: Optional[MediaPacket]` → packet kết quả (khi SUCCESS).
  - `skip_reason` → lý do bỏ (khi SKIPPED).
  - `error_type` / `error_message` → **tên loại lỗi** + **chuỗi mô tả** (KHÔNG phải Exception object).
  - `stage` → tên stage tạo ra kết quả này.
- 3 **factory method** (`@classmethod` tạo sẵn cho từng ca):
  - `success(packet, stage)` → StageResult SUCCESS.
  - `skipped(reason, stage)` → SKIPPED + lý do.
  - `error(error, stage)` → ERROR, NHƯNG chỉ lấy `type(error).__qualname__` (tên loại) + `str(error)` (lời nhắn) — **KHÔNG lưu chính `error`**.
- Trường `error_traceback` (E-16): giữ traceback **DẠNG CHUỖI** (`traceback.format_exc()`, do `BaseStage` truyền vào — mẩu 04). Chuỗi → có thông tin debug đầy đủ nhưng **KHÔNG giữ tham chiếu frame/biến** → không rò RAM (vẫn đúng tinh thần chống traceback retention).

## 5. Là gì (1–2 câu)
`StageResult` là result-object cho MỘT stage: mang status rõ ràng + dữ liệu kèm theo. Điểm đặc biệt:
khi lỗi, nó chỉ giữ **chuỗi** (tên + lời nhắn), KHÔNG giữ đối tượng `Exception`.

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (traceback retention)
- **Result-object thay vì trả thẳng packet/None:** mỗi stage trả status rõ → bước sau / executor xử lý đúng từng ca, không đoán.
- **KHÔNG giữ `Exception` object (chống traceback retention):** một `Exception` còn sống thì **kéo theo traceback** → traceback giữ tham chiếu tới các **khung biến** (frame locals), trong đó có thể có **cả ndarray ảnh lớn**. Giữ `Exception` lâu trong hàng đợi/log → ảnh không được giải phóng → **rò RAM** (bug thật Module 05, R5).
  - **Fix cái NGỌN (sai):** mỗi nơi cầm Exception nhớ `del` thủ công → dễ quên.
  - **Fix tận GỐC (đã làm):** `StageResult` **về bản chất không có chỗ chứa Exception** — `error()` chỉ trích `type` + `str` ngay lúc tạo. Không ai giữ Exception được nữa.

## 7. Dùng ở đâu trong project (cụ thể)
- `BaseStage.process()` (mẩu 04) gọi `StageResult.success/skipped/error` để gói kết quả.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_stage_error_does_not_retain_exception_object` (R5-CRITICAL-02): `error_type`/`error_message` là `str`; **trường `error` KHÔNG tồn tại** trong `fields(StageResult)`.
  - `test_dark_filter_errors_without_brightness`: `result.error_message` là `str`, chứa "brightness".

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Trả thẳng packet/None: lẫn "bỏ cố ý" với "lỗi"; không rõ stage nào.
- Giữ `Exception` object: traceback retention → ảnh lớn không giải phóng → RAM phình theo thời gian (rất khó lần, chỉ lộ khi chạy lâu).

## 9. Ví von đời thường
`StageResult` như **phiếu kết quả công đoạn**: ghi rõ "Đạt / Bỏ (lý do) / Lỗi (loại + mô tả)". Phần lỗi
chỉ **ghi lại bằng chữ** (biên bản), KHÔNG giữ luôn "hiện trường" cồng kềnh (Exception + ảnh) → kho không phình.

## 10. Liên kết bức tranh lớn
Đây là viên gạch kết quả ở `kernel`, cùng họ với `ReadResult` (#02) — đều là result-object trạng-thái-tường-minh.
`BaseStage` (mẩu 04) sinh ra nó; `ExecutionResult` (mẩu 02) gói kết quả TOÀN pipeline từ nó.

## 11. Cạm bẫy / lỗi thường gặp
- Thêm trường `error: Exception` vào `StageResult` "cho tiện" → tái sinh bug traceback retention. Cố ý KHÔNG có trường đó.
- Quên `stage` → khó biết lỗi/bỏ ở bước nào khi đọc log.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: 4 `StageStatus` là gì? Vì sao `error()` không lưu `Exception` object?
- Tình huống: nếu giữ `Exception` trong hàng đợi kết quả lâu, điều gì xảy ra với RAM? Vì sao?
- Giải thích lại bằng LỜI MÌNH: "StageResult để ... ; không giữ Exception vì ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 4 status + vì sao không giữ Exception | 1 tuần → tự viết result-object cho việc khác | 1 tháng → giải thích traceback retention.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` (đã ĐỌC nguyên văn `StageStatus`+`StageResult`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm `test_stage_error_does_not_retain_exception_object`). · Độ chắc: **cao**.
- Traceback retention (R5): cơ chế Python (Exception giữ `__traceback__` → frame locals) có tài liệu; bug ghi ở Module 05. · Độ chắc: cao về cơ chế.
