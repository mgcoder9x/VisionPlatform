# #03 · Mẩu 07: Contract test — `pytest` parametrize + builder fixture · "1 suite, mọi adapter phải qua"

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/tests/test_step_03_frame_source_contract.py` · tầng **tests** ·
đây là "trọng tài" ép MỌI adapter tôn trọng hợp đồng `IFrameSource` (mẩu 02).

## 2. Cần biết trước
- [fixture](../../knowledge-base/00-GLOSSARY.md#fixture-pytest) ·
  [pytest](../../knowledge-base/00-GLOSSARY.md#pytest) ·
  [Protocol](../../knowledge-base/00-GLOSSARY.md#protocol-typingprotocol)
- Mẩu 02 (hợp đồng) — contract test ép từng điều khoản ở đó.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)

> **🖼 Sơ đồ ma trận test (nguồn Draw.io):** [contract-test-matrix.drawio](diagrams/contract-test-matrix.drawio) — 3 nguồn × 9 điều khoản → 30 passed/1 skip.
> Xem nhúng: Draw.io → **Export as → SVG** → lưu `diagrams/contract-test-matrix.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

```python
# vision-platform/tests/test_step_03_frame_source_contract.py
@pytest.fixture(params=[
    pytest.param(
        lambda: FakeFrameSource(width=320, height=240, max_frames=5),
        id="fake_finite_5",
    ),
    pytest.param(
        lambda: FakeFrameSource(width=160, height=120, max_frames=None),
        id="fake_infinite",
    ),
    pytest.param(
        lambda: NoiseFrameSource(width=320, height=240, max_frames=5),
        id="noise_finite_5",
    ),
])
def source(request):
    """Builder fixture - tạo adapter mới mỗi test (isolation)."""
    src = request.param()
    src.setup()
    yield src
    src.teardown()


class TestFrameSourceContract:
    """Mọi IFrameSource impl PHẢI thỏa các contract sau."""

    def test_read_returns_readresult(self, source):
        result = source.read(timeout_ms=100)
        assert hasattr(result, "status")

    # ... (8 test contract còn lại — xem mẩu 02 §7) ...
```

## 4. Giải thích từng phần nhỏ nhất
- `@pytest.fixture(params=[...])` → khai báo một **fixture có nhiều tham số**: pytest sẽ chạy MỖI test một lần cho TỪNG param → 1 test viết 1 lần, chạy cho cả 3 nguồn.
- `pytest.param(lambda: FakeFrameSource(...), id="fake_finite_5")`:
  - `lambda: FakeFrameSource(...)` → **builder** (hàm tạo), KHÔNG phải instance sẵn. Mỗi test gọi builder → **instance MỚI** → các test không dùng chung 1 nguồn (isolation, tránh ảnh hưởng lẫn nhau).
  - `id="..."` → tên hiển thị trong báo cáo test (vd `fake_finite_5`).
- 3 param: Fake hữu hạn (5 frame), Fake vô hạn (`max_frames=None`), Noise hữu hạn (5 frame).
- `def source(request):` → fixture tên `source`; test nào nhận tham số `source` thì được tiêm 1 nguồn.
  - `src = request.param()` → gọi builder của param hiện tại → tạo nguồn.
  - `src.setup()` → chuẩn bị trước khi giao cho test.
  - `yield src` → trao nguồn cho test chạy.
  - `src.teardown()` → dọn SAU khi test xong (phần sau `yield`).
- `class TestFrameSourceContract:` → gom các test hợp đồng. Mỗi method nhận `source` → tự động chạy cho cả 3 nguồn.
- `test_read_returns_readresult`: `assert hasattr(result, "status")` — ép điều khoản "read trả ReadResult (có `status`)". (8 test còn lại đã liệt kê ở mẩu 02 §7.)

## 5. Là gì (1–2 câu)
Contract test là **1 bộ test chung** mà mọi adapter `IFrameSource` đều phải chạy qua. `fixture(params=...)`
+ builder-lambda khiến cùng bộ test tự động chạy cho từng nguồn, mỗi lần 1 instance mới.

## 6. Tại sao tồn tại / vấn đề nó giải
Hợp đồng (mẩu 02) chỉ là chữ; phải có thứ **ép** mới chắc adapter tuân. Nếu mỗi adapter viết test riêng →
trùng lặp + dễ bỏ sót điều khoản. **1 suite chung** đảm bảo: mọi adapter (hiện tại + tương lai) qua đúng
cùng một bộ luật. **Thêm adapter = thêm 1 dòng `pytest.param`** → toàn bộ luật tự áp cho nó. **Builder
(lambda) thay vì instance** → mỗi test một nguồn mới, không rò state giữa các test (isolation).

## 7. Dùng ở đâu trong project (cụ thể)
- Ép cả `FakeFrameSource` (2 cấu hình) + `NoiseFrameSource` qua 9 test hợp đồng (mẩu 02 §7).
- Test thật đã CHẠY pass: `pytest tests/test_step_03_frame_source_contract.py` → **30 passed, 1 skipped**
  (3 nguồn × 9 contract = 27, trừ 1 skip `fake_infinite` ở `test_finite_source_eventually_eofs`, + 4 test adapter-specific = 30 passed/1 skip).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Không contract test: adapter mới có thể "lách" (quên idempotent, trả None) mà không ai phát hiện tới khi
chạy thật → lõi vỡ ở production. Suite chung là lưới an toàn cho MỌI adapter.

## 9. Ví von đời thường
Contract test như **bài kiểm định chung cho mọi mẫu xe** trước khi ra đường: cùng 1 bộ tiêu chuẩn (phanh,
đèn, khí thải) áp cho xe nào cũng vậy. Có mẫu xe mới → cho chạy đúng bộ kiểm đó. `params` = "danh sách xe cần kiểm".

## 10. Liên kết bức tranh lớn
Đây là mảnh KHÉP LẠI bài #03: port (mẩu 01) + hợp đồng (mẩu 02) + 2 adapter (mẩu 03–06) + **contract test
ép tất cả**. Nhờ vậy bài #04 (pipeline) tin tưởng dùng bất kỳ nguồn nào qua port mà không sợ adapter ẩu.

## 11. Cạm bẫy / lỗi thường gặp
- Dùng instance sẵn thay builder (`params=[FakeFrameSource(...)]`) → các test DÙNG CHUNG 1 nguồn → state rò rỉ giữa test (vd `_frame_count` đã tăng). Builder-lambda cho mỗi test 1 nguồn mới.
- Quên `teardown` sau `yield` → rò tài nguyên giữa test.
- Thêm adapter mới mà quên thêm `pytest.param` → adapter đó KHÔNG được kiểm hợp đồng.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao dùng builder-lambda thay vì instance sẵn trong `params`? `yield` trong fixture chia code làm 2 phần gì?
- Tình huống: thêm `RtspFrameSource` — cần làm gì để nó được kiểm cùng bộ contract?
- Giải thích lại bằng LỜI MÌNH: "contract test để ... ; params + builder để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại "1 suite mọi adapter" + builder | 1 tuần → tự viết 1 fixture params cho 2 impl | 1 tháng → giải thích contract test vs test riêng từng lớp.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/tests/test_step_03_frame_source_contract.py` (đã ĐỌC nguyên văn fixture + class). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_03_frame_source_contract.py` → **30 passed, 1 skipped**. · Độ chắc: **cao**.
