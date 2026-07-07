# #03 · Mẩu 02: Hợp đồng `IFrameSource` — 5 điều khoản + idempotent + "read trả ReadResult, không None"

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/kernel/ports/frame_source.py` (docstring Contract) +
`tests/test_step_03_frame_source_contract.py` (test ép hợp đồng) · tầng **kernel** + **tests**.

## 2. Cần biết trước
- [Protocol](../../knowledge-base/00-GLOSSARY.md#protocol-typingprotocol) ·
  [ReadResult](../02-data-objects/04-readresult-status.md) ·
  [fixture](../../knowledge-base/00-GLOSSARY.md#fixture-pytest)
- Mẩu 01 (IFrameSource là Protocol) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/ports/frame_source.py  (docstring của IFrameSource)
    """Inbound source of frames (np.ndarray).

    Contract:
        - setup() MUST be called before first read(). Idempotent.
        - read(timeout_ms) returns ReadResult — KHÔNG return None.
        - teardown() releases resources. Idempotent.
        - is_finite True for batch (file ends → EOF), False for stream.
        - source_id unique cho logging/metrics.
    """
```

## 4. Giải thích từng điều khoản (nhỏ nhất)
- **(1) `setup()` MUST be called before first `read()`. Idempotent.** → phải khởi tạo trước khi đọc; gọi `setup()` nhiều lần KHÔNG lỗi (idempotent = gọi lại an toàn, kết quả như gọi 1 lần).
- **(2) `read(timeout_ms)` returns ReadResult — KHÔNG return None.** → luôn trả gói `ReadResult` (mẩu #02-04) kèm `status` rõ ràng; cấm trả `None` mơ hồ.
- **(3) `teardown()` releases resources. Idempotent.** → dọn tài nguyên; gọi nhiều lần cũng an toàn.
- **(4) `is_finite` True cho batch (file hết → EOF), False cho stream.** → đánh dấu nguồn HỮU HẠN (video file: hết là EOF, đúng) hay VÔ HẠN (camera stream: EOF là bất thường).
- **(5) `source_id` unique** → mỗi nguồn 1 mã riêng để log/đo (chi tiết + bug E-13 ở mẩu 05).
- *idempotent* = tính chất "làm lại nhiều lần ra cùng kết quả, không gây hại" (vd bấm nút thang máy 5 lần cũng chỉ gọi 1 chuyến).

## 5. Là gì (1–2 câu)
Đây là **bộ luật** mọi nguồn frame phải tuân: khởi tạo trước khi đọc, đọc luôn trả trạng thái rõ ràng,
dọn được, khai báo hữu hạn/vô hạn, có mã riêng. Docstring nêu luật; contract test ép luật.

## 6. Tại sao tồn tại / vấn đề nó giải
Có hợp đồng thì lõi pipeline dùng BẤT KỲ nguồn nào theo cùng một cách, không cần biết nguồn cụ thể.
Quan trọng: hợp đồng chỉ là chữ — phải có **contract test** kiểm, nếu không adapter dễ "lách" (vd quên
idempotent, hoặc trả None) → lõi vỡ khi gặp adapter ẩu. Test biến luật thành thứ kiểm được.

## 7. Dùng ở đâu trong project (cụ thể)
Mỗi điều khoản có test ép tương ứng trong `TestFrameSourceContract` (đã CHẠY pass):
- (1) idempotent setup → `test_setup_idempotent` (gọi `setup()` lần 2 không raise).
- (2) read trả ReadResult, status hợp lệ → `test_read_returns_readresult` (`hasattr(result,"status")`), `test_first_read_returns_valid_status` (status ∈ 6 loại).
- (2b) FRAME thì có data, non-FRAME thì không → `test_frame_status_implies_data` (`isinstance(data, np.ndarray)`, `ndim==3`), `test_non_frame_status_no_data`.
- (3) idempotent teardown → `test_teardown_idempotent`.
- (4) is_finite bool + batch eventually EOF → `test_is_finite_is_bool`, `test_finite_source_eventually_eofs`.
- (5) source_id là chuỗi không rỗng → `test_source_id_is_str`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Không hợp đồng + không contract test: mỗi adapter tự do hành xử (nguồn A trả None, nguồn B ném exception,
nguồn C quên setup vẫn đọc) → lõi phải xử lý từng ngoại lệ, dễ vỡ. Hợp đồng + test ép mọi adapter đồng nhất.

## 9. Ví von đời thường
Hợp đồng như **bộ quy chuẩn an toàn cho thiết bị điện**: mọi nhà sản xuất phải đạt (phích đúng chuẩn,
chống giật...). Contract test = **khâu kiểm định**: chưa đạt thì không cho bán. Người mua (lõi) yên tâm dùng.

## 10. Liên kết bức tranh lớn
Hợp đồng này nối port (mẩu 01) với 2 adapter (mẩu 03–06). Điều khoản (2) chính là lý do bài #02 tạo
`ReadResult` (trạng thái tường minh). Contract test (mẩu 07) là "trọng tài" ép cả 2 adapter tuân luật.

## 11. Cạm bẫy / lỗi thường gặp
- Quên idempotent: `setup()`/`teardown()` lần 2 mà raise → vi phạm hợp đồng (test bắt).
- `read()` trả `None` khi hết/timeout → sai điều khoản (2); phải trả `ReadResult(status=EOF/TIMEOUT...)`.
- Nhầm batch/stream: để `is_finite=True` cho camera stream → coi mất kết nối là "hết" rồi tắt oan.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: "idempotent" nghĩa là gì? Vì sao `read()` không được trả `None`?
- Tình huống: viết adapter mới nhưng `setup()` gọi lần 2 thì lỗi — test nào sẽ fail? Vì sao hợp đồng cần điều đó?
- Giải thích lại bằng LỜI MÌNH: "hợp đồng port để ... ; contract test để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → kể 5 điều khoản | 1 tuần → tự viết contract docstring cho 1 port khác | 1 tháng → giải thích "luật cần test mới có hiệu lực".

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: docstring `frame_source.py` + `tests/test_step_03_frame_source_contract.py` (đã ĐỌC nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_03_frame_source_contract.py` → **30 passed, 1 skipped** (skip = fake_infinite ở test eventually_eofs). · Độ chắc: **cao**.
