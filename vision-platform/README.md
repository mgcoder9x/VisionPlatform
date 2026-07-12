# vision_platform

Nền tảng thị giác **real-time multi-camera** (Python thuần + numpy), kiến trúc **Hexagonal 6 layer** ép bằng
import-linter, chạy được **không cần GPU** (đường CPU/ONNX) và mở rộng lên GPU khi có.

> 📐 **Đánh giá kiến trúc đầy đủ (cho người review): [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)** (gốc repo)
> — thiết kế, 6 package + 5 contract, ports, luồng dữ liệu, patterns (Forces/cái giá/khi-KHÔNG-dùng),
> hiệu năng, giới hạn trung thực, hướng dẫn review.
>
> 🧾 Xuất xứ quyết định: `ai-decision-journal/` (D/C/T/K) + `AI-IMPLEMENTATION-LOG.md` (gốc repo).

## Số liệu là gì (CHỐNG DRIFT — không hardcode trong README)

README này **không ghi cứng** số test/lint (nguồn drift kinh điển). Muốn số THẬT tại thời điểm hiện tại, chạy:

```
cmd /c scripts\vp.cmd verify   # pytest + import-linter + drift-check (từ gốc repo)
cmd /c scripts\vp.cmd test     # dòng cuối = số passed/skipped chính xác
lint-imports                   # (trong vision-platform/) → "N kept, 0 broken"
```

## Kiến trúc — 6 package, hướng phụ thuộc ÉP BẰNG MÁY

`domain ← kernel ← runtime ← application`; `adapters` (leaf: implement ports) + `profiles` (composition root)
ở rìa. 5 contract import-linter trong `pyproject.toml` (chạy `lint-imports` để verify "0 broken"):

- `domain/` — logic thuần (bbox, geometry, letterbox, motion, nms, tracking). KHÔNG cv2/torch/zmq/I/O.
- `kernel/` — DTO bất biến + **Ports (Protocol)**: `IFrameSource`/`IDetector`/`ISink`/`ITracker`/
  `IPipelineObserver`/`IInferenceClient`; DTO: MediaPacket, ReadResult, stage_contract, inference_protocol,
  crossing_event, metric_sample, capabilities, config, observability_port, backpressure, shm_layout.
- `runtime/` — cơ chế: PipelineRunner, SyncLinearExecutor, stages (motion_gate/detect/tracking/line_crossing/
  count/brightness/dark_filter), observability (structlog + InMemoryMetrics), iou_tracker, ipc (SHM ring +
  ring_control_plane + ring_pool).
- `application/` — điều phối đa-process: supervisor (bulkhead + cascade shutdown), ring_supervisor,
  writer/reader_epoch_coordinator, inline_inference_client, inference_server, config_loader.
- `adapters/` — leaf: frame source (fake/noise/video/rtsp/push), detector (fake/onnx/yolov5_pt/blob),
  sink (jsonl/crossing-jsonl/crossing-sqlite), metrics_http_server, metrics_exposition, capability_probe,
  zmq_inference_client.
- `profiles/` — composition root: **`vision_slice_app`** (entry chính, CLI), pipeline_factory, demo_pipeline,
  vision_demo_app, vision_web_app, vision_fullstack_profile.

## Patterns đã triển khai + kiểm chứng

- **Hexagonal** (ports + adapters, ép hướng phụ thuộc bằng import-linter).
- **Bulkhead** (supervisor đa-process, cách ly crash 1 camera/process).
- **Backpressure** (BoundedQueue 4 policy: DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT).
- **Immutability + CoW** (MediaPacket frozen; config frozen + MappingProxyType/tuple).
- **Ring-epoch switchover / ABA-prevention** (SHM generation counter + control-plane epoch + pool tái dùng).
- **Capability-aware execution** (`resolve_device` thuần, fail-fast; probe ở adapter → DTO `MachineCapabilities`).
- **Observability** (đo → render Prometheus 0.0.4 → serve `/metrics` HTTP secure-default localhost).
- **Analytics chuỗi**: tracking (IoU) → line-crossing → crossing-event (JSONL/SQLite) → motion-gate (ROI+illum).

## Quick start (Windows)

