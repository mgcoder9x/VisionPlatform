# Vấn đề #09 — Supervisor + shutdown protocol cascade (PHA 1 valid)

> **Nguồn Design:** `Design/module-03-build-along/step-09-add-shutdown.md` (đọc nguyên văn) — ĐÃ chứa fix ERRATA E-10.
> **Trạng thái:** PHA 1 valid — thiết kế sạch (đã sửa E-10 từ trước). 0 deviation logic. Tiến thẳng PHA 2.
> **Cập nhật lúc:** 2026-07-04.

## 1. Mục tiêu #09 (theo Design)
- `application/supervisor.py` — `WorkerSpec` (spec spawn worker) + `Supervisor` (spawn N worker process, monitor, restart capped, cascade shutdown cooperative-first).
- `tests/worker_funcs_for_step_09.py` — worker functions module-level (spawn Windows cần picklable, tách khỏi test file).
- `tests/test_step_09_shutdown.py` — 6 test (gồm bulkhead isolation + cooperative cleanup).

## 2. Đối chiếu Design ↔ CODE THẬT (chống bịa)
| Design giả định | Code THẬT | Kết luận |
|---|---|---|
| package `vision_demo` | `vision_platform` | đổi tên nhất quán |
| `application/supervisor.py` | CHƯA tồn tại (application/ có ring_supervisor, *_epoch_coordinator) | additive, 0 đụng độ |
| import multiprocessing/signal/os/structlog ở application | contract #4 application forbidden = adapters/profiles (KHÔNG cấm mp/signal/structlog) | ✅ hợp lệ layer |
| `from tests.worker_funcs_for_step_09 import ...` | `tests/__init__.py` TỒN TẠI → tests là package → import + spawn re-import OK | ✅ |
| cascade cooperative-first (E-10 fix) | ERRATA E-10 + LOG #40 (verify 20×: cũ 1/20, mới 20/20, script tạm đã xoá) | ✅ design đã sửa; #09 chạy lại verify |

## 3. F1/E-10 — đã sửa TỪ TRƯỚC (không phải deviation mới)
- LOG Entry #40 (2026-06-14): bug cascade cũ = `terminate()` NGAY sau set event → cooperative cleanup bị race (Windows TerminateProcess không chạy `finally`) → flaky. Fix (lựa chọn A của user): cascade **cooperative-first** (set event → JOIN coop với grace → terminate non-coop/hang → kill straggler).
- Verify: script tạm `_verify_cascade.py` chạy 20× → CŨ cleanup 1/20, MỚI 20/20 → bug thật, fix đúng. Script đã xoá.
- Design step-09 HIỆN TẠI đã phản ánh bản fixed. #09 = implement bản đã fixed + CHẠY THẬT test cascade tại #09 (tracker: "tích hợp Supervisor đầy đủ chạy lại khi build #09").

## 4. Đánh giá diện rộng (doubt-driven — cho sản phẩm thương mại)
- **Cascade cooperative-first:** đúng bản chất — worker cooperative (`uses_shutdown_event`) được cleanup sạch TRƯỚC (join grace), chỉ non-coop/hang mới bị terminate/kill. Phân biệt coop vs non-coop để non-coop không chờ grace vô ích.
- **Giới hạn nền tảng (thật, ghi rõ):** graceful chỉ đúng khi worker CHỦ ĐỘNG poll shutdown_event. Windows `terminate()` = TerminateProcess (kill cứng, KHÔNG chạy finally) → non-coop worker KHÔNG cleanup. Đây là lý do có `graceful_worker` (coop) mẫu.
- **daemon=True:** an toàn (worker chết theo parent nếu supervisor crash). Đánh đổi: worker không spawn con được.
- **restart cap `>` (not `>=`):** "max 3 restarts" = restart đúng 3 lần rồi give up (tránh restart loop vô tận CPU 100%).

## 5. Điều NÊN BIẾT (ghi journal)
- **K-020 (hang detection thiếu):** Supervisor check `is_alive()` → CHỈ phát hiện crash (process exit), KHÔNG phát hiện **hang/deadlock** (process alive nhưng kẹt). Sản phẩm thật cần **heartbeat liveness** (worker ghi timestamp / ZMQ heartbeat; supervisor kill nếu mtime quá hạn). Design ghi rõ (Self-check #5).
- **K-021 (restart backoff thiếu):** restart ngay không có exponential backoff — worker crash liên tục sẽ spawn/exit nhanh tới khi cap. Production cần `sleep(2^n)`. Design ghi (simplified).
- **Graceful = cooperative-only trên Windows** (mục 4) — non-coop worker bị kill cứng, không cleanup.
- Wiring worker Vision thật (camera/inference) vào Supervisor = composition bước sau; #09 giao cơ chế supervisor + test.

## 6. Kế hoạch PHA 2 (TDD)
1. `application/supervisor.py` theo Design (giữ nguyên, bản đã fix E-10; structlog logger).
2. `tests/worker_funcs_for_step_09.py` (ok/crash/short_lived/eternally_failing/graceful worker).
3. `tests/test_step_09_shutdown.py`: 6 test (spawns+terminate · bulkhead isolation · graceful cleanup · restart crashed · give-up-after-max · non-coop terminated).
4. Chạy THẬT `pytest tests/test_step_09_shutdown.py` (multi-process, chậm ~9s) + full + `lint-imports` (kỳ vọng 5 kept/0 broken).
