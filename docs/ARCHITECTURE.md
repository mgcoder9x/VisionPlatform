# ARCHITECTURE — Vision Platform (bản đánh giá cho người ngoài)

> **Mục đích:** để một kỹ sư/kiến trúc sư CHƯA từng đọc repo này có thể đọc 1 file, hiểu và **đánh giá**
> được: thiết kế, pattern, ranh giới module, tổ chức code, đặc tính hiệu năng, và **cách tự kiểm chứng**.
>
> **Phạm vi:** mô tả hệ **đang có thật** trong `vision-platform/src/vision_platform/` (đọc code trực tiếp,
> không phải blueprint trong `Design/`). `Design/` là giáo trình *khái niệm*; file này là *hiện trạng*.
>
> **Cập nhật:** 2026-07-11 · gắn với `AI-IMPLEMENTATION-LOG.md` Entry #316. Tài liệu là ảnh-chụp-thời-điểm;
> **nguồn sự thật SỐNG** = code + `ai-decision-journal/` (quyết định) + kết quả `vp verify`.

---

## 0. Cách kiểm chứng mọi khẳng định trong file này (đọc trước)

Tài liệu này CỐ Ý **không hardcode số dễ đổi** (số test, số commit) trong văn xuôi — để tránh drift (README
cũ từng kẹt "290 test"). Thay vào đó, mọi khẳng định kiểm-chứng-được bằng lệnh cố định:

| Muốn kiểm | Lệnh (Windows) | Ý nghĩa |
|---|---|---|
| Ranh giới 6 layer còn nguyên | `lint-imports` (trong `vision-platform/`) | In "N kept, 0 broken" cho các contract §2 |
| Toàn bộ test xanh | `cmd /c scripts\vp.cmd verify` | pytest + import-linter + drift-check |
| Số test/skip THẬT hiện tại | `cmd /c scripts\vp.cmd test` | Dòng cuối `pytest` = con số chính xác lúc chạy |
| Năng lực máy (GPU/torch/cv2) | `python -m vision_platform.profiles.vision_slice_app --capabilities` | In JSON `{has_torch,has_cuda,gpu_name,...}` |
| Bản ghi quyết định nhất quán | `cmd /c scripts\vp.cmd check` | drift-check C1–C7 + self-test |

→ Khi review, đừng tin số trong prose bất kỳ đâu — **chạy lệnh trên**. Đó là thiết kế chống-drift chủ đích.

---

## 1. Hệ này là gì

Nền tảng thị giác **real-time multi-camera** (phát hiện/đếm/analytics vật thể từ nhiều camera), viết bằng
Python thuần + numpy, chạy được **không cần GPU** (đường CPU/ONNX) và mở rộng lên GPU khi có. Trọng tâm kỹ thuật:

- **Cách ly lỗi giữa camera** (1 camera hỏng KHÔNG kéo sập cả hệ) — pattern bulkhead đa-process.
- **Truyền frame zero-copy giữa process** qua shared-memory ring buffer (SHM) có chống ABA (epoch/generation).
- **Chống nghẽn (backpressure)** khi nguồn nhanh hơn khả năng xử lý — hàng đợi giới hạn, 4 chính sách.
- **Khai báo pipeline bằng file TOML** (deploy nhiều camera không sửa code).
- **Observability chuẩn Prometheus** (đo → render text 0.0.4 → phục vụ `/metrics` HTTP).
- **Ranh giới kiến trúc ép bằng máy** (import-linter), không dựa kỷ luật con người.

Dependencies lõi (từ `pyproject.toml`, đã đọc): `numpy`, `psutil`, `structlog`, `pyzmq`, `msgpack`.
Optional (extras): `cv2` (opencv), `onnx`/`onnxruntime`, `web` (flask), `pt` (yolov5+torch — NẶNG), `dev`
(pytest/import-linter/hypothesis). Python `>=3.11`.

---

## 2. Kiến trúc phân tầng — 6 package, hướng phụ thuộc 1 chiều (ÉP BẰNG MÁY)

Code chia thành **6 package** dưới `vision_platform/`, tổ chức thành chuỗi phụ thuộc 4 tầng + 2 package ở rìa:

