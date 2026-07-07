# Mẩu 04 — `Detection`: kết quả mang `BBox` có `CoordinateSpace` (invariant Step 02)

**(1) Thuộc về đâu:** `kernel/inference_protocol.py`, class `Detection`. Dùng `BBox`/`CoordinateSpace`
từ `domain/bbox.py`.

**(2) Cần biết trước:** `BBox` (bài #02: hộp bao vật thể x/y/w/h); `CoordinateSpace` (bài #02: "toạ độ
này thuộc hệ nào" — frame gốc? input model 640×640? chuẩn hoá 0–1? màn hình?).

**(3) Code thật (quote `kernel/inference_protocol.py`):**
```python
@dataclass(frozen=True)
class Detection:
    """Kết quả detection thuần — KHÔNG phụ thuộc model (YOLO/RTMDet/...).

    `box` là BBox có CoordinateSpace tag (invariant Step 02). Adapter model convert raw output
    → Detection; đổi model chỉ đổi adapter, Detection không động.
    """
    label: str
    confidence: float
    box: BBox
```
Và `domain/bbox.py`:
```python
class CoordinateSpace(Enum):
    ORIGINAL_FRAME = "original"   # tọa độ trên frame raw (pre-resize)
    MODEL_INPUT = "model_input"   # tọa độ trên model input (e.g. 640x640)
    NORMALIZED = "normalized"     # 0.0-1.0 (relative to frame)
    DISPLAY = "display"           # tọa độ trên frame UI hiển thị
```

**(4) Giải thích từng dòng:**
- `label: str` → tên lớp vật ("object", "person"...).
- `confidence: float` → độ tin (0–1).
- `box: BBox` → hộp bao **kèm `space`**. KHÔNG dùng 4 số x/y/w/h trần.

**(5) Là gì:** `Detection` = một vật được phát hiện: nhãn + độ tin + hộp bao có gắn hệ toạ độ.

**(6) Tại sao tồn tại / vấn đề nó giải:** model nhận frame đã **resize/letterbox** (ví dụ 640×640 =
`MODEL_INPUT`), nhưng UI vẽ trên **frame gốc** (`ORIGINAL_FRAME`). Nếu box chỉ là số trần, downstream
không biết toạ độ thuộc hệ nào → **vẽ lệch**. `space` ép mọi consumer phải *transform trước khi dùng*
— chính là bug kinh điển bài #02 dạy cách chặn.

**(7) Dùng ở đâu trong project:** `FakeDetector.detect` trả `Detection(..., box=BBox(..., space=
CoordinateSpace.MODEL_INPUT))` (mẩu 08). `InferenceResponse.detections` là tuple các `Detection` (mẩu 06).

**(8) Không có `space` thì sao:** quay lại đúng lỗi #02 — vẽ box lệch vì không ai biết cần transform.

**(9) Ví von:** ghi toạ độ mà không ghi "theo bản đồ nào" (Google Maps? bản vẽ tay?) → người nhận đặt
sai chỗ. `space` = tên bản đồ đính kèm mỗi toạ độ.

**(10) Liên kết bức tranh lớn:** `Detection` **không phụ thuộc model** → đổi YOLO→RTMDet chỉ sửa
adapter, `Detection` bất động (nối luật hexagonal: domain/kernel không biết công nghệ cụ thể).

**(11) Cạm bẫy:** đặt raw float vào `Detection` = bypass pattern coordinate-space. Adapter phải khai
báo đúng `space` của output model (thường `MODEL_INPUT`).

**(12) Tự kiểm:**
- Vì sao `Detection.box` phải mang `space`? Cho 1 ví dụ vẽ lệch nếu thiếu.
- Đổi sang model khác thì file nào đổi, file nào không?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/inference_protocol.py` (Detection) · `domain/bbox.py` (BBox/CoordinateSpace) ·
Design step-06 ("Detection ... toạ độ luôn có space"). Độ chắc: cao (quote thật).
