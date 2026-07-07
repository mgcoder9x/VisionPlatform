# Bài #06 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung: correlation + stale-epoch → giải pháp). Rồi tới các mẩu dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + code verify. Cột Feynman = riêng (người học tự chốt).
> Bám code thật (trạng thái #06 PHA 2 xong): full **261 passed/1 skipped** · lint **5 kept/0 broken** ·
> `tests/test_step_06_inference.py` **9 passed**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-inference-service.md` | Bức tranh: camera → SHM → inference; vé mỏng thay vì gửi cả frame; inline giờ / ZMQ sau | `application/inline_inference_client.py` (docstring) | ✅ |
| 02 | `02-request-id-correlation.md` | **Nỗi đau A**: response async đảo thứ tự → cần `request_id` để khớp; kịch bản bug nếu thiếu | `inference_protocol.py` (InferenceRequest.request_id) + test correlation | ✅ |
| 03 | `03-inference-request-dto.md` | `InferenceRequest` NHÚNG `frame_ref: ShmFrameRefData` (E-06-2) — vì sao nhúng thay vì field rời | `kernel/inference_protocol.py` | ✅ |
| 04 | `04-detection-bbox-space.md` | `Detection{label, confidence, box: BBox}`; box mang `CoordinateSpace` (invariant Step 02) | `kernel/inference_protocol.py` + `domain/bbox.py` | ✅ |
| 05 | `05-inference-error-string-only.md` | `InferenceError{error_type, error_message, retryable}` — CHỈ chuỗi, không giữ Exception; `retryable` | `kernel/inference_protocol.py` | ✅ |
| 06 | `06-inference-response-is-success.md` | `InferenceResponse` echo `request_id` + property `is_success`; freeze list→tuple | `kernel/inference_protocol.py` | ✅ |
| 07 | `07-idetector-port.md` | `IDetector` Protocol (setup/detect/teardown) — cổng driven, cùng pattern IFrameSource | `kernel/ports/detector.py` | ✅ |
| 08 | `08-fake-detector-adapter.md` | `FakeDetector` (lá adapter): deterministic confidence=brightness/255; fail-fast chưa setup | `adapters/fake_detector.py` | ✅ |
| 09 | `09-inline-client-o-dau.md` | **E-06-1**: vì sao client ở `application/` chứ KHÔNG `adapters/` (contract cấm adapters→runtime) | `application/inline_inference_client.py` + `pyproject.toml` contract #4/#5 | ✅ |
| 10 | `10-infer-luong-readref.md` | Luồng `infer()`: `read_ref` (stale-check) → None→error; detect→bọc Exception thành string | `application/inline_inference_client.py` | ✅ |
| 11 | `11-tests-9-correlation-stale.md` | 9 test: 3 detector / 3 DTO / 3 client (correlation + stale-epoch chứng minh F-2) | `tests/test_step_06_inference.py` | ✅ |

> ✅ **ĐỦ 11/11 MẨU** — quote nguyên văn code + neo test đã pass (9 passed, full 261/1 skipped).
> Mỗi mẩu theo template 14 mục (LESSON-RULES §4). Không dán lesson vào chat.
> **Cổng Feynman:** người học tự giải thích lại (bạn học sau — theo yêu cầu). AI KHÔNG tự chấm "đã hiểu".
> Sơ đồ (tùy chọn, chưa làm): luồng request/response correlation + chỗ đặt file theo layer.
