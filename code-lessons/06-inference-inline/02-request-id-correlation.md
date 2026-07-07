# Mẩu 02 — `request_id`: khớp yêu cầu ↔ kết quả khi thứ tự bị đảo

**(1) Thuộc về đâu:** trường `request_id` trong `InferenceRequest`/`InferenceResponse` (kernel) + test
`test_inline_client_correlates_request_id`. Đây là **pattern lõi** của bài #06.

**(2) Cần biết trước:** async là gì (glossary `#async` — làm việc không chờ tuần tự); batch (gộp lô).

**(3) Code thật (quote `tests/test_step_06_inference.py`):**
```python
def test_inline_client_correlates_request_id(ring):
    """Nhiều request → mỗi response.request_id phải khớp request.request_id (correlation)."""
    ...
    for i, ref in enumerate(refs):
        req = InferenceRequest(request_id=f"req_{i}", source_id="cam1", frame_ref=ref)
        resp = client.infer(req)
        assert resp.request_id == f"req_{i}"   # correlation đảm bảo
```

**(4) Giải thích từng ý nhỏ:**
- `request_id=f"req_{i}"` → mỗi yêu cầu có **mã riêng** ("req_0", "req_1", "req_2").
- `resp.request_id == f"req_{i}"` → response phải mang **đúng mã** của request tương ứng. Test này là
  bằng chứng "không nhận nhầm kết quả".

**(5) Là gì:** `request_id` = mã định danh duy nhất cho mỗi yêu cầu; response *echo* (lặp lại) mã đó để
người gọi biết kết quả này là của yêu cầu nào.

**(6) Tại sao tồn tại / vấn đề nó giải:** (nỗi đau A ở cau-chuyen) inference async + gộp lô → response
có thể về **không đúng thứ tự** gửi. Kịch bản bug nếu THIẾU mã:
- cam1 gửi t=0, cam2 gửi t=1; GPU xử cam2 xong trước → trả cam2 rồi cam1.
- Không mã → cam1 vớ phải kết quả cam2 → **tracking lệch khắp nơi**.
Có mã → mỗi bên khớp qua bản đồ `request_id → chỗ chờ`, lấy đúng của mình.

**(7) Dùng ở đâu trong project:** `InlineInferenceClient.infer` set `response.request_id =
request.request_id` (mẩu 10). Bản inline trả ngay nên "đảo thứ tự" chưa xảy ra, nhưng **API đã sẵn**
mã để bản ZMQ (async thật) dùng y nguyên.

**(8) Không có nó thì sao:** không thể ghép response về đúng camera/frame khi có nhiều luồng → hệ vô
dụng lúc tải cao (đúng lúc cần nhất).

**(9) Ví von:** số thứ tự ở quầy bánh mì. Bạn lấy số 27; dù bánh của người số 30 ra trước, bạn vẫn chỉ
nhận khi gọi "số 27". Không có số → ai nhanh tay thì vớ nhầm ổ của người khác.

**(10) Liên kết bức tranh lớn:** đây là "hợp đồng" giữa camera-side và inference-side, độc lập
transport (inline/ZMQ). Là lý do `request_id` nằm ở **cả** request lẫn response (mẩu 03, 06).

**(11) Cạm bẫy:** đừng dựa "gửi trước nhận trước" để bỏ mã — đó chính là giả định vỡ khi batch. Mã
phải **duy nhất** (thường UUID) để không hai request trùng mã.

**(12) Tự kiểm:**
- Kể một kịch bản cụ thể mà thiếu `request_id` sẽ gây kết quả sai.
- Vì sao bản inline (trả ngay) vẫn nên giữ `request_id`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_step_06_inference.py::test_inline_client_correlates_request_id` (9 passed) ·
Design step-06 (phần "request_id correlation" + Self-check #1). Độ chắc: cao (test thật).
