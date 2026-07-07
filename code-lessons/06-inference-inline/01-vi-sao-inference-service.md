# Mẩu 01 — Vì sao cần tầng inference (và vì sao "vé mỏng" thay vì gửi cả frame)

**(1) Thuộc về đâu:** Bức tranh tổng của bài #06 — tầng inference nối sau SHM ring (#05). Chưa vào 1
file cụ thể; đây là "móc treo" để các mẩu sau gắn vào.

**(2) Cần biết trước:** SHM ring là gì (bài #05 + `knowledge-base/00-GLOSSARY.md#shm`); tiến trình
(process) là gì (glossary `#process`); DTO là gì (`#dto` — vật mang dữ liệu thuần, không hành vi).

**(3) Code thật (quote docstring `application/inline_inference_client.py`):**
```python
"""InlineInferenceClient — inference cùng process (no IPC), dùng cho dev/test.
...
Production Vision Platform dùng AsyncInferenceClient qua ZMQ ROUTER/DEALER (sub-spec riêng, hoãn).
Pattern GIỮ NGUYÊN: request_id correlation + InferenceResponse echo request_id. Chỉ khác transport.
"""
```

**(4) Giải thích từng ý nhỏ:**
- "inference cùng process (no IPC)" → bản bài này chạy detector **trong cùng tiến trình** với người
  gọi, không qua liên-tiến-trình (IPC). Đơn giản để học.
- "Production ... ZMQ ROUTER/DEALER ... hoãn" → bản thật sẽ tách sang tiến trình riêng qua ZMQ (thư
  viện gửi tin giữa các tiến trình). Ta **chưa làm** ở #06 (xem nhịp 4 cau-chuyen).
- "Pattern GIỮ NGUYÊN: request_id correlation" → dù inline hay ZMQ, **cách khớp yêu cầu–kết quả là
  một** (mẩu 02). Học inline = học sẵn cho ZMQ.

**(5) Là gì:** Tầng inference = bộ phận nhận "yêu cầu phát hiện vật thể trên 1 frame" và trả "danh
sách vật phát hiện được". Bản #06 là bản *inline* (cùng process).

**(6) Tại sao tồn tại / vấn đề nó giải:** hệ thị giác cần biết *trong frame có gì*. Việc này nặng (chạy
mô hình AI) nên trong sản phẩm thật thường tách riêng để **cách ly sự cố** (detector crash không kéo
sập camera) và **gộp lô GPU**. Bản inline là bước học pattern trước khi lên bản tách tiến trình.

**(7) Dùng ở đâu trong project:** `InlineInferenceClient.infer(request)` — người gọi (composition
root / test) tạo `InferenceRequest` từ ref mà `ShmFrameWriter.write` trả về, rồi nhận `InferenceResponse`.

**(8) Không có nó thì sao:** có ảnh trong SHM nhưng **không biết trong ảnh có gì** → hệ chỉ là bộ
truyền khung hình, chưa phải hệ thị giác.

**(9) Ví von:** như quầy giặt là. Bạn không mang cả tủ quần áo tới (gửi cả frame) — bạn đưa **phiếu**
ghi "đồ ở ngăn số 5" (`frame_ref`) kèm **số thứ tự phiếu** (`request_id`). Thợ lấy đồ ở ngăn đó, giặt,
trả kèm đúng số phiếu để bạn nhận đúng đồ của mình.

**(10) Liên kết bức tranh lớn:** nằm cuối chuỗi camera → pipeline → SHM → **inference**. DTO/port ở
`kernel`, detector giả ở `adapters`, client ở `application` (mẩu 03–10).

**(11) Cạm bẫy:** đừng nghĩ "inline nghĩa là bỏ SHM cho nhanh". Ta CỐ Ý giữ đọc qua SHM để API giống
production (xem self-check #5 trong Design step-06) — đổi transport sau không phải sửa logic.

**(12) Tự kiểm (retrieval + Feynman):**
- Vì sao camera gửi "vé" (`frame_ref` + `request_id`) chứ không gửi cả mảng pixel?
- Nói bằng lời của bạn: "inline" khác "ZMQ" ở đâu, và cái gì GIỮ NGUYÊN giữa hai bản?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `vision-platform/src/vision_platform/application/inline_inference_client.py` (docstring,
trạng thái #06 PHA 2) · Design `module-03-build-along/step-06-add-inference.md` (Mục tiêu + ERRATA).
Độ chắc: cao (quote docstring thật + test 9 passed).
