# VALIDATION REVIEW - SHM Production Hardening Design

> File được tạo bởi Codex, 2026-06-24.  
> Phạm vi: đọc cực kỹ `.kiro/specs/shm-production-hardening/design.md`, đối chiếu với code #05 hiện tại, review rủi ro cũ, một số nguồn chính thống về primitive nền tảng.  
> Không sửa `design.md`, không sửa code.

## Phán quyết ngắn

**VALID CÓ ĐIỀU KIỆN.**

Bản sửa `design.md` đã chốt đúng điểm sống còn: **`QUARANTINED` phải là terminal**, không reclaim về `FREE`. Đây là sửa đúng bản chất vì `multiprocessing.Lock` hiện bọc `SemLock(..., SEMAPHORE, 1, 1)`, không phải robust mutex; nếu process chết khi đã acquire, trạng thái trong SHM không thể tự giải phóng semaphore vật lý.

Tuy nhiên, **chưa nên chuyển thẳng sang Requirements/Tasks** nếu chưa sửa lại vài điểm trong design, đặc biệt:

1. `Testing Strategy` vẫn còn câu cũ: crash recovery đưa slot "về FREE". Câu này **mâu thuẫn trực tiếp** với `QUARANTINED terminal`.
2. Pseudo-code `ctypes` cho Windows PID liveness còn thiếu các chi tiết bắt buộc (`WinDLL(..., use_last_error=True)`, `argtypes/restype`, xử lý `WAIT_FAILED`).
3. Cơ chế "tạo lại toàn bộ ring khi quá ngưỡng" mới là khẩu hiệu, chưa có protocol switchover/ring epoch/control-plane.
4. `Property 3: No permanent stuck của RING` đang nói hơi quá. Đúng hơn: ring không deadlock toàn cục **khi còn slot khỏe**; nếu quarantine tích lũy tới ngưỡng thì phải rebuild ring có kiểm soát.

## Chốt 6 câu ở Testing Strategy

### 1. `ctypes` hay `psutil`

**Chốt khuyến nghị: dùng `psutil` làm dependency production cho liveness + `create_time`; không tự hand-roll ctypes ở vòng đầu.**

Lý do:

- `psutil` sinh ra đúng cho bài toán process identity/liveness đa nền tảng, và tài liệu của nó nhấn mạnh `Process.is_running()` đáng tin hơn kiểm PID thô khi có PID reuse.
- Thiết kế `ctypes` có thể đúng, nhưng dễ sai chi tiết: chỉ cần quên `use_last_error=True`, quên `restype=wintypes.HANDLE`, hoặc không xử lý `WAIT_FAILED` là có false-dead/false-alive.
- Đây là production hardening, không phải bài tối thiểu dependency. Thêm một dependency vận hành đã trưởng thành rẻ hơn tự giữ một lớp WinAPI + `/proc` riêng.

Điều kiện đi kèm:

- Thêm `psutil>=5.9` hoặc phiên bản phù hợp vào runtime dependencies khi implement.
- Nếu môi trường deployment cấm dependency native wheel, mới quay lại phương án `ctypes`/`/proc`, nhưng phải coi đó là một sub-spec riêng có test Windows/Linux đầy đủ.
- Bất kỳ trạng thái "không truy cập được process" phải được phân loại **alive_or_unknown**, không được coi là dead để quarantine.

### 2. Cơ chế `create_time`

**Chốt khuyến nghị: lưu process identity là `(pid, create_time_ns)` lấy từ `psutil.Process(pid).create_time()`.**

Quy tắc:

- Khi writer/reader pin slot, ghi `pid` và `create_time_ns` của chính process đó vào header.
- Khi recovery kiểm tra, process được coi là "cùng owner" chỉ khi PID còn tồn tại **và** `create_time_ns` khớp giá trị đã lưu.
- `NoSuchProcess` => dead.
- `AccessDenied`, lỗi quyền, lỗi platform, hoặc không đọc được `create_time` => **unknown/alive**, không quarantine; emit metric/cảnh báo.

Ghi chú precision:

