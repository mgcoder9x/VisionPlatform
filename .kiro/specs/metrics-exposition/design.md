# Design Document — metrics-exposition (phơi metrics ra Prometheus text format, no-GPU)

## Overview

Đóng mảnh khoá còn lại của observability (D-069/D-070): metrics đang bị nhốt trong `InMemoryMetrics` (RAM,
trong-tiến-trình). Thêm một **renderer THUẦN** biến nội dung metrics của một tiến trình thành **Prometheus text
exposition format 0.0.4** để hệ giám sát bên ngoài (Prometheus scrape → Grafana/Alertmanager) đọc được.

**Nguyên tắc gốc:** renderer là NGƯỜI-ĐỌC cùng một registry mà `MetricsObserver` GHI vào — KHÔNG thêm đường-ghi
mới, KHÔNG đụng `PipelineRunner`. Renderer THUẦN (không I/O, không thời gian thực) → phơi bày qua HTTP là mối lo
RIÊNG (follow-on). Điều này giữ slice v1 kiểm-chứng-mạnh (assert chuỗi, no-GPU/no-mạng) và cắm đúng vào hexagonal.

**Phạm vi v1:** render **counter + gauge** (2 loại map thẳng sang Prometheus GAUGE/COUNTER). Histogram (cần
bucket) = Non-Goal v1. Phục vụ HTTP `/metrics` = follow-on (nêu phương án + trade-off, không code PHA này).

## Bằng chứng code đã đọc (chống bịa)
- `runtime/observability.py::InMemoryMetrics`:
  - `_counters: dict[str,int]`, `_gauges: dict[str,float]`, `_histograms: dict[str,list[float]]` (thread-safe, `Lock`).
  - `snapshot() -> {"counters":{...}, "gauges":{...}, "histograms":{k:list}}` (bản sao dưới lock).
  - `_key(name, labels)`: không label → `name`; có label → `name{k=v,k2=v2}` (labels **sorted**, `,`-ngăn,
    value KHÔNG ngoặc kép). ⇒ key nội bộ KHÔNG phải exposition hợp lệ, và parse-ngược bị **lossy** nếu value
    nhãn chứa `,`/`=`/`}` (rủi ro R4.3).
- `runtime/observers.py::MetricsObserver.on_snapshot` (D-069): CHỈ gọi `.gauge("pipeline_fps"|"pipeline_skip_rate"|
  "pipeline_frames_read"|"pipeline_stage_errors", value, source=snap.source_id)`. Nhãn duy nhất `source` (bounded).
