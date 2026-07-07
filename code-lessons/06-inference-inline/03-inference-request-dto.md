# Mẩu 03 — `InferenceRequest`: vé nhúng thẳng `ShmFrameRefData` (E-06-2)

**(1) Thuộc về đâu:** `kernel/inference_protocol.py`, class `InferenceRequest`. Layer kernel (DTO thuần).

**(2) Cần biết trước:** `ShmFrameRefData` là gì (bài #05: DTO chỉ vị trí frame trong SHM, gồm cả
`ring_epoch`); `@dataclass(frozen=True)` (glossary `#dataclass`, `#frozen` — vật dữ liệu bất biến);
`ring_epoch` (bài #05b: số thế hệ ring, tăng mỗi lần switchover).

**(3) Code thật (quote `kernel/inference_protocol.py`):**
```python
@dataclass(frozen=True)
class InferenceRequest:
    """Request gửi từ camera process → inference service.

    `frame_ref` là ShmFrameRefData ĐẦY ĐỦ (ring_name/slot/generation/ring_epoch/H/W/C) —
    1 nguồn sự thật về vị trí frame trong SHM. Không lặp lại field rời (tránh lệch dữ liệu).
    """
    request_id: str          # UUID — correlation key (khoá để match response)
    source_id: str           # camera_id (logging/routing)
    frame_ref: ShmFrameRefData
```

**(4) Giải thích từng dòng:**
- `@dataclass(frozen=True)` → tạo class dữ liệu, **bất biến** (gán lại field sẽ nổ lỗi). Request là
  "tấm vé" — không nên sửa sau khi phát.
- `request_id: str` → mã correlation (mẩu 02).
- `source_id: str` → camera nào gửi (để log/định tuyến), không ảnh hưởng đọc frame.
- `frame_ref: ShmFrameRefData` → **nhúng thẳng** DTO vị trí frame của #05. Đây là điểm cốt lõi
  (E-06-2): thay vì chép rời `slot`, `generation`, `ring_epoch`... ta giữ **nguyên một khối**.

**(5) Là gì:** DTO "tấm vé" camera gửi cho inference: mã yêu cầu + nguồn + con trỏ tới frame trong SHM.

**(6) Tại sao tồn tại / vấn đề nó giải:** hai vấn đề gộp:
- correlation (mẩu 02) → cần `request_id`.
- **stale-epoch** (nỗi đau B) → cần `ring_epoch`. Design gốc chỉ có `shm_generation`, thiếu epoch →
  sau switchover có thể đọc nhầm frame. Nhúng cả `ShmFrameRefData` giải trọn: vé tự mang `ring_epoch`,
  client gọi `read_ref` để kiểm (mẩu 10).

**(7) Dùng ở đâu trong project:** test dựng `InferenceRequest(request_id=..., source_id="cam1",
frame_ref=ref)` với `ref` do `ShmFrameWriter.write` trả về (mẩu 11). Client đọc `request.frame_ref`.

**(8) Không có field `frame_ref` (hoặc để field rời thiếu epoch) thì sao:** thiếu `ring_epoch` → mất
lá chắn stale sau switchover (đọc nhầm frame ring mới). Chép field rời → dễ **lệch dữ liệu** (sửa
`ShmFrameRefData` mà quên sửa request).

**(9) Ví von:** vé gửi xe có sẵn cả **số ô + mã bãi + "đợt" gửi**. Nếu bãi vừa làm lại sơ đồ (đổi
"đợt"), vé đợt cũ sẽ không mở nhầm ô đợt mới — vì trên vé ghi rõ đợt.

**(10) Liên kết bức tranh lớn:** `InferenceRequest` là biên giới giữa camera-side và inference-side.
Nhúng `ShmFrameRefData` = tái dùng "một nguồn sự thật" của #05, nối #06 khớp #05b.

**(11) Cạm bẫy (ERRATA E-06-2):** Design gốc dùng field rời `shm_ring_name/shm_slot/shm_generation`
KHÔNG có epoch — ta đã sửa. Đừng quay lại kiểu field rời khi lên ZMQ; chỉ cần serialize khối
`ShmFrameRefData` (msgpack lồng được).

**(12) Tự kiểm:**
- Vì sao nhúng `ShmFrameRefData` an toàn hơn chép `slot/generation` rời?
- `ring_epoch` trong vé chống được bug gì? (nối bài #05b)

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/inference_protocol.py` (class InferenceRequest) · `kernel/shm_frame_ref.py`
(ShmFrameRefData, #05) · Design step-06 ERRATA E-06-2 · journal C-007/D-023. Độ chắc: cao (quote thật).
