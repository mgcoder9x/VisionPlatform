# Requirements Document

> **Spec:** test-stability-hardening (ổn định test cross-process — cổng kiểm thử đáng tin, no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi sửa test.
> **Vấn đề gốc (chẩn đoán từ CODE THẬT, không đoán):** `test_supervisor_liveness` + `test_step_09_shutdown`
> flaky kinh niên dưới tải (K-035). ĐÃ kiểm chặt bằng git-stash (#284): trên baseline SẠCH fail 4/6 → flaky
> là PRE-EXISTING, KHÔNG do thay đổi feature. Supervisor sản xuất ĐÚNG; lỗi ở THIẾT KẾ TEST.
> **Nền tảng (đã ĐỌC CODE thật):**
> - `application/supervisor.py::Supervisor.run(duration_s)` **BLOCK** cả luồng gọi tới hết `duration_s` rồi mới
>   `_cascade_shutdown()` → test không quan sát-tiến-độ được, chỉ "chạy N giây rồi soi log". `run()` không
>   duration → chạy tới `_shutdown_requested`. Có `_shutdown_requested` (bool) nhưng KHÔNG có API public dừng.
> - `tests/worker_funcs_for_step_09.py`: `ok_worker` ghi `alive_{t}` mỗi 0.05s; `graceful_worker` ghi `alive_`
>   rồi `cleanup_done` trong `finally`. `tests/liveness_workers.py`: `heartbeat_ok_worker` beat mỗi 0.05s.
> - Test dùng `duration_s` tuyệt đối 0.4–1.5s + `heartbeat_timeout_s=0.5` + assert **rate/count** (`len>5`).
> - Windows `spawn` = re-import interpreter (startup 0.5–2s dưới tải) → cửa sổ nhỏ không đủ spawn+chạy.
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Cổng kiểm thử (`vp verify`) là hạ tầng NỀN TẢNG cho sản phẩm thương mại: nếu test flaky, mỗi lần đỏ không phân
biệt được LỖI THẬT vs NHIỄU → xói mòn niềm tin, che hồi-quy thật. Hiện 2–4 test cross-process (supervisor
spawn/heartbeat/shutdown) flaky dưới tải (K-035) — đã xác nhận PRE-EXISTING (git-stash #284), tức đây là nợ
kỹ thuật test, KHÔNG phải lỗi feature.

**Chẩn đoán bản chất (3 chế độ hỏng, verified từ code):**
1. **Rate-coupling:** `assert len(w2_lines) > 5` sau `run(1.5s)` mã hoá GIẢ ĐỊNH TỐC ĐỘ ghi (~6 dòng/1.5s). Máy
   tải nặng + worker khác respawn cạnh tranh → w2 ghi ít hơn → fail (`4 > 5`) dù PROPERTY ("w2 sống sót khi w1
   crash") vẫn đúng.
2. **Window-race:** `run(0.5s)` rồi assert `alive_` + `cleanup_done`. Spawn >0.5s → worker chưa ghi `alive_`
   thì đã shutdown → chỉ `cleanup_done` → fail. Cửa sổ nhỏ hơn độ trễ spawn.
3. **Tight-timeout false-positive:** `heartbeat_timeout_s=0.5` + beat mỗi 0.05s. Máy tải → khe lịch >0.5s →
   supervisor phát hiện "hang" ĐÚNG CHỨC NĂNG → restart → `counts!=0` → test coi là fail (nhưng supervisor
   không sai — timeout test quá chặt so với jitter thực).

**Nguyên tắc gốc để sửa (fix bản chất, KHÔNG fix ngọn):** test phải kiểm **PROPERTY** (bất biến hành vi), KHÔNG
kiểm **RATE/timing tuyệt đối**; đồng bộ trên **TIẾN ĐỘ QUAN SÁT ĐƯỢC** (event-driven) thay vì "ngủ N giây rồi
hy vọng"; timeout test phản ánh **cấu hình thực tế** (margin >> jitter). Retry-che-lỗi = fix ngọn (BÁC).

**Chống bịa:** mọi tham chiếu (run block, không API dừng public, worker ghi gì, timeout/duration cụ thể, spawn
Windows) ĐÃ đọc code thật. Giới hạn verify (trung thực): chứng minh VẮNG-flake là THỐNG KÊ (chạy lặp nhiều lần)
— event-driven xoá RACE về nguyên tắc, nhưng không thể chứng minh 0-flake trên máy tải VÔ HẠN.

### Goals
- Test cross-process kiểm **property bất biến** (sống-sót-sau-crash, cleanup-chạy, không-false-positive-hang)
  mà KHÔNG phụ thuộc rate/độ-trễ-spawn tuyệt đối.
- Đồng bộ **event-driven** (chờ tiến-độ-quan-sát-được tới deadline GENEROUS) thay vì cửa sổ wall-clock cứng.
- Timeout test phản ánh cấu hình thực tế (margin lớn so với jitter) → không false-positive dưới tải hợp lý.
- Giữ ĐỘ PHỦ (không xoá test); Supervisor PRODUCTION behavior KHÔNG đổi (nó đang đúng).
- (Tổ chức) marker cho test cross-process/timing → chạy tách được, nhất quán pattern marker `gpu` đã có.

### Non-Goals
- KHÔNG retry-che-lỗi (pytest-rerunfailures) — che flaky, không sửa gốc (BÁC rõ).
- KHÔNG đổi hành vi/tính đúng Supervisor sản xuất (heartbeat/backoff/cascade giữ nguyên); chỉ CÓ THỂ THÊM API
  dừng public (additive) phục vụ đồng bộ test.
- KHÔNG bảo đảm 0-flake trên máy tải BẤT KỲ (bất khả về lý thuyết); mục tiêu = loại race thiết kế + margin thực tế.
- KHÔNG đụng logic test không-timing (unit test thuần) — chỉ nhóm cross-process spawn.

## Glossary
- **Rate-coupling** — assertion phụ thuộc SỐ sự kiện trong cửa sổ thời gian cố định (giả định tốc độ).
- **Window-race** — assertion đúng chỉ khi việc xảy ra kịp trong cửa sổ wall-clock cố định (thua độ trễ spawn).
- **Event-driven wait** — chờ tới khi ĐIỀU KIỆN quan sát được thoả (poll trạng thái/log) tới deadline generous.
- **Property (bất biến)** — điều PHẢI đúng bất kể timing (vd "w2 tiếp tục chạy sau khi w1 crash").
- **Generous deadline** — thời hạn chờ đủ lớn để bao độ trễ spawn+chạy hợp lý (không phải cửa sổ khít).

## Requirements

### Requirement 1: Test kiểm PROPERTY, không kiểm rate/timing tuyệt đối
**User Story:** Là kỹ sư, tôi muốn test cross-process khẳng định BẤT BIẾN hành vi (không phải tốc độ) để không đỏ oan khi máy chậm/tải.
#### Acceptance Criteria
- 1.1 — THE test isolation SHALL khẳng định PROPERTY "worker ổn định tiếp tục chạy SAU khi worker khác crash" bằng bằng chứng KHÔNG-phụ-thuộc-rate (vd: có thêm output MỚI sau mốc crash), KHÔNG dùng ngưỡng đếm tuyệt đối (`>5`) mã hoá giả định tốc độ.
- 1.2 — THE test graceful SHALL khẳng định "worker ĐÃ chạy rồi ĐÃ cleanup" bằng cách ĐẢM BẢO worker chạy TRƯỚC khi shutdown (đồng bộ tiến độ), KHÔNG dựa cửa sổ 0.5s khít hơn độ trễ spawn.
- 1.3 — WHERE test cần "đã chạy đủ", THE test SHALL chờ tiến độ quan sát được (event-driven) tới deadline generous rồi mới assert/kết thúc.

### Requirement 2: Đồng bộ event-driven (không cửa sổ wall-clock cứng)
**User Story:** Là kỹ sư, tôi muốn test chờ ĐÚNG điều kiện đã xảy ra rồi mới hành động, để loại race ở gốc.
#### Acceptance Criteria
- 2.1 — THE Supervisor SHALL cung cấp cách DỪNG có kiểm soát từ luồng khác (API public additive, vd `request_stop()` set cờ shutdown) — KHÔNG đổi hành vi hiện có (không gọi = như cũ).
- 2.2 — THE harness test SHALL có helper `wait_until(predicate, deadline_s, poll_s)` chờ điều kiện thoả (vd log chứa `alive_`) tới deadline generous, fail RÕ nếu quá hạn (phân biệt "chưa xảy ra thật" vs "máy chậm").
- 2.3 — WHERE dùng event-driven, THE test SHALL chạy supervisor trong luồng nền (run() bắt ValueError signal khi không main-thread — đã có), poll tiến độ, rồi `request_stop()` + join.

### Requirement 3: Timeout test phản ánh cấu hình thực tế (margin >> jitter)
**User Story:** Là kỹ sư, tôi muốn test heartbeat "không false-positive" dùng timeout đủ rộng so với nhịp beat, để jitter lịch dưới tải hợp lý không bị coi là hang.
#### Acceptance Criteria
- 3.1 — THE test "beat đều → không restart" SHALL dùng `heartbeat_timeout_s` với MARGIN lớn so với nhịp beat (vd ≥20–60× nhịp), phản ánh cấu hình vận hành thực (timeout >> beat).
- 3.2 — THE test phát-hiện-hang (đúng chức năng) SHALL vẫn kiểm được: worker NGỪNG beat hẳn → bị phát hiện (dùng property "eventually detected", chờ tới deadline generous), KHÔNG phụ thuộc mốc tuyệt đối chặt.

### Requirement 4: Giữ độ phủ + không đổi production + tổ chức marker
**User Story:** Là kiến trúc sư, tôi muốn ổn định test mà KHÔNG giảm phủ và KHÔNG đổi hành vi supervisor thật.
#### Acceptance Criteria
- 4.1 — THE Supervisor production behavior (heartbeat/backoff/cascade/restart-cap) SHALL KHÔNG đổi; chỉ THÊM API dừng (additive) nếu cần.
- 4.2 — THE test cross-process/timing SHALL được đánh dấu marker (vd `slow`) — nhất quán pattern `gpu` (conftest) — để chạy tách/định vị được; MẶC ĐỊNH vẫn trong gate (giữ phủ).
- 4.3 — THE thay đổi SHALL KHÔNG xoá test/giảm phủ property; số test giữ hoặc tăng.

### Requirement 5: Kiểm chứng (trung thực về giới hạn)
**User Story:** Là kỹ sư, tôi muốn bằng chứng độ ổn định tăng, và hiểu rõ giới hạn.
#### Acceptance Criteria
- 5.1 — SAU sửa, THE nhóm test cross-process SHALL chạy LẶP nhiều lần (vd 5×) để lấy bằng chứng ổn định (pass mọi lần trên máy dev hiện tại) — thay vì 1 lần.
- 5.2 — THE báo cáo SHALL ghi RÕ: event-driven loại RACE thiết kế (nguyên tắc), nhưng KHÔNG chứng minh 0-flake trên máy tải vô hạn ([giới hạn], không over-claim).
- 5.3 — THE unit test khác (573+ hiện có) SHALL KHÔNG bị ảnh hưởng (vẫn pass).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format: Overview/Architecture/Components/Data Models/Error
Handling/Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) 3 chế độ hỏng
map fix; (b) API dừng public additive Supervisor + helper `wait_until` + pattern chạy-nền-poll-stop; (c) đổi
assertion rate→property cụ thể cho từng test; (d) timeout thực tế; (e) marker `slow`; (f) kế hoạch verify lặp
+ giới hạn trung thực. **KHÔNG sửa test/code ở PHA này** (chờ user valid thiết kế).
