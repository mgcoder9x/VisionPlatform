# Design Document — pipeline-observability (quan sát vận hành, no-GPU)

## Overview

Đóng K-017/K-040-C1 (phần no-GPU): thêm **quan sát vận hành ĐỊNH KỲ, theo camera** phát ra TRONG lúc
`PipelineRunner.run()` chạy, qua **một PORT observer tiêm vào** (hexagonal). Opt-in, **mặc định no-op → hành vi
+ `RunStats` hiện tại giữ NGUYÊN** (backward-compat). Giải quyết 2 hạn chế bản chất đã đọc code: (1) `RunStats`
chỉ trả lúc `run()` KẾT THÚC → luồng RTSP vô hạn = mù; (2) số nghiệp vụ nằm trong artifacts, chưa wire quan sát.

**Nguyên tắc gốc:** quan sát là kênh SONG SONG, phụ trợ — KHÔNG đổi ngữ nghĩa pipeline, KHÔNG được làm sập vòng
lặp chính khi observer lỗi. Con số (fps, skip_rate) là DẪN XUẤT số học từ bộ đếm đã có trong `run()` + clock TIÊM
→ kiểm chứng xác định, no-GPU.

## Bằng chứng code đã đọc (chống bịa)
- `runtime/pipeline_runner.py::PipelineRunner.run`: đã đếm local `frames_read/processed/skipped/stage_errors/
  cancelled/eof/source_errors`; có `self._clock_ns` (monotonic_ns tiêm); vòng lặp `read→execute→sink.handle`;
  teardown trong `finally` (sink→executor→source). Trả `RunStats(frozen)` cuối hàm.
- `runtime/observability.py::InMemoryMetrics`: `counter/gauge/histogram`, thread-safe (tái dùng cho impl v1).
- `kernel/ports/frame_source.py::IFrameSource.source_id`: id duy nhất/camera.
- `runtime/stages/motion_gate_stage.py`: SKIP → executor trả `StageStatus.SKIPPED` → `run()` tăng `skipped`
  (nên `skip_rate` = skipped/frames_read đúng nghĩa "frame bị gate bỏ").

## Architecture

Thêm 1 port thuần ở `kernel` + wiring ở `runtime`. KHÔNG layer mới, KHÔNG đảo hướng phụ thuộc.

```
adapters/ (Prometheus/StatsD/OTLP)   ← Non-Goal v1 (port sẵn-sàng-cắm)
      ┆ implements
      ▼
kernel/observability_port.py
   • PipelineSnapshot (frozen DTO — thuần, no lib ngoài)
   • IPipelineObserver (Protocol: on_snapshot(snapshot))
      ▲ dùng
      │
runtime/pipeline_runner.py  PipelineRunner.run(...)
   • đếm nhịp emit (emit_every_n / emit_interval_s) + tính fps/skip_rate từ clock TIÊM
   • gọi observer.on_snapshot(...) — BỌC try/except (isolation, R4.2)
   • observer mặc định = _NoopObserver (backward-compat, R1.4)
      │ 1 impl v1 (tái dùng InMemoryMetrics/structlog)
      ▼
runtime/observers.py  MetricsObserver / LoggingObserver (no dep ngoài)
```

- **Hướng phụ thuộc:** `kernel` (port + DTO thuần) ← `runtime` (runner + impl). Adapter ngoài (Prometheus) sẽ ở
  `adapters` và chỉ phụ thuộc `kernel` (đúng contract). Không vi phạm import-linter.
- **Vì sao port ở kernel, DTO ở kernel:** để adapter tương lai implement mà KHÔNG import runtime (giữ adapters=leaf).
- **Vì sao impl v1 ở runtime:** tái dùng `InMemoryMetrics` (đã ở runtime) → zero dependency mới; đủ cho demo/test.

## Components and Interfaces

