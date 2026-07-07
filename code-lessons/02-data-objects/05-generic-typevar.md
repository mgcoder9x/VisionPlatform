# #02 · Mẩu 05: `Generic[T]` + `TypeVar` — vì sao `ReadResult` "generic"

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/read_result.py` · tầng **kernel** ·
đây là phần "kiểu tổng quát" làm `ReadResult` dùng được cho nhiều loại dữ liệu.

## 2. Cần biết trước
- [TypeVar](../../knowledge-base/00-GLOSSARY.md#typevar) ·
  [Generic[T]](../../knowledge-base/00-GLOSSARY.md#generict) ·
  [Optional](../../knowledge-base/00-GLOSSARY.md#optional)
- Mẩu 04 (ReadResult/status) — đọc trước; đây là phần "T" đã hoãn lại ở mẩu 04.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/read_result.py
from typing import Generic, Optional, TypeVar

# ... (class ReadStatus nằm ở đây — đã quote ở mẩu 04) ...

T = TypeVar("T")


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """Explicit status. Caller MUST handle each status."""
    status: ReadStatus
    data: Optional[T] = None
    error: Optional[Exception] = None
    retry_after_ms: Optional[int] = None
```

## 4. Giải thích từng phần nhỏ nhất
- `from typing import Generic, Optional, TypeVar` → lấy 3 công cụ "gợi ý kiểu" từ thư viện `typing`.
- `T = TypeVar("T")` → tạo một **biến kiểu** tên `T`: nó là "chỗ giữ chỗ" cho một kiểu CHƯA biết, sẽ điền lúc dùng.
- `class ReadResult(Generic[T]):` → khai báo `ReadResult` là lớp **tổng quát theo `T`** → có thể viết `ReadResult[np.ndarray]`, `ReadResult[MediaPacket]`...
- `data: Optional[T] = None` → trường `data` mang **đúng kiểu `T`** đã chọn (hoặc `None`). Nếu là `ReadResult[np.ndarray]` thì `data` được hiểu là `np.ndarray | None`.
- Lưu ý quan trọng: đây là **gợi ý cho công cụ kiểm kiểu** (như mypy/IDE). Python **KHÔNG ép kiểu lúc chạy** — gán sai kiểu vẫn chạy, chỉ là công cụ static sẽ cảnh báo.

## 5. Là gì (1–2 câu)
`Generic[T]` + `TypeVar("T")` biến `ReadResult` thành một **khuôn dùng cho nhiều kiểu dữ liệu**, vẫn ghi
rõ "lần này đang chứa kiểu gì". Đó là lý do gọi nó "generic" (tổng quát).

## 6. Tại sao tồn tại / vấn đề nó giải
Một nguồn có thể trả frame là `np.ndarray`, nguồn khác trả `MediaPacket`. Không generic thì hoặc (a)
viết `ReadResultNdarray`, `ReadResultPacket`... lặp nhiều lớp, hoặc (b) để `data` kiểu `Any` → mất hết
thông tin kiểu, IDE/mypy không cảnh báo khi dùng sai. `Generic[T]` cho **một lớp duy nhất** mà vẫn giữ
kiểu cụ thể: `ReadResult[np.ndarray]` thì IDE biết `r.data` là `np.ndarray`.

## 7. Dùng ở đâu trong project (cụ thể)
- `ReadResult` được dùng làm kiểu trả của cổng đọc nguồn (bài #03). Tùy nguồn, `T` là kiểu frame tương ứng.
- Kiểm chứng thật (đã CHẠY): `ReadResult[np.ndarray]` → in ra `vision_platform.kernel.read_result.ReadResult[numpy.ndarray]` (subscript hợp lệ); tạo `ReadResult(status=FRAME, data=zeros)` → `has_data == True`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Dùng `Any` cho `data`: chạy được nhưng mất kiểm tra kiểu — gán nhầm kiểu không ai cảnh báo, bug lộ muộn.
- Viết nhiều lớp riêng cho từng kiểu: trùng lặp, khó bảo trì. `Generic[T]` gộp lại 1 lớp + giữ kiểu.

## 9. Ví von đời thường
`Generic[T]` như **hộp đựng có ô dán nhãn `[___]`**: cùng một loại hộp, lúc đựng táo thì dán `[táo]`,
lúc đựng sách thì dán `[sách]`. Người nhận nhìn nhãn là biết bên trong kiểu gì, không phải mở ra đoán.

## 10. Liên kết bức tranh lớn
Generic là công cụ "giữ an toàn kiểu" cho các **DTO** ở `kernel`. Tinh thần chung của tầng kernel: hợp đồng
dữ liệu rõ ràng (status tường minh + kiểu tường minh) để các tầng khác dùng mà ít sai.

## 11. Cạm bẫy / lỗi thường gặp
- Tưởng `ReadResult[int]` sẽ **chặn** gán `data="abc"` lúc chạy — KHÔNG. Đó chỉ là gợi ý kiểu; muốn chặn thật phải validate trong code (như `BBox.__post_init__`) hoặc chạy mypy.
- Nhầm `TypeVar` với `Generic`: `TypeVar` tạo biến kiểu `T`; `Generic[T]` mới là cái gắn `T` vào lớp.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `TypeVar("T")` để làm gì? `Generic[T]` cho phép viết gì? Generic có ép kiểu lúc chạy không?
- Tình huống: một nguồn trả `MediaPacket`, nguồn khác trả `np.ndarray` — generic giúp 1 lớp `ReadResult` phục vụ cả hai thế nào?
- Giải thích lại bằng LỜI MÌNH: "Generic[T] để ... ; nó KHÔNG ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại generic là gì + có ép kiểu lúc chạy không | 1 tuần → tự viết 1 lớp generic nhỏ | 1 tháng → giải thích vì sao generic hơn `Any`.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/read_result.py` (đã ĐỌC LẠI nguyên văn `TypeVar`+`Generic[T]`). · Độ chắc: **cao**.
- Hành vi subscript `ReadResult[np.ndarray]`: đã CHẠY THẬT lệnh python → in `ReadResult[numpy.ndarray]` + `has_data: True` (đọc output). · Độ chắc: **cao**.
- "Generic là gợi ý kiểu, KHÔNG ép lúc chạy": là đặc tính của `typing` Python — tài liệu chính thống (PEP 484); [chưa kiểm bằng thực nghiệm gán sai kiểu để xem không raise tại mẩu này], nhưng đúng nguyên lý. · Độ chắc: cao.
