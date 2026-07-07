# Mẩu 08 — `FakeDetector`: adapter giả deterministic + fail-fast chưa setup

**(1) Thuộc về đâu:** `adapters/fake_detector.py`, class `FakeDetector`. Layer adapters (lá — cài đặt cụ thể).

**(2) Cần biết trước:** adapter (bản cài đặt một port — `knowledge-base/hexagonal-architecture/`);
`frame.mean()` (numpy: trung bình mọi pixel → độ sáng); deterministic (cùng input → cùng output).

**(3) Code thật (quote `adapters/fake_detector.py`):**
```python
class FakeDetector:
    def __init__(self) -> None:
        self._is_setup = False

    def setup(self) -> None:
        self._is_setup = True

    def teardown(self) -> None:
        self._is_setup = False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # Fail-fast: quên setup() = lỗi cấu hình, phải nổ ngay (không detect ngầm).
        if not self._is_setup:
            raise RuntimeError("setup() must be called before detect()")

        h, w = frame.shape[:2]
        brightness = float(frame.mean())

        return [
            Detection(
                label="object",
                confidence=brightness / 255.0,
                box=BBox(
                    x=w * 0.25, y=h * 0.25, w=w * 0.5, h=h * 0.5,
                    space=CoordinateSpace.MODEL_INPUT,
                ),
            )
        ]
```

**(4) Giải thích từng dòng:**
- `self._is_setup = False` → cờ đã-nạp-chưa.
- `setup()` bật cờ, `teardown()` tắt — cả hai idempotent (gọi nhiều lần vẫn ổn).
- `if not self._is_setup: raise RuntimeError(...)` → **fail-fast**: quên setup thì nổ ngay.
- `brightness = float(frame.mean())` → độ sáng trung bình 0–255.
- `confidence = brightness / 255.0` → độ tin 0–1, **suy ra từ độ sáng** → deterministic.
- `box=BBox(x=w*0.25, y=h*0.25, w=w*0.5, h=h*0.5, space=MODEL_INPUT)` → 1 hộp giữa frame, rộng 50%,
  gắn space `MODEL_INPUT` (mẩu 04).

**(5) Là gì:** detector giả trả **1 detection/frame**, confidence tính từ độ sáng — đủ "thật" để test
pipeline mà không cần GPU/model.

**(6) Tại sao tồn tại / vấn đề nó giải:** cần một `IDetector` chạy được để dev/test luồng inference mà
không phụ thuộc YOLO/CUDA. Deterministic → test **verify được** (sáng 255 → confidence 1.0).

**(7) Dùng ở đâu trong project:** test #06 (`FakeDetector().setup()` rồi truyền vào
`InlineInferenceClient`). Kiểm confidence scale theo brightness (mẩu 11).

**(8) Không có nó thì sao:** phải cài model thật để test → chậm, nặng, không deterministic → test flaky.

**(9) Ví von:** ma-nơ-canh trong lớp học lái xe: không phải người thật nhưng đủ để tập thao tác an toàn.

**(10) Liên kết bức tranh lớn:** là **lá adapter** — chỉ import `domain` (BBox) + `kernel` (Detection),
KHÔNG import runtime/application → giữ luật "adapters là lá" (lint kept). Đối xứng `FakeFrameSource` (#03).

**(11) Cạm bẫy:** `frame.mean()` trên frame rỗng/không phải uint8 sẽ lệch — nhưng writer #05 đã ép
uint8 nên an toàn. Đừng quên `setup()` (đã fail-fast nhắc).

**(12) Tự kiểm:**
- Vì sao `detect` fail-fast khi chưa `setup`? Không fail-fast thì hại gì?
- Vì sao dùng confidence suy từ brightness thay vì số ngẫu nhiên?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `adapters/fake_detector.py` · Design step-06 (Phần 3 FakeDetector). Độ chắc: cao (quote
thật + test confidence scale pass).
