# #04 · Mẩu 04: `IStage` (Protocol) + `BaseStage` (ABC + Template Method)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `IStage` ở `vision-platform/src/vision_platform/kernel/stage_contract.py`
(tầng **kernel**) · `BaseStage` ở `vision-platform/src/vision_platform/runtime/base_stage.py` (tầng **runtime**) ·
đây là "hợp đồng 1 bước" + "khung viết sẵn" để tạo stage.

## 2. Cần biết trước
- [Protocol (typing.Protocol)](../../knowledge-base/00-GLOSSARY.md#protocol-typingprotocol) ·
  [ABC (Abstract Base Class)](../../knowledge-base/00-GLOSSARY.md#abc-abstract-base-class) ·
  [Template Method](../../knowledge-base/00-GLOSSARY.md#template-method-mẫu-thiết-kế) ·
  [stage](../../knowledge-base/00-GLOSSARY.md#stage-bước-xử-lý)
- Mẩu 01 (`StageResult` + factory `success/skipped/error`) + mẩu 03 (`SkipFrameSignal`) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/stage_contract.py
class IStage(Protocol):
    """Sync stage. Process 1 packet → 1 packet (or skip/error)."""
    @property
    def name(self) -> str: ...

    def process(self, packet: MediaPacket) -> StageResult: ...

    def setup(self) -> None: ...

    def teardown(self) -> None: ...
```

```python
# vision-platform/src/vision_platform/runtime/base_stage.py
class BaseStage(ABC):
    """Scaffold: tự handle SkipFrameSignal + Exception thành StageResult."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def setup(self) -> None: ...

    def teardown(self) -> None: ...

    def process(self, packet: MediaPacket) -> StageResult:
        try:
            result_packet = self._do_process(packet)
            # R6 (ERRATA E-16): fail-fast nếu lớp con trả sai kiểu (None / ndarray / ...)
            # → biến thành ERROR result ngay tại stage, không để lọt xuống downstream xa.
            if not isinstance(result_packet, MediaPacket):
                raise TypeError(
                    f"_do_process must return MediaPacket, got "
                    f"{type(result_packet).__name__}"
                )
            return StageResult.success(result_packet, stage=self._name)
        except SkipFrameSignal as e:
            return StageResult.skipped(reason=str(e), stage=self._name)
        except Exception as e:
            # R1 (ERRATA E-16): giữ traceback DẠNG CHUỖI (format_exc) cho debug —
            # chuỗi KHÔNG giữ tham chiếu frame/biến local → không rò RAM.
            return StageResult.error(
                error=e, stage=self._name, traceback_str=traceback.format_exc()
            )

    @abstractmethod
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        """Subclass implement. Return new MediaPacket (CoW). Raise to skip/error."""
        ...
```

## 4. Giải thích từng phần nhỏ nhất
**`IStage` (hợp đồng — kernel):**
- `class IStage(Protocol):` → định nghĩa hợp đồng theo **structural typing**: lớp nào CÓ ĐỦ 4 thứ dưới là "khớp", không cần kế thừa.
- `name -> str` (property) · `process(packet) -> StageResult` · `setup() -> None` · `teardown() -> None` — 4 điều khoản một stage phải có. `...` = thân trống (chỉ là hợp đồng).

**`BaseStage` (khung — runtime):**
- `class BaseStage(ABC):` → lớp cha **trừu tượng** (Abstract Base Class) — không tạo trực tiếp được, phải kế thừa.
- `__init__(self, name)` → lưu tên stage vào `self._name`.
- `name` (property) → trả `self._name`. (Cùng tên với điều khoản trong `IStage` → `BaseStage` khớp hợp đồng.)
- `setup()` / `teardown()` → mặc định trống (`...`); lớp con override nếu cần mở/đóng tài nguyên.
- `process(packet)` → **trái tim Template Method**: viết sẵn khung try/except:
  - gọi `self._do_process(packet)` (phần lớp con điền) → kiểm `isinstance(..., MediaPacket)` (R6/E-16: lớp con trả sai kiểu → `TypeError` → ERROR, fail-fast) → nếu OK: `StageResult.success(...)`.
  - `except SkipFrameSignal` → `StageResult.skipped(...)` (mẩu 03 → status SKIPPED).
  - `except Exception` → `StageResult.error(..., traceback_str=traceback.format_exc())` (mẩu 01: KHÔNG giữ Exception, nhưng giữ traceback DẠNG CHUỖI cho debug — E-16) → ERROR.
- `@abstractmethod _do_process(packet) -> MediaPacket` → **ô trống bắt buộc lớp con điền**: chỉ lo logic riêng, trả packet mới (CoW), `raise` để skip/error.

## 5. Là gì (1–2 câu)
`IStage` là hợp đồng "thế nào là 1 stage". `BaseStage` là khung viết sẵn theo **Template Method**:
phần chung (bắt lỗi → result-object) viết MỘT lần ở cha; lớp con chỉ điền `_do_process`.

> 📊 **Sơ đồ: `process()` map exception → StageStatus** (nguồn: [`diagrams/stage-status-state.drawio`](diagrams/stage-status-state.drawio) → Export SVG ra `diagrams/stage-status-state.svg`). _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (bắt lỗi nhất quán)
- **Vấn đề:** nếu MỖI stage tự viết try/except riêng → chỗ bắt `SkipFrameSignal`, chỗ quên; chỗ trả `None`, chỗ raise → **không nhất quán**, dễ rò Exception.
- **Fix cái NGỌN (sai):** dặn "mọi stage nhớ bắt lỗi giống nhau" → người viết stage mới sẽ quên.
- **Fix tận GỐC (đã làm):** đưa try/except vào **`BaseStage.process` viết một lần**. Lớp con KHÔNG được đụng `process`, chỉ điền `_do_process`. Vậy mọi stage **chắc chắn** bắt lỗi đồng nhất → result-object đúng status.
- `IStage` (Protocol) tách hợp đồng khỏi cài đặt: executor (mẩu 07) chỉ cần "thứ khớp IStage", không quan tâm có kế thừa `BaseStage` hay không.

## 7. Dùng ở đâu trong project (cụ thể)
- `BrightnessStage` (mẩu 05) + `DarkFilterStage` (mẩu 06) **kế thừa** `BaseStage`, chỉ điền `_do_process`.
- `SyncLinearExecutor` (mẩu 07) nhận `list[IStage]` — nhờ Protocol, nhận mọi thứ khớp hợp đồng.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_custom_stage_via_subclass`: subclass `CountStage(BaseStage)` chỉ viết `_do_process` → `process` tự gói `StageResult`; `r1.packet.artifacts["count"] == 1`, input `p` KHÔNG bị sửa.
  - `test_dark_filter_errors_without_brightness`: `_do_process` raise `ValueError` → `process` trả status ERROR (không sập).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Không có `BaseStage`: mỗi stage lặp lại try/except → trùng code + dễ quên 1 nhánh → lỗi lọt hoặc skip bị tính nhầm.
- Không có `IStage` (Protocol): executor phải biết kiểu cụ thể từng stage → cứng nhắc, khó cắm stage mới.

## 9. Ví von đời thường
`BaseStage` như **mẫu đơn in sẵn**: phần khung (kẻ ô, đóng dấu, kiểm tra hợp lệ) đã in; người dùng chỉ
**điền 1 ô trống** (`_do_process`). Ai cũng nộp ra cùng một định dạng → bộ phận sau xử lý nhất quán.

## 10. Liên kết bức tranh lớn
`IStage` (kernel, hợp đồng) ↔ `BaseStage` (runtime, khung) — đúng kiểu port/adapter nhưng ở mức "bước
xử lý". `BaseStage` dùng `StageResult` (mẩu 01) + `SkipFrameSignal` (mẩu 03); các stage cụ thể (mẩu
05/06) kế thừa nó; `SyncLinearExecutor` (mẩu 07) lái chuỗi `IStage`.

## 11. Cạm bẫy / lỗi thường gặp
- Override `process` ở lớp con → phá khung bắt-lỗi → tái sinh sự không nhất quán. Chỉ điền `_do_process`.
- Quên `@abstractmethod` → quên cài `_do_process` mà không bị báo lỗi → chạy mới vỡ.
- `_do_process` SỬA input packet thay vì trả packet mới → phá bất biến/CoW (xem mẩu 05).
- Nhầm `Protocol` (structural, không cần kế thừa) với `ABC` (nominal, phải kế thừa) — hai cơ chế khác nhau.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `BaseStage.process` bắt mấy loại exception? mỗi loại thành status gì?
- Tình huống: viết 1 stage mới đếm số frame — bạn cần override method nào, KHÔNG được đụng method nào? Vì sao?
- Giải thích lại bằng LỜI MÌNH: "Template Method ở đây nghĩa là ... ; IStage khác BaseStage ở ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 3 nhánh try/except + vì sao ở lớp cha | 1 tuần → tự viết 1 BaseStage-subclass | 1 tháng → giải thích Protocol vs ABC.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `kernel/stage_contract.py` (`IStage`) + `runtime/base_stage.py` (`BaseStage`) — đã ĐỌC nguyên văn. · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm `test_custom_stage_via_subclass`, `test_dark_filter_errors_without_brightness`). · Độ chắc: **cao**.