```powershell
# Setup venv + deps (launcher cross-machine, tự dò interpreter/GPU/extras)
cmd /c scripts\vp.cmd setup     # (từ gốc repo) — hoặc: python -m venv .venv; pip install -e .[dev,onnx,cv2,web]

# Kiểm máy TRƯỚC khi deploy (đổi máy GPU/không-GPU)
python -m vision_platform.profiles.vision_slice_app --capabilities
# → {"has_torch": ..., "has_cuda": ..., "gpu_name": ..., "has_cv2": ...}

# Chạy 1 pipeline (fake detector, no-GPU) — analytics + đếm-qua-vạch + lưu sự kiện
python -m vision_platform.profiles.vision_slice_app --source noise --frames 20 --track --line "0.0,0.5,1.0,0.5" --out events.jsonl

# Bật observability + phục vụ /metrics (Prometheus scrape)
python -m vision_platform.profiles.vision_slice_app --source noise --frames 100 --observe --metrics-port 9108
# scrape: curl http://127.0.0.1:9108/metrics   ·   health: curl http://127.0.0.1:9108/healthz

# Deploy khai báo bằng TOML (nhiều pipeline; observability khai trong file)
python -m vision_platform.profiles.vision_slice_app --config configs/example_analytics.toml
python -m vision_platform.profiles.vision_slice_app --config configs/example_rtsp_gpu.toml --validate  # chỉ KIỂM, không chạy
```

Cờ CLI chính (đọc từ `profiles/vision_slice_app.py`): `--config`/`--validate` (đường TOML) · `--source
{fake,noise,video,rtsp}` · `--detector {fake,pt}` `--weights` `--device auto|cpu|cuda|cuda:N` · `--motion-gate`
(+`--motion-gate-roi`/`--motion-gate-illum-robust`/`--motion-gate-max-skip`) · `--track` (+`--track-iou`/
`--track-max-age`) · `--line "ax,ay,bx,by"` · `--out`/`--crossing-out`/`--crossing-db` · `--observe`
(+`--observe-interval`/`--observe-every`) · `--metrics-port`/`--metrics-host` · `--capabilities`.

## Đã xong (no-GPU thương mại) vs Còn hoãn (TRUNG THỰC)

**Đã xong + verify (no-GPU):** hexagonal 6-layer (import-linter 0 broken) · analytics chuỗi (tracking →
line-crossing → crossing-event JSONL/SQLite → motion-gate ROI/illum) · observability TRỌN (đo → render →
serve `/metrics` + `--observe`/`--metrics-port`/`--capabilities`) · capability-aware GPU/CPU · SHM production
hardening + ring-epoch switchover · config-declarative TOML · dev-env launcher + CI + anti-drift 4-tầng.

**Còn hoãn — CHẶN điều kiện (không làm speculative):**
- **Nhánh GPU/CUDA**: máy có GPU nhưng torch chưa cài (K-079); cài = op nặng-mạng → chờ. `resolve_device`/probe
  đã xử lý no-GPU đúng; chỉ thiếu bằng chứng chạy detector CUDA thật.
- **Sink DB-server** (Postgres...): hiện có JSONL + SQLite (file); DB-server cần server thật để verify.
- **Runtime song song đa-pipeline**: `_run_from_config` chạy tuần tự (1 pipeline live/lúc) — scale tương lai.
- **ZMQ cross-process inference**: có adapter; đường mặc định là InlineInferenceClient (cùng process).
- **POSIX/ARM teardown atomicity**: verify chủ yếu trên Windows/x86.
- **Bảo mật `/metrics`**: mặc định localhost an toàn; phơi `0.0.0.0` ra internet chưa có auth/rate-limit (K-072).

> Mục 🔴/🟡 mở được theo dõi ở `ai-decision-journal/00-INDEX.md` (lọc 🔴/🟡).

## Tham chiếu

- **Kiến trúc đầy đủ + đánh giá:** `docs/ARCHITECTURE.md` (gốc repo).
- Thiết kế nguồn (giáo trình khái niệm): `Design/module-03-build-along/`.
- Bài học chi tiết từng bước: `code-lessons/` (gốc repo).
- Config mẫu: `configs/*.toml`. Benchmark: `benchmarks/`. Deploy: `deploy/` (Dockerfile + compose).
