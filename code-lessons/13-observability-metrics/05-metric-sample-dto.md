# 13.05 — `MetricSample` DTO — vì sao CÓ CẤU TRÚC (name+labels tách) thay chuỗi `name{k=v}`

## 1. Thuộc về đâu
Layer **kernel** — `kernel/metric_sample.py`. DTO dùng CHUNG giữa runtime (tạo) và adapters (render) → cả hai → kernel (không đảo hướng).

## 2. Cần biết trước
mẩu 04 (MetricsObserver ghi gauge). "lossy" = mất thông tin khi biến đổi (ở đây: parse ngược chuỗi key).

## 3. Code thật (quote nguyên văn — `kernel/metric_sample.py`)
```python
@dataclass(frozen=True)
class MetricSample:
    """1 điểm metric: loại + tên + nhãn (bounded) + giá trị. Immutable, thuần."""
    mtype: str                                  # "counter" | "gauge"
    name: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)
```
Docstring:
```python
"""Vì sao có cấu trúc (name + labels tách rời) thay vì chuỗi key `name{k=v}`: key nội bộ của InMemoryMetrics
nối chuỗi KHÔNG escape → parse-ngược bị LOSSY khi value nhãn chứa `,`/`=`/`}`. DTO này giữ (name, labels)
nguyên vẹn từ lúc GHI → renderer khỏi parse → đúng tuyệt đối (fix gốc, xem spec D-071/#280)."""
```

## 4. Giải thích từng mẩu nhỏ nhất
- `mtype` — "counter"/"gauge" (v1; histogram = Non-Goal).
- `name` — tên metric (vd `pipeline_fps`).
- `value` — giá trị float.
- `labels: Mapping[str,str]` — nhãn TÁCH RỜI (vd `{"source": "cam_1"}`), KHÔNG nhét vào tên.
- `frozen` — bất biến.

## 5. Là gì
DTO 1 điểm metric giữ (loại, tên, nhãn, giá trị) TÁCH BẠCH — không gộp thành chuỗi.

## 6. Tại sao CÓ CẤU TRÚC (fix gốc lossy)
`InMemoryMetrics` lưu key nội bộ dạng chuỗi `name{k=v,...}` (nối, KHÔNG escape). Nếu renderer PARSE NGƯỢC chuỗi key
đó để lấy lại (name, labels) → LOSSY khi value nhãn chứa `,`/`=`/`}` (parse nhầm ranh giới). Giải GỐC: giữ (name,
labels) nguyên vẹn từ lúc GHI trong `MetricSample` → renderer nhận cấu trúc, KHỎI parse → đúng tuyệt đối (D-071/#280).

## 7. Dùng ở đâu
`InMemoryMetrics.iter_metrics()` (mẩu 06) TẠO `list[MetricSample]`; `render_prometheus` (mẩu 07) TIÊU THỤ. Là "ngôn
ngữ chung" runtime↔adapters, đặt ở kernel (cả hai import xuống kernel, không đảo hướng).

## 8. Không có nó thì sao
Renderer parse chuỗi key `name{k=v}` → sai khi nhãn có ký tự đặc biệt (lossy). Hoặc runtime trả tuple thô → adapters
đoán cấu trúc. DTO frozen có cấu trúc = hợp đồng đúng + an toàn.

## 9. Ví von
Gửi bưu kiện với NHÃN riêng (tên, địa chỉ tách ô) thay vì viết tất cả thành 1 dòng rồi người nhận tự cắt — cắt sai nếu địa chỉ có dấu phẩy.

## 10. Liên kết bức tranh lớn
Ranh giới runtime↔adapters qua kernel DTO (giống `Detection`/`Track`/`CrossingEvent`). Fix lossy = "fix bản chất" (không parse ngược).

## 11. Cạm bẫy
- Đừng quay lại parse chuỗi key để render → lossy. Luôn dùng MetricSample (name, labels) từ nguồn.
- `labels` bounded (K-019) — DTO không ép, nhưng nguồn (MetricsObserver) phải giữ bounded.

## 12. Tự kiểm (Feynman)
- Vì sao render TỪ MetricSample (name+labels tách) đúng hơn parse chuỗi `name{k=v}`? Ca nào parse sai?
- MetricSample đặt ở tầng nào, vì sao (ai tạo, ai tiêu thụ)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/metric_sample.py` (đọc thật phiên này) · D-071/#280. Độ chắc: cao (quote trực tiếp).
