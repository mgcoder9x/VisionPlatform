# #03 · Mẩu 03: `FakeFrameSource` khung — dataclass + `field(init=False)` + setup/teardown idempotent

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/adapters/fake_frame_source.py` · tầng **adapters** (rìa) ·
đây là **adapter** đầu tiên khớp port `IFrameSource` — nguồn frame giả cho test/dev offline.

## 2. Cần biết trước
- [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass)
- Mẩu 01 (Protocol/port) + mẩu 02 (hợp đồng) — đọc trước. `read()` → mẩu 04; `source_id`/counter → mẩu 05.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/adapters/fake_frame_source.py
@dataclass
class FakeFrameSource:
    """In-memory frame generator. Implements IFrameSource."""
    width: int = 640
    height: int = 480
    max_frames: Optional[int] = 100
    inject_error_at: Optional[int] = None
    # ... (_source_id auto-unique — xem mẩu 05) ...
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)

    def setup(self) -> None:
        self._frame_count = 0
        self._is_setup = True

    # ... (read() — xem mẩu 04) ...

    def teardown(self) -> None:
        self._is_setup = False

    def __enter__(self) -> "FakeFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False  # KHÔNG nuốt exception của thân `with`

    @property
    def is_finite(self) -> bool:
        return self.max_frames is not None
```

## 4. Giải thích từng phần nhỏ nhất
- `@dataclass class FakeFrameSource:` → adapter khai báo bằng dataclass. **KHÔNG** `(IFrameSource)` — chỉ cần đủ method đúng dạng (structural typing, mẩu 01).
- **Tham số cấu hình** (có thể truyền khi tạo):
  - `width: int = 640`, `height: int = 480` → kích thước frame giả, mặc định 640×480.
  - `max_frames: Optional[int] = 100` → sinh tối đa 100 frame rồi EOF; `None` = vô hạn.
  - `inject_error_at: Optional[int] = None` → cho phép "tiêm lỗi" ở frame thứ N để test xử lý ERROR (mẩu 04).
- **State nội bộ** (`field(..., init=False)` = KHÔNG nằm trong tham số khởi tạo, tự quản):
  - `_frame_count: int = field(default=0, init=False)` → đếm đã sinh bao nhiêu frame. `init=False` → caller không truyền được, luôn bắt đầu 0.
  - `_is_setup: bool = field(default=False, init=False)` → cờ "đã setup chưa".
  - Dấu `_` đầu tên = quy ước "nội bộ, đừng đụng từ ngoài".
- `setup()` → đặt `_frame_count=0`, `_is_setup=True`. Gọi lại nhiều lần → vẫn về 0/True (idempotent).
- `teardown()` → `_is_setup=False` (dọn). Gọi lại nhiều lần cũng an toàn (idempotent).
- `__enter__`/`__exit__` (R2#04/E-16) → context manager: `with FakeFrameSource(...) as s:` tự `setup()` lúc vào, `teardown()` lúc ra (kể cả khi raise); `__exit__` trả `False` (không nuốt exception). Đồng bộ vòng đời với executor → dùng `with source, executor:` (#04 mẩu 09).
- `is_finite` → `True` nếu `max_frames` khác `None` (hữu hạn), `False` nếu vô hạn.

## 5. Là gì (1–2 câu)
`FakeFrameSource` là nguồn frame **giả** (sinh trong bộ nhớ) khớp hợp đồng `IFrameSource`. Mẩu này lo phần
"khung": tham số cấu hình + state nội bộ + vòng đời `setup`/`teardown` + `is_finite`.

## 6. Tại sao tồn tại / vấn đề nó giải
Cần test pipeline mà KHÔNG có camera/file thật → cần một nguồn "đoán trước được", bật/tắt nhanh. `FakeFrameSource`
cho đúng điều đó. `field(init=False)` tách rõ "cấu hình do người dùng đặt" với "state máy tự quản" → caller
không lỡ truyền `_frame_count` bậy. `is_finite` để pipeline biết EOF là "hết bình thường" hay "bất thường".

## 7. Dùng ở đâu trong project (cụ thể)
- Dùng trong contract test (mẩu 07) + demo pipeline (#04) làm nguồn mặc định.
- Idempotent setup/teardown đã CHẠY pass: `test_setup_idempotent`, `test_teardown_idempotent` (trong 30 passed, mẩu 02).
- `is_finite` bool: `test_is_finite_is_bool` pass.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Không có nguồn giả: mọi test/dev phải có camera/file → chậm, phụ thuộc thiết bị, khó tái lập. `FakeFrameSource`
cho frame đoán trước (mẩu 04: `frame_count % 256`) → test xác định, chạy ở đâu cũng giống nhau.

## 9. Ví von đời thường
`FakeFrameSource` như **maniken/người mẫu thử đồ** trong xưởng may: không phải khách thật, nhưng đủ để
thử dáng (test pipeline) trước khi gặp khách (camera thật). `field(init=False)` = các bộ phận "gắn trong",
khách không tháo lắp được.

## 10. Liên kết bức tranh lớn
Đây là adapter khớp port (mẩu 01) theo hợp đồng (mẩu 02). Cùng với `NoiseFrameSource` (mẩu 06) tạo ≥2 adapter
→ chứng minh giá trị của port (đổi nguồn không đụng lõi). `read()` (mẩu 04) là phần "sinh frame" cốt lõi.

## 11. Cạm bẫy / lỗi thường gặp
- Bỏ `init=False` cho state nội bộ → caller có thể truyền `_frame_count=99` lúc tạo → state rác. `init=False` chặn việc đó.
- Quên `setup()` rồi `read()` → `read()` sẽ raise (mẩu 04). `_is_setup` chính là cờ canh.
- Tưởng phải `class FakeFrameSource(IFrameSource)` → KHÔNG cần (structural typing).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `field(init=False)` để làm gì? Vì sao tách "cấu hình" khỏi "state nội bộ"?
- Tình huống: gọi `setup()` 2 lần liên tiếp — có sao không? `_frame_count` thành mấy?
- Giải thích lại bằng LỜI MÌNH: "adapter này để ... ; init=False để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại cấu hình vs state nội bộ | 1 tuần → tự viết 1 dataclass có field(init=False) | 1 tháng → giải thích idempotent setup/teardown.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/adapters/fake_frame_source.py` (đã ĐỌC LẠI nguyên văn). · Độ chắc: **cao**.
- Hành vi idempotent + is_finite: đã CHẠY THẬT — nằm trong `pytest test_step_03...` → 30 passed/1 skipped (mẩu 02), gồm `test_setup_idempotent`/`test_teardown_idempotent`/`test_is_finite_is_bool`. · Độ chắc: **cao**.
