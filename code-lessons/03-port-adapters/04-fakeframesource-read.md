# #03 · Mẩu 04: `FakeFrameSource.read` — sinh frame, EOF, inject_error, check setup

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/adapters/fake_frame_source.py` (method `read`) · tầng **adapters** ·
đây là trái tim adapter: mỗi lần gọi trả về 1 `ReadResult` đúng hợp đồng.

## 2. Cần biết trước
- [ndarray (numpy array)](../../knowledge-base/00-GLOSSARY.md#ndarray-numpy-array) ·
  [ReadResult](../02-data-objects/04-readresult-status.md)
- Mẩu 02 (hợp đồng: read trả ReadResult, không None) + mẩu 03 (khung Fake) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)

> **🖼 Sơ đồ luồng quyết định (nguồn Draw.io):** [fake-read-flow.drawio](diagrams/fake-read-flow.drawio) — `read()` theo thứ tự: setup → error → EOF → frame.
> Xem nhúng: Draw.io → **Export as → SVG** → lưu `diagrams/fake-read-flow.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

```python
# vision-platform/src/vision_platform/adapters/fake_frame_source.py  (trong class FakeFrameSource)
    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")

        if self.inject_error_at is not None and self._frame_count == self.inject_error_at:
            self.inject_error_at = None
            return ReadResult(
                status=ReadStatus.ERROR,
                error=RuntimeError("Injected fake error"),
                retry_after_ms=100,
            )

        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)

        frame = np.full(
            (self.height, self.width, 3),
            fill_value=self._frame_count % 256,
            dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)
```

## 4. Giải thích từng phần nhỏ nhất (đọc theo THỨ TỰ kiểm tra)
- `def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:` → trả `ReadResult` chứa `np.ndarray`. `timeout_ms` có ở đây cho đúng hợp đồng (nguồn giả không thực sự chờ).
- **(1) Chưa setup → lỗi:** `if not self._is_setup: raise RuntimeError("setup() must be called before read()")` → ép đúng điều khoản "setup trước read" (mẩu 02).
- **(2) Tiêm lỗi (nếu cấu hình):** `if self.inject_error_at is not None and self._frame_count == self.inject_error_at:` → tới đúng frame đã hẹn thì:
  - `self.inject_error_at = None` → tắt cờ (chỉ lỗi 1 lần).
  - `return ReadResult(status=ReadStatus.ERROR, error=RuntimeError("Injected fake error"), retry_after_ms=100)` → trả trạng thái ERROR kèm lỗi + gợi ý chờ 100ms.
- **(3) Hết frame → EOF:** `if self.max_frames is not None and self._frame_count >= self.max_frames: return ReadResult(status=ReadStatus.EOF)` → nguồn hữu hạn đã sinh đủ → báo hết.
- **(4) Sinh frame:** 
  - `frame = np.full((self.height, self.width, 3), fill_value=self._frame_count % 256, dtype=np.uint8)` → tạo ảnh `cao×rộng×3`, **mọi pixel = `frame_count % 256`** (đoán trước được). `np.full` = mảng điền cùng 1 giá trị; `% 256` để giữ trong 0..255 (kiểu `uint8`).
  - `self._frame_count += 1` → tăng đếm.
  - `return ReadResult(status=ReadStatus.FRAME, data=frame)` → trả frame.
- Thứ tự kiểm rất quan trọng: setup → error → EOF → frame.

## 5. Là gì (1–2 câu)
`read()` trả 1 `ReadResult` mỗi lần gọi, theo thứ tự ưu tiên: chưa setup thì lỗi, tới frame hẹn thì ERROR,
hết thì EOF, còn lại thì sinh 1 frame "đoán trước được".

## 6. Tại sao tồn tại / vấn đề nó giải
- **Frame đoán trước (`% 256`):** test cần dữ liệu xác định để assert (vd "frame 0 toàn số 0, frame 1 toàn số 1"). Random sẽ không assert nổi.
- **inject_error:** muốn test "pipeline xử lý ERROR thế nào" mà không cần lỗi thật → hẹn lỗi ở frame N.
- **EOF tường minh + check setup:** tuân đúng hợp đồng port (mẩu 02), để lõi xử lý nhất quán.

## 7. Dùng ở đâu trong project (cụ thể)
- Test thật (đã CHẠY pass — `pytest -k "fake_frame_content or fake_inject"` → **2 passed**):
  - `test_fake_frame_content_predictable`: frame 0 → `data[0,0,0] == 0`; frame 1 → `== 1` (đúng `% 256`).
  - `test_fake_inject_error`: với `inject_error_at=2` → read 2 lần FRAME, lần 3 **ERROR** (`"Injected" in str(r.error)`), lần 4 lại FRAME (cờ đã tắt).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Sinh frame ngẫu nhiên: không assert được nội dung → test yếu.
- Không có đường ERROR/EOF: không test được nhánh lỗi/hết của pipeline → bug nhánh hiếm lọt ra production.

## 9. Ví von đời thường
`read()` như **máy phát mẫu thử theo kịch bản**: phát N tấm ảnh có đánh số sẵn (đoán trước), tới tấm đã
hẹn thì cố tình "lỗi" để xem dây chuyền phản ứng ra sao, hết thì báo "hết hàng" (EOF).

## 10. Liên kết bức tranh lớn
Đây là phần hiện thực điều khoản (2) của hợp đồng (mẩu 02): luôn trả `ReadResult` với `status` rõ ràng.
Bài #04 (pipeline) tiêu thụ chuỗi `ReadResult` này; nhánh ERROR/EOF/SKIP sẽ được executor xử lý.

## 11. Cạm bẫy / lỗi thường gặp
- Quên `setup()` → `read()` raise `RuntimeError` (cố ý, đúng hợp đồng).
- Tưởng `inject_error` lỗi mãi → KHÔNG, nó tự tắt sau 1 lần (`inject_error_at = None`).
- Quên `% 256` với `uint8`: khi `frame_count ≥ 256` (nguồn vô hạn chạy lâu), `np.full(fill_value=256, dtype=np.uint8)` **raise `OverflowError`** ("Python integer 256 out of bounds for uint8" — đã CHẠY kiểm numpy 2.4.6), KHÔNG phải lặng lẽ wrap. `% 256` giữ giá trị trong 0..255 nên an toàn. (Với `max_frames` mặc định 100 thì chưa tới 256 — `%256` ở đây là phòng thủ cho nguồn vô hạn.)

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: thứ tự 4 bước kiểm trong `read()`? Vì sao frame phải "đoán trước được"?
- Tình huống: `FakeFrameSource(max_frames=3)` — gọi `read()` 4 lần ra các status nào?
- Giải thích lại bằng LỜI MÌNH: "read() trả ... theo thứ tự ... ; %256 để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 4 bước trong read | 1 tuần → tự viết 1 nguồn giả sinh frame đoán trước | 1 tháng → giải thích vì sao test cần dữ liệu xác định.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/adapters/fake_frame_source.py` (đã ĐỌC LẠI nguyên văn `read`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest -k "fake_frame_content or fake_inject"` → **2 passed** (frame đoán trước + inject_error). · Độ chắc: **cao**.
