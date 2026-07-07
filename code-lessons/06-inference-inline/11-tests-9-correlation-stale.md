# Mẩu 11 — 9 test: chứng minh correlation + stale-epoch (F-2)

**(1) Thuộc về đâu:** `tests/test_step_06_inference.py`. Đây là "bằng chứng" mọi khẳng định ở mẩu 01–10.

**(2) Cần biết trước:** pytest fixture (glossary `#fixture` — dựng sẵn tài nguyên cho test);
`dataclasses.replace` (tạo bản sao DTO đổi 1 field); `pytest.approx` (so sánh số thực gần đúng).

**(3) Code thật — hai test cốt lõi (quote `tests/test_step_06_inference.py`):**

Test stale-epoch (chứng minh F-2):
```python
def test_inline_client_stale_epoch_ref_returns_error(ring):
    """F-2: ref mang ring_epoch cũ (khác epoch ring hiện tại) → read_ref None → error response."""
    ...
    ref = writer.write(_frame(50))
    assert ref is not None
    # Giả lập ref stale: epoch cũ hơn ring hiện tại (ring epoch mặc định = 1 → dùng 0).
    stale_ref = dataclasses.replace(ref, ring_epoch=ref.ring_epoch - 1)
    req = InferenceRequest(request_id="req_stale", source_id="cam1", frame_ref=stale_ref)
    resp = client.infer(req)
    assert resp.is_success is False
    assert resp.error.error_type == "ShmReadFailed"
    assert resp.request_id == "req_stale"
```

Test correlation:
```python
    for i, ref in enumerate(refs):
        req = InferenceRequest(request_id=f"req_{i}", source_id="cam1", frame_ref=ref)
        resp = client.infer(req)
        assert resp.request_id == f"req_{i}"   # correlation đảm bảo
        assert resp.is_success is True
```

**(4) Giải thích từng ý nhỏ:**
- `stale_ref = dataclasses.replace(ref, ring_epoch=ref.ring_epoch - 1)` → tạo vé y hệt nhưng epoch
  **cũ hơn 1** → giả lập "ref của thế hệ trước switchover".
- `resp.is_success is False` + `error_type == "ShmReadFailed"` → `read_ref` phát hiện epoch lệch →
  trả None → client trả lỗi. **Đây là bằng chứng F-2 hoạt động thật.**
- Vòng lặp correlation: 3 vé mã khác nhau → mỗi response khớp đúng mã.

**(5) Là gì:** bộ 9 test = 3 detector + 3 DTO + 3 client (end-to-end / stale / correlation).

**(6) Tại sao tồn tại / vấn đề nó giải:** biến các khẳng định ("stale bị chặn", "mã khớp") thành
**bằng chứng chạy được** — theo luật §5 (code = chạy test thật mới gọi "xong").

**(7) Dùng ở đâu / kết quả thật:** `pytest tests/test_step_06_inference.py -q` → **9 passed**; full
suite **261 passed, 1 skipped**; `lint-imports` **5 kept, 0 broken**.

**(8) Không có test này thì sao:** không có gì chứng minh F-2 (stale-check) thực sự chặn — chỉ là
"đọc code thấy đúng" = CHƯA verify (luật §5). Correlation cũng chỉ là niềm tin.

**(9) Ví von:** thử vé hết hạn ở cổng thật xem máy có từ chối không — thay vì tin lời "chắc máy chặn".

**(10) Liên kết bức tranh lớn:** test stale nối thẳng #05b (switchover epoch); test correlation nối
pattern lõi #06. Đây là nơi #05 và #06 gặp nhau và được kiểm chứng.

**(11) Cạm bẫy:** ring mặc định `ring_epoch=1` (không phải 0) — nên test giả lập stale bằng
`ref.ring_epoch - 1` (=0), không hard-code. `dataclasses.replace` chỉ được vì DTO frozen (bất biến).

**(12) Tự kiểm:**
- Test stale chứng minh điều gì về tích hợp #06↔#05b?
- Nếu bỏ kiểm `ring_epoch` trong `read_ref`, test nào sẽ đỏ?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_step_06_inference.py` (9 test, đã chạy pass) · Design step-06 (Phần 5
Tests). Độ chắc: cao (output pytest thật: 9 passed / full 261 passed, 1 skipped).
