# Mẩu 06 — `InMemoryMetrics`: counter / gauge / histogram (+ Lock)

**(1) Thuộc về đâu:** `runtime/observability.py`, class `InMemoryMetrics`.

**(2) Cần biết trước:** `Lock` (khoá — bài #07); `defaultdict(int)`/`defaultdict(list)` (dict tự tạo
giá trị mặc định); 3 loại số đo (counter/gauge/histogram).

**(3) Code thật (quote `runtime/observability.py`):**
```python
def __init__(self):
    self._lock = Lock()
    self._counters: dict[str, int] = defaultdict(int)
    self._gauges: dict[str, float] = {}
    self._histograms: dict[str, list[float]] = defaultdict(list)

def counter(self, name: str, value: float = 1.0, **labels) -> None:
    key = self._key(name, labels)
    with self._lock:
        self._counters[key] += int(value)

def gauge(self, name: str, value: float, **labels) -> None:
    key = self._key(name, labels)
    with self._lock:
        self._gauges[key] = value

def histogram(self, name: str, value: float, **labels) -> None:
    key = self._key(name, labels)
    with self._lock:
        self._histograms[key].append(value)
```

**(4) Giải thích từng loại:**
- `counter` → **chỉ tăng** (`+=`). Dùng cho "tổng số ..." (frames_processed_total).
- `gauge` → **gán đè** (lên/xuống). Dùng cho "mức hiện tại" (queue_depth, gpu_memory).
- `histogram` → **append vào list** (phân phối giá trị). Dùng cho "độ trễ" (latency_ms) để tính percentile.
- Mọi thao tác `with self._lock:` → nguyên tử, thread-safe.
- `key = self._key(name, labels)` → gộp tên + nhãn thành 1 khoá (mẩu 07).

**(5) Là gì:** kho số đo trong bộ nhớ, thread-safe, 3 loại theo cách tổng hợp khác nhau.

**(6) Tại sao 3 loại (không gộp 1):** mỗi loại **tổng hợp khác nhau**: counter cộng dồn (rate), gauge
lấy giá trị mới nhất, histogram cần cả phân phối (p50/p95/p99). Prometheus cũng phân biệt đúng 3 loại này.

**(7) Dùng ở đâu trong project:** nơi cần đo (vd `metrics.counter("frames_processed", camera_id=...,
status="ok")`). Là *sink* cho counters backpressure (#07) khi wire (bước sau). Test 4 loại + thread-safe (mẩu 09).

**(8) Không có Lock thì sao:** nhiều thread `+= 1` cùng lúc → **mất update** (race): đọc-cộng-ghi
xen kẽ → đếm thiếu. Test thread-safe (10×100=1000) chứng minh Lock giữ đúng.

**(9) Ví von:** counter = công-tơ-mét (chỉ tiến); gauge = kim xăng (lên xuống); histogram = sổ ghi mọi
lần đo để sau vẽ biểu đồ phân phối. Lock = mỗi lần chỉ 1 người được ghi sổ.

**(10) Liên kết bức tranh lớn:** trụ Metrics của observability. `InMemoryMetrics` là bản đơn giản —
production thay bằng adapter Prometheus/StatsD (cùng khái niệm 3 loại). Nối K-017 (wire backpressure).

**(11) Cạm bẫy:** `counter` ép `int(value)` — truyền float lẻ sẽ bị cắt. `gauge` gán đè (không cộng) —
đừng nhầm với counter. `histogram` giữ TẤT CẢ giá trị (list lớn dần) → production cần bucket/giới hạn.

**(12) Tự kiểm:**
- 3 loại metric khác nhau ở cách tổng hợp thế nào? Cho 1 ví dụ mỗi loại.
- Vì sao cần Lock? Test nào chứng minh?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (InMemoryMetrics) · test `test_counter_*`/`test_gauge_*`/
`test_histogram_*`/`test_metrics_thread_safe` · Design step-08 (Phần 3). Độ chắc: cao (quote thật + test pass).