```
        domain  ←  kernel  ←  runtime  ←  application
          ▲          ▲          ▲            ▲
          └──────────┴─────┬────┴────────────┘
                     adapters (leaf: implement ports)
                     profiles (composition root: ráp mọi thứ)
```

- **`domain/`** — logic thuần: hình học/thuật toán, KHÔNG I/O, KHÔNG lib nặng.
  (`bbox`, `geometry`, `letterbox_transform`, `motion`, `nms`, `tracking`.)
- **`kernel/`** — hợp đồng: **DTO bất biến + Ports (Protocol)**. Chỉ phụ thuộc `domain`. KHÔNG adapter cụ thể.
  (`ports/` = IFrameSource/IDetector/ISink/ITracker/IInferenceClient; DTO: `media_packet`, `read_result`,
  `stage_contract`, `inference_protocol`, `crossing_event`, `metric_sample`, `capabilities`, `config`,
  `observability_port`, `backpressure`, `shm_layout`/`shm_control_plane_layout`.)
- **`runtime/`** — cơ chế thực thi + hạ tầng: chỉ phụ thuộc `kernel`.
  (`pipeline_runner`, `sync_linear_executor`, `base_stage` + `stages/`, `observability` (structlog+InMemoryMetrics),
  `observers`, `iou_tracker`, `composite_sink`/`collecting_sink`, `ipc/` = `shm_frame_ring`/`ring_control_plane`/`ring_pool`.)
- **`application/`** — điều phối vòng đời + đa process: phụ thuộc `kernel` + `runtime`.
  (`supervisor` (bulkhead process + cascade shutdown), `ring_supervisor`, `writer/reader_epoch_coordinator`,
  `inline_inference_client`, `inference_server`, `config_loader`.)
- **`adapters/`** — **leaf**: hiện thực Ports, được chạm dep cụ thể (cv2/onnx/torch/zmq). KHÔNG import ngược lên.
  (frame source: `fake`/`noise`/`video_file`/`rtsp`/`push`; detector: `fake`/`onnx`/`yolov5_pt`/`blob`;
  sink: `jsonl_event`/`crossing_event`/`crossing_event_sqlite`; `metrics_http_server`, `metrics_exposition`,
  `capability_probe`, `zmq_inference_client`, `detector_pipeline`, `yolo_postprocess`.)
- **`profiles/`** — **composition root**: nơi DUY NHẤT ráp adapter thật vào ports, phụ thuộc mọi thứ.
  (`vision_slice_app` = entry sản phẩm chính (CLI); `pipeline_factory`, `demo_pipeline`, `vision_demo_app`,
  `vision_web_app`, `vision_fullstack_profile`.)

### 2.1 Ranh giới ÉP BẰNG MÁY — 5 contract import-linter (bằng chứng, không phải lời hứa)

`pyproject.toml` khai báo 5 contract `forbidden` (chạy `lint-imports` để verify "0 broken"):

1. **domain** cấm import: `cv2, torch, zmq, multiprocessing, psutil, msgpack, onnxruntime, onnx, yolov5,
   ultralytics` + mọi layer khác (`kernel/runtime/application/adapters/profiles`). → domain thuần tuyệt đối.
2. **kernel** cấm: các lib I/O trên + `shared_memory` + `runtime/application/adapters/profiles`. → kernel chỉ
   thấy `domain`. (numpy được phép — domain cũng dùng.)
3. **runtime** cấm import `application/adapters/profiles`. → cơ chế không biết ai điều phối nó.
4. **application** cấm import `adapters/profiles`. → điều phối chỉ nói chuyện qua **Ports**, không biết adapter cụ thể.
5. **adapters** cấm import `runtime/application/profiles`. → adapter là leaf, cắm-vào chứ không kéo-ngược.

Đây là "Dependency Inversion" được **cưỡng chế**: nghiệp vụ (domain/kernel) không bao giờ phụ thuộc chi tiết
hạ tầng (cv2/torch/zmq). Đổi detector YOLO→ONNX, đổi sink file→DB = thêm adapter, KHÔNG đụng lõi.

