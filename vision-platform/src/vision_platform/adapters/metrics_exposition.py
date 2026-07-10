r"""Render metrics → Prometheus text exposition format 0.0.4 (spec metrics-exposition). Layer: adapters (leaf).

Hàm THUẦN: nhận list `MetricSample` (DTO kernel, dữ liệu thuần) → chuỗi text để hệ giám sát (Prometheus)
scrape. KHÔNG import runtime/application/profiles (adapters=leaf); chỉ stdlib + kernel DTO.

Chuẩn (prometheus.io exposition_formats 0.0.4): mỗi family 1 dòng `# TYPE <name> <type>`; mỗi sample
`name{k="v",...} value` (nhãn optional); value nhãn escape `\`→`\\`, `"`→`\"`, newline→`\n`; value số dùng
`+Inf`/`-Inf`/`NaN` cho vô cực/không-xác-định. Xác định (family sort theo name, sample sort theo nhãn).
"""
from __future__ import annotations

import math
from typing import Iterable

from vision_platform.kernel.metric_sample import MetricSample

_ALLOWED_TYPES = frozenset({"counter", "gauge"})  # v1: histogram/summary = Non-Goal


def _esc_label_value(v: str) -> str:
    """Escape value nhãn theo chuẩn Prometheus. Backslash TRƯỚC (tránh double-escape)."""
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _fmt_value(x: float) -> str:
    """Số → text hợp lệ Prometheus. inf/nan → +Inf/-Inf/NaN (KHÔNG phải 'inf'/'nan' chữ thường)."""
    if math.isinf(x):
        return "+Inf" if x > 0 else "-Inf"
    if math.isnan(x):
        return "NaN"
    return repr(float(x))  # giữ đủ độ chính xác (0.005 không thành 0); exponent Go-style hợp lệ


def render_prometheus(samples: Iterable[MetricSample]) -> str:
    """list `MetricSample` → Prometheus text 0.0.4. THUẦN, xác định.

    Xung đột name↔type (cùng tên vừa counter vừa gauge) → raise ValueError (fail-fast; exposition 2 `# TYPE`
    mâu thuẫn là HỎNG — bug lập trình phải lộ). Input rỗng → "" (không raise).
    """
    items = list(samples)
    if not items:
        return ""

    types: dict[str, str] = {}
    families: dict[str, list[MetricSample]] = {}
    for s in items:
        if s.mtype not in _ALLOWED_TYPES:
            continue  # histogram... = Non-Goal v1 → bỏ qua (không phát TYPE sai)
        prev = types.get(s.name)
        if prev is not None and prev != s.mtype:
            raise ValueError(
                f"metric {s.name!r} có type XUNG ĐỘT: {prev!r} vs {s.mtype!r} — "
                f"1 tên metric chỉ được 1 type (exposition Prometheus hợp lệ)."
            )
        types[s.name] = s.mtype
        families.setdefault(s.name, []).append(s)

    lines: list[str] = []
    for name in sorted(families):
        lines.append(f"# TYPE {name} {types[name]}")
        for s in sorted(families[name], key=lambda x: sorted(x.labels.items())):
            val = _fmt_value(s.value)
            if s.labels:
                lbl = ",".join(f'{k}="{_esc_label_value(str(v))}"'
                               for k, v in sorted(s.labels.items()))
                lines.append(f"{name}{{{lbl}}} {val}")
            else:
                lines.append(f"{name} {val}")
    return "\n".join(lines) + "\n"
