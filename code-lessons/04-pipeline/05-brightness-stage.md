# #04 · Mẩu 05: `BrightnessStage` — stage cụ thể đầu tiên (tính độ sáng, CoW)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/runtime/stages/brightness_stage.py` ·
tầng **runtime** · đây là một stage CỤ THỂ: tính độ sáng trung bình của frame, ghi vào artifact.

## 2. Cần biết trước
- Mẩu 04 (`BaseStage` + `_do_process`) — đọc trước; `BrightnessStage` kế thừa nó.
- [ndarray (numpy array)](../../knowledge-base/00-GLOSSARY.md#ndarray-numpy-array) ·
  [immutable (bất biến)](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến)
- `with_artifact` + Copy-on-Write của `MediaPacket` → bài #02 ([CoW](../02-data-objects/09-mediapacket-cow.md)).

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/runtime/stages/brightness_stage.py
class BrightnessStage(BaseStage):
    """Tính frame.mean() → packet.artifacts['brightness']."""

    def __init__(self):
        super().__init__("brightness")

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        frame = packet.media_ref.array
        brightness = float(frame.mean())
        return packet.with_artifact("brightness", brightness)
```

## 4. Giải thích từng phần nhỏ nhất
- `class BrightnessStage(BaseStage):` → kế thừa khung `BaseStage` (mẩu 04) → tự có `process`, `setup`, `teardown`, bắt-lỗi.
- `__init__(self)` → `super().__init__("brightness")`: đặt **tên stage** = `"brightness"` (đẩy lên lớp cha lưu vào `self._name`).
- `_do_process(self, packet)` → **ô trống** lớp con điền (chỉ logic riêng, không bắt lỗi — cha lo rồi):
  - `frame = packet.media_ref.array` → lấy mảng ảnh (ndarray) ra.
  - `brightness = float(frame.mean())` → `numpy.mean()` tính trung bình mọi pixel → ép về `float` Python.
  - `return packet.with_artifact("brightness", brightness)` → trả về **packet MỚI** có thêm artifact `brightness` (CoW), KHÔNG sửa packet cũ.

## 5. Là gì (1–2 câu)
`BrightnessStage` là một stage cụ thể: đo độ sáng trung bình của frame và **gắn kết quả vào một packet
mới** (không đụng packet gốc). Nó chỉ viết đúng 1 method `_do_process` nhờ khung `BaseStage`.

## 6. Tại sao tồn tại / vấn đề nó giải
- Đây là **worked example** của "viết 1 stage đúng cách": kế thừa `BaseStage`, đặt tên, điền `_do_process`, trả packet mới.
- **Không sửa input (CoW):** `with_artifact` trả packet mới thay vì `packet.artifacts["brightness"] = ...`. Vì packet là immutable + có thể được nhiều nơi/nhiều tiến trình tham chiếu — sửa tại chỗ sẽ gây bug "ai đó đổi lén". Đây là fix tận gốc ở tầng dữ liệu (#02), stage chỉ tuân theo.
- **Tách brightness thành stage riêng:** `DarkFilterStage` (mẩu 06) cần con số này → tách ra để tái dùng + ráp theo thứ tự.

## 7. Dùng ở đâu trong project (cụ thể)
- `demo_pipeline` (mẩu 09) đặt `BrightnessStage()` **đầu tiên** trong `SyncLinearExecutor([...])`.
- Kết quả `artifacts["brightness"]` được `DarkFilterStage` (mẩu 06) đọc để quyết định skip.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_brightness_stage_computes_mean`: frame value=100 → `result.packet.artifacts["brightness"] ≈ 100.0`.
  - `test_brightness_stage_does_not_mutate_input`: sau `process`, `"brightness" not in packet.artifacts` (packet gốc KHÔNG đổi) nhưng `"brightness" in result.packet.artifacts` → chứng minh CoW.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Gộp tính-sáng + lọc-tối vào 1 stage: không tái dùng được số brightness; khó test riêng; vi phạm "1 stage = 1 việc".
- Nếu sửa input tại chỗ (`packet.artifacts[...] = ...`): packet đang chia sẻ bị đổi lén → frame khác/tiến trình khác đọc nhầm. CoW chặn từ gốc.

## 9. Ví von đời thường
`BrightnessStage` như **trạm cân**: đặt món lên cân, ghi số cân vào **một tem mới** dán lên bản sao
phiếu, KHÔNG sửa phiếu gốc của người khác. Trạm sau đọc tem đó để quyết định.

## 10. Liên kết bức tranh lớn
Đây là `IStage` cụ thể đầu tiên: dùng `BaseStage` (mẩu 04) + `with_artifact`/CoW (#02). Đầu ra của nó
là đầu vào điều kiện cho `DarkFilterStage` (mẩu 06) → minh hoạ "thứ tự stage quan trọng" (mẩu 06/07).

## 11. Cạm bẫy / lỗi thường gặp
- Sửa `packet.artifacts` tại chỗ thay vì `with_artifact` → phá bất biến/CoW.
- Quên `super().__init__("brightness")` → stage không có tên → log/StageResult thiếu `stage`.
- Trả `frame.mean()` (numpy float) mà không `float(...)` → kiểu numpy lọt vào artifact (thường vẫn chạy nhưng không thuần Python; code chủ ý ép `float`).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `BrightnessStage` override method nào? vì sao KHÔNG override `process`?
- Tình huống: vì sao trả packet mới (`with_artifact`) thay vì gán thẳng `artifacts["brightness"]`? Bug gì xảy ra nếu gán thẳng?
- Giải thích lại bằng LỜI MÌNH: "BrightnessStage làm ... ; CoW ở đây để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 3 dòng `_do_process` + vì sao CoW | 1 tuần → tự viết 1 stage tính thuộc tính khác | 1 tháng → giải thích vì sao tách thành stage riêng.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/runtime/stages/brightness_stage.py` (đã ĐỌC nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm `test_brightness_stage_computes_mean`, `test_brightness_stage_does_not_mutate_input`). · Độ chắc: **cao**.