- Import contract (đã verify #278 lint 5/0): "Adapters là leaf — không import runtime/application/profiles".

## Nguồn chuẩn (kiến thức — độ chắc chắn CAO, sẽ xác nhận lại lúc code)
Prometheus text exposition format 0.0.4 (docs chính thống prometheus.io/docs/instrumenting/exposition_formats):
- Mỗi dòng: `metric_name [ "{" label_name "=" `"`value`"` (, ...) "}" ] value [timestamp]`.
- `# TYPE <name> <type>` khai báo loại (counter/gauge/histogram/summary/untyped); `# HELP <name> <text>` optional.
- Value nhãn: escape `\`→`\\`, `"`→`\"`, newline→`\n`. Tên metric/nhãn theo `[a-zA-Z_][a-zA-Z0-9_]*`.
- Content-Type khi phục vụ: `text/plain; version=0.0.4; charset=utf-8`.
> Các khẳng định format trên gắn **độ chắc chắn CAO** (chuẩn công khai ổn định); lúc code sẽ đối chiếu lại 1 mẫu
> `prometheus_client.generate_latest()` (nếu cài được) hoặc docs để xác nhận byte-khớp — KHÔNG tự tin mù.

## Architecture

Thêm 1 renderer THUẦN ở `adapters` + 1 accessor đọc-có-cấu-trúc ADDITIVE ở `runtime`. KHÔNG layer mới, KHÔNG đảo hướng.

```
  Prometheus server ──scrape GET /metrics──► (follow-on: HTTP endpoint @profiles/web)
                                                   │ gọi
                                                   ▼
              adapters/metrics_exposition.py   render_prometheus(metrics_data) -> str   (THUẦN, stdlib-only)
                                                   ▲ nhận DỮ LIỆU THUẦN (list các MetricSample)
                                                   │
              runtime/observability.py  InMemoryMetrics.iter_metrics() -> list[MetricSample]  (ADDITIVE accessor)
                                                   ▲ ghi bởi
              runtime/observers.py  MetricsObserver (D-069, KHÔNG đổi)
```

- **Hướng phụ thuộc:** `adapters` (renderer) nhận dữ liệu thuần → KHÔNG import `runtime`. `profiles` (composition)
  gọi `InMemoryMetrics.iter_metrics()` rồi đưa dữ liệu cho `render_prometheus`. Không vi phạm import-linter.
- **Vì sao renderer ở `adapters`:** exposition format là GIAO THỨC NGOÀI (giống JSONL/SQLite sink) → đúng chỗ adapters.
- **Vì sao THÊM `iter_metrics()` (fix GỐC, không parse-ngược):** xem "Quyết định gốc" dưới.

## Quyết định gốc: lấy dữ liệu có-cấu-trúc thay vì parse-ngược chuỗi key (R4.3)

Vấn đề bản chất: `snapshot()` trả key dạng chuỗi `name{k=v,k2=v2}`. Muốn render `name{k="v"} value` phải tách lại
name + từng (k,v). Nhưng `_key` nối bằng `,`/`=` KHÔNG escape → nếu source_id chứa `,`/`=`/`}` thì parse-ngược
**sai** (lossy). Đây là format nội bộ, vốn KHÔNG thiết kế để parse lại.

- **Phương án A (fix ngọn):** renderer tự parse chuỗi key. Zero runtime-change, nhưng MONG MANH (sai với value
  nhãn lạ) → vi phạm tinh thần R4.3.
- **Phương án B (fix GỐC — CHỌN):** THÊM accessor `InMemoryMetrics.iter_metrics() -> list[MetricSample]` trả dữ
  liệu CÓ CẤU TRÚC `(mtype, name, labels: dict, value)`. `InMemoryMetrics` là nơi DUY NHẤT biết chắc (name, labels)
  trước khi bị `_key` nối chuỗi — nên đây là nơi đúng để phơi cấu trúc. Renderer nhận cấu trúc → KHÔNG parse →
  đúng tuyệt đối + đơn giản hơn. Additive (thêm method, không đổi `_key`/`snapshot`/đường-ghi).

> Cần lưu ý (trung thực): `_key` LƯU key đã-nối, nên `iter_metrics()` vẫn phải suy ra (name, labels). Để đúng
> tận gốc, `iter_metrics()` sẽ lưu-kèm cấu trúc lúc GHI (thêm map phụ `_labelsets[key] = (name, labels)` cập
> nhật trong `counter/gauge/histogram`) → không bao giờ phải parse chuỗi. Đây là phần additive nhỏ ở runtime,
> thiết kế chi tiết + test ở PHA2. (Phương án A vẫn ghi lại để user cân nếu muốn tối thiểu-diff.)

## Components and Interfaces

### 1. runtime/observability.py — accessor ADDITIVE (Phương án B)
```
@dataclass(frozen=True)
class MetricSample:              # dữ liệu THUẦN (đặt ở kernel hoặc runtime — xem Data Models)
    mtype: str                  # "counter" | "gauge"  (v1; "histogram" Non-Goal)
    name: str
    labels: dict[str, str]      # {} nếu không nhãn
    value: float

class InMemoryMetrics:
    # THÊM (không đổi cái cũ): lưu kèm cấu trúc lúc ghi để iter_metrics không parse chuỗi.
    def iter_metrics(self) -> list[MetricSample]: ...   # snapshot có-cấu-trúc, dưới lock, sorted
```
- `iter_metrics` trả list ĐÃ SẮP XẾP (theo name, rồi theo sorted labels) → renderer khỏi lo thứ tự (R3.1).

### 2. adapters/metrics_exposition.py — renderer THUẦN (stdlib-only)
```
def render_prometheus(samples: Iterable[MetricSample]) -> str:
    """Dữ liệu metrics có-cấu-trúc → Prometheus text exposition 0.0.4. THUẦN, xác định."""
```
- Thuật toán: (1) gom theo `name` (family) giữ thứ tự sorted; (2) mỗi family phát 1 dòng `# TYPE <name> <mtype>`;
  (3) mỗi sample phát `name{k="esc(v)",...} value` (nhãn sorted, value escape) hoặc `name value` nếu không nhãn;
  (4) `\n` nối dòng, kết thúc bằng `\n`.
- `esc(v)`: thay `\`→`\\`, `"`→`\"`, `\n`→`\\n` (đúng thứ tự: backslash TRƯỚC).
- Chỉ nhận `MetricSample` (dữ liệu thuần) → KHÔNG import runtime (giữ adapters=leaf, R4.1).
- Input rỗng → trả `""` (hoặc 1 comment) — không raise (R3.2).

### 3. profiles / web (follow-on — KHÔNG code v1)
- Composition: `text = render_prometheus(metrics.iter_metrics())` rồi phục vụ.
- Phương án phục vụ (thiết kế, chọn sau): (a) thêm route `/metrics` vào `vision_web_app` (Flask, đã có) —
  hợp tiến trình có web; (b) `http.server` tối giản riêng cho `camera_worker` headless (giống
  `prometheus_client.start_http_server`) — cần cho tiến trình không-Flask. Content-Type `text/plain; version=0.0.4`.

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `MetricSample` | frozen dataclass | `mtype∈{counter,gauge}`; `name` hợp lệ Prom; `labels` bounded; `value` số | kernel (thuần) | iter_metrics + renderer |
| `iter_metrics()` | method | trả list `MetricSample` sorted, dưới lock | runtime (InMemoryMetrics) | composition |
| `render_prometheus` | hàm thuần | Iterable[MetricSample] → str; xác định; no I/O | adapters | phục vụ /metrics |

- Đặt `MetricSample` ở **kernel** (DTO thuần, giống `PipelineSnapshot`) để CẢ `runtime` (tạo ra) LẪN `adapters`
  (tiêu thụ) dùng chung mà không đảo hướng (adapters→kernel hợp lệ; runtime→kernel hợp lệ). KHÔNG numpy/lib ngoài.
- KHÔNG đổi `snapshot()`/`_key`/`_counters`/`_gauges` (giữ nguyên). `iter_metrics` là kênh đọc-có-cấu-trúc THÊM.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| value nhãn chứa `"`/`\`/newline | `esc()` escape đúng chuẩn (backslash trước) → output hợp lệ | R2.1, P3 |
| input rỗng (không metric) | trả `""` (không comment thừa) — KHÔNG raise | R3.2, P7 |
| mtype ngoài {counter,gauge} (vd histogram) | v1 BỎ QUA family đó (Non-Goal) — không raise, không phát TYPE sai | Non-Goal |
| name không hợp lệ Prometheus | v1 giả định name do code nội bộ đặt (đã hợp lệ); KHÔNG tự ý sửa (nếu cần, sanitize = sub-spec) | 1.1 |
| gọi `iter_metrics` khi đang ghi | dưới `Lock` (như `snapshot`) → nhất quán, không race | R4.2 |

- Renderer THUẦN → không nuốt lỗi ngầm; lỗi lập trình (kiểu sai) để raise tự nhiên lúc test (fail nhanh).

## Correctness Properties

### Property 1: Gauge render đúng chuẩn (TYPE + sample)
Một gauge tên `g` nhãn `{source:"cam0"}` value 1.5 → output chứa `# TYPE g gauge` và dòng `g{source="cam0"} 1.5`.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Counter + không-nhãn
Một counter tên `c` không nhãn value 7 → output chứa `# TYPE c counter` và dòng `c 7`.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 3: Escaping đúng chuẩn
value nhãn `a"b\c` + newline → trong output thành `a\"b\\c\n` (backslash escape trước), bọc ngoặc kép.
**Validates: Requirements 2.1**

### Property 4: Một TYPE cho family nhiều sample
Gauge `g` với 2 nhãn khác nhau (source cam0, cam1) → output có ĐÚNG 1 dòng `# TYPE g gauge`, 2 dòng sample.
**Validates: Requirements 1.4, 2.2**

### Property 5: Xác định / idempotent
Gọi `render_prometheus` 2 lần trên cùng input → chuỗi GIỐNG HỆT (family sorted theo name, sample sorted theo nhãn).
**Validates: Requirements 3.1**

### Property 6: Input rỗng an toàn
`render_prometheus([])` → `""` (không raise).
**Validates: Requirements 3.2**

### Property 7: Không mất/nhầm nhãn (fix gốc, chống lossy)
Với source_id chứa ký tự phân tách (vd `cam,x=1`), qua `iter_metrics()` (cấu trúc) → render giữ ĐÚNG nhãn (không như parse-ngược chuỗi key). Test dựng nhãn có `,`/`=` → khớp.
**Validates: Requirements 4.3**

### Property 8: Ranh giới layer
`adapters/metrics_exposition.py` import CHỈ stdlib + kernel DTO (không runtime/application/profiles); import-linter 5 kept/0 broken.
**Validates: Requirements 4.1**

### Property 9: Tích hợp với MetricsObserver (end-to-end no-GPU)
Chạy pipeline fake + `MetricsObserver(m)` → `render_prometheus(m.iter_metrics())` chứa `pipeline_fps{source="..."}` + `pipeline_skip_rate{source="..."}` đúng camera.
**Validates: Requirements 5.4**

## Testing Strategy

- **Format cơ bản (P1,P2):** dựng `MetricSample` gauge/counter có/không nhãn → assert dòng `# TYPE` + sample đúng.
- **Escaping (P3):** value nhãn `"`, `\`, newline → assert `\"`, `\\`, `\n` trong output.
- **Family gom TYPE (P4):** 2 sample cùng name khác nhãn → đúng 1 TYPE + 2 sample.
- **Xác định (P5):** render 2 lần → bằng nhau; kiểm thứ tự sorted ổn định.
- **Rỗng (P6):** `render_prometheus([])` → `""`.
- **Không lossy (P7):** nhãn value chứa `,`/`=` qua `iter_metrics` → render đúng nhãn (đối chiếu với rủi ro parse-ngược).
- **Layer (P8):** lint `importlinter.api` 5 kept/0 broken; kiểm adapters không import runtime.
- **Tích hợp (P9):** pipeline fake + MetricsObserver → iter_metrics → render → assert có metric pipeline_* nhãn source.
- **Đối chiếu chuẩn (lúc code):** nếu `prometheus_client` cài được → so 1 mẫu output với `generate_latest` để xác nhận byte-khớp; nếu không → đối chiếu docs (ghi rõ [đã kiểm]/[chưa kiểm]).

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** đúng-chuẩn (scraper không lỗi) ⟂ zero-dep (không kéo prometheus_client) ⟂ layer sạch (adapters=leaf)
  ⟂ đúng-tận-gốc nhãn (không lossy) ⟂ additive (không đụng đường-ghi). Cân được: DTO thuần @kernel + accessor
  cấu-trúc @runtime + renderer thuần @adapters.
- **What varies?** ĐỊNH DẠNG phơi (Prometheus text v1; OpenMetrics/JSON tương lai) → trừu tượng = 1 hàm render
  nhận `MetricSample` (đổi format = thêm hàm render khác, không đụng nguồn). Loại metric (counter/gauge/histogram)
  = tham số `mtype`, không subclass.
- **Which way deps point?** kernel(MetricSample thuần) ← runtime(iter_metrics tạo) ; kernel ← adapters(renderer
  tiêu thụ). Không đảo. Không ai phụ thuộc format cụ thể ngoài adapters.
- **Cái GIÁ:** thêm 1 DTO + 1 accessor (lưu kèm `_labelsets` lúc ghi — chi phí RAM O(số-metric-key), nhỏ vì
  bounded K-019) + 1 renderer. Chấp nhận: đổi lấy đúng-tận-gốc + phơi được ra hệ giám sát chuẩn.
- **prometheus_client vs hand-roll?** hand-roll (CHỌN): (a) dữ liệu đã có trong `InMemoryMetrics` → chỉ cần
  format (nhỏ, thuần, test byte-khớp được); (b) prometheus_client có REGISTRY RIÊNG → dùng nó nghĩa là BỎ
  `InMemoryMetrics` hoặc bắc cầu (phức tạp hơn, +dep); (c) tính năng mạnh của nó (multiprocess mode, bucket
  histogram) v1 CHƯA cần. Cái mất: phải tự bảo trì format nếu chuẩn đổi (hiếm; 0.0.4 ổn định nhiều năm).
- **Khi nào KHÔNG dùng (renderer này):** (a) đã dùng prometheus_client toàn hệ → dùng `generate_latest` của nó,
  không cần renderer riêng. (b) cần histogram bucket/summary quantile → v1 chưa đủ (sub-spec sau). (c) gộp
  cross-process → cần push-gateway/federation (tầng cụm), renderer per-process không đủ một mình.
- **Recognize (dấu hiệu cần):** "đo được metrics nhưng không có gì scrape/dashboard được" = triệu chứng thiếu exposition.

## Non-Goals (nhắc lại)
Histogram/summary bucket · HTTP `/metrics` endpoint (follow-on) · dependency prometheus_client · gộp
cross-process (push-gateway/federation, tầng cụm K-040 C1) · đổi ngữ nghĩa `InMemoryMetrics`/`_key`/`snapshot`
hiện có · sanitize tên metric không hợp lệ (giả định code nội bộ đặt tên hợp lệ).