---

## 3. Ports — các "khớp nối" (seams) để thay thế/kiểm thử

Ports là `typing.Protocol` thuần trong `kernel/ports/` (structural typing → adapter không cần kế thừa, chỉ
cần khớp chữ ký). Đây là điểm mấu chốt cho testability (tiêm fake) và cho việc thay công nghệ.

| Port | Vai trò | Hợp đồng cốt lõi (đọc từ code) | Impl thật (adapters/runtime) |
|---|---|---|---|
| `IFrameSource` | Nguồn frame vào | `setup()` idempotent → `read(timeout_ms)->ReadResult` (KHÔNG return None) → `teardown()`; `is_finite` (batch/stream); `source_id`; là context manager (`__exit__` KHÔNG nuốt exception) | fake/noise/video_file/rtsp/push |
| `IDetector` | Phát hiện vật | `setup()` (nạp model) → `detect(frame)->list[Detection]` → `teardown()`; box ở space detector khai báo | fake/onnx/yolov5_pt/blob |
| `ISink` | Đích kết quả | `setup()` → `handle(ExecutionResult)` (nhận CẢ non-SUCCESS: SKIPPED/ERROR/CANCELLED) → `teardown()` | jsonl/crossing-jsonl/crossing-sqlite/collecting/composite |
| `ITracker` | Theo dõi xuyên frame | `update(detections)->tuple[Track]` + `reset()` + `unique_count`/`active_count`; **stateful, camera-affinity** (1 instance/1 camera) | `runtime/iou_tracker` (IoU-greedy) |
| `IPipelineObserver` | Nhận số liệu định kỳ | `on_snapshot(PipelineSnapshot)`; impl PHẢI non-blocking (chạy trong thread run()) | `runtime/observers`, MetricsObserver |
| `IInferenceClient` | Gọi inference (có thể cross-process) | request/response DTO | `inline_inference_client`, `zmq_inference_client` |

**Nhận xét thiết kế (để reviewer soi):** hợp đồng nhấn mạnh (a) `setup/teardown` **idempotent**; (b) lifecycle
đối xứng; (c) trả **DTO đầy đủ trạng thái** thay vì `None` (vd `ReadResult` có `status` EOF/ERROR/TIMEOUT/
RECONNECTING; `ExecutionResult` có `StageStatus`) — nơi gọi tự quyết, không mất thông tin.

---

## 4. Luồng dữ liệu end-to-end (1 pipeline = 1 camera)

Engine trung tâm là `runtime/pipeline_runner.py::PipelineRunner.run()` (đã đọc verbatim). Vòng lặp:

```
setup: source → executor → sink        (teardown NGƯỢC lại trong finally, LUÔN chạy kể cả raise)
loop mỗi vòng:
  1. (nếu bật) emit snapshot THEO GIỜ ở ĐẦU loop  → mất-camera/reconnecting vẫn phát được số liệu
  2. check should_stop / max_frames
  3. r = source.read(timeout_ms)
     - EOF + is_finite  → break; EOF + stream → continue
     - ERROR            → source_errors++, continue
     - !has_data        → continue (TIMEOUT/RECONNECTING/DROPPED)
  4. dựng MediaPacket (media_ref = factory(frame); mặc định InMemoryArrayRef.from_copy; SHM cắm không sửa runner)
  5. result = executor.execute(packet)   → phân loại SUCCESS/SKIPPED/ERROR/CANCELLED
  6. (nếu bật) emit snapshot THEO FRAME (mỗi N frame)
  7. sink.handle(result)   ← LUÔN gọi, mọi status
finally: emit snapshot CUỐI (is_final=True)
```

Các stage xử lý (trong `runtime/stages/`, ráp theo config): `motion_gate` (bỏ frame tĩnh) → `dark_filter`/
`brightness` → `detect` (qua IDetector) → `tracking` (qua ITracker) → `line_crossing` → `count`. Kết quả đổ ra
sink (JSONL/SQLite) và/hoặc số liệu ra observer → `/metrics`.