### 1. kernel/observability_port.py (thuần — Protocol + DTO)
```
@dataclass(frozen=True)
class PipelineSnapshot:
    source_id: str
    frames_read: int
    processed: int
    skipped: int
    stage_errors: int
    frames_per_second: float
    skip_rate: float
    is_final: bool = False        # True cho snapshot cuối (R1.3)

class IPipelineObserver(Protocol):
    def on_snapshot(self, snapshot: PipelineSnapshot) -> None: ...
```
- DTO immutable, thuần Python (no numpy/lib ngoài) → nằm kernel hợp lệ. `is_final` phân biệt snapshot chốt.
- Protocol 1 method (YAGNI) — lifecycle setup/teardown chưa cần (impl tự quản trong __init__).

### 2. runtime — `_NoopObserver` (default) + wiring vào PipelineRunner
```
class _NoopObserver:
    def on_snapshot(self, snapshot): return None      # backward-compat: default, không làm gì

# PipelineRunner.__init__ thêm (đều optional, default giữ hành vi cũ):
    observer: IPipelineObserver = _NoopObserver(),
    emit_every_n: int = 0,          # 0 = KHÔNG emit định kỳ (chỉ emit cuối nếu observer != noop)
    emit_interval_s: float = 0.0,   # >0 = emit khi đã trôi >= interval kể từ lần emit trước
```
- Trong `run()`: giữ nguyên các biến đếm. Thêm state: `start_ns`, `last_emit_ns`, `last_emit_frames` (cho interval-fps).
  - **Kiểm nhịp THEO GIỜ ở ĐẦU mỗi vòng lặp (fix Lỗ-review-A):** ngay đầu `while True`, nếu
    `emit_interval_s>0 and (clock_ns()-last_emit_ns)/1e9 >= emit_interval_s` → `_emit(is_final=False)`.
    **Đặt ở đầu để mất-camera/reconnecting (read()→no-data→continue) VẪN phát snapshot** (đó là lúc cần quan sát
    nhất: frames_read đứng yên + source_errors tăng). Nhịp-theo-giây KHÔNG phụ thuộc có data hay không.
  - **Kiểm nhịp THEO FRAME trên nhánh CÓ data:** sau khi `frames_read++` + execute + cập nhật đếm, nếu
    `emit_every_n>0 and frames_read % emit_every_n == 0` → `_emit(is_final=False)`.
  - `_emit(is_final)`: dựng `PipelineSnapshot` rồi `_safe_emit`; cập nhật `last_emit_ns`, `last_emit_frames`.
    - `skip_rate = skipped/frames_read` (0.0 nếu frames_read==0).
    - `frames_per_second` = **INTERVAL throughput (fix Lỗ-review-C)**: `(frames_read-last_emit_frames) /
      max((clock_ns()-last_emit_ns)/1e9, ε)` — phản ánh nhịp GẦN ĐÂY (không che sự cố), không phải trung bình tích luỹ.
      Snapshot đầu tiên (last_emit_ns=start_ns) → interval từ đầu run.
  - **Emit cuối (R1.3):** trong `finally` NGOÀI CÙNG (trước `return RunStats`), LUÔN gọi `_emit(is_final=True)`
    (fix Lỗ-review-B: KHÔNG isinstance-check observer; `_NoopObserver.on_snapshot` là guard rẻ) — đảm bảo chốt
    kể cả khi thân raise/should_stop.
- `_safe_emit` bọc try/except (xem Error Handling) → observer lỗi KHÔNG sập pipeline.

### 3. runtime/observers.py — impl v1 (tái dùng hạ tầng có sẵn, no dep mới)
- `MetricsObserver(metrics: InMemoryMetrics)`: `on_snapshot` → `metrics.gauge("pipeline_skip_rate", snap.skip_rate,
  source=snap.source_id)` + `gauge("pipeline_fps", ...)` + `counter(...)`. Nhãn CHỈ `source_id` (bounded, K-019).
