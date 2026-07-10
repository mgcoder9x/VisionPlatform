# Requirements Document

> **Spec:** supervisor-liveness-hardening (bền vững liveness trên máy chậm/tải + test xác định — đóng K-035)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Đóng:** K-035 (supervisor/liveness/step_09 flaky dưới tải) — nhưng KHÔNG fix ngọn (bump timeout); fix 2
> root-cause đã CHẨN ĐOÁN từ code thật.
> **Nền tảng (đã ĐỌC CODE thật `application/supervisor.py` + 2 test):**
> - `Supervisor._is_hung`: `last = hb.value if hb.value>0 else self._spawn_walltime; hung = (now-last) > heartbeat_timeout_s`.
>   → TRƯỚC beat đầu, mốc = spawn time, ngưỡng = **cùng** `heartbeat_timeout_s`. Startup-latency dùng CHUNG
>   ngưỡng với steady-state-liveness.
> - `_spawn`: `mp.Process(..., daemon=True).start()` (Windows spawn = re-import nặng) → `_spawn_walltime=time.time()`.
> - Test `test_supervisor_liveness.py::test_heartbeat_ok_worker_not_restarted`: `heartbeat_timeout_s=0.5`, assert `counts==0`.
> - Test `test_step_09_shutdown.py`: `sup.run(duration_s=0.4..1.5)` cố định RỒI assert side-effect (`'alive_' in log`, `len(lines)>5`).
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Bộ test process (supervisor/liveness/step_09) flaky KINH NIÊN dưới tải (K-035) → xói mòn niềm tin CI, mâu thuẫn
chính nền tảng "verify bằng chạy thật" của dự án. Đã CHẨN ĐOÁN (đọc code, khớp từng assertion với ngân sách
thời gian) ra **2 nguyên nhân GỐC phân biệt**, KHÔNG phải 1:

1. **(Production, bản chất) Supervisor nhập nhằng startup-latency với steady-state-liveness.** `_is_hung` dùng
   `heartbeat_timeout_s` cho CẢ (a) chờ beat ĐẦU sau spawn và (b) khoảng-cách-tối-đa giữa 2 beat. Nhưng spawn
   (Windows: re-import cả interpreter; node tải nặng) tốn lâu hơn nhiều so với nhịp steady-state → worker KHOẺ
   bị coi HANG lúc khởi động → **restart OAN**. Đây là lỗ THẬT khi vận hành ~100 cam trên node chậm/đang tải,
   KHÔNG chỉ là hiện tượng test.

2. **(Test) Ngân sách-thời-gian-cứng thay vì chờ-sự-kiện.** Nhiều test `sup.run(duration_s=X)` cố định RỒI mới
   assert side-effect (log có "alive_", số dòng > 5, "cleanup_done"). Nếu spawn chậm hơn X → side-effect chưa
   kịp xảy ra → fail. Đây là RACE (fixed-sleep-then-check), không phải chờ điều kiện.

Fix BẢN CHẤT (không bump timeout bừa = fix ngọn): (1) tách `startup_grace_s` (rộng, cho spawn) khỏi
`heartbeat_timeout_s` (chặt, steady-state) trong Supervisor; (2) viết lại test theo **chờ-sự-kiện** (poll điều
kiện tới khi thoả, cap RỘNG) → xác định trên MỌI tốc độ máy (pass nhanh khi máy nhanh, chỉ fail nếu điều kiện
KHÔNG BAO GIỜ xảy ra trong cap). Verify: chạy lặp nhiều lần phải ỔN ĐỊNH (không flaky), no-GPU.