- `psutil.create_time()` trả về seconds dạng float. Khi lưu `*_ns`, nên convert nhất quán trong một helper duy nhất, ví dụ `int(create_time * 1_000_000_000)`.
- Không cần tuyên bố nanosecond thật tuyệt đối; đây là "process start identity token" quy đổi sang int để so sánh ổn định.
- Test phải mô phỏng PID reuse bằng fake provider, vì ép OS reuse PID trong test thật sẽ flaky.

### 3. `MAX_READERS`

**Chốt khuyến nghị: `MAX_READERS = 8`.**

Lý do:

- `4` đủ cho demo, nhưng sản phẩm 24/7 rất dễ phát sinh reader phụ: inference, recorder, preview, health probe/debug, replay, audit.
- Header tăng từ khoảng `192B/slot` lên `256B/slot`, vẫn nhỏ so với frame data cỡ MB.
- `8` cho dư địa vận hành mà không kéo design sang dynamic registry phức tạp.

Quy tắc khi đầy registry:

- Reader mới phải fail-fast với event `shm_reader_registry_full`, không spin vô hạn.
- `reader_count` phải được định nghĩa là số ô registry hợp lệ, không phải một biến độc lập có thể lệch pha.
- Cleanup dead reader phải xóa đúng ô registry rồi tính/ghi lại count dưới lock.

### 4. Giá trị lease

**Chốt khuyến nghị ban đầu:**

- `WRITE_LEASE_NS = 2_000_000_000` (2s)
- `READ_LEASE_NS = 2_000_000_000` (2s)
- Tách riêng `LOCK_ACQUIRE_TIMEOUT_S`; khuyến nghị production ban đầu `0.05s` đến `0.10s`, không dùng 2s như demo cho đường scan realtime.

Lý do:

- Reader hiện copy frame ra ngoài rồi mới inference; lease chỉ cần bao bọc pha pin/copy/unpin, không bao bọc model inference.
- Recovery chỉ quarantine khi **lease expired + owner dead + identity khớp dead**. Lease ngắn không được tự gây corrupt nếu rule này giữ đúng.
- 2s đủ rộng cho Windows scheduling/GC trong pipeline thường; test có thể override xuống ms để chạy nhanh.

Điều kiện:

- Lease phải là config, không hard-code vĩnh viễn.
- Nếu owner còn sống nhưng quá lease: log/metric `lease_expired_owner_alive`, skip slot, tuyệt đối không quarantine.
- Nếu liveness unknown: log/metric `owner_liveness_unknown`, skip slot.

### 5. Chính sách ARM

**Chốt khuyến nghị: vòng hardening này chỉ claim production cho x86-64. ARM phải được gate riêng.**

Không nên chọn "ARM dùng lock thuần" như một câu trả lời đủ, vì nếu lock đã poison thì dùng lock thuần sẽ mất chính khả năng bypass lock chết. Cách nói đúng hơn:

- x86-64: bật lock-free `state` sentinel path.
- ARM64/ARM: không claim production cho crash/poison recovery cho tới khi có primitive atomic/fence rõ ràng hoặc một thư viện/native helper đã test trên phần cứng thật.
- Nếu target thật có Jetson/Apple Silicon/Graviton, tạo task riêng: `arm-atomic-sentinel-validation`, gồm stress test visibility, kill-holder test, và benchmark jitter.

Sticky sentinel làm rủi ro ARM nhẹ hơn về mặt correctness dài hạn, nhưng **không đủ để gọi là verified** nếu chưa có barrier/hardware test.

### 6. Overhead header

**Chốt khuyến nghị: chấp nhận overhead header `256B/slot` với `MAX_READERS=8`.**

Tính nhanh:

- Base v2: `48B`.
- Reader registry: `8 * 24B = 192B`.
- Tổng: `240B`, pad lên cache-line => `256B`.

So với frame `1920x1080x3 uint8` khoảng `6MB`, overhead này không đáng kể. Thứ đáng chú ý hơn không phải bytes header mà là số lượng OS objects/SHM segments/locks và protocol cleanup.

## Findings bắt buộc xử lý trước Requirements/Tasks

### P0-1. Testing Strategy đang giữ logic cũ `slot về FREE`

Trong `design.md`, phần test mới cần có nói: crash writer giữa `WRITING` -> parent recovery -> **slot về FREE**. Điều này sai sau quyết định R-1.1.

Kỳ vọng đúng:

