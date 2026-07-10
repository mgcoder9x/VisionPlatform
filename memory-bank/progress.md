# progress.md — Xong gì / còn gì / bug (cập nhật mỗi phiên = chân lý hiện tại)

> **Mốc hiện tại (2026-07-10, máy `k.nguyen.manh.toan`, LOG #293):** baseline **601 passed/2 skipped · lint 5 kept/0 broken · drift-check PASS · RULES_VERSION 15**. Nhánh `chore/dev-env-launcher-portable-hooks` push đều mỗi lượt (git HOẠT ĐỘNG — K-007 cũ đã hết on-hold). Chi tiết per-turn: `activeContext.md`; quyết định: `ai-decision-journal/`.

## Đã xong (mốc no-GPU thương mại — verify THẬT)
- **Nền tảng kiến trúc:** hexagonal 6 layer + import-linter **5 contract** cưỡng chế (5 kept/0 broken). SHM ring/epoch-switchover/supervisor-liveness/ZMQ inference/backpressure-cross-process (đóng K-040 A2+A3) + real-detector (transform/nms/onnx/yolo) + sources (rtsp/video/noise/fake) + web UI + `IMediaRef` port + `PipelineRunner`/Stage/`ISink`.
- **Analytics no-GPU (chuỗi nghiệp vụ, deploy-by-config):** object-tracking-count (IoU-greedy, D-059) → line-crossing-count (D-060) → crossing-event-log JSONL (D-061) → config-declarative analytics (D-062) → crossing-event-sqlite-sink (D-063) → motion-gate (D-064/065) → motion-gate-roi (ROI+bền-illumination, D-066/067). Chuỗi: source→[motion_gate ROI+illum]→detect→track→line_crossing→count; sink JSONL/SQLite.
- **Observability (chuỗi TRỌN no-GPU):** đo (`MetricsObserver`→`InMemoryMetrics`, D-069) → wire CLI `--observe` (D-069) + config `--observe` (D-070) → render Prometheus text (`render_prometheus`+`iter_metrics` không-lossy, D-074) → **serve `/metrics` HTTP** (`MetricsHttpExporter`, secure-default localhost, D-079). Live per-camera fps/skip_rate/errors.
- **Capability-aware (đổi máy GPU/không-GPU):** `MachineCapabilities`+`resolve_device`(auto/fail-fast-cuda/ordinal) @kernel + `probe_capabilities` @adapters + gate test `@pytest.mark.gpu` + lệnh operator `--capabilities` (D-072/073/080).
- **Hạ tầng dev/CI/anti-drift:** dev-env launcher `scripts/vp.cmd` cross-machine (D-057) + CI `verify.yml` (D-058) + **`ai-decision-journal/` 4 file (D/C/T/K) + `tests/drift_check.py` (memory consistency + RULES_VERSION sync) + hook agentStop tự chạy** (D-052/053/056) — cơ chế chống-drift máy-kiểm.
- **test-stability-hardening (D-077):** viết lại test cross-process EVENT-DRIVEN (`wait_until` an-toàn-ngoại-lệ + `Supervisor.request_stop()` additive + timeout thực tế) → giảm-thiểu MẠNH flaky K-035 (5/5 ổn định isolated + vp verify xanh).

## Đang làm
- (không có việc dở giữa chừng) — vừa chốt mốc sạch #293. Chờ user chọn hướng kế.

## Còn lại — CHẶN bởi điều kiện (trung thực, KHÔNG làm speculative)
- **🔴 K-035 flaky residual:** supervisor/step_09 flaky RẤT HIẾM (~2/5 full-run 80s+ dưới tải CỰC ĐẠI máy yếu) — event-driven đã diệt race THIẾT KẾ (5/5 isolated), residual là bản chất môi-trường. **Đo + đóng tuyệt đối cần máy mạnh/CI** (không bump-timeout che; startup_grace không verify được isolated nên chưa vá — D-080/#292).
- **🔴 GPU/CUDA (máy không GPU + không CUDA):** nhánh `Yolov5PtDetector` device cuda · tune ngưỡng motion-gate-roi trên RTSP thật · node-capacity-benchmark (K-040 A1/R6.1) · verify `probe_capabilities` nhánh có-CUDA. Cần máy GPU.
- **🔴 server-DB sink (Postgres nhiều-cam):** cần DB server để verify thật (SQLite đã có, no-GPU).
- **🔴 config-path metrics/observability đa-cam:** `_run_from_config` TUẦN TỰ (T-015) → /metrics giá trị hạn chế tới khi runtime SONG SONG/async (việc scale tương lai, cần GPU + benchmark).
- **🔴 môi trường khác:** ARM atomicity (K-001) · POSIX teardown/liveness (K-003) · SLA threshold (K-004) · tải thật (K-014).
- **⚠️ bảo mật:** URL `origin` nhúng GitHub PAT plaintext (K-031/#256) → user NÊN rotate + dùng credential manager. Secret production trong config syn (K-031) → user nên rotate.

## Bug / nợ đã biết
- K-035 residual (xem trên) — mitigated, chưa đóng tuyệt đối.
- Validate kiến thức = best-effort (không chống 100% hallucination); chỉ CODE validate khách quan bằng test chạy thật.
- Nợ kiến trúc (không phải bug): artifacts stringly-typed (Gap-5 K-037); 4 profile trùng vòng lặp (đóng dần bởi PipelineRunner).
