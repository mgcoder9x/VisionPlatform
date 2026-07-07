# #04 · Mẩu 03: `SkipFrameSignal` — exception để BỎ frame một cách CỐ Ý

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` · tầng **kernel** ·
đây là "tín hiệu" một stage phát ra khi muốn **bỏ qua** frame (không phải lỗi).

## 2. Cần biết trước
- [result object](../../knowledge-base/00-GLOSSARY.md#result-object-đối-tượng-kết-quả) ·
  [stage (bước xử lý)](../../knowledge-base/00-GLOSSARY.md#stage-bước-xử-lý)
- Mẩu 01 (`StageStatus.SKIPPED` vs `ERROR`) — đọc trước; `SkipFrameSignal` chính là thứ map thành `SKIPPED`.
- `Exception` của Python: lớp nền cho **hầu hết** các lỗi bắt được (gốc thật là `BaseException`); `raise` để phát, `except` để bắt.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/stage_contract.py
class SkipFrameSignal(Exception):
    """Stage raises this to skip frame intentionally (motion gate, ROI filter)."""
    pass
```

## 4. Giải thích từng phần nhỏ nhất
- `class SkipFrameSignal(Exception):` → định nghĩa một loại exception MỚI, **kế thừa** `Exception`.
- `"""..."""` docstring nói rõ mục đích: stage `raise` cái này để **bỏ frame CỐ Ý** (vd cổng chuyển động `motion gate`, lọc vùng quan tâm `ROI filter`).
- `pass` → thân lớp trống: không thêm trường/method gì, chỉ cần **một cái TÊN riêng** để phân biệt với lỗi thật.

## 5. Là gì (1–2 câu)
`SkipFrameSignal` là một exception "tên riêng" để stage báo "tôi cố ý bỏ frame này", khác hẳn với
exception lỗi (`ValueError`, `RuntimeError`...). Có tên riêng nên `BaseStage` bắt được nó **tách bạch**.

## 6. Tại sao tồn tại / vấn đề nó giải
"Bỏ frame" là chuyện **bình thường** (frame tối, không có chuyển động) — KHÔNG phải lỗi. Nhưng cả hai
đều cần "dừng xử lý frame này giữa chừng". Nếu dùng chung một loại exception (vd `raise Exception(...)`)
thì không phân biệt được "bỏ cố ý" với "hỏng thật" → đếm nhầm, báo động nhầm.
- **Fix tận GỐC:** tạo MỘT loại exception riêng (`SkipFrameSignal`). `BaseStage.process()` (mẩu 04)
  bắt **nó** trước → `SKIPPED`; bắt `Exception` còn lại → `ERROR`. Phân biệt nằm ở **loại exception**, không phải ở chuỗi thông điệp (dễ vỡ).

## 7. Dùng ở đâu trong project (cụ thể)
- **Phát ra:** `DarkFilterStage._do_process` (mẩu 06) → `raise SkipFrameSignal(f"too_dark (brightness={brightness:.2f})")` khi frame tối.
- **Bắt:** `BaseStage.process` (mẩu 04) → `except SkipFrameSignal as e: return StageResult.skipped(reason=str(e), ...)`.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_dark_filter_skips_below_threshold`: frame value=10 → `result.status == SKIPPED`, `"too_dark" in result.skip_reason`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Dùng chung `Exception` cho cả "bỏ" và "lỗi": `BaseStage` không biết đường nào là skip → hoặc coi mọi
thứ là lỗi (báo động sai cho frame tối), hoặc phải đoán qua nội dung chuỗi (mong manh, đổi chữ là vỡ).
`SkipFrameSignal` là "bản chất": phân biệt bằng **kiểu**, máy kiểm chắc chắn.

## 9. Ví von đời thường
Trên dây chuyền: công nhân **giơ thẻ XANH "bỏ qua sản phẩm này"** (cố ý, đúng quy trình) khác hẳn
**chuông ĐỎ "máy hỏng"**. Cùng là "dừng xử lý món này" nhưng ý nghĩa và cách phản ứng khác nhau hoàn toàn.

## 10. Liên kết bức tranh lớn
`SkipFrameSignal` (kernel) là cầu nối giữa "stage muốn bỏ" và `StageStatus.SKIPPED` (mẩu 01). Nó để
`BaseStage` (mẩu 04 — Template Method) **dịch** ý định của lớp con thành result-object đúng status.

## 11. Cạm bẫy / lỗi thường gặp
- Dùng `raise Exception("skip")` thay vì `SkipFrameSignal` → `BaseStage` bắt vào nhánh `Exception` → bị đếm là ERROR (báo động sai).
- Nhầm "skip" với "lỗi": skip = đúng quy trình, không cần alert; error = cần đếm/cảnh báo.
- Thêm logic nặng vào `SkipFrameSignal` → thừa: nó chỉ cần là một cái tên.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao "bỏ frame" cần một exception RIÊNG thay vì dùng `Exception` chung?
- Tình huống: `DarkFilterStage` gặp frame tối — nó raise gì? `BaseStage` biến nó thành status nào?
- Giải thích lại bằng LỜI MÌNH: "SkipFrameSignal để ... ; khác lỗi thật ở ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại skip ≠ error + ai raise / ai bắt | 1 tuần → tự thiết kế signal-exception cho việc khác | 1 tháng → giải thích vì sao phân biệt bằng KIỂU tốt hơn bằng chuỗi.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/stage_contract.py` (đã ĐỌC nguyên văn `SkipFrameSignal`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm `test_dark_filter_skips_below_threshold`). · Độ chắc: **cao**.
