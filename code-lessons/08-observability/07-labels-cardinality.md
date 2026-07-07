# Mẩu 07 — Labels (`_key`) + ngân sách cardinality (K-019)

**(1) Thuộc về đâu:** `runtime/observability.py`, `InMemoryMetrics._key`. Kèm quy tắc vận hành K-019.

**(2) Cần biết trước:** label/nhãn (chiều phân loại metric, vd camera_id); cardinality (số lượng giá
trị khác nhau của nhãn); Prometheus (hệ metrics phổ biến).

**(3) Code thật (quote `runtime/observability.py`):**
```python
@staticmethod
def _key(name: str, labels: dict) -> str:
    if not labels:
        return name
    labelstr = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{labelstr}}}"
```

**(4) Giải thích từng ý nhỏ:**
- `if not labels: return name` → không có nhãn thì key = tên (vd `"frames"`).
- `sorted(labels.items())` → **sắp xếp nhãn** → thứ tự truyền khác nhau vẫn ra **cùng key** (ổn định).
- `f"{name}{{{labelstr}}}"` → ghép kiểu Prometheus: `frames{camera_id=cam_1,status=ok}`.

**(5) Là gì:** hàm tạo khoá duy nhất từ tên metric + tập nhãn (sorted → ổn định).

**(6) Tại sao tồn tại / vấn đề nó giải:** cho phép cùng một metric tách theo chiều (camera_id, status)
→ query kiểu Prometheus (`sum by (camera_id) ...`). `sorted` để `counter("f", a=1, b=2)` và
`counter("f", b=2, a=1)` ra cùng key (không nhân đôi nhầm).

**(7) Dùng ở đâu trong project:** mọi `counter/gauge/histogram/get_*` gọi `_key(name, labels)`. Test
`test_counter_with_labels` (kể cả kiểm thứ tự nhãn khác nhau → cùng key).

**(8) Không có `_key` (hoặc không sort) thì sao:** không tách được theo chiều; không sort → cùng dữ
liệu nhưng thứ tự nhãn khác → 2 key khác nhau → đếm tách nhầm.

**(9) Ví von:** mã hàng gồm "tên + thuộc tính sắp xếp" (áo{màu=đỏ,size=M}). Sắp xếp thuộc tính để
"đỏ,M" và "M,đỏ" cùng một mã, không tạo 2 mã cho cùng cái áo.

**(10) Liên kết bức tranh lớn — K-019 (ngân sách cardinality):** đây là ràng buộc VẬN HÀNH sống còn.
Nhãn PHẢI là **tập hữu hạn nhỏ** (camera_id<100, status<10). ⛔ TUYỆT ĐỐI không đặt nhãn vô hạn:
```python
metrics.counter("frames_processed", packet_id=packet_id)   # ← SAI: mỗi packet = 1 key
```
30fps × 60s × 16 cam ≈ 28800 key/phút → **Prometheus OOM** trong vài giờ. Dữ liệu high-cardinality
(coords, packet_id) → cho vào **LOGS** (structlog), KHÔNG vào label metric.

**(11) Cạm bẫy:** `InMemoryMetrics` KHÔNG tự chặn cardinality (không thể — là kỷ luật con người). Người
viết call-site phải tự giữ. Đây là lỗi kinh điển làm sập hệ metrics production.

**(12) Tự kiểm:**
- Vì sao `_key` sort nhãn?
- Đặt `bbox coords` làm label metric — sai chỗ nào? Nên để coords ở đâu?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (_key) · journal K-019 · Design step-08 (Labels + Cardinality
budget + Self-check #3). Độ chắc: cao (quote thật + test labels pass).
