# Mẩu 04 — Tổng kết Module 03: bản đồ pattern #01–#10 + trade-offs hoãn

**(1) Thuộc về đâu:** tổng kết toàn hành trình `code-lessons/01..10` + `implement/00-IMPLEMENTATION-TRACKER.md`.

**(2) Cần biết trước:** đã đọc qua các bài #01–#09 (mỗi bài có folder `code-lessons/<NN>/`).

**(3) Bản đồ pattern đã dựng + kiểm chứng (mỗi cái neo bài + code thật):**

| # | Vấn đề | Pattern / khái niệm lõi | Code thật (layer) |
|---|--------|-------------------------|-------------------|
| 01 | Skeleton + layout | 6 layer hexagonal + import-linter ép hướng phụ thuộc | `pyproject.toml` (5 contract) |
| 02 | Data objects | Immutability/frozen + CoordinateSpace + DTO | `domain/bbox.py`, `kernel/{media_packet,read_result}` |
| 03 | Port + adapter | Port (Protocol) + adapter + contract test | `kernel/ports/frame_source.py`, `adapters/*_frame_source.py` |
| 04 | Pipeline | Stage + Template Method + executor + context manager | `runtime/{base_stage,sync_linear_executor,stages}` |
| 05 | SHM frame bus | Shared memory ring + ABA(generation) + lease/quarantine/multi-reader/single-writer | `runtime/ipc/shm_frame_ring.py`, `kernel/shm_frame_ref.py` |
| 05b | Ring switchover | Control-plane epoch + ring pool + coordinator + cross-process lock thừa kế | `runtime/ipc/{ring_control_plane,ring_pool}`, `application/*coordinator` |
| 06 | Inference inline | request_id correlation + IDetector port + read_ref stale-check | `kernel/inference_protocol.py`, `application/inline_inference_client.py` |
| 07 | Backpressure | BoundedQueue 4 policy + Condition/wait_for (thread-safe, not process) | `kernel/backpressure.py` |
| 08 | Observability | structlog + contextvars log_context + InMemoryMetrics (cardinality) | `runtime/observability.py` |
| 09 | Shutdown | Bulkhead (process-per-worker) + cascade cooperative-first (E-10) | `application/supervisor.py` |
| 10 | Package + ship | Wheel/sdist + DoD + số thật | `README.md`, `dist/*.whl` |

**(4) Giải thích:** mỗi vấn đề giải quyết 1 nỗi đau thật của hệ real-time multi-camera; các pattern
xếp chồng thành 1 mini Vision Platform chạy được + test được (290 passed/1 skipped).

**(5) Là gì:** bức tranh hợp nhất — từ folder rỗng tới gói shippable qua 10 bước.

**(6) Tại sao tổng kết quan trọng:** giúp thấy **liên kết** (không phải 10 mẩu rời): port (#03) dùng lại
ở detector (#06); SHM (#05) là nền cho switchover (#05b) + inference đọc frame (#06); bulkhead (#09)
bọc mọi worker; observability (#08) + backpressure (#07) là hạ tầng vận hành.

**(7) Trade-offs HOÃN cho production (đã ghi journal — trung thực):**
- ZMQ cross-process inference (thay inline #06) · production log handlers non-blocking/rotation (K-018) ·
  hang detection/heartbeat + restart backoff (K-020/K-021) · teardown POSIX/ARM atomicity (K-001/K-003) ·
  REBUILD_THRESHOLD SLA (K-004) · secrets management + circuit breaker/DLQ/TrackerScope.

**(8) Nếu không tổng kết:** dễ quên "vì sao" từng mảnh + không thấy đường lên production.

**(9) Ví von:** bản đồ metro sau khi đã đi từng tuyến — giờ thấy cả mạng lưới nối nhau, biết đổi tuyến ở đâu.

**(10) Liên kết bức tranh lớn:** đây là cửa ngõ sang Module 04 (deep dives) / 06 (triển khai dự án thật).
Mọi 🔴/🟡 mở nằm ở `ai-decision-journal/`.

**(11) Cạm bẫy:** mini Vision Platform ≠ production — đừng deploy nguyên si (xem trade-offs hoãn). Số
thật 290/1 là trên Windows/x86; POSIX/ARM chưa verify.

**(12) Tự kiểm (Feynman toàn Module — user làm sau):**
- Vẽ lại bản đồ 6 layer + đặt mỗi pattern #01–#10 vào đúng layer.
- Chọn 1 pattern (vd switchover #05b) giải thích: nỗi đau gì → giải pháp → cái giá.
- Kể đường từ inline (#06) lên ZMQ production mà KHÔNG đổi pattern (chỉ swap adapter/transport).

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng (đặc biệt ôn liên kết giữa các bài).

**(14) Nguồn:** `implement/00-IMPLEMENTATION-TRACKER.md` + `code-lessons/01..10` + `ai-decision-journal/`.
Độ chắc: cao (bản đồ neo code thật + full 290 passed/1 skipped verify).