- Nếu process chết khi giữ lock vật lý: slot chuyển `QUARANTINED`, terminal, không acquire lại lock đó.
- Ring tiếp tục với `n_slots - quarantined_slots`.
- Khi vượt ngưỡng quarantine: tạo ring mới bằng protocol switchover, không recycle slot cũ.

Khuyến nghị sửa design:

- Đổi test thành `dead_writer_holding_lock_marks_slot_quarantined_terminal`.
- Thêm assert writer/reader không acquire lock slot đó nữa.
- Thêm test `ring_degrades_capacity_after_quarantine`.
- Thêm test `ring_rebuild_after_quarantine_threshold` nhưng chỉ sau khi có ring epoch/switchover protocol.

### P0-2. Pseudo-code Windows `ctypes` chưa đủ an toàn

Nếu vẫn chọn `ctypes`, pseudo-code hiện tại chưa đủ production:

- `ctypes.windll.kernel32` + `ctypes.get_last_error()` không phải pattern an toàn; cần `ctypes.WinDLL("kernel32", use_last_error=True)`.
- `OpenProcess` phải khai báo `argtypes`/`restype`; HANDLE trên 64-bit không được để default `c_int`.
- `WaitForSingleObject` có `WAIT_FAILED`; code hiện tại chỉ so `WAIT_TIMEOUT`, nên failure có thể bị diễn dịch thành "dead".
- `CloseHandle` cũng cần prototype.

Khuyến nghị:

- Vì đã chốt `psutil`, đưa pseudo-code ctypes xuống appendix/fallback, không để nó là đường chính.
- Nếu fallback vẫn tồn tại, test bắt buộc gồm: self alive, child dead, access denied/unknown mocked, invalid handle mocked, create_time mismatch.

### P0-3. Ring rebuild chưa có protocol

`design.md` nói "quá ngưỡng -> tạo lại toàn bộ ring", nhưng production cần câu trả lời cụ thể:

- Ai là authority tạo ring mới?
- Ring name mới được publish qua đâu?
- Các `ShmFrameRefData` cũ xử lý thế nào?
- Reader đang cầm ref cũ thấy ring epoch mismatch thì trả gì?
- Khi nào unlink old SHM?
- Nếu writer rebuild trong khi reader cũ còn attach thì có data loss hay leak không?

Khuyến nghị:

- Thêm ring-level metadata: `ring_id`/`epoch`/`header_version`.
- `ShmFrameRefData` hiện chưa có `ring_epoch`; hoặc phải thêm trường này, hoặc control-plane bảo đảm ref cũ không đi qua sau switchover. Cần chốt trước khi tasks.
- Rebuild không nên nằm ẩn trong per-slot recovery. Nó là ring-level operation có observability và handshake riêng.

### P1-1. Recovery đọc nhiều field lock-free chưa có snapshot rule

Lock-free `state` 4-byte là hợp lý. Nhưng recovery còn cần đọc `owner_pid`, `owner_create_time_ns`, `lease_deadline_ns`, reader registry. Đây là nhiều field, không phải một snapshot atomic.

Rủi ro:

- Nếu đọc trong lúc owner sống đang đổi header, có thể ghép owner cũ + lease mới.
- Nếu lock đang poison do process chết giữa chừng khi cập nhật header, snapshot có thể partial.
- Trên ARM, visibility/order càng không nên nói chắc.

Khuyến nghị:

- Chỉ đọc lock-free multi-field sau khi acquire lock timeout.
- Đọc snapshot 2 lần liên tiếp; chỉ hành động khi hai snapshot giống nhau hoặc state đã là `QUARANTINED`.
- Unknown/torn/snapshot không ổn định => không quarantine ngay; emit metric và retry sau.
- Owner fields nên được ghi theo thứ tự có chủ ý: identity trước, lease sau, state cuối khi có thể. Với state terminal, chỉ `state` là authority để skip.

### P1-2. Reader registry cần invariant chặt hơn

Thiết kế reader registry là hướng đúng, nhưng cần invariant rõ để tránh `reader_count` lệch:

- `reader_count == số ô registry active`.
- Mỗi reader có một slot registry duy nhất cho mỗi SHM slot.
- Pin chỉ thành công nếu còn ô trống; nếu không, fail-fast.
- Unpin xóa ô theo `(pid, create_time)` rồi recompute count.
- Cleanup dead reader chỉ xóa reader dead/expired; nếu còn reader sống thì slot vẫn `READING`.