**Chống bịa:** `_is_hung`/`_spawn`/`heartbeat_timeout_s`/`duration_s` + assertion test ĐÃ đọc code thật. Chẩn
đoán "spawn > timeout → false hang" là suy luận từ code + KHỚP failure quan sát (`counts!=0`, `'alive_' thiếu`)
+ đã kiểm bằng git-stash (#284: baseline sạch cũng fail → pre-existing, không do thay đổi khác).

### Goals
- Supervisor KHÔNG restart oan worker khoẻ đang khởi động chậm (tách startup-grace khỏi heartbeat-timeout).
- Test process XÁC ĐỊNH: chờ-sự-kiện + cap rộng → pass ổn định trên máy chậm/tải (hết flaky K-035).
- Giữ ngữ nghĩa liveness đúng: vẫn phát hiện hang steady-state (beat rồi ngừng) + crash + give-up cap.
- Backward-compat: default hành vi giữ nguyên khi không bật tính năng mới; baseline test pass (không giảm phủ).

### Non-Goals
- KHÔNG bump timeout bừa để "qua test" (fix ngọn — cấm).
- KHÔNG xoá/skip vĩnh viễn test flaky (giảm phủ = che bug, KHÔNG chấp nhận). Marker chỉ để phân loại, không bỏ.
- KHÔNG đổi cơ chế cascade shutdown (E-10) / bulkhead / backoff logic (đã đúng, không đụng).
- KHÔNG thêm retry-tự-động cho test (che flaky thay vì diệt gốc — chỉ dùng nếu chứng minh không thể xác định hoá).
- KHÔNG xử POSIX-specific (giữ phạm vi win32 như spec gốc; POSIX chưa verify — ghi rõ).

## Glossary
- **Startup grace** — khoảng thời gian RỘNG cho worker spawn + import + beat ĐẦU, TRƯỚC khi áp liveness steady-state.
- **Steady-state heartbeat timeout** — khoảng-cách-tối-đa cho phép giữa 2 beat khi worker đã chạy ổn định.
- **Chờ-sự-kiện (event-based wait)** — poll một điều kiện (log chứa marker, đủ số dòng...) tới khi thoả HOẶC hết cap.
- **False hang** — worker KHOẺ bị coi hang (do startup chậm) → restart oan.
- **Cap (rộng)** — giới hạn TRÊN của chờ-sự-kiện; chỉ để chặn treo vô hạn, KHÔNG phải mốc kỳ vọng (pass sớm khi điều kiện tới).

## Requirements

### Requirement 1: Tách startup-grace khỏi steady-state heartbeat-timeout (Supervisor, production)
**User Story:** Là kỹ sư vận hành ~100 cam trên node có thể chậm/đang tải, tôi muốn worker KHOẺ nhưng khởi động chậm KHÔNG bị restart oan, để hệ không tự-đá-chân khi cao tải.
#### Acceptance Criteria
- 1.1 — THE `WorkerSpec` SHALL có `startup_grace_s` RIÊNG (mặc định ≥ `heartbeat_timeout_s`, đủ rộng cho spawn) tách khỏi `heartbeat_timeout_s`.
- 1.2 — WHILE worker CHƯA gửi beat đầu (hb==0), THE `_is_hung` SHALL dùng `startup_grace_s` (tính từ spawn) làm ngưỡng — KHÔNG dùng `heartbeat_timeout_s`.
- 1.3 — WHEN worker ĐÃ gửi ≥1 beat, THE `_is_hung` SHALL dùng `heartbeat_timeout_s` (steady-state) tính từ beat cuối (giữ nguyên phát hiện hang steady-state).
- 1.4 — THE thay đổi SHALL additive: `startup_grace_s` default = giá trị GIỮ hành vi tương thích (vd = heartbeat_timeout_s nếu không set) → spec/test cũ không bắt buộc đổi; bật rộng hơn là opt-in.

### Requirement 2: Test process XÁC ĐỊNH bằng chờ-sự-kiện (đóng flaky K-035)
**User Story:** Là kỹ sư, tôi muốn test supervisor pass ỔN ĐỊNH trên máy chậm/tải, để CI đáng tin (phân biệt lỗi thật vs nhiễu).
#### Acceptance Criteria
- 2.1 — THE test assert side-effect (log chứa "alive_"/"cleanup_done", số dòng, restart_count) SHALL CHỜ điều kiện đó tới khi thoả (poll) với cap RỘNG, thay vì `sleep(duration cố định)` rồi assert.
- 2.2 — THE cap SHALL đủ rộng cho spawn chậm (vd ≥ nhiều giây) — chỉ chặn treo, KHÔNG phải mốc kỳ vọng; test pass NGAY khi điều kiện tới (nhanh trên máy nhanh).
- 2.3 — WHERE test kiểm liveness (heartbeat_ok không-restart), THE `heartbeat_timeout_s`/`startup_grace_s` dùng trong test SHALL phản ánh thực tế spawn (đủ để beat-đầu tới trong startup-grace) → không false-hang.
- 2.4 — THE re-run bộ test đã sửa SHALL ổn định: chạy LẶP (vd 5 lần) KHÔNG flaky (không fail ngẫu nhiên) — bằng chứng verify.

### Requirement 3: Giữ đúng ngữ nghĩa liveness + không giảm phủ
**User Story:** Là kiến trúc sư, tôi muốn hardening KHÔNG làm mất khả năng phát hiện hang/crash thật.
#### Acceptance Criteria
- 3.1 — THE test hang-detection (beat rồi ngừng → restart) SHALL vẫn PASS (phát hiện hang steady-state không đổi).
- 3.2 — THE test crash-detection + give-up-after-max SHALL vẫn PASS (đếm + cap không đổi).
- 3.3 — THE tổng số test SHALL KHÔNG giảm (không xoá/skip vĩnh viễn); marker (nếu thêm) chỉ phân loại.
- 3.4 — THE `import-linter` SHALL giữ 5 kept/0 broken (không đổi ranh giới layer).

### Requirement 4: Kiểm chứng KHÔNG cần GPU
**User Story:** Là kỹ sư, tôi muốn verify hardening trên máy dev no-GPU (chính máy đang gây flaky).
#### Acceptance Criteria
- 4.1 — `_is_hung`/startup-grace logic SHALL test được IN-PROCESS xác định (tiêm hb value + mốc thời gian) — không cần spawn thật.
- 4.2 — Test cross-process (spawn) SHALL chạy no-GPU (multiprocessing thuần) + ổn định qua chờ-sự-kiện.
- 4.3 — Chạy lặp bộ test process (≥5 lần) trên máy này SHALL ổn định — là bằng chứng đóng K-035.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format) có: (a) sửa `_is_hung` + `WorkerSpec.startup_grace_s`
(additive, default-tương-thích) + chứng minh phân biệt startup vs steady-state; (b) helper `wait_until(predicate,
cap, interval)` + cách viết lại từng test flaky theo chờ-sự-kiện (map từng assertion); (c) test in-process
xác định cho `_is_hung` (tiêm hb/thời gian); (d) chiến lược verify chống-flaky (chạy lặp ≥5 lần); (e) backward-compat
+ ranh giới layer + Non-Goal (không bump-bừa/không-skip). **KHÔNG code ở PHA này** (chờ user valid thiết kế).
