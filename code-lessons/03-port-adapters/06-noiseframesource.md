# #03 · Mẩu 06: `NoiseFrameSource` — RNG + seed tái lập · vì sao cần ≥2 adapter

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/adapters/noise_frame_source.py` · tầng **adapters** ·
đây là **adapter thứ 2** khớp cùng port `IFrameSource` — sinh frame nhiễu ngẫu nhiên (tái lập được).

## 2. Cần biết trước
- [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
  [ndarray (numpy array)](../../knowledge-base/00-GLOSSARY.md#ndarray-numpy-array)
- Mẩu 03–05 (FakeFrameSource) — đọc trước; Noise có cùng khung, khác cách sinh frame.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/adapters/noise_frame_source.py
@dataclass
class NoiseFrameSource:
    """Random noise generator. Useful cho test detector against random input."""
    width: int = 320
    height: int = 240
    max_frames: Optional[int] = 50
    seed: Optional[int] = 42
    # ... (_source_id auto-unique như Fake — mẩu 05) ...
    _rng: np.random.Generator = field(default=None, init=False)
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)

    def setup(self) -> None:
        self._frame_count = 0
        self._rng = np.random.default_rng(self.seed)
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")

        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)

        frame = self._rng.integers(
            0, 256, size=(self.height, self.width, 3), dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._is_setup = False
        self._rng = None

    def __enter__(self) -> "NoiseFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False  # KHÔNG nuốt exception của thân `with`
```

## 4. Giải thích từng phần nhỏ nhất
- Cấu hình giống Fake nhưng mặc định khác: `width=320, height=240, max_frames=50` + thêm `seed: Optional[int] = 42`.
- `seed` → "hạt giống" cho bộ sinh số ngẫu nhiên: cùng seed → cùng dãy số → frame **tái lập được**.
- `_rng: np.random.Generator = field(default=None, init=False)` → bộ sinh ngẫu nhiên, state nội bộ (chưa có tới khi `setup`).
- `setup()`:
  - `self._rng = np.random.default_rng(self.seed)` → tạo bộ sinh ngẫu nhiên gieo từ `seed`. Cùng seed → cùng kết quả.
- `read()`: khung y hệt Fake (check setup → max_frames EOF → sinh frame), CHỈ KHÁC chỗ sinh:
  - `frame = self._rng.integers(0, 256, size=(self.height, self.width, 3), dtype=np.uint8)` → mảng số NGẪU NHIÊN trong [0,256) (tức 0..255), kích thước cao×rộng×3.
  - (Noise không có nhánh `inject_error` như Fake.)
- `teardown()` → ngoài `_is_setup=False` còn `_rng=None` (thả bộ sinh).
- `__enter__`/`__exit__` (R2#04/E-16) → context manager giống Fake: `with NoiseFrameSource(...) as s:` tự setup/teardown; `__exit__` trả `False`.

## 5. Là gì (1–2 câu)
`NoiseFrameSource` là adapter thứ hai cùng khớp `IFrameSource`, sinh frame **nhiễu ngẫu nhiên nhưng tái
lập được** (nhờ `seed`). Dùng để test detector trước đầu vào ngẫu nhiên.

## 6. Tại sao tồn tại / vấn đề nó giải — VÌ SAO CẦN ≥2 ADAPTER
- **Giá trị của port chỉ lộ ra khi có ≥2 adapter:** 1 adapter thì chưa thấy lợi của trừu tượng. Có Fake (đoán trước) + Noise (ngẫu nhiên) chứng minh: lõi/contract test dùng CHUNG một cách cho cả hai → đổi/thêm nguồn không đụng lõi. Đây là "bằng chứng sống" cho Hexagonal.
- **seed để tái lập:** test với dữ liệu ngẫu nhiên mà KHÔNG tái lập được thì lúc pass lúc fail (flaky). `seed` cố định → cùng seed cho cùng frame → test ổn định.

## 7. Dùng ở đâu trong project (cụ thể)
- Là 1 trong các param của contract test (mẩu 07): `NoiseFrameSource(width=320, height=240, max_frames=5)`.
- Test thật (đã CHẠY pass — `pytest -k noise` → **10 passed**):
  - `test_noise_seed_reproducible`: 2 nguồn cùng `seed=42` → `np.array_equal(fa, fb)` (frame đầu giống hệt) → tái lập được.
  - Các test contract (parametrized cho `noise_finite_5`) cũng nằm trong 10 passed.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Chỉ có 1 adapter (Fake): port trông "thừa" vì chưa ai thay thế. Thêm Noise cho thấy thật sự **thay nguồn
mà lõi/contract không đổi** → port chứng minh được giá trị. Không có `seed`: test ngẫu nhiên thành flaky.

## 9. Ví von đời thường
Port như ổ cắm; Fake và Noise là **2 thiết bị khác nhau** cùng cắm vừa. Có 2 thiết bị mới thấy "ổ cắm
chuẩn" hữu ích (đổi thiết bị không đổi ổ). `seed` như **công thức pha màu cố định**: cùng công thức ra cùng màu.

## 10. Liên kết bức tranh lớn
Noise + Fake là 2 adapter (mẩu 03–05 + mẩu này) cùng khớp port (mẩu 01) theo hợp đồng (mẩu 02). Chính
việc CÓ 2 adapter làm contract test (mẩu 07) có ý nghĩa: "1 bộ test, mọi adapter phải qua".

## 11. Cạm bẫy / lỗi thường gặp
- `seed=None` → mỗi lần chạy khác nhau (không tái lập) → test flaky. Test nên cố định seed.
- Quên `setup()` lại `_rng=None` → `read()` raise (check `_is_setup` trước).
- Tưởng Noise giống Fake mọi mặt — KHÔNG: Noise sinh ngẫu nhiên + không có `inject_error`.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao cần ≥2 adapter để thấy giá trị port? `seed` giải quyết vấn đề gì của test ngẫu nhiên?
- Tình huống: 2 `NoiseFrameSource(seed=42)` đọc frame đầu — giống hay khác nhau? Vì sao?
- Giải thích lại bằng LỜI MÌNH: "Noise khác Fake ở ... ; seed để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại vì sao cần ≥2 adapter | 1 tuần → tự viết adapter thứ 3 khớp port | 1 tháng → giải thích "seed → test tái lập".

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/adapters/noise_frame_source.py` (đã ĐỌC nguyên văn). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest -k noise` → **10 passed** (gồm `test_noise_seed_reproducible` + contract param noise). · Độ chắc: **cao**.
