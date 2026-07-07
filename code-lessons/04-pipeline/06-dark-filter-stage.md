# #04 · Mẩu 06: `DarkFilterStage` — skip khi tối + ÉP thứ tự stage (cần artifact `brightness`)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/runtime/stages/dark_filter_stage.py` ·
tầng **runtime** · đây là stage lọc: bỏ frame quá tối, và **báo lỗi rõ** nếu bị đặt sai thứ tự.

## 2. Cần biết trước
- Mẩu 04 (`BaseStage`) + mẩu 03 (`SkipFrameSignal`) + mẩu 05 (`BrightnessStage` tạo artifact `brightness`) — đọc trước.
- [stage](../../knowledge-base/00-GLOSSARY.md#stage-bước-xử-lý) ·
  [result object](../../knowledge-base/00-GLOSSARY.md#result-object-đối-tượng-kết-quả)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/runtime/stages/dark_filter_stage.py
class DarkFilterStage(BaseStage):
    """Skip frame nếu artifact 'brightness' < threshold.

    Yêu cầu: BrightnessStage phải chạy TRƯỚC stage này.
    """

    def __init__(self, threshold: float):
        super().__init__("dark_filter")
        self._threshold = threshold

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        brightness = packet.artifacts.get("brightness")
        if brightness is None:
            raise ValueError(
                "DarkFilterStage requires 'brightness' artifact. "
                "Did you forget to add BrightnessStage before this?"
            )
        if brightness < self._threshold:
            raise SkipFrameSignal(f"too_dark (brightness={brightness:.2f})")
        return packet
```

## 4. Giải thích từng phần nhỏ nhất
- `class DarkFilterStage(BaseStage):` → kế thừa khung `BaseStage` (mẩu 04).
- docstring ghi rõ **điều kiện thứ tự**: `BrightnessStage` phải chạy TRƯỚC.
- `__init__(self, threshold)` → `super().__init__("dark_filter")` đặt tên + lưu `self._threshold` (ngưỡng sáng).
- `_do_process(self, packet)`:
  - `brightness = packet.artifacts.get("brightness")` → đọc artifact do `BrightnessStage` ghi. `.get(...)` trả `None` nếu chưa có.
  - `if brightness is None: raise ValueError(...)` → **chưa có brightness** = stage bị đặt SAI THỨ TỰ → báo lỗi RÕ (gợi ý "quên thêm BrightnessStage?") thay vì im lặng.
  - `if brightness < self._threshold: raise SkipFrameSignal(...)` → frame **quá tối** → bỏ CỐ Ý (mẩu 03), kèm lý do `too_dark (brightness=..)`.
  - `return packet` → đủ sáng → trả packet **nguyên vẹn** (stage này không thêm gì, chỉ lọc).

## 5. Là gì (1–2 câu)
`DarkFilterStage` là stage lọc: nếu độ sáng < ngưỡng → skip frame; nếu thiếu dữ liệu brightness (đặt
sai thứ tự) → báo lỗi rõ ràng. Nó minh hoạ cả hai nhánh `SKIPPED` và `ERROR`.

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (fail-fast khi sai thứ tự)
- **Vấn đề thứ tự stage:** `DarkFilterStage` phụ thuộc kết quả của `BrightnessStage`. Nếu ai đó ráp sai thứ tự (đặt filter trước) → không có artifact `brightness`.
- **Fix cái NGỌN (sai):** nếu thiếu brightness thì "cứ cho qua" (`return packet`) → frame tối lọt lưới **âm thầm**, sau này mới phát hiện sai → rất khó lần.
- **Fix tận GỐC (đã làm):** thiếu `brightness` → **`raise ValueError` ngay** (fail-fast) với thông điệp gợi ý nguyên nhân. Lỗi nổ ngay tại chỗ ráp sai, không trôi xuống cuối.
- **Skip vs Error tách bạch:** frame tối → `SkipFrameSignal` (bình thường); thiếu dữ liệu → `ValueError` (lỗi cấu hình). Nhờ mẩu 03 + `BaseStage`, hai ca ra hai status khác nhau (SKIPPED ≠ ERROR).

## 7. Dùng ở đâu trong project (cụ thể)
- `demo_pipeline` (mẩu 09): `DarkFilterStage(threshold=args.threshold)` đặt **SAU** `BrightnessStage()`.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_dark_filter_skips_below_threshold`: brightness=10 < 50 → `SKIPPED`, `"too_dark" in skip_reason`.
  - `test_dark_filter_passes_above_threshold`: brightness=200 ≥ 50 → `SUCCESS`.
  - `test_dark_filter_errors_without_brightness`: không có artifact → `ERROR`, `"brightness" in error_message.lower()`.
  - `test_executor_stops_on_error` (chỉ có mình `DarkFilterStage`): thiếu brightness → pipeline `ERROR`, `failed_stage == "dark_filter"`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Không fail-fast (thiếu brightness mà cứ cho qua): frame tối lọt → kết quả sai âm thầm, debug rất tốn công.
- Dùng `Exception` chung cho cả "tối" và "thiếu dữ liệu": không phân biệt skip với lỗi cấu hình → báo động sai cho frame tối.

## 9. Ví von đời thường
`DarkFilterStage` như **trạm kiểm tra cuối**: cần xem **số cân** (trạm trước ghi). Nếu món quá nhẹ →
loại (skip, đúng quy trình). Nếu **chưa có phiếu cân** (ai đó xếp trạm sai) → **bấm chuông báo ngay**,
không cho hàng trôi tiếp.

## 10. Liên kết bức tranh lớn
`DarkFilterStage` dùng artifact của `BrightnessStage` (mẩu 05) → minh hoạ "đầu ra stage này là đầu vào
điều kiện của stage kia" + tầm quan trọng của thứ tự (executor mẩu 07 chạy đúng thứ tự đã ráp). Phát ra
`SkipFrameSignal` (mẩu 03) / `ValueError`, `BaseStage` (mẩu 04) gói thành `StageResult` đúng status.

## 11. Cạm bẫy / lỗi thường gặp
- Đặt `DarkFilterStage` TRƯỚC `BrightnessStage` → thiếu artifact → ERROR (đúng như fail-fast cảnh báo).
- Sửa thành "thiếu brightness thì bỏ qua kiểm tra" → tái sinh bug "lọt âm thầm". Giữ fail-fast.
- Nhầm `threshold` (ngưỡng sáng) với giá trị pixel cụ thể — đây là so với **trung bình** frame.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: 3 nhánh của `_do_process` ra 3 kết cục gì (status nào)?
- Tình huống: ráp `DarkFilterStage` trước `BrightnessStage` → chuyện gì xảy ra, vì sao như vậy TỐT hơn "cho qua"?
- Giải thích lại bằng LỜI MÌNH: "DarkFilter skip khi ... ; báo lỗi khi ... ; vì sao tách 2 ca" (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại skip vs error trong stage này | 1 tuần → tự viết 1 filter-stage phụ thuộc artifact | 1 tháng → giải thích fail-fast vs lọt-âm-thầm.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/runtime/stages/dark_filter_stage.py` (đã ĐỌC nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm 3 test dark_filter + `test_executor_stops_on_error`). · Độ chắc: **cao**.
