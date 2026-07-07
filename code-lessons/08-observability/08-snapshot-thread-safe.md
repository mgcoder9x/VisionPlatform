# Mẩu 08 — `snapshot` copy độc lập + `get_histogram` copy under-lock

**(1) Thuộc về đâu:** `runtime/observability.py`, `InMemoryMetrics.snapshot` + `get_histogram`.

**(2) Cần biết trước:** reference vs copy (glossary — tham chiếu dùng chung vs bản sao riêng);
"mutated during iteration" (sửa list/dict trong lúc đang duyệt → lỗi).

**(3) Code thật (quote `runtime/observability.py`):**
```python
def get_histogram(self, name: str, **labels) -> list[float]:
    # PHẢI giữ lock — list() duyệt qua; histogram() append đồng thời sẽ race.
    with self._lock:
        return list(self._histograms[self._key(name, labels)])

def snapshot(self) -> dict[str, Any]:
    with self._lock:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: list(v) for k, v in self._histograms.items()},
        }
```

**(4) Giải thích từng ý nhỏ:**
- `list(self._histograms[...])` → tạo **bản copy** của list, KHÔNG trả tham chiếu tới list nội bộ.
- `with self._lock:` bao quanh cả lúc copy → trong lúc copy, thread khác không append được (chống
  "list mutated during iteration").
- `snapshot`: `dict(self._counters)` copy dict; `{k: list(v) ...}` copy từng list histogram → toàn bộ snapshot **độc lập** với internal.

**(5) Là gì:** hai cách đọc metrics ra ngoài — đều trả **bản sao** dưới khoá, không lộ tham chiếu nội bộ.

**(6) Tại sao tồn tại / vấn đề nó giải:**
- *Copy (không trả ref):* nếu trả thẳng list/dict nội bộ, caller `snap["counters"]["x"]=999` sẽ **sửa
  thẳng metrics thật** (nhiễm bẩn). Copy → caller mutate thoải mái, internal an toàn.
- *Copy dưới lock:* nếu copy ngoài lock, thread khác `append` đúng lúc `list()` duyệt → **RuntimeError
  (mutated during iteration)**. Giữ lock khi copy → an toàn.

**(7) Dùng ở đâu trong project:** exporter/endpoint đọc `snapshot()` để xuất metrics; `get_histogram`
để tính percentile. Test `test_snapshot_is_independent_copy` (mutate snapshot không đụng internal).

**(8) Không copy / copy ngoài lock thì sao:** caller mutate → nhiễm bẩn metrics thật; hoặc race
"mutated during iteration" → crash ngẫu nhiên lúc tải cao.

**(9) Ví von:** đưa khách **bản photocopy** sổ sách (không phải sổ gốc) — khách ghi chú lên bản copy
không làm hỏng sổ gốc. Và photocopy lúc đã khoá cửa (không ai đang viết vào sổ) → không nhoè.

**(10) Liên kết bức tranh lớn:** cùng nguyên tắc "đóng băng ở biên" như DTO (freeze list→tuple ở #06)
và thread-safety ở #07. Đây là defensive design cho đọc metrics an toàn.

**(11) Cạm bẫy:** đừng "tối ưu" bằng cách trả thẳng `self._histograms[key]` (ref) — sẽ nhiễm bẩn +
race. `dict(...)`/`list(...)` là copy NÔNG (shallow) — ở đây đủ vì phần tử là số (immutable).

**(12) Tự kiểm:**
- Cho 1 bug nếu `snapshot` trả tham chiếu thay vì copy.
- Vì sao copy phải nằm TRONG `with self._lock`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (snapshot/get_histogram) · test `test_snapshot_is_independent_copy` ·
Design step-08 (snapshot copy + Self-check #5). Độ chắc: cao (quote thật + test pass).