- `LoggingObserver()`: `on_snapshot` → structlog 1 dòng JSON/snapshot (parse được bởi Loki/ELK). Tuỳ chọn.
- (Prometheus/StatsD = Non-Goal v1 → adapters sub-spec sau, chỉ cần implement `IPipelineObserver`.)

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `PipelineSnapshot` | frozen dataclass | các đếm ≥0; `skip_rate`,`fps` ∈ [0,∞); `is_final` bool | kernel | port on_snapshot |
| `IPipelineObserver` | Protocol | 1 method `on_snapshot(PipelineSnapshot)->None` | kernel | runner DI |
| `emit_every_n` | int | ≥0 (0=tắt nhịp-theo-frame) | runtime | PipelineRunner.__init__ |
| `emit_interval_s` | float | ≥0.0 (0=tắt nhịp-theo-giây) | runtime | PipelineRunner.__init__ |

- KHÔNG đổi `RunStats` (giữ frozen như cũ). Snapshot là DTO RIÊNG, kênh song song.
- `skip_rate = skipped/frames_read` (guard 0, tích luỹ). `frames_per_second` = INTERVAL: `(frames_read-last_emit_frames)/max(Δt,ε)` với Δt từ clock TIÊM (phản ánh nhịp GẦN ĐÂY, không che sự cố — fix Lỗ-review-C). Test xác định nhờ clock tiêm bước cố định.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| `observer.on_snapshot` ném lỗi | `_safe_emit` bắt Exception (chừa BaseException) → structlog.warning("observer_error", ...) + tăng bộ đếm nội bộ `_observer_errors`; **tiếp tục vòng lặp** (không sập pipeline chính) | R4.2, P4 |
| `frames_read==0` lúc emit | `skip_rate=0.0`, `fps=0.0` (guard chia 0) — không raise | R2.2 |
| `elapsed_s==0` (clock chưa nhích) | `fps=0.0` (guard) | 1.2 |
| observer là `_NoopObserver` (default) | `on_snapshot` return None → zero overhead ngữ nghĩa; RunStats + hành vi y hệt | R1.4, R4.1 |

- Nguyên tắc: quan sát PHỤ TRỢ → lỗi observer bị **cô lập** (bọc), nhưng **log rõ** (không nuốt im lặng che bug).
  Lỗi PIPELINE chính (stage/source) vẫn theo đường cũ (RunStats.stage_errors/source_errors) — KHÔNG đụng.

## Correctness Properties

### Property 1: Emit định kỳ đúng nhịp (không đợi kết thúc)
Với `emit_every_n=N>0` + observer spy, chạy M frame → observer nhận snapshot tại mỗi bội số N của frames_read (không phải chỉ lúc cuối).
**Validates: Requirements 1.1, 4.3**

### Property 2: Snapshot cuối luôn được phát
Khi `run()` kết thúc (EOF/should_stop/kể cả thân raise), observer (khác no-op) nhận đúng 1 snapshot `is_final=True` trước khi `RunStats` trả về.
**Validates: Requirements 1.3**

### Property 3: Số liệu đúng số học + per-camera
Snapshot mang `source_id` đúng; `skip_rate == skipped/frames_read` (0 nếu frames_read=0); `frames_per_second == (frames_read-last_emit_frames)/Δt` (interval, clock tiêm bước cố định → xác định).
**Validates: Requirements 1.2, 2.1, 2.2**

### Property 7: Emit khi camera mất-kết-nối (không data) — fix Lỗ-review-A
Với `emit_interval_s>0`, khi source liên tục trả no-data/RECONNECTING (frames_read đứng yên), observer VẪN nhận snapshot theo nhịp giờ (thấy sự cố live), KHÔNG im lặng tới lúc dừng.
**Validates: Requirements 1.1**

### Property 4: Isolation lỗi observer
observer.on_snapshot luôn raise → `run()` vẫn xử lý HẾT frame + trả `RunStats` đúng (bằng no-op) + `_observer_errors>0`.
**Validates: Requirements 4.2**

### Property 5: Backward-compat tuyệt đối
KHÔNG truyền observer (default no-op) + emit_every_n=0 → `RunStats` + hành vi BẰNG hiện tại (so số trên loạt input); baseline 546/1 giữ.
**Validates: Requirements 1.4, 4.1**

### Property 6: Bounded cardinality + ranh giới layer
Nhãn metric chỉ `source_id`+tên cố định (không packet_id/toạ độ); kernel port thuần (no lib ngoài); lint 5 kept/0 broken.
**Validates: Requirements 2.3, 3.1, 3.4**

