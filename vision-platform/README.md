# vision_platform

Mini Vision Platform — dựng theo `Design/module-03-build-along` (Step 01→10) để **kiểm chứng thiết kế**
kiến trúc real-time multi-camera. Đây là bản đã **production-hardening** (vượt blueprint `vision_demo`
gốc): thêm SHM production hardening (#05), ring-epoch switchover (sub-spec #05b), observability, backpressure,
supervisor shutdown.

> ⚠️ Số liệu dưới đây là **thực tế đã verify trên máy này** (Windows, Python 3.13.12), KHÔNG phải con số
> blueprint trong Design (Design nói 110 test cho `vision_demo` MVP — dự án này đã tiến hoá xa hơn).

## Kiến trúc — 4 layer Hexagonal (+ adapter rim + profiles composition root)

Hướng phụ thuộc (ép bằng import-linter, 5 contract, **0 broken**): `domain ← kernel ← runtime ← application`;
`adapters`/`profiles` ở rìa.

- `domain/` — logic thuần (`BBox`, `CoordinateSpace`). KHÔNG import I/O.
- `kernel/` — DTO + ports thuần: `MediaPacket`, `ReadResult`, `ShmFrameRefData`, `inference_protocol`
  (InferenceRequest/Detection/InferenceError/InferenceResponse), `backpressure` (BackpressurePolicy + BoundedQueue),
  `stage_contract`, `shm_layout`/`shm_control_plane_layout`; `ports/` (`IFrameSource`, `IDetector`).
- `runtime/` — thực thi + hạ tầng: `SyncLinearExecutor`, `BaseStage` + `stages/`, `observability`
  (structlog + log_context + InMemoryMetrics), `ipc/` (`shm_frame_ring`, `ring_control_plane`, `ring_pool`).
- `application/` — điều phối: `ring_supervisor`, `writer/reader_epoch_coordinator`, **`inline_inference_client`**
  (ở đây, KHÔNG ở adapters — vì cần import runtime; xem ERRATA E-06-1), `supervisor` (process + cascade shutdown).
- `adapters/` — leaf: `FakeFrameSource`, `NoiseFrameSource`, `FakeDetector`.
- `profiles/` — composition root: `demo_pipeline.py`.

## Patterns đã triển khai + kiểm chứng

- **Hexagonal** (ports + adapters, ép hướng phụ thuộc bằng import-linter).
- **Bulkhead** (supervisor đa-process, cách ly crash — #09).
- **Backpressure** (BoundedQueue 4 policy: DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT — #07).
- **Immutability + CoW** (MediaPacket frozen — #02).
- **ABA prevention + ring-epoch switchover** (SHM generation counter + control-plane epoch, pool tái dùng — #05/#05b).
- **SHM production hardening**: lease deadline, QUARANTINED slot, multi-reader pinning, single-writer, crash-recovery (#05).
- **Observability**: structlog JSON + contextvars log_context + InMemoryMetrics (#08).
- **Cascade shutdown cooperative-first** (graceful trên cả Windows lẫn POSIX — #09, ERRATA E-10).

## Quick start (Windows PowerShell)

```powershell
# Setup
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]

# Chạy test
pytest                    # → 290 passed, 1 skipped

# Kiểm ranh giới layer
lint-imports              # → 5 kept, 0 broken

# Chạy demo end-to-end
python -m vision_platform.profiles.demo_pipeline --source noise --frames 10 --threshold 100.0
python -m vision_platform.profiles.demo_pipeline --source fake  --frames 5  --threshold 100.0
```

## Test count (THẬT — đã verify, không phải blueprint)

**290 passed, 1 skipped** (~16s; multi-process spawn của #05/#05b/#09 làm chậm). 1 skip có chủ đích
(guard theo nền tảng, vd ARM/POSIX skip trên Windows). Bao gồm test cross-process THẬT (SHM #05, switchover
T-B #05b, multi-reader, supervisor #09) + property-based test (Hypothesis, #05b).

Build wheel: `python -m build` → `dist/vision_platform-0.1.0-py3-none-any.whl` + `.tar.gz`
(fresh-install verify: `import vision_platform` → 0.1.0).

## Trade-offs vs Vision Platform production (đã hoãn có chủ ý)

- **ZMQ ROUTER/DEALER** cross-process inference — dùng `InlineInferenceClient` (cùng process); ZMQ là sub-spec production sau.
- **Production log handlers** (non-blocking queue / rotation / flush-on-shutdown) — K-018.
- **Hang detection / heartbeat liveness** — supervisor hiện chỉ bắt crash, không bắt hang (K-020); restart chưa có exponential backoff (K-021).
- **Cardinality guard** cho metrics — quy tắc vận hành thủ công (K-019).
- **Teardown POSIX / ARM atomicity** — verify mới trên Windows/x86 (K-001/K-003).
- **Secrets management** (RTSP credentials, mask URL trước log), **circuit breaker / DLQ / TrackerScope per source** — production concern.

> Các mục 🔴/🟡 mở được theo dõi đầy đủ ở `ai-decision-journal/` (gốc repo). Nhật ký quyết định: `AI-IMPLEMENTATION-LOG.md`.

## Definition of Done (#10)

- [x] Tests pass: `pytest` → **290 passed, 1 skipped** (verify thật).
- [x] No deps leak: `lint-imports` → **5 kept, 0 broken** (domain/kernel không import I/O ngoài).
- [x] Type hints ở public API.
- [x] Immutability (MediaPacket frozen) + idempotent setup/teardown.
- [x] Process isolation (bulkhead) verify qua test #09.
- [x] Backpressure 4 policy đúng spec (#07).
- [x] End-to-end demo chạy (`--source noise` processed 10; `--source fake` skipped 5).
- [x] Package builds: `python -m build` → wheel + sdist; fresh-install `__version__` = 0.1.0.
- [x] README (file này) — kiến trúc + quick start + số thật + trade-offs.

## Tham chiếu

- Thiết kế nguồn: `Design/module-03-build-along/` (Step 01→10).
- Production đầy đủ: `Vision_platform_architecture_design/`.
- Bài học chi tiết từng bước: `code-lessons/` (gốc repo).