**Điểm cần khen/soi (reviewer):** (a) teardown lồng `try/finally` nhiều tầng đảm bảo giải phóng tài nguyên
đúng thứ tự ngược — quan trọng cho service chạy dài; (b) **observer được cô lập lỗi** (`_emit` bọc
`try/except`, đếm `_observer_errors`, KHÔNG sập pipeline) — quan sát là phụ trợ, không được kéo sập xử lý;
(c) `media_ref_factory` là seam để chuyển in-memory → SHM mà không sửa engine.

---

## 5. Patterns đã triển khai (kèm Forces / cái giá / khi nào KHÔNG dùng)

Bám POSA — mỗi pattern nêu *vì sao*, *cái giá*, *giới hạn* (đầy đủ trong `ai-decision-journal/` + `knowledge-base/`).

- **Hexagonal (Ports & Adapters).** *Forces:* cần thay công nghệ I/O (camera/detector/sink) mà không đụng
  nghiệp vụ + test không cần phần cứng. *Cái giá:* nhiều lớp gián tiếp (Protocol + factory + composition root)
  → boilerplate cho hệ nhỏ. *Khi KHÔNG dùng:* script 1-lần, không có nhiều biến thể adapter.
- **Bulkhead (đa-process, 1 camera/process — `application/supervisor.py`).** *Forces:* 1 camera lỗi/leak
  không được kéo sập cả fleet; tận dụng nhiều core (né GIL). *Cái giá:* IPC phức tạp (SHM + serialize), tốn RAM
  hơn thread. *Khi KHÔNG dùng:* 1 camera, hoặc tải nhẹ chạy 1 process đủ.
- **Backpressure (`kernel/backpressure.py`, BoundedQueue 4 policy: DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT).**
  *Forces:* nguồn (camera 30fps) nhanh hơn khả năng xử lý → phải chọn CÁCH mất mát có kiểm soát thay vì OOM.
  *Cái giá:* phải chọn policy đúng ngữ cảnh (realtime nên DROP_OLDEST; batch nên BLOCK). *Khi KHÔNG dùng:*
  throughput luôn ≥ ingest.
- **Immutability + Copy-on-Write (`MediaPacket` frozen; config frozen + `MappingProxyType`/`tuple`).** *Forces:*
  chia sẻ dữ liệu qua nhiều stage/process an toàn, không sửa nhầm state toàn cục. *Cái giá:* copy khi cần đổi.
- **Ring-epoch switchover / ABA-prevention (`runtime/ipc/` + `*_epoch_coordinator`).** *Forces:* SHM ring tái
  dùng slot → reader cũ có thể đọc nhầm frame mới cùng địa chỉ (ABA). *Giải:* generation counter + control-plane
  epoch + pool tái dùng. *Cái giá:* logic đồng bộ tinh vi (đã có PBT Hypothesis + test cross-process).
- **Capability-aware execution (`kernel/capabilities.py::resolve_device`).** *Forces:* chạy trên máy hỗn tạp
  GPU/CPU mà không rải `if torch...` khắp nơi. *Giải:* DTO `MachineCapabilities` (probe ở adapter) + hàm THUẦN
  `resolve_device(requested, caps)` fail-fast (ép `cuda` trên máy không GPU → `CapabilityError` rõ ràng, không
  fail mù). Test tiêm caps giả → xác định, không cần GPU.
- **Observability port (`kernel/observability_port.py`).** *Forces:* thấy sức khỏe live per-camera (RTSP vô hạn)
  mà lõi không phụ thuộc Prometheus. *Giải:* `PipelineSnapshot` (frozen) + `IPipelineObserver` thuần; adapter
  Prometheus/log ở rìa. `frames_per_second` là throughput **interval** (không che sự cố như trung bình tích luỹ).

---

## 6. Đặc tính hiệu năng (TRUNG THỰC: cái nào đã đo vs chưa đo)

- **Zero-copy giữa process:** frame truyền qua SHM ring (`runtime/ipc/shm_frame_ring.py`) — tránh copy/serialize
  cả ảnh. Có `benchmarks/bench_capacity.py` + `benchmarks/README.md`. → **[đã có cơ chế + benchmark harness]**;
  con số throughput cụ thể phụ thuộc máy → chạy benchmark để lấy số THẬT (chưa chốt trong doc để tránh drift).
