# 11.09 — Lazy-import trong builder: vì sao `import` NẰM TRONG hàm

## 1. Thuộc về đâu
profiles — `pipeline_factory.py`, các builder `_src_*`/`_det_*`/`_stage_*`/`_sink_*`.

## 2. Cần biết trước
mẩu 08 (registry). "Lazy import" = import lúc CHẠY hàm, không phải lúc nạp module. Dep nặng: torch (~GB), cv2.

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`)
```python
def _src_rtsp(params: Mapping):
    from vision_platform.adapters.rtsp_frame_source import RtspFrameSource
    _need(params, "url", "source rtsp")
    return RtspFrameSource(params["url"], max_reconnect=params.get("max_reconnect"))
```
```python
def _det_pt(params: Mapping):
    from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
    _need(params, "weights", "detector pt")
    ...
    return Yolov5PtDetector(params["weights"], device=dev)
```
Và docstring đầu file:
```python
"""Lazy-import trong từng builder → registry import KHÔNG kéo dep nặng/optional (torch của `pt`, cv2 của video/rtsp)
lúc nạp module; chỉ import khi thực sự dựng loại đó.
"""
```

## 4. Giải thích từng mẩu nhỏ nhất
- `from ... import X` đặt **bên trong** hàm builder → chỉ chạy khi hàm ĐƯỢC GỌI (tức khi config thật sự dùng
  loại đó), KHÔNG chạy khi `import pipeline_factory`.
- `_det_pt` import `Yolov5PtDetector` (kéo torch) chỉ khi có detector `pt`; config toàn `fake` → torch KHÔNG bị import.

## 5. Là gì
Kỹ thuật hoãn import dep nặng/optional tới đúng lúc cần.

## 6. Tại sao tồn tại / vấn đề nó giải
Nếu import ở đầu file: nạp `pipeline_factory` (mà `validate_config`/`build_runner` luôn cần) sẽ KÉO torch+cv2
NGAY — máy no-GPU/không cài torch (như máy hiện tại, K-079) sẽ **ImportError** dù chỉ chạy config `fake`.
Lazy-import → chạy được trên máy tối giản; chỉ config nào cần `pt`/`video` mới đòi dep đó.

## 7. Dùng ở đâu
Mọi builder trong registry (mẩu 08). Đặc biệt quan trọng cho `validate_config` (mẩu 12): kiểm config `pt`
trên máy dev KHÔNG torch mà KHÔNG crash — vì `validate_config` chỉ TRA registry (không GỌI builder → không import torch).

## 8. Không có nó thì sao
Import đầu file → `import pipeline_factory` fail trên máy thiếu torch/cv2 → cả đường config sập, kể cả config
không dùng torch. Test no-GPU cũng không collect được. (Đúng nỗi đau capability-aware, K-079.)

## 9. Ví von
Chỉ mở va-li đồ nghề nặng KHI có việc cần nó — không vác cả kho ra mỗi lần mở cửa hàng.

## 10. Liên kết bức tranh lớn
Lazy-import + `validate_config`-chỉ-tra-registry = cặp bài trùng cho "chạy/kiểm trên máy no-GPU" (capability-aware,
`docs/ARCHITECTURE.md` §9). Nối với K-049 (không auto-thêm torch vào extras).

## 11. Cạm bẫy
- Đặt import đầu file "cho gọn" → phá tính chạy-được-máy-tối-giản. Giữ import TRONG builder.
- Lazy-import ẩn lỗi tên module tới lúc chạy (không phải lúc nạp) → phải có test dựng từng loại để phát hiện.

## 12. Tự kiểm (Feynman)
- Vì sao import torch đặt trong `_det_pt` chứ không đầu file? Máy no-torch chạy config `fake` sẽ ra sao nếu đặt đầu file?
- `validate_config` kiểm được config `pt` trên máy không torch nhờ điều gì? (gợi ý: tra ≠ gọi)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py` (đọc thật #322/#324) · K-049/K-079 (torch/máy no-GPU). Độ chắc: cao (quote trực tiếp).