Test bắt buộc:

- 2 reader sống + 1 reader chết => cleanup giảm count, không quarantine slot.
- Reader chết khi đang giữ lock lúc pin/unpin => slot terminal, vì lock vật lý có thể poison.
- Registry full => reader mới fail rõ, không làm hỏng count.

### P1-3. Cross-process single-writer enforcement còn quá mỏng

`register_writer()` trong process chỉ chặn lỗi nội bộ một process. Production cần chặn cross-process:

- Ring-level writer registry lưu `(writer_pid, writer_create_time_ns, writer_lease_ns)`.
- Nếu writer hiện tại còn sống và create_time khớp, writer mới bị reject.
- Nếu writer cũ dead/expired, policy phải chốt: cho writer mới takeover ring cũ hay bắt rebuild ring mới.

Khuyến nghị của tôi: **writer death nên ưu tiên rebuild/switchover ring**, không takeover im lặng trên ring cũ đã có slot terminal, trừ khi spec chứng minh takeover an toàn.

### P1-4. Cold-start sanitation cần phân biệt POSIX và Windows

Thiết kế "unlink segment cũ + lock mới" đúng hướng nhưng chưa đủ nền tảng:

- Python docs nói `SharedMemory.unlink()` không có tác dụng trên Windows; block biến mất khi tất cả handle đóng.
- Trên POSIX, unlink name có thể ngăn attach mới nhưng memory còn sống tới khi handle cuối đóng.
- Resource tracker của Python có hành vi khác nhau giữa process có chung ancestor và process độc lập.

Khuyến nghị:

- Creator `create=True` không nên attach vào segment cũ nếu name đã tồn tại.
- Dùng tên ring có epoch/uuid cho phiên mới thay vì cố tái sử dụng name cố định.
- Nếu cần well-known name, nó nên trỏ tới control-plane nhỏ, còn data ring dùng name theo epoch.

### P1-5. Property 3 đang overclaim

"No permanent stuck của RING" chỉ đúng nếu hiểu là "không kẹt toàn cục vì một lock poison". Nhưng terminal quarantine làm mất capacity vĩnh viễn.

Khuyến nghị sửa wording:

> Dead owner + expired lease => slot terminal quarantine; ring avoids deadlock by skipping that slot while enough healthy slots remain. Availability degrades monotonically until ring-level rebuild.

### P2-1. Header v2 nên có version/magic rõ ràng

Hiện state giữ offset 0 là đúng. Nhưng khi đã có v2 header và cold-start sanitation, attach path cần biết mình đang đọc layout nào.

Khuyến nghị:

- Có ring-level header hoặc per-slot constant cho `magic`, `header_version`, `header_size`, `max_readers`.
- Attach mismatch => fail fast, không diễn dịch bytes rác thành state hợp lệ.
- `struct.calcsize`/offset constants phải có unit test khóa layout.

### P2-2. Observability nên có taxonomy tối thiểu

Hook no-op/stderr là đủ cho slice đầu, nhưng event fields cần chốt sớm để test không mơ hồ:

- `shm_slot_lock_timeout`
- `shm_slot_quarantined`
- `shm_reader_registry_full`
- `shm_reader_reaped`
- `shm_owner_liveness_unknown`
- `shm_ring_rebuild_requested`
- `shm_ring_capacity_degraded`

Mỗi event nên có tối thiểu: `ring_name`, `ring_epoch`, `slot`, `state`, `owner_pid`, `owner_create_time_ns`, `quarantined_count`, `healthy_slots`.

## Test matrix khuyến nghị

### Slice 1 - header v2

- `struct.calcsize` và offsets đúng.
- `state` offset 0, 4-byte aligned.
- 8-byte fields nằm ở offset chia hết cho 8.
- `MAX_READERS=8` => header padded 256B.
- attach vào header version sai => fail fast.

### Slice 2 - pid/process identity

- self alive.
- child alive rồi dead.
- fake PID reuse: same pid, different create_time => not same owner.
- `AccessDenied`/unknown => không quarantine.
- Nếu dùng psutil: mock `NoSuchProcess`, `AccessDenied`, `ZombieProcess`.

### Slice 3 - terminal quarantine