- **Né GIL bằng đa-process** (bulkhead) thay vì thread cho khối CPU-bound (inference/decode). → thiết kế đúng
  hướng cho Python; hiệu quả thực tế cần đo trên máy đích.
- **Motion-gate cắt tải:** bỏ frame tĩnh (`runtime/stages/motion_gate_stage.py` + `domain/motion.py`) → giảm số
  lần chạy detector (đắt nhất). `skip_rate` phơi qua observability.
- **Backpressure** chặn OOM khi ingest > xử lý (mất mát có kiểm soát).
- **CHƯA đo/CHƯA đóng (trung thực):** (a) benchmark throughput/latency end-to-end trên GPU thật; (b) nhánh CUDA
  (torch chưa cài trên máy hiện tại — xem §9); (c) độ ổn định dưới full-suite tải cực đại (K-035, xem §9).

---

## 7. Cấu hình khai báo (declarative TOML) — deploy không sửa code

`kernel/config.py` (đã đọc): toàn bộ config là **dataclass frozen** → bất biến sau parse (`params` bọc
`MappingProxyType`, list → `tuple`). Cây: `AppConfig` → nhiều `PipelineConfig` (mỗi cái 1 camera: `source` +
`stages[]` + `sinks[]` + `detector?` + `max_frames?`) + `ObservabilityConfig?` (top-level, fleet-level).

- Đọc/validate file: `application/config_loader.py`. Dựng object thật: `profiles/pipeline_factory.py`.
- `ObservabilityConfig` (top-level, mặc định TẮT): `observe`, `metrics_port`, `metrics_host`,
  `observe_interval_s`, `observe_every_n` — precedence **CLI-explicit > TOML > default**. Không section →
  `observability=None` → hành vi cũ giữ nguyên (backward-compat).
- Config mẫu: `vision-platform/configs/*.toml`. Có test chạy full `validate_config` trên mọi config ship.

---

## 8. Observability & capability — chuỗi hoàn chỉnh

**Đo → Render → Serve:** `MetricsObserver` (impl `IPipelineObserver`) ghi vào `InMemoryMetrics`
(`runtime/observability.py`) → `adapters/metrics_exposition.py::render_prometheus` render text format Prometheus
0.0.4 (escape label, xử lý inf/nan, raise khi xung đột name↔type) → `adapters/metrics_http_server.py::
MetricsHttpExporter` phục vụ `/metrics` + `/healthz` qua `http.server` (daemon thread, non-blocking, guard
`_serving` chống deadlock lúc stop, **secure-default bind localhost**; `0.0.0.0` = opt-in + cảnh báo không-auth).

- 1 `InMemoryMetrics` + 1 exporter DÙNG CHUNG → tự **aggregate theo `source_id`** (nhãn `source`).
- Bật qua CLI (`--observe`/`--metrics-port`/`--metrics-host`) HOẶC khai báo TOML (§7). Mô hình deploy:
  1 process/1 camera, mỗi process 1 port `/metrics` → Prometheus scrape N target.
- **Lệnh operator `--capabilities`:** in JSON năng lực máy (torch/cuda/gpu_name/cv2) để kiểm TRƯỚC khi deploy
  lên máy đổi GPU↔CPU.

⚠️ **An ninh (reviewer lưu ý):** `/metrics` mặc định localhost (an toàn); nếu phơi `0.0.0.0` ra mạng
không-firewall thì chưa có auth/rate-limit (ghi rõ ở journal K-072 — chỉ cần khi expose ra internet).

---

## 9. Giới hạn đã-biết & hướng còn chặn (TRUNG THỰC — không giấu)

- **Nhánh GPU/CUDA chưa verify:** máy hiện tại có GPU phần cứng (nvidia-smi OK) nhưng **torch chưa cài ở bất kỳ
  interpreter nào** (đã kiểm triệt để — journal K-079). Cài torch = op nặng mạng → chờ đèn xanh. `resolve_device`
  + `capability_probe` đã xử lý no-GPU đúng thiết kế; chỉ thiếu bằng chứng chạy detector CUDA thật.
