# 12.02 — `domain/tracking.py::greedy_associate` — vì sao INDEX-based (domain cấm import kernel)

## 1. Thuộc về đâu
Layer **domain** (tầng THẤP NHẤT) — `domain/tracking.py`. Thuật toán ghép "vật khung trước ↔ vật khung này" THUẦN.

## 2. Cần biết trước
mẩu 01 (stateful). `iou` (bài #06/nms — độ chồng 2 hộp ∈ [0,1]). Ranh giới: domain cấm import kernel (contract #1/#2).

## 3. Code thật (quote nguyên văn — `domain/tracking.py`)
```python
def greedy_associate(
    prev_boxes: Sequence[BBox],
    new_boxes: Sequence[BBox],
    iou_threshold: float,
    *,
    prev_labels: Optional[Sequence[str]] = None,
    new_labels: Optional[Sequence[str]] = None,
) -> list[tuple[int, int]]:
    """Ghép new↔prev theo IoU-greedy. Trả list `(new_idx, prev_idx)` (sort theo new_idx — xác định)."""
```
Docstring module:
```python
"""...KHÔNG import `Detection`@kernel (domain là tầng THẤP NHẤT, cấm import kernel) → API INDEX-BASED
(giống `nms_indices`): nhận boxes/labels rời, trả cặp index. Tầng trên (`runtime/iou_tracker.py`) ghép
index ↔ track_id/Detection."""
```

## 4. Giải thích từng mẩu nhỏ nhất
- Nhận `prev_boxes`/`new_boxes` (list `BBox`) + labels RỜI — KHÔNG nhận `Detection` (Detection ở kernel, domain
  cấm import).
- Trả `list[(new_idx, prev_idx)]` — chỉ INDEX (vị trí trong list), KHÔNG trả object track.
- `iou_threshold` ∈ [0,1]: chỉ ghép cặp có iou >= ngưỡng.
- labels optional: nếu có → chỉ ghép CÙNG label (xe không khớp với người).

## 5. Là gì
Hàm thuần ghép cặp new↔prev theo độ chồng hộp, trả về các cặp index.

## 6. Tại sao tồn tại / vấn đề nó giải (INDEX-based)
`Detection`/`Track` sống ở **kernel**; domain là tầng DƯỚI kernel → domain KHÔNG được import kernel (nếu import
→ `lint-imports` báo broken contract #1). Nhưng thuật toán association là toán THUẦN, nên đặt ở domain (tái dùng,
test dễ). Giải: domain làm việc trên **index + BBox** (BBox ở domain), tầng trên (`runtime/iou_tracker.py`) ghép
index ↔ `Detection`/`track_id`. Cùng khuôn `nms_indices` (bài #06).

## 7. Dùng ở đâu
`runtime/iou_tracker.py::update`: dựng `prev_boxes`/`new_boxes` từ tracks hiện có + detections mới → gọi
`greedy_associate` → nhận cặp index → ánh xạ index→track_id (mẩu 04).

## 8. Không có nó thì sao (nếu domain nhận Detection)
domain import kernel → vi phạm contract #1 → `lint-imports` đỏ → cổng verify fail. Hoặc nhét association vào
runtime → mất tính "toán thuần tái dùng ở domain" + khó test độc lập.

## 9. Ví von
Trọng tài chấm cặp đôi thi đấu chỉ theo SỐ ÁO (index) + hạng cân (label), không cần biết tên/hồ sơ (Detection) —
việc tra tên để ban tổ chức (runtime) làm.

## 10. Liên kết bức tranh lớn
Minh hoạ ranh giới domain (tầng thấp nhất, thuần, không kernel). Cùng triết lý `nms_indices`. Nối mẩu 04 (runtime ghép index↔id).

## 11. Cạm bẫy
- Cám dỗ trả `Detection`/`Track` cho tiện → kéo domain import kernel → thủng ranh giới. Giữ index-based.
- Nhớ kiểm độ dài labels khớp boxes (hàm có `raise ValueError` nếu lệch).

## 12. Tự kiểm (Feynman)
- Vì sao `greedy_associate` trả index chứ không trả `Track`/`Detection`? (contract nào?)
- Ai ghép index ↔ track_id? (tầng nào)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/tracking.py` (đọc thật phiên này) · `pyproject.toml` contract #1 (domain cấm kernel). Độ chắc: cao (quote trực tiếp).
