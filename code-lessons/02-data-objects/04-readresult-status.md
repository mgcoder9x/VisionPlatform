# #02 · Mẩu 04: `ReadResult` + `ReadStatus` + `has_data` — trả trạng thái rõ ràng thay vì `None`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/read_result.py` · tầng **kernel** ·
đây là "gói kết quả" mà một nguồn dữ liệu (camera/video) trả về mỗi lần đọc một frame.

## 2. Cần biết trước
- [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [Enum (enumeration)](../../knowledge-base/00-GLOSSARY.md#enum-enumeration) ·
  [DTO](../../knowledge-base/00-GLOSSARY.md#dto-data-transfer-object)
- `Generic[T]` / `TypeVar` / `Optional` trong code dưới → để dành **mẩu 05** (chưa cần hiểu ở đây).

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/read_result.py
class ReadStatus(Enum):
    FRAME = "frame"
    EOF = "eof"
    TIMEOUT = "timeout"
    RECONNECTING = "reconnecting"
    DROPPED = "dropped"
    ERROR = "error"


# ... (giữa 2 lớp có dòng `T = TypeVar("T")` — xem mẩu 05) ...


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """Explicit status. Caller MUST handle each status."""
    status: ReadStatus
    data: Optional[T] = None
    error: Optional[Exception] = None
    retry_after_ms: Optional[int] = None

    @property
    def has_data(self) -> bool:
        return self.status == ReadStatus.FRAME and self.data is not None
```

## 4. Giải thích từng phần nhỏ nhất
- `class ReadStatus(Enum):` → liệt kê **6 trạng thái** một lần đọc có thể rơi vào:
  - `FRAME` = đọc được 1 frame; `EOF` = hết video; `TIMEOUT` = chờ quá lâu chưa có;
    `RECONNECTING` = đang kết nối lại (camera rớt); `DROPPED` = frame bị bỏ (quá tải); `ERROR` = lỗi.
- `@dataclass(frozen=True) class ReadResult(...)` → gói kết quả **bất biến** (không sửa sau khi tạo).
  - `status: ReadStatus` → **bắt buộc**: kết quả này thuộc trạng thái nào.
  - `data: Optional[T] = None` → frame thật (nếu có); mặc định `None`. (`Optional[T]` = "có thể là T hoặc None" — kiểu T giải thích mẩu 05.)
  - `error: Optional[Exception] = None` → lỗi kèm theo (khi `status=ERROR`).
  - `retry_after_ms: Optional[int] = None` → gợi ý "chờ bao nhiêu mili-giây rồi thử lại" (khi TIMEOUT/RECONNECTING).
- `@property has_data` → trả `True` **chỉ khi** `status == FRAME` VÀ `data` khác `None`. Một câu hỏi gọn: "kết quả này có frame để xài không?".

## 5. Là gì (1–2 câu)
`ReadResult` là gói kết quả đọc kèm **một nhãn trạng thái rõ ràng** (6 loại) + dữ liệu/lỗi đi cùng.
`has_data` là lối tắt kiểm "có frame dùng được không".

## 6. Tại sao tồn tại / vấn đề nó giải
Cách ngây thơ: hàm đọc trả `frame` hoặc trả `None` khi "không có gì". Nhưng `None` **mơ hồ**: hết video?
timeout? camera rớt? lỗi? Người gọi không phân biệt được → xử lý sai (vd coi camera rớt là hết video rồi
tắt hẳn). `ReadResult` biến mọi khả năng thành **trạng thái tường minh**: người gọi BẮT BUỘC nhìn `status`
để xử lý đúng từng ca (đọc tiếp / dừng / chờ rồi thử lại / báo lỗi).

## 7. Dùng ở đâu trong project (cụ thể)
- Là kiểu trả về của cổng đọc nguồn (port `IFrameSource`, sẽ học ở bài #03).
- Test thật `tests/test_step_02_domain.py` (đã CHẠY pass):
  - `test_readresult_frame_has_data`: `ReadResult(status=FRAME, data=arr)` → `assert r.has_data`, `r.data is arr`.
  - `test_readresult_eof_no_data`: `ReadResult(status=EOF)` → `assert not r.has_data`, `r.data is None`.
  - `test_readresult_immutable`: gán lại `r.status` → raise (vì frozen).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Trả `None` hoặc ném exception cho mọi thứ: người gọi đoán mò "None nghĩa là gì lần này". Một ca xử lý
sai (vd timeout bị coi là EOF) làm cả pipeline dừng oan. `ReadResult` ép xử lý đúng theo trạng thái.

## 9. Ví von đời thường
`ReadResult` như **phiếu kết quả xét nghiệm có ô "Kết luận"**: thay vì đưa tờ giấy trắng (None) bắt bạn
tự đoán, nó ghi rõ "Bình thường / Cần theo dõi / Bất thường" + số liệu kèm theo.

## 10. Liên kết bức tranh lớn
Cùng tinh thần `CoordinateSpace` (mẩu 02): **làm hiện rõ cái ngầm**. Đây cũng là một **DTO** ở `kernel` —
gói dữ liệu thuần truyền giữa các phần, không chứa logic. Bài #03 sẽ dùng nó làm "ngôn ngữ chung" giữa port và adapter.

## 11. Cạm bẫy / lỗi thường gặp
- Quên kiểm `status` mà đọc thẳng `data` → có thể nhận `None` lúc EOF/timeout → lỗi. Dùng `has_data` hoặc `match status`.
- Tưởng `has_data` chỉ kiểm `data is not None` — KHÔNG: nó còn đòi `status == FRAME` (một frame DROPPED có thể không kèm data hợp lệ).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: kể vài trạng thái trong `ReadStatus`. Vì sao trả `None` cho "không có frame" là mơ hồ?
- Tình huống: camera rớt mạng tạm thời — nên trả status nào, và `retry_after_ms` dùng làm gì?
- Giải thích lại bằng LỜI MÌNH: "ReadResult để ... ; has_data đúng khi ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → kể 6 trạng thái | 1 tuần → tự thiết kế 1 kiểu kết quả có status cho việc khác | 1 tháng → giải thích "tránh trả None mơ hồ".

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/read_result.py` (đã ĐỌC LẠI nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_02_domain.py -k readresult` → **3 passed**. · Độ chắc: **cao**.
- `Generic[T]`/`TypeVar`/`Optional`: là phần kiểu (typing) — giải thích ở mẩu 05; ở đây CHỈ giới thiệu, [chưa giải thích sâu tại mẩu này] (cố ý hoãn để không nhồi).