- **K-035 (flaky supervisor dưới tải full-suite):** chạy riêng ổn định (đã điều tra 24/24 isolated); residual
  ~hiếm chỉ dưới tải full-suite cực đại = **contention môi-trường máy yếu, không phải bug logic**. Đóng tuyệt đối
  cần máy mạnh/CI. KHÔNG vá speculative (đúng "không kiểm được thì không đoán").
- **DB sink server (Postgres...):** hiện có sink JSONL + SQLite (file). Sink DB-server cần DB thật để verify.
- **Runtime song song đa-pipeline:** `_run_from_config` hiện chạy TUẦN TỰ (1 pipeline live/lúc). Chạy song song
  nhiều camera trong 1 process là việc scale tương lai.
- **ZMQ cross-process inference:** có `zmq_inference_client`/`inference_server`; đường mặc định là
  `InlineInferenceClient` (cùng process).
- **POSIX/ARM:** phần lớn verify trên Windows/x86; teardown atomicity POSIX/ARM chưa verify đầy đủ.

---

## 10. Kiểm thử & xuất xứ (provenance) & chống-drift

- **Test:** unit + property-based (Hypothesis, cho switchover/config) + **cross-process THẬT** (SHM, switchover,
  multi-reader, supervisor shutdown). Marker `gpu` (tự skip khi không CUDA), `slow` (cross-process/timing).
  Số THẬT: chạy `vp verify` / `vp test`.
- **Ranh giới:** import-linter 5 contract (§2.1) — chạy `lint-imports`.
- **Xuất xứ quyết định:** `ai-decision-journal/` (4 file: Quyết-định D / Đổi-yêu-cầu C / Trade-off T / Cần-biết K)
  + `AI-IMPLEMENTATION-LOG.md` (nhật ký thời gian). Mỗi khẳng định "vì sao" truy được về ID D/C/T/K.
- **Chống-drift bằng máy:** `tests/drift_check.py` (chạy qua `vp check`) — C1–C7 kiểm bản ghi khớp thực tế +
  self-test [3/3] (guard-the-guard) + RULES_VERSION sync 5 file. File ARCHITECTURE.md này **không hardcode số
  dễ đổi** để không tạo nguồn drift mới (§0).

---

## 11. Hướng dẫn cho người review (đọc theo thứ tự này)

1. **`pyproject.toml`** §`[tool.importlinter]` → hiểu 5 ranh giới; chạy `lint-imports` xem còn nguyên không.
2. **`kernel/ports/`** → đọc 6 Protocol = "bề mặt hợp đồng" của hệ (thay gì được, test gì được).
3. **`runtime/pipeline_runner.py`** → engine trung tâm (vòng lặp, teardown, cô lập observer).
4. **`profiles/vision_slice_app.py`** → composition root: adapter thật ráp vào ports thế nào + CLI.
5. **`kernel/config.py` + `application/config_loader.py`** → mô hình khai báo TOML.
6. **`runtime/ipc/`** → phần khó nhất (SHM ring + epoch switchover) — soi ABA-prevention.
7. **`ai-decision-journal/00-INDEX.md`** → 1 trang rà mọi quyết định + mục 🔴/🟡 (rủi ro mở).

**Câu hỏi gợi ý để đánh giá (probe):** (a) Bỏ Port, cho application import thẳng adapter thì vỡ gì? (b) SHM ring
tái dùng slot mà không có epoch → bug ABA nào? (c) Camera RTSP rớt mạng — pipeline phát hiện & phản ứng ở đâu?
(d) Ép `device=cuda` trên máy không GPU → điều gì xảy ra, và tại sao fail-fast tốt hơn fallback im lặng?
(e) `/metrics` phơi `0.0.0.0` — rủi ro gì, hệ mặc định chống thế nào?

---
*Tài liệu bám code thật đã đọc tại thời điểm #316. Khi code đổi lớn → cập nhật file này + ghi LOG; số liệu
sống luôn lấy từ `vp verify`, không từ prose.*
