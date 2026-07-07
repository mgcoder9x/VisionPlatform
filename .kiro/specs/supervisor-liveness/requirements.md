# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid trước khi design chi tiết/tasks/code.
> **Mục đích:** đóng **K-020** (Supervisor chỉ bắt crash, KHÔNG bắt hang) + **K-021** (restart không backoff).
> **Cập nhật lúc:** 2026-07-04.

## Introduction

`Supervisor` (#09) giám sát worker bằng `p.is_alive()` → CHỈ phát hiện **crash** (process exit). Nếu worker
**hang/deadlock** (process còn sống nhưng kẹt, không xử lý frame) → `is_alive()`=True → supervisor tưởng
khoẻ → camera "chết thầm". Đây là lỗi 24/7 nghiêm trọng + IM LẶNG nhất. Ngoài ra restart hiện không có
**exponential backoff** → worker crash liên tục spawn/exit dồn dập (CPU spike).

Sub-spec này thêm **heartbeat liveness** (phát hiện hang) + **restart backoff**, theo hướng **ADDITIVE**
(không đổi hành vi worker không dùng heartbeat → giữ 6 test #09 xanh).

**Ranh giới nguồn (chống bịa):** neo code thật `application/supervisor.py` (WorkerSpec/`_spawn`/`run`) +
journal K-020/K-021 + Design step-09 (Self-check #5). KHÔNG neo tài liệu upstream (vắng). Ẩn số (mp.Value
cross-process trên Windows) gắn **[chưa kiểm]** tới PHA build.

## Glossary

- **heartbeat**: nhịp sống worker phát định kỳ (cập nhật timestamp chia sẻ) để supervisor biết còn "làm việc".
- **hang/deadlock**: process còn sống (is_alive=True) nhưng kẹt, không tiến triển.
- **exponential backoff**: chờ tăng dần `base·2^n` (có trần) giữa các lần restart.
- **mp.Value**: ô nhớ chia sẻ liên-tiến-trình (ctypes) — truyền qua Process(args=) như shutdown_event.

## Requirements

### Requirement 1: Phát hiện hang qua heartbeat (đóng K-020)
**User Story:** Là kỹ sư vận hành 24/7, tôi muốn supervisor phát hiện worker treo (không chỉ crash), để camera không chết thầm.
#### Acceptance Criteria
- 1.1 — WorkerSpec có tuỳ chọn heartbeat (mặc định TẮT). Khi BẬT, worker nhận kênh heartbeat (mp.Value) để cập nhật nhịp.
- 1.2 — Supervisor PHẢI coi worker là HANG khi: `is_alive()`=True VÀ heartbeat bật VÀ (now − nhịp-cuối) > `heartbeat_timeout_s`.
- 1.3 — Worker mới spawn CHƯA kịp beat lần đầu KHÔNG bị coi hang tới khi quá `heartbeat_timeout_s` tính từ lúc spawn (startup grace).
- 1.4 — Khi phát hiện hang: `terminate()` worker (+ kill nếu ngoan cố) rồi xử lý như một FAILURE (restart theo cap, giống crash).
- *Nguồn:* K-020; `supervisor.py` (`run` check `is_alive`).

### Requirement 2: ADDITIVE — không đổi hành vi worker không heartbeat
**User Story:** Là maintainer, tôi muốn thêm heartbeat mà không phá worker/test hiện có, để #09 giữ nguyên.
#### Acceptance Criteria
- 2.1 — Worker KHÔNG bật heartbeat PHẢI hành xử y như #09 (chỉ crash-detection). 6 test #09 giữ xanh.
- 2.2 — Trường heartbeat trong WorkerSpec PHẢI có default TẮT (backward-compat).
- *Nguồn:* #09 tests; nguyên tắc additive (D-003/D-008 style).

### Requirement 3: Restart exponential backoff (đóng K-021)
**User Story:** Là hệ thống, tôi muốn giãn nhịp restart khi worker crash liên tục, để không spike CPU.
#### Acceptance Criteria
- 3.1 — WorkerSpec có `restart_backoff_base_s` (mặc định 0 = KHÔNG backoff, giữ hành vi #09) + trần `restart_backoff_cap_s`.
- 3.2 — Khi base>0: sau failure lần n, worker chỉ được respawn sau `min(base·2^(n−1), cap)` giây.
- 3.3 — Backoff PHẢI **non-blocking**: đang chờ backoff 1 worker KHÔNG được chặn giám sát các worker khác (vòng run vẫn chạy).
- *Nguồn:* K-021; Design step-09 (Restart cap — simplified).

### Requirement 4: Thống nhất xử lý failure (crash + hang) dưới restart cap
**User Story:** Là supervisor, tôi muốn crash và hang đi qua cùng đường restart/cap, để logic nhất quán.
#### Acceptance Criteria
- 4.1 — Cả crash lẫn hang PHẢI tăng `restart_counts` + tuân `max_restarts` (`>` → give up) + backoff (nếu bật).
- 4.2 — Give-up (vượt max) áp dụng cho cả hang lẫn crash.
- *Nguồn:* `supervisor.py` restart block.

### Requirement 5: Observability
**User Story:** Là vận hành, tôi muốn thấy lý do restart (crash vs hang), để chẩn đoán.
#### Acceptance Criteria
- 5.1 — Supervisor PHẢI phát sự kiện phân biệt: `worker_heartbeat_timeout` (hang) vs restart do crash (đã có `worker_restarting` với exit_code).
- 5.2 — Log/sự kiện PHẢI có `worker_id` + lý do; KHÔNG cardinality nổ.
- *Nguồn:* #08 observability; K-019.

### Requirement 6: Verify cross-process THẬT trên Windows
**User Story:** Là kỹ sư, tôi muốn bằng chứng chạy thật, để tin heartbeat hoạt động.
#### Acceptance Criteria
- 6.1 — Test spawn worker TREO (beat vài lần rồi ngừng beat nhưng vẫn alive) → supervisor phát hiện hang → restart (chứng minh đóng K-020).
- 6.2 — Test worker beat đều → KHÔNG bị restart nhầm (không false-positive).
- 6.3 — Test backoff: worker crash liên tục + base>0 → khoảng cách giữa restart tăng dần (đo thời điểm).
- *Nguồn:* §5 verify-bằng-chạy-thật; #09/#05b spawn pattern.

## Non-Goals (HOÃN — chống phình)
Remote/ZMQ heartbeat reply (cho inference service, để sau) · adaptive timeout tự chỉnh · health-check nội dung (chỉ liveness, không kiểm "đúng-sai").

## Tiêu chí ĐẬU (Definition of Done)
WorkerSpec + Supervisor heartbeat/backoff (additive); test THẬT cross-process (hang→restart · beat-đều-không-restart · backoff-giãn); 6 test #09 giữ xanh; lint 5/0; không claim xong khi chưa chạy test (§5).
