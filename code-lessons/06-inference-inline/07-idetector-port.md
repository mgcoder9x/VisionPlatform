# Mẩu 07 — `IDetector`: cổng (port) cho detector

**(1) Thuộc về đâu:** `kernel/ports/detector.py`, `IDetector`. Layer kernel/ports (hợp đồng, không cài đặt).

**(2) Cần biết trước:** Port/Adapter (hexagonal — `knowledge-base/hexagonal-architecture/`); `Protocol`
(glossary `#protocol` — "vịt": ai có đủ method là hợp lệ, không cần kế thừa); `IFrameSource` (bài #03,
cùng pattern).

**(3) Code thật (quote `kernel/ports/detector.py`):**
```python
class IDetector(Protocol):
    """Detector interface.

    Contract:
        - setup() gọi trước detect() đầu tiên (nạp model/weights). Idempotent.
        - detect(frame) trả list[Detection]; box ở space detector khai báo (thường MODEL_INPUT).
        - teardown() giải phóng tài nguyên (GPU/model). Idempotent.
    """
    def detect(self, frame: np.ndarray) -> list[Detection]: ...

    def setup(self) -> None: ...

    def teardown(self) -> None: ...
```

**(4) Giải thích từng dòng:**
- `class IDetector(Protocol)` → định nghĩa **hợp đồng**: bất cứ class nào có đủ 3 method này là một
  detector hợp lệ (không cần `extends`).
- `detect(frame) -> list[Detection]` → nhận mảng ảnh, trả danh sách `Detection`.
- `setup()/teardown()` → nạp/giải phóng model. `...` = thân rỗng (Protocol chỉ khai báo, không cài).

**(5) Là gì:** `IDetector` = "ổ cắm" chuẩn cho mọi detector. Ai cắm vừa (đủ 3 method) đều dùng được.

**(6) Tại sao tồn tại / vấn đề nó giải:** để `application`/client **không phụ thuộc** YOLO/RTMDet cụ
thể. Client chỉ biết "có cái gì đó `detect` được". Đổi model = thay adapter cắm vào, không sửa client.

**(7) Dùng ở đâu trong project:** `FakeDetector` (mẩu 08) thoả `IDetector`. `InlineInferenceClient.
__init__(ring, detector: IDetector)` nhận **qua port** (tiêm phụ thuộc — DI) chứ không tạo detector
cụ thể bên trong (mẩu 09).

**(8) Không có port thì sao:** client phải `import` thẳng YOLO → dính chặt công nghệ; đổi model phải
sửa client + không test được bằng detector giả.

**(9) Ví von:** cổng USB. Máy tính không cần biết bạn cắm chuột hãng nào — cứ đúng chuẩn USB là chạy.
`IDetector` là "chuẩn USB" cho detector.

**(10) Liên kết bức tranh lớn:** cùng pattern `IFrameSource` (#03). Port sống ở `kernel/ports`; cài
đặt (`FakeDetector`) ở `adapters`. Đây là "hình chữ D" của hexagonal (driven port).

**(11) Cạm bẫy:** Protocol không ép lúc `import` — nếu class thiếu method, lỗi chỉ lộ khi gọi. Nên có
test contract (bài #03 có; #06 kiểm gián tiếp qua test client + detector).

**(12) Tự kiểm:**
- `Protocol` khác class kế thừa thường ở điểm nào?
- Vì sao client nhận `IDetector` thay vì tự tạo `FakeDetector`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/ports/detector.py` · Design step-06 ("IDetector port ... same pattern như
IFrameSource"). Độ chắc: cao (quote thật).
