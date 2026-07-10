# Requirements Document

> **Spec:** metrics-exposition (phơi metrics ra chuẩn Prometheus text format — no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Đóng:** mảnh khoá còn lại của observability (D-069/D-070): `MetricsObserver` → `InMemoryMetrics` mới chỉ
> đo TRONG-tiến-trình (RAM). Ở quy mô ~100 cam (nhiều tiến trình `camera_worker`), operator KHÔNG có cách gom/
> dashboard/cảnh báo tập trung → vẫn "mù ở tầng fleet". Cần kênh PHƠI metrics theo chuẩn để hệ giám sát scrape.
> **Nền tảng (đã ĐỌC CODE thật — `runtime/observability.py`):**
> - `InMemoryMetrics` giữ 3 bảng: `_counters: dict[str,int]`, `_gauges: dict[str,float]`, `_histograms: dict[str,list[float]]`.
> - `snapshot() -> {"counters":{...}, "gauges":{...}, "histograms":{...}}` (bản sao thread-safe).
> - Key mỗi metric do `_key(name, labels)` sinh: nếu không label → `name`; có label → `name{k=v,k2=v2}`
>   (labels **sorted**, ngăn bằng `,`, value **KHÔNG** có ngoặc kép). Đây KHÔNG phải chuẩn Prometheus.
> - `MetricsObserver.on_snapshot` (D-069) hiện CHỈ gọi `.gauge(...)` với nhãn duy nhất `source` (bounded, K-019).
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Observability (D-069/D-070) đã đo được sức khỏe runtime per-camera và ghi vào `InMemoryMetrics`. Nhưng
`InMemoryMetrics` **chỉ sống trong bộ nhớ tiến trình** — không có cách nào để một hệ giám sát bên ngoài
(Prometheus/Grafana/Alertmanager) đọc được. Với sản phẩm thương mại ~100 camera chạy trên **nhiều tiến trình**,
đây là lỗ gốc: đo được nhưng không **phơi bày** được → operator vẫn không dashboard/cảnh báo tập trung được.

Chuẩn công nghiệp để phơi metrics là **Prometheus text exposition format** (`text/plain; version=0.0.4`):
mỗi tiến trình phát ra một khối text (mỗi metric 1 dòng `name{label="value"} number`, kèm dòng `# TYPE`), một
scraper (Prometheus) kéo định kỳ qua HTTP `/metrics`, rồi Grafana vẽ + Alertmanager cảnh báo.

Tính năng này thêm khả năng **render `InMemoryMetrics` → Prometheus text format** — một hàm THUẦN, xác định,
kiểm chứng được **không cần GPU/mạng** (assert chuỗi output). Nó cắm đúng vào kiến trúc đã có: `MetricsObserver`
GHI vào `InMemoryMetrics`, renderer ĐỌC cùng registry đó và phát ra text — không thêm đường-ghi mới, không đụng
`PipelineRunner`. Phần phục vụ qua HTTP `/metrics` được tách làm bước sau (follow-on) để giữ slice v1 kiểm-chứng-mạnh.

**Ranh giới layer (bám luật §4):** renderer nằm ở `adapters` (exposition format = giao thức NGOÀI). `adapters`
là leaf — KHÔNG import `runtime`/`application`/`profiles`. Do đó renderer nhận **dữ liệu thuần** (dict/list do
`InMemoryMetrics` trả ra), KHÔNG import kiểu `InMemoryMetrics`. Composition (lấy dữ liệu từ metrics → render →
phục vụ) xảy ra ở `profiles`/web. KHÔNG cv2/torch.

**Chống bịa:** mọi tham chiếu (cấu trúc `snapshot()`, format `_key`, `MetricsObserver` chỉ dùng gauge nhãn
`source`) ĐÃ đọc code thật `runtime/observability.py`. Chuẩn Prometheus text format 0.0.4 là chuẩn công khai
(sẽ trích dẫn nguồn chính thống trong design; các khẳng định về format gắn độ-chắc-chắn).

### Goals
- Phơi nội dung `InMemoryMetrics` ra **Prometheus text exposition format 0.0.4 hợp lệ** (gauge + counter).
- Đúng chuẩn: mỗi metric family 1 dòng `# TYPE`, mỗi sample `name{label="value"} value`, **escape** value nhãn.
- Xác định + ổn định: cùng input → cùng output (thứ tự sorted) → diff được, test được không cần GPU/mạng.
- Giữ nguyên đường-ghi hiện tại (`MetricsObserver`→`InMemoryMetrics`); renderer là NGƯỜI-ĐỌC, additive.
- Giữ layer sạch: renderer ở `adapters` (leaf), nhận dữ liệu thuần; import-linter 5 kept/0 broken.

### Non-Goals
- KHÔNG histogram/summary với bucket (`_bucket{le=...}`) ở v1 — `InMemoryMetrics` lưu list thô, chưa có ranh
  giới bucket; phơi histogram đúng chuẩn cần thiết kế bucket riêng (sub-spec sau). v1 phủ **counter + gauge**.
- KHÔNG dựng HTTP `/metrics` endpoint ở v1 (cần server chạy → verify yếu trên máy no-server). Phục vụ HTTP =
  follow-on (tái dùng web app / `http.server`), thiết kế nêu phương án + trade-off, KHÔNG code ở PHA này.
- KHÔNG thêm dependency `prometheus_client` (xem trade-off design — hand-roll đủ + zero-dep + kiểm-soát-format).
- KHÔNG gộp metrics cross-process (push-gateway/federation) — tầng cụm K-040 C1, sub-spec scale sau.
- KHÔNG đổi ngữ nghĩa `InMemoryMetrics` đang có (chỉ CÓ THỂ THÊM accessor đọc — additive, xem design).

## Glossary
- **Exposition format** — định dạng text chuẩn Prometheus (`text/plain; version=0.0.4`) mà scraper đọc từ `/metrics`.
- **Metric family** — nhóm sample cùng tên metric (vd `pipeline_fps`) khác nhau ở nhãn; chia sẻ 1 dòng `# TYPE`.
- **Sample** — 1 dòng dữ liệu: `metric_name{label="value",...} number` (nhãn optional).
- **Label escaping** — trong exposition, value nhãn phải escape: `\`→`\\`, `"`→`\"`, xuống-dòng→`\n`.
- **Scrape** — hành động Prometheus GET `/metrics` định kỳ để thu số liệu (pull model).
- **Bounded cardinality (K-019)** — nhãn chỉ giá trị hữu hạn biết trước (source_id); CẤM packet_id/toạ độ.

## Requirements

### Requirement 1: Render gauge/counter ra Prometheus text format hợp lệ
**User Story:** Là kỹ sư vận hành, tôi muốn một khối text đúng chuẩn Prometheus từ metrics của tiến trình, để Prometheus scrape và Grafana vẽ được mà không cần bộ chuyển đổi riêng.
#### Acceptance Criteria
- 1.1 — WHEN nhận nội dung metrics (gauge/counter) của một tiến trình, THE renderer SHALL trả về chuỗi Prometheus text exposition format 0.0.4 hợp lệ.
- 1.2 — THE renderer SHALL phát đúng 1 dòng `# TYPE <name> gauge` cho mỗi gauge family và `# TYPE <name> counter` cho mỗi counter family, ĐỨNG TRƯỚC các sample của family đó.
- 1.3 — THE mỗi sample SHALL có dạng `name value` (không nhãn) hoặc `name{k1="v1",k2="v2"} value` (có nhãn), với value là số.
- 1.4 — WHERE một metric family có NHIỀU sample (khác nhãn), THE renderer SHALL gom chúng dưới **một** dòng `# TYPE` duy nhất (không lặp TYPE mỗi sample).

### Requirement 2: Đúng chuẩn escaping + nhãn
**User Story:** Là kỹ sư, tôi muốn output không vỡ khi value nhãn chứa ký tự đặc biệt, để scraper không lỗi parse.
#### Acceptance Criteria
- 2.1 — THE value của mỗi nhãn SHALL được bọc trong ngoặc kép và escape theo chuẩn: `\`→`\\`, `"`→`\"`, ký tự xuống dòng→`\n`.
- 2.2 — THE tên nhãn trong output SHALL giữ đúng như nguồn (chỉ value được escape); các nhãn của một sample SHALL theo thứ tự xác định (sorted) để output ổn định.
- 2.3 — WHERE nhãn được phơi ra, THE renderer SHALL chỉ phơi các nhãn bounded do nguồn cung cấp (source_id + tên metric cố định) — KHÔNG tự thêm nhãn high-cardinality (K-019).

### Requirement 3: Xác định + ổn định (diff được, test được)
**User Story:** Là kỹ sư, tôi muốn cùng một trạng thái metrics luôn cho cùng một output, để test bằng assert chuỗi và so sánh giữa lần scrape.
#### Acceptance Criteria
- 3.1 — WHEN gọi renderer hai lần trên cùng một input, THE output SHALL GIỐNG HỆT nhau (xác định — thứ tự family sorted theo tên, sample sorted theo nhãn).
- 3.2 — WHEN input rỗng (không metric nào), THE renderer SHALL trả về output HỢP LỆ (rỗng hoặc chỉ comment) mà KHÔNG raise.
- 3.3 — THE renderer SHALL là hàm THUẦN (không I/O, không thời gian thực, không trạng thái ẩn) → kiểm chứng xác định không cần GPU/mạng.

### Requirement 4: Ranh giới layer + additive (không phá baseline)
**User Story:** Là kiến trúc sư, tôi muốn khả năng phơi metrics không đảo hướng phụ thuộc và không làm hỏng đường-ghi hiện tại.
#### Acceptance Criteria
- 4.1 — THE renderer SHALL nằm ở `adapters` và chỉ nhận **dữ liệu thuần** (dict/list Python), KHÔNG import `runtime`/`application`/`profiles` (adapters = leaf); import-linter 5 kept/0 broken.
- 4.2 — THE thay đổi SHALL additive: KHÔNG đổi chữ ký/hành vi `MetricsObserver`/`PipelineRunner`/`InMemoryMetrics` hiện có; baseline **560 passed/1 skipped · lint 5/0** giữ (+ test mới). Nếu cần accessor đọc mới ở `InMemoryMetrics` thì phải THÊM (không sửa cái cũ).
- 4.3 — THE renderer SHALL KHÔNG mất mát/nhầm nhãn: dữ liệu nhãn phơi ra SHALL khớp đúng nhãn nguồn (giải quyết tận gốc rủi ro parse-ngược chuỗi key `name{k=v}` bị lossy khi value chứa `,`/`=`/`}`).

### Requirement 5: Kiểm chứng KHÔNG cần GPU/mạng (xác định)
**User Story:** Là kỹ sư, tôi muốn test exposition xác định trên máy dev để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test dựng metrics thủ công (gauge + counter, có/không nhãn) → assert output chứa đúng dòng `# TYPE` + sample đúng định dạng.
- 5.2 — Test escaping: value nhãn chứa `"`, `\`, xuống-dòng → assert output escape đúng chuẩn.
- 5.3 — Test xác định: gọi 2 lần → output bằng nhau; input rỗng → không raise.
- 5.4 — Test tích hợp với `MetricsObserver`: chạy pipeline fake có `MetricsObserver` → lấy dữ liệu metrics → render → assert có `pipeline_fps`/`pipeline_skip_rate` với nhãn `source="..."` đúng camera.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format: Overview/Architecture/Components/Data Models/Error
Handling/Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) vị trí renderer
(`adapters`) + chữ ký hàm thuần nhận dữ liệu thuần; (b) **quyết định gốc**: cách lấy dữ liệu metrics có-cấu-trúc
(accessor mới `InMemoryMetrics.iter_metrics()` additive) để tránh parse-ngược lossy — kèm phương án thay thế +
trade-off; (c) thuật toán render (nhóm family + TYPE + escaping + sorted) chứng minh xác định; (d) trade-off
hand-roll vs `prometheus_client`; (e) phương án phục vụ HTTP `/metrics` (follow-on) + vì sao tách; (f) backward-compat
+ ranh giới layer. **KHÔNG code ở PHA này** (chờ user valid thiết kế).
