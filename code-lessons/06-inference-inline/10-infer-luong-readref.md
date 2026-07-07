# Mẩu 10 — Luồng `infer()`: `read_ref` (stale-check) → detect → bọc lỗi

**(1) Thuộc về đâu:** `application/inline_inference_client.py`, method `infer`. Đây là "trái tim" bài #06.

**(2) Cần biết trước:** `read_ref` của `ShmFrameReader` (#05: đọc theo `ShmFrameRefData`, tự kiểm
`ring_epoch` — ref epoch cũ → trả None); `try/except` (bắt lỗi); mẩu 03/05/06 (các DTO).

**(3) Code thật (quote `application/inline_inference_client.py`):**
```python
def infer(self, request: InferenceRequest) -> InferenceResponse:
    # 1. Đọc frame từ SHM qua read_ref (tự kiểm gen + ring_epoch stale — P0-3/F-2).
    frame = self._reader.read_ref(request.frame_ref)

    if frame is None:
        ref = request.frame_ref
        return InferenceResponse(
            request_id=request.request_id,
            error=InferenceError(
                error_type="ShmReadFailed",
                error_message=(
                    f"slot {ref.slot} gen {ref.generation} epoch {ref.ring_epoch} "
                    "not readable (overwritten / stale-epoch / wrong state)"
                ),
                retryable=False,
            ),
        )

    # 2. Detect. Exception → bọc thành InferenceError (chỉ string, không giữ Exception gốc).
    try:
        dets = self._detector.detect(frame)
        return InferenceResponse(
            request_id=request.request_id,
            detections=tuple(dets),   # freeze list → tuple ở biên DTO
        )
    except Exception as e:
        return InferenceResponse(
            request_id=request.request_id,
            error=InferenceError(
                error_type=type(e).__qualname__,
                error_message=str(e),
                retryable=False,
            ),
        )
```

**(4) Giải thích từng bước:**
- `frame = self._reader.read_ref(request.frame_ref)` → đọc frame từ SHM **qua ref đầy đủ**. `read_ref`
  tự kiểm `ring_epoch`: ref epoch cũ (sau switchover) → trả `None` (không đọc nhầm frame ring mới).
- `if frame is None:` → đọc thất bại (bị ghi đè / stale-epoch / sai trạng thái) → trả
  `InferenceResponse` mang `InferenceError("ShmReadFailed", retryable=False)`, **vẫn echo `request_id`**.
- `dets = self._detector.detect(frame)` → chạy detector (qua port).
- `detections=tuple(dets)` → **đóng băng** list thành tuple ở biên DTO (bất biến).
- `except Exception as e:` → mọi lỗi detect → bọc thành `InferenceError` **chỉ chuỗi**
  (`type(e).__qualname__`, `str(e)`), không giữ Exception gốc (mẩu 05).
- Cả 3 nhánh (đọc lỗi / ok / detect lỗi) đều trả response mang `request_id` → correlation luôn đảm bảo.

**(5) Là gì:** hàm điều phối 1 yêu cầu inference: đọc frame an toàn → detect → trả response chuẩn.

**(6) Tại sao tồn tại / vấn đề nó giải:** gói 3 rủi ro vào một luồng an toàn: (a) frame biến mất/stale
→ báo lỗi chứ không crash; (b) detector ném lỗi → không kéo sập; (c) mọi kết cục vẫn correlate được.

**(7) Dùng ở đâu:** test end-to-end (`test_inline_client_end_to_end`), stale (`..._stale_epoch_ref...`),
correlation (`..._correlates_request_id`) — mẩu 11.

**(8) Không có `read_ref` (dùng `read(slot, gen)` trần) thì sao:** mất kiểm `ring_epoch` → sau
switchover đọc nhầm frame. Không `try/except` → detector lỗi làm sập client.

**(9) Ví von:** nhân viên quầy: kiểm vé còn hạn (đúng đợt gửi) trước khi lấy đồ; đồ hỏng thì ghi biên
bản (error) chứ không bỏ chạy; luôn dán lại đúng số phiếu (request_id) khi trả.

**(10) Liên kết bức tranh lớn:** đây là chỗ #06 **ăn khớp #05b**: `read_ref` là lá chắn switchover.
Client (application) gọi reader (runtime) + detector (port) — đúng hướng phụ thuộc.

**(11) Cạm bẫy:** đừng `except` rồi nuốt lặng (phải trả error DTO). Đừng quên set `request_id` ở nhánh
lỗi (mất correlation). `tuple(dets)` cần thiết vì DTO nên bất biến.

**(12) Tự kiểm:**
- Kể 3 nhánh kết cục của `infer` và mỗi nhánh trả gì.
- Vì sao dùng `read_ref` chứ không `read(slot, generation)`? (nối #05b)

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/inline_inference_client.py` (infer) · `runtime/ipc/shm_frame_ring.py`
(`read_ref`, #05) · test #06. Độ chắc: cao (quote thật + 9 test pass).
