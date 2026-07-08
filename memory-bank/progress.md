# progress.md — Xong gì / còn gì / bug (cập nhật mỗi phiên = chân lý hiện tại)

## Đã xong
- **[2026-07-08 máy `toann`] 🎯 Spec `backpressure-cross-process` HOÀN TẤT (Wave 1–5, đóng K-040 A2+A3):** Metric_DTO kernel (`backpressure_metrics.py`) + `ZmqInferenceClient` set HWM-trước-connect (A3) + đường async `submit()/poll_responses()/metrics_snapshot()` flow-control (đếm submitted-lúc-gửi K-051) + `FakeDetector.delay_s` + `PushFrameSource` + `camera_worker` async submit+drain+hạch toán backpressure 2-tầng (SHM ring ⊥ client-window, K-053) + guard cấm BLOCK+RTSP (R3, hàm thuần) + test overload cross-process assert bất biến bảo toàn. **Verify THẬT máy `toann` (venv py3.13.12): 465 passed/1 skipped · lint 5/0** (3 lần full sạch; 1 flake tạm K-035 shutdown = không hồi quy). ADDITIVE (infer() sync + 5 test cross-process cũ không đổi). Journal D-048..051/C-018..019/T-018..021/K-050..053. (Chi tiết per-turn: `activeContext.md`.)
- **[2026-07-06] ✅ Sub-spec media-ref-port** (đóng seam K-038 phần 1): `kernel/media_ref.py::IMediaRef` (Protocol) + nới `MediaPacket.media_ref: IMediaRef`; InMemoryArrayRef không sửa. Verify THẬT **369 passed/1 skipped · lint 5/0**. (Chi tiết mới nhất xem `activeContext.md` — chân lý per-turn.)
- Hệ điều hành học (Phase 0+1): luật 4 tool, skill, log (ở root), bộ nhớ, bản đồ học, **knowledge-base** (kiến thức tái dùng), hook chốt phiên.
- Gia cố: PLAN-FIRST, Feynman gate, drift-check, RULES_VERSION **14** + `tests/test_rules_sync.py` (PASS #209), spec-kit templates ở `specs/`, lesson templates.
- **Module 03 (vision-platform) TRIỂN KHAI XONG trên Windows:** hexagonal 6 layer + import-linter **5 contract** cưỡng chế + Stage pipeline + SHM/ZMQ/switchover/supervisor + real-detector (transform/nms/onnx/yolo) + sources (rtsp/video/noise) + web UI + IMediaRef port. Baseline **369 passed/1 skipped · lint 5/0** (verify thật #209). code-lessons #01–#10 (+05b/06b/09b) đủ mẩu.
- **Phương pháp dạy PATTERN** (rút từ `pattern-study/`, gom trong `knowledge-base/_pattern-method/`): `00-PATTERN-METHOD.md` (5 cấp+4 bước), `_TEMPLATE-pattern.md` (POSA), `00-TAXONOMY.md`, `_TEMPLATE-quiz.md` + luật AGENTS §1.6 + bản portable trong kit.
- ✅ Đã verify cấu trúc đầy đủ + linter → **SẴN SÀNG hoạt động**.

## Đang làm
- **[2026-07-07 máy `k.nguyen.manh.toan`] ĐỔI MÁY + rebuild venv + re-verify:** working tree sync sang desktop mới (py3.11.9). `.venv` cũ (trỏ máy `endgame`/toann) hỏng → rebuild `py -3.11 -m venv` + `.[dev,onnx,cv2,web]` (KHÔNG pt). **Verify THẬT: `pytest -q`=436 passed/1 skipped · import-linter=5 kept/0 broken** — khớp #232/#233 dù đổi py 3.13→3.11. Fix K-044: gọi lint programmatic phải `import importlinter.api` trước (il 2.13 KeyError USER_OPTION_READERS nếu thiếu). Con trỏ đã đồng bộ #233 (torch CPU-only ở endgame; máy này chưa có torch). (Chi tiết per-turn: `activeContext.md`.)
- **[2026-07-06 máy `endgame`] config-declarative + 2 lỗ review ĐÓNG:** D-042/D-043 (schema+loader+factory+wire+validate, đóng K-040 C2) ✅; **D-044 bulkhead per-pipeline (đóng K-045)** ✅; **D-045 strict-key params (đóng K-046)** ✅. Baseline verify THẬT máy `endgame` (scoop py3.13.12): **427 passed/1 skipped · lint 5/0** (LOG #230). Venv dựng lại (K-047 đóng). Sổ `ai-decision-journal/` đủ (123 entry). (Chi tiết per-turn: `activeContext.md`.)
- **🔴 Còn nợ:** R3 guard cấm BLOCK+RTSP CHƯA wire end-to-end (config chưa mang policy per-source — D-050/T-021) · POSIX chưa verify (test cross-process guard win32) · K-035 shutdown flaky dưới tải · GPU end-to-end (pt/cuda/rtsp, máy no-GPU) · git on-hold K-007 · secret rotate K-031 · hướng scale còn (K-040 A1 batching/C1 metrics, K-041 benchmark).

## Còn lại (theo lộ trình)
- **Nghiệp vụ (chờ user):** ALPR (biển+OCR) / tracking / face / storage / security — chưa bắt đầu (user chốt để sau).
- **Khi có nghiệp vụ đầu tiên:** lấy `pipeline-runner` (design sẵn) ra code; cân nhắc ShmMediaRef (Stage chạy thật trên SHM) + bộ Stage vision + ports ITracker/IOcr/IEventSink (Gap-2 K-037).
- **🔴 cần môi trường khác (không verify được trên Windows):** ARM (K-001) · POSIX teardown (K-003) · SLA threshold (K-004) · AccessDenied cross-priv (K-005) · throughput tải thật (K-014).

## Bug / nợ đã biết
- **🔴 vận hành:** git on-hold + push 403 (K-007) → 43 commit chưa push + 82 working-tree chưa commit = CHƯA BACKUP. **🔴 bảo mật:** secret production lộ trong config syn (K-031) → user nên rotate.
- Validate kiến thức là best-effort (không chống 100% hallucination); chỉ code validate khách quan bằng test.
- Nợ kiến trúc (không phải bug): 4 profile trùng vòng lặp (đóng bởi pipeline-runner khi cần); artifacts stringly-typed (Gap-5 K-037).
