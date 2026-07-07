# #03 · Mẩu 05: `source_id` DUY NHẤT — `itertools.count` + `default_factory` (ERRATA E-13)

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/adapters/fake_frame_source.py` (và `noise_frame_source.py`) ·
tầng **adapters** · đây là cách bảo đảm mỗi nguồn có **mã định danh riêng**, đúng hợp đồng port.

## 2. Cần biết trước
- [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass)
- Mẩu 02 (hợp đồng: `source_id` unique) + mẩu 03 (khung Fake) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/adapters/fake_frame_source.py
import itertools
# ...
# Bộ đếm để source_id mặc định DUY NHẤT trong 1 process (ERRATA E-13, Risk 3).
# Port contract yêu cầu source_id unique; default cố định sẽ trùng khi tạo nhiều instance.
_fake_source_counter = itertools.count()


@dataclass
class FakeFrameSource:
    # ...
    _source_id: str = field(default_factory=lambda: f"fake_{next(_fake_source_counter)}")
    # ...

    @property
    def source_id(self) -> str:
        return self._source_id
```
(`noise_frame_source.py` có cùng cơ chế với `_noise_source_counter` → `"noise_0"`, `"noise_1"`...)

## 4. Giải thích từng phần nhỏ nhất
- `import itertools` → thư viện chuẩn có các "bộ tạo dãy".
- `_fake_source_counter = itertools.count()` → tạo **bộ đếm vô hạn** ở cấp module: mỗi lần gọi `next(...)` trả số kế tiếp 0,1,2,... Đặt ở **module** (không trong class) → dùng chung cho mọi instance trong 1 process.
- `_source_id: str = field(default_factory=lambda: f"fake_{next(_fake_source_counter)}")`:
  - `default_factory=...` → giá trị mặc định được **tính bằng cách GỌI hàm** mỗi lần tạo instance (khác `default=...` dùng chung 1 giá trị).
  - `lambda: f"fake_{next(_fake_source_counter)}"` → hàm vô danh: lấy số kế tiếp từ bộ đếm, ghép thành `"fake_0"`, `"fake_1"`...
  - Vì là `field` thường (không `init=False`) → caller VẪN truyền được id tường minh: `FakeFrameSource(_source_id="cam1")`.
- `source_id` property → trả `_source_id` ra ngoài (đọc).

## 5. Là gì (1–2 câu)
Đây là cơ chế cấp **mã `source_id` tự động khác nhau** cho mỗi nguồn (fake_0, fake_1, ...), đồng thời vẫn
cho phép đặt id tường minh. Dùng bộ đếm dùng-chung-process + `default_factory`.

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (ERRATA E-13)
**Bug E-13 (Risk 3):** bản đầu đặt `source_id` mặc định **CỐ ĐỊNH** (vd luôn `"fake_0"`). Tạo 2 nguồn →
**trùng id** → vi phạm hợp đồng port "source_id unique" → log/metrics lẫn lộn 2 nguồn.
- **Fix cái NGỌN (sai):** mỗi chỗ tạo nguồn lại tự nhớ đặt id khác nhau bằng tay → dễ quên, bug quay lại.
- **Fix tận GỐC (đã làm):** sửa **chính cơ chế sinh default** → `default_factory` + bộ đếm → **mọi** instance tự khác nhau, không ai phải nhớ gì. Gốc của bug ("default cố định") bị loại bỏ, không chỉ vá 1 điểm.

## 7. Dùng ở đâu trong project (cụ thể)
- Áp cho cả `FakeFrameSource` (`fake_*`) và `NoiseFrameSource` (`noise_*`).
- **Kiểm chứng thật (đã CHẠY phiên này):** `FakeFrameSource().source_id` → `fake_0`, lần 2 → `fake_1` (khác nhau); `FakeFrameSource(_source_id="cam1").source_id` → `cam1` (id tường minh giữ nguyên). Test `test_source_id_unique_by_default` → **1 passed**.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Default cố định: 2 camera cùng `source_id="fake_0"` → khi đọc log/metric không phân biệt được nguồn nào lỗi →
chẩn đoán sai. Hợp đồng "unique" tồn tại chính vì điều đó; E-13 là minh chứng "luật + test bắt được bug thật".

## 9. Ví von đời thường
`itertools.count` + `default_factory` như **máy phát số thứ tự ở quầy dịch vụ**: mỗi khách tới tự được 1 số
khác nhau, nhân viên không phải tự nghĩ số (fix gốc). Ai có "số VIP riêng" (id tường minh) thì vẫn dùng số đó.

## 10. Liên kết bức tranh lớn
Đây là một điều khoản hợp đồng (mẩu 02) được bảo đảm tận gốc. Cùng tinh thần "fail fast / dữ liệu đúng từ
gốc" như `BBox.__post_init__` (bài #02). E-13 ghi ở `Design/00-ERRATA.md`.

## 11. Cạm bẫy / lỗi thường gặp
- Dùng `default=...` thay `default_factory=...` cho giá trị "phải mới mỗi lần" → mọi instance DÙNG CHUNG 1 giá trị (đúng bug gốc). Cái gì cần tạo-mới-mỗi-lần phải dùng `default_factory`.
- Đặt bộ đếm TRONG class thay vì module → mỗi định nghĩa lại reset; đặt ở module để duy nhất trong process.
- Lưu ý phạm vi: "duy nhất trong 1 process" — qua nhiều process khác nhau, bộ đếm bắt đầu lại từ 0 (nếu cần unique toàn cục phải cơ chế khác, vd uuid).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `default_factory` khác `default` ở chỗ nào? Vì sao bộ đếm đặt ở module?
- Tình huống (fix gốc vs ngọn): nếu chỉ "nhắc nhau đặt id khác nhau khi tạo" thì sao? Cách hiện tại tốt hơn vì?
- Giải thích lại bằng LỜI MÌNH: "E-13 gốc là ... ; fix gốc bằng ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại gốc E-13 + cách fix | 1 tuần → tự dùng default_factory cấp id tự tăng | 1 tháng → giải thích "fix gốc vs fix ngọn" qua ví dụ này.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `adapters/fake_frame_source.py` + `noise_frame_source.py` (đã ĐỌC nguyên văn `itertools.count` + `default_factory`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT — `fake_0`/`fake_1` khác nhau + `cam1` giữ nguyên + `test_source_id_unique_by_default` → **1 passed** (đọc output). · Độ chắc: **cao**.
- E-13 ghi ở `Design/00-ERRATA.md`. · Độ chắc: **cao**.
