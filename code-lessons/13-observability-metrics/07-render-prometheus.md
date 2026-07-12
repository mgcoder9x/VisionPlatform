# 13.07 — `render_prometheus` — `# TYPE`, escape nhãn, `+Inf`/`NaN`, SORT xác định, raise name↔type xung đột

## 1. Thuộc về đâu
Layer **adapters** (leaf) — `adapters/metrics_exposition.py`. Hàm THUẦN: `list[MetricSample]` → text Prometheus 0.0.4. Chỉ stdlib + kernel DTO.

## 2. Cần biết trước
mẩu 05 (MetricSample), 06 (iter_metrics). Prometheus text 0.0.4: mỗi family 1 `# TYPE`, mỗi sample `name{k="v"} value`.

## 3. Code thật (quote nguyên văn — `adapters/metrics_exposition.py`)
```python
def _esc_label_value(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def _fmt_value(x: float) -> str:
    if math.isinf(x): return "+Inf" if x > 0 else "-Inf"
    if math.isnan(x): return "NaN"
    return repr(float(x))

def render_prometheus(samples):
    ...
    for s in items:
        if s.mtype not in _ALLOWED_TYPES: continue
        prev = types.get(s.name)
        if prev is not None and prev != s.mtype:
            raise ValueError(f"metric {s.name!r} có type XUNG ĐỘT: {prev!r} vs {s.mtype!r} ...")
        types[s.name] = s.mtype; families.setdefault(s.name, []).append(s)
    lines = []
    for name in sorted(families):
        lines.append(f"# TYPE {name} {types[name]}")
        for s in sorted(families[name], key=lambda x: sorted(x.labels.items())):
            ...
    return "\n".join(lines) + "\n"
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_esc_label_value` — escape theo chuẩn: `\`→`\\` (TRƯỚC, tránh double-escape), `"`→`\"`, newline→`\n`. Không escape → value nhãn có `"` sẽ phá cú pháp.
- `_fmt_value` — `inf`→`+Inf`/`-Inf`, `nan`→`NaN` (Prometheus yêu cầu VIẾT HOA vậy, KHÔNG phải 'inf'/'nan'). `repr(float)` giữ đủ độ chính xác (0.005 không thành 0).
- `if s.mtype not in _ALLOWED_TYPES: continue` — bỏ qua histogram (Non-Goal v1) thay vì phát TYPE sai.
- `raise ValueError` khi 1 `name` có 2 `mtype` (vừa counter vừa gauge) — exposition 2 `# TYPE` mâu thuẫn = HỎNG → fail-fast (bug lập trình phải lộ).
- `for name in sorted(families)` + `sorted(labels)` — SORT xác định → output ổn định (test/diff được).
- `+ "\n"` cuối — kết thúc bằng newline (chuẩn).

## 5. Là gì
Hàm thuần biến danh sách metric thành text đúng chuẩn Prometheus, xác định, an toàn ký tự.

## 6. Tại sao tồn tại / vấn đề nó giải
Prometheus scrape text theo LUẬT chặt; sai luật (không escape, sai +Inf, 2 TYPE) → Prometheus từ chối/parse sai.
Hàm này gói mọi luật + fail-fast khi dữ liệu mâu thuẫn (name↔type) → phơi bug thay vì phát text hỏng âm thầm.

## 7. Dùng ở đâu
`MetricsHttpExporter._MetricsHandler.do_GET` (mẩu 08): `render_prometheus(provider()).encode("utf-8")` cho `/metrics`.

## 8. Không có nó thì sao
Tự nối chuỗi metric rải rác → quên escape (value có `"` phá cú pháp), quên +Inf (Prometheus lỗi), thứ tự đổi (khó
test). Gom về 1 hàm thuần chuẩn-hoá + test riêng.

## 9. Ví von
Máy in hoá đơn theo mẫu chuẩn của cơ quan thuế: đúng ô, đúng ký tự thoát, số vô cực ghi đúng ký hiệu — sai mẫu thì cơ quan (Prometheus) không nhận.

## 10. Liên kết bức tranh lớn
Khâu RENDER: nhận MetricSample (05) từ iter_metrics (06) → text → exporter (08) phục vụ. THUẦN + xác định → dễ test (không cần HTTP).

## 11. Cạm bẫy
- Escape `\` PHẢI trước `"`/newline (thứ tự) — sai thì double-escape.
- `+Inf`/`NaN` viết hoa đúng chuẩn (không 'inf'/'nan').
- 1 name = 1 type — trộn counter/gauge cùng tên → raise (đúng).

## 12. Tự kiểm (Feynman)
- Vì sao escape `\` trước `"`? Vì sao `+Inf` không phải `inf`?
- Vì sao raise khi name có 2 type thay vì cứ render?
- Vì sao sort family + labels? (xác định)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`adapters/metrics_exposition.py` (đọc thật phiên này) · spec metrics-exposition (K-068). Độ chắc: cao (quote trực tiếp).