## Testing Strategy

- **Nhịp emit (P1):** FakeFrameSource(max_frames=10) + `emit_every_n=3` + ObserverSpy → spy nhận snapshot tại frames_read=3,6,9 (+1 cuối). Clock tiêm.
- **Snapshot cuối (P2):** chạy tới EOF + should_stop + trường hợp stage raise → luôn có đúng 1 `is_final=True` cuối.
- **Số học (P3):** dựng pipeline có motion-gate skip vài frame → kiểm `skip_rate` khớp `skipped/frames_read`; clock tiêm bước cố định → `frames_per_second` (interval) xác định; `source_id` đúng.
- **Mất-kết-nối (P7 — fix Lỗ-review-A):** FakeSource trả TIMEOUT/no-data liên tục + `emit_interval_s>0` + clock tiêm nhảy đủ interval → observer NHẬN snapshot dù frames_read đứng yên (không đợi kết thúc).
- **Isolation (P4):** ObserverRaising (on_snapshot luôn raise) → RunStats == chạy no-op + vòng lặp không sập + `_observer_errors>0`.
- **Backward-compat (P5):** không observer vs no-op, so `RunStats` trên loạt input → bằng nhau; full `pytest -q` ≥ 546/1.
- **Layer (P6):** lint `importlinter.api` 5 kept/0 broken; kiểm kernel port không import lib ngoài.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** thấy-sớm-live (an toàn vận hành) ⟂ overhead-thấp (không gọi mỗi frame → emit_every_n) ⟂ không-làm-sập-pipeline (isolation lỗi) ⟂ backward-compat (no-op default) ⟂ hexagonal (port, không cột backend). Cân được: nhịp cấu hình + no-op default + bọc lỗi.
- **What varies?** BACKEND quan sát (in-mem/log/Prometheus/StatsD) → trừu tượng đúng chỗ = PORT (Protocol) + DTO, KHÔNG phải nhồi backend vào runner. NHỊP emit = tham số, không phải subclass.
- **Which way deps point?** kernel(port/DTO thuần) ← runtime(runner+impl) ← (adapters sau). Không đảo. Adapter Prometheus phụ thuộc kernel, không phụ thuộc runtime.
- **Cái GIÁ:** thêm vài phép so-sánh nhịp + 1 lần dựng DTO mỗi lần emit (rẻ, theo nhịp không theo frame); 1 port + 1 DTO + 1 impl. Chấp nhận được so với giá trị "không bay mù".
- **Khi nào KHÔNG dùng:** (a) batch ngắn chạy 1 lần rồi xong → `RunStats` cuối là đủ, không cần live (để observer no-op). (b) cross-process ~100 cam gộp metrics → CẦN adapter Prometheus + scrape/push (Non-Goal v1, tầng cụm). (c) cần per-detection analytics → KHÔNG dùng metric (cardinality); dùng event sink (đã có CrossingEvent).
- **Recognize (dấu hiệu cần):** vận hành RTSP dài mà "không biết gì đang xảy ra" tới lúc dừng = triệu chứng thiếu observability → bật observer + emit_interval_s.

## Ràng buộc dùng (hợp đồng — không phải bug)
- **observer PHẢI non-blocking/nhanh:** `on_snapshot` chạy TRONG thread vòng lặp `run()` → nếu observer làm I/O
  chậm (push mạng) sẽ backpressure lên pipeline (đọc frame chậm lại). Observer nặng (Prometheus push/HTTP) PHẢI
  tự buffer async nội bộ. v1 impl (InMemoryMetrics/log) là non-blocking. Ghi rõ để adapter tương lai tuân.

## Non-Goals (nhắc lại)
Adapter Prometheus/StatsD/OTLP cụ thể · gộp metrics cross-process (tầng cụm K-040 C1) · per-packet label ·
tracing/log-handler production (K-018) · đổi ngữ nghĩa RunStats · observer async/buffered (impl adapter tự lo).