- Process chết khi giữ lock => acquire timeout => state becomes `QUARANTINED`.
- Subsequent writer/reader peek sees `QUARANTINED` and never tries the lock.
- Test cũ "slot về FREE" bị xóa/đổi.

### Slice 4 - reader registry

- 2 readers pin/unpin parallel.
- 1 reader chết sau pin => cleanup registry, count giảm.
- 1 reader chết khi đang giữ lock => terminal quarantine.
- registry full => fail-fast + metric.

### Slice 5 - ring degradation/rebuild

- Quarantine 1 slot => writer still writes to remaining slots.
- Quarantine threshold reached => `ring_rebuild_requested`.
- Ring epoch/name switchover test: ref cũ không đọc nhầm ring mới.

### Slice 6 - architecture/lint

- `kernel` vẫn không import `multiprocessing`, `shared_memory`, `psutil`.
- `psutil` chỉ nằm ở `runtime/ipc`.
- `lint-imports`: 5 kept, 0 broken.

## Implementation order khuyến nghị

1. **Design correction pass**: sửa wording/test expectation trong `design.md` trước khi generate tasks.
2. **Process identity adapter**: `_process_identity.py` trong `runtime/ipc`, ưu tiên psutil, test fake provider.
3. **Header v2 constants**: offsets, layout tests, version/magic.
4. **Lock-free state peek + terminal quarantine**: chưa reader registry.
5. **Reader registry**: count derived from registry, cleanup dead reader.
6. **Observability hook**: event taxonomy tối thiểu.
7. **Writer registry/ring epoch**: chỉ sau khi chốt switchover.
8. **Ring rebuild**: không gộp vào per-slot quarantine.

## Kết luận thiết kế

Thiết kế đã sửa đúng lỗi chí tử nhất. Tôi đồng ý với hướng:

- `QUARANTINED` terminal.
- Lock-free peek state trước acquire.
- Reader registry cố định.
- `(pid, create_time)` thay vì PID thô.
- Cold-start sanitation.
- Không claim ARM khi chưa có barrier/test.

Nhưng tôi **không khuyến nghị ship tasks ngay** nếu `design.md` chưa sửa các mâu thuẫn P0 ở trên. Đặc biệt, chỉ một dòng test "slot về FREE" còn sót cũng đủ kéo implementer quay lại bug R-1.1.

## Đã verify

- Đã đọc `.kiro/specs/shm-production-hardening/design.md`.
- Đã đọc `review/shm_production_hardening_design_review.md`.
- Đã đọc code hiện tại:
  - `vision-platform/src/vision_platform/runtime/ipc/shm_frame_ring.py`
  - `vision-platform/src/vision_platform/kernel/shm_frame_ref.py`
  - `vision-platform/tests/test_step_05_shm.py`
  - `vision-platform/pyproject.toml`
  - `Design/module-04-deep-dives/02-shm-atomicity-explained.md`
- Đã chạy `tests/test_step_05_shm.py -q`: **16 passed**.
- Đã chạy `lint-imports`: **5 kept, 0 broken**.
- Đã kiểm local Python 3.12.10: `multiprocessing.synchronize.Lock` gọi `SemLock(..., SEMAPHORE, 1, 1)`.
- Đã đối chiếu nguồn chính thống:
  - Python `ctypes` docs: `use_last_error=True` là cơ chế an toàn cho Windows last-error copy.
  - Python `shared_memory` docs: `unlink()` không có tác dụng trên Windows; Windows xóa khi mọi handle đóng.
  - psutil docs: `Process.is_running()` xử lý tốt hơn PID thô khi PID reuse.
  - Microsoft `OpenProcess`, `WaitForSingleObject`, `GetExitCodeProcess` docs: `ERROR_ACCESS_DENIED`, `WAIT_TIMEOUT/WAIT_FAILED`, và bẫy `STILL_ACTIVE=259`.

## Chưa verify

- Chưa repro thật process chết khi đang giữ `multiprocessing.Lock`.
- Chưa test Windows `psutil` với process khác quyền.
- Chưa test ARM memory visibility/barrier.
- Chưa có ring rebuild/switchover implementation để verify.
- Chưa chạy full test suite toàn repo trong lượt này; chỉ chạy test #05 và import-linter.

