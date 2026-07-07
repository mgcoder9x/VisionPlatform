# Vấn đề #05 — SHM frame bus + multi-process bulkhead

> Nguồn Design (đọc trực tiếp): `Design/module-03-build-along/step-05-add-shm.md`.
> **Quy trình 3 PHA tách riêng (người dùng yêu cầu):** (1) VALID THIẾT KẾ cực sâu → (2) TRIỂN KHAI sạch + test sâu → (3) TẠO BÀI HỌC.
> File này = **sản phẩm PHA 1** (design validation). Pha 2/3 append sau.

## Mục tiêu (xong = gì)
Multi-process frame transport: frame ndarray qua ranh giới process bằng `multiprocessing.shared_memory`
(~5µs/copy), ring buffer N slot, ABA prevention bằng generation counter, per-slot lock. **13 test** (gồm
1 cross-process subprocess thật). Đạt = test xanh THẬT trên máy này (Windows, Python 3.12.10).

## File sẽ tạo (3) — đổi `vision_demo`→`vision_platform`
1. `kernel/shm_frame_ref.py` — `ShmFrameRefData` (DTO thuần: ring_name/slot/generation/h/w/c; KHÔNG import multiprocessing).
2. `runtime/ipc/shm_frame_ring.py` — `SlotState`(IntEnum) · `ShmRingBuffer` · `ShmFrameWriter` · `ShmFrameReader` (transport, có multiprocessing/shared_memory). *(`runtime/ipc/__init__.py` đã tồn tại — rỗng.)*
3. `tests/test_step_05_shm.py` — 13 test.

## Concept cốt lõi (Pha 3 sẽ dạy)
- **SHM thay ZMQ cho frame**: 6MB/frame → memcpy ~5µs vs pickle/ZMQ ~10ms. ZMQ chỉ cho metadata (step-06).
- **5 SlotState**: FREE→WRITING→READY→READING→DONE (DONE recyclable như FREE).
- **Generation counter (ABA prevention)**: reader giữ `(slot, gen)`; slot tái dùng → gen tăng; reader check `actual_gen==expected_gen` mới trust → tránh đọc nhầm data mới bằng ref cũ.
- **Per-slot `mp.Lock` pass cross-process** qua `Process(args=...)` (pickle handle kernel object, KHÔNG tạo lock local trong child).
- **Lock chỉ bảo vệ state-transition; ghi/đọc 6MB data NGOÀI lock** (slot ở WRITING/READING → an toàn, giảm contention).
- **Layer**: DTO thuần ở `kernel/`; transport (I/O) ở `runtime/ipc/`.

---

## 🔬 PHA 1 — VALID THIẾT KẾ (cực sâu) — findings

> Nhãn: **[verified]** = đã đọc file/config thật · **[design-gap]** = thiếu trong thiết kế · **[chưa kiểm]** = phải kiểm khi triển khai (Pha 2).

### F-1 [verified] — import-linter KHÔNG ép được "kernel cấm multiprocessing" (ROOT, không phải ngọn)
- Design nói: đặt transport ở `runtime/ipc` vì contract "Kernel chỉ phụ thuộc domain" *cấm `multiprocessing` trong kernel*.
- **Đọc `vision-platform/pyproject.toml`:** contract **Domain** CÓ `"multiprocessing"` trong `forbidden_modules`; contract **Kernel** chỉ cấm `cv2, torch, zmq, runtime, application` — **THIẾU `multiprocessing` + `shared_memory`**.
- Hệ quả: lỡ `import multiprocessing` vào `kernel/` → `lint-imports` vẫn **KEPT** (không bắt). Ranh giới chỉ là quy ước trên giấy.
- **Fix tận GỐC (đề xuất, Q1):** thêm `"multiprocessing", "shared_memory"` (cân nhắc cả `PyQt6`, `fastapi`) vào `forbidden_modules` của contract Kernel → contract thật sự bảo vệ DTO kernel thuần. Sau khi thêm, chạy `lint-imports` phải vẫn 5 kept/0 broken (vì kernel không import chúng).

### F-2 [verified] — lệch tên Design (`vision_demo`) vs code thật (`vision_platform`)
- Code mẫu step-05 dùng `src/vision_demo/...`. Code thật ta là `vision_platform` (đã build #01–#04). → Triển khai dùng `vision_platform`, KHÔNG copy nguyên `vision_demo`.

### F-3 [design-gap, = F2 tracker] — slot kẹt `WRITING` khi acquire-lock lần 2 timeout
- Writer: mark WRITING → ghi data ngoài lock → **acquire lock lần 2 commit READY**; nếu lần 2 timeout (2s) → Design `return None` → **slot kẹt WRITING vĩnh viễn** (writer chỉ tái dùng FREE/DONE; demo không có lease/quarantine).
- Tinh tế: "rollback về DONE" cũng cần lock — mà lock đang là thứ timeout → rollback ngây thơ KHÔNG giải được nếu lock poison. Fix tận gốc THẬT = lease-timeout/quarantine (Design CỐ Ý hoãn sang production).
- **3 lựa chọn (Q2):** (A) giữ như Design + ghi rõ giới hạn (ERRATA) · (B) retry commit-acquire vài lần · (C) làm hẳn lease/quarantine (vượt scope step-05).
- **Khuyến nghị:** (A) — đúng phạm vi "demo kiểm chứng pattern"; mở ERRATA ghi "production cần lease/quarantine"; coi (C) là 1 vấn đề riêng sau.

### F-4 [verified bằng đọc code Design] — generation counter là WRITER-LOCAL → ring giả định 1 WRITER/ring
- `self._next_generation` khởi tạo =1 trong MỖI `ShmFrameWriter` instance, tăng dần.
- Nếu 2 writer cùng ghi 1 ring → 2 chuỗi gen độc lập (đều bắt đầu 1) → có thể trùng gen trên cùng slot → **ABA prevention vỡ**.
- Model Design: "mỗi camera = 1 process" = **1 writer/ring** → an toàn cho demo. → Phải GHI RÕ invariant "1 writer/ring" (DTO/docstring) để không ai dùng sai.

### F-5 [verified] — `runtime/ipc/__init__.py` đã tồn tại (rỗng); `kernel/shm_frame_ref.py` chưa có; KHÔNG có code/test SHM nào → slate sạch.

### F-6 [design-gap, robustness] — writer chỉ check `frame.shape`, KHÔNG check `dtype`
- `np.copyto(arr_uint8, frame)` với frame không phải uint8 → ép kiểu/cắt ÂM THẦM. Nên thêm check `frame.dtype == np.uint8` (fail-fast) HOẶC ghi rõ giả định. (Hardening — quyết ở Pha 2.)

### F-7 [verified bằng đọc test Design] — test ABA phụ thuộc `n_slots=4`
- `test_aba_prevention...` ghi thêm 3 frame ([2,3,4]) để ép tái dùng slot 0 → chỉ đúng khi `n_slots=4`. Fixture `ring` PHẢI là `n_slots=4`, nếu không assert `ref_new.slot==ref_old.slot` vỡ. → Pha 2 định nghĩa fixture đúng.

### F-8 [chưa kiểm — Pha 2, Windows] — `shared_memory` lifetime + `resource_tracker`
- Windows: segment gắn lifetime của creator → **creator (parent) phải còn sống** khi child đọc/ghi. Test mẫu: parent=creator (create=True) + child attach (create=False) → đúng chiều, OK theo Design.
- `resource_tracker` hay in `leaked shared_memory ... at shutdown` — [vấn đề đã biết CPython], thường vô hại nếu `cleanup_all()` đã close()+unlink(). → Phải CHẠY THẬT + đọc output, xác minh segment đã unlink. KHÔNG tin số "13 passed/1.63s" của tác giả.

### F-9 [verified safe] — annotation `mp.synchronize.Lock` chỉ hợp lệ nhờ `from __future__ import annotations` (lazy/string). PHẢI giữ dòng future import (Design có).

### F-10 [chưa kiểm — Pha 2, RỦI RO NHẤT, Windows spawn] — pass `list[mp.Lock]` qua `Process(args=...)`
- Windows dùng **spawn** (không fork): args bị pickle. `mp.Lock` chỉ share được qua cơ chế spawn của Process (KHÔNG qua Queue). Đây là claim rủi ro nhất → test cross-process phải CHẠY THẬT trên máy này mới kết luận. Design đã cảnh báo.

### F-11 [verified] — `HEADER_FMT="<IQQ"` = 4+8+8 = 20 byte; `SLOT_HEADER_BYTES=32` (pad). pack_into offset 0 size 20 ≤ 32 → OK, không tràn.

---

## ❓ Cần DUYỆT trước khi sang PHA 2 (triển khai)
- **Q1 (F-1):** Thêm `multiprocessing` + `shared_memory` vào `forbidden_modules` của contract Kernel? (khuyến nghị: CÓ — fix tận gốc enforcement.)
- **Q2 (F-3):** Hướng xử lý slot-kẹt-WRITING: (A) giữ + ERRATA / (B) retry / (C) lease-quarantine? (khuyến nghị: A.)
- F-4/F-6/F-7 sẽ xử lý lúc code (ghi invariant 1-writer, cân nhắc check dtype, fixture n_slots=4) — báo lại ở Pha 2.

## Trạng thái
- 🔬 **PHA 1 (valid thiết kế): XONG** — 11 finding (F-1..F-11), 2 câu hỏi duyệt (Q1/Q2). Bằng chứng: đọc `pyproject.toml` + `step-05-add-shm.md` + cây source thật.
- ✅ **PHA 2 (triển khai + test): XONG + VERIFY THẬT (2026-06-21)** — quyết Q1=CÓ, Q2=A.
  - File: `kernel/shm_frame_ref.py` (DTO), `runtime/ipc/shm_frame_ring.py` (SlotState/ShmRingBuffer/Writer/Reader), `tests/test_step_05_shm.py` (16 test).
  - **F-1 fix + kiểm chứng negative-test:** thêm `multiprocessing`/`shared_memory`/`PyQt6`/`fastapi` vào forbidden_modules Kernel; tạm import multiprocessing → lint BROKEN đúng → gỡ → 5 kept/0 broken. (ERRATA E-15.)
  - **F-3 (Q2=A):** giữ hành vi demo, ghi ERRATA E-15 + docstring (slot kẹt WRITING; production cần lease/quarantine).
  - **F-3b (RE-REVIEW phát hiện):** reader kẹt READING đối xứng F-3 (Pha-1 bỏ sót) — ghi docstring + ERRATA + comment inline.
  - **F-4:** ghi invariant 1-writer/ring trong docstring DTO + writer.
  - **F-6 (hardening):** thêm check `dtype==uint8` + test. **+2 defensive guard test** (re-review) → **16 test**.
  - **F-7:** fixture `n_slots=4` (recycle/ABA đúng).
  - **F-8/F-10 [VERIFY THẬT Windows]:** cross-process test PASS; **5× run KHÔNG flaky**; grep warning/leaked/resource_tracker → 0 match.
  - **Bằng chứng:** `pytest tests/test_step_05_shm.py` → **16 passed**; full `pytest -q` → **80 passed, 1 skipped**; `lint-imports` → **5 kept, 0 broken**; `struct.calcsize("<IQQ")=20` (chạy thật).
- ⬜ **PHA 3 (bài học `code-lessons/05-shm-frame-bus/`):** chờ — làm riêng, sau khi Pha 2 đã xanh thật (đã xanh).


---

## 🏭 PHA 1b — THẨM ĐỊNH CHUẨN PRODUCTION (thương mại Mỹ+Nhật, KHÔNG phải demo)

> Người dùng làm rõ: #05 là sản phẩm thương mại, KHÔNG phải demo → phải "kiểm chứng thiết kế ĐÚNG + TỐT".
> Nguồn thẩm định (đã đọc): `Design/module-04-deep-dives/02-shm-atomicity-explained.md` (R5-CRITICAL-01,
> lock vs seqlock, QUARANTINED). **Lưu ý E-5:** folder spec production đầy đủ
> `Vision_platform_architecture_design/05-inference-and-ipc/` **KHÔNG có trong repo** → phần protocol lease
> đầy đủ phải (RE)THIẾT KẾ + valid, KHÔNG copy được.

### Kết luận 2 mặt (trung thực)
- ✅ **ĐÚNG về tính nguyên tử/đua tranh (trong model 1-writer/1-reader):** MỌI truy cập header `<IQQ`
  (20 byte — KHÔNG atomic trên x86-64, Intel SDM Vol 3A §8.1.1: chỉ ≤8 byte aligned mới atomic) trong code ta
  ĐỀU nằm trong per-slot lock → KHÔNG torn read. ABA chặn bằng generation. Reader `arr.copy()` trước khi
  nhả slot → không đọc data đã ghi đè. 16 test xanh, cross-process 5× không flaky. → Trong phạm vi đã tuyên bố, code ĐÚNG.
- ❌ **CHƯA TỐT cho production 24/7:** thiết kế step-05 tự nhận là "simplified demo". Các thiếu sót dưới là
  defect **tính sẵn sàng/vận hành** với sản phẩm thương mại — phải xử lý tận gốc, không chấp nhận như demo.

### Khoảng trống production (P-1..P-6) — grounded từ deep-dive + lý do
- **P-1 [CRITICAL] Không có hồi phục khi process chết / lock poison.** Hiện timeout → `continue`/`return`
  để slot kẹt WRITING (F-3) / READING (F-3b) **vĩnh viễn** → ring cạn slot → frame bus đứng. Production
  (R5-CRITICAL-01) cần: (a) **QUARANTINED sentinel** ghi **lock-free bằng 1 store 32-bit aligned** (atomic) khi
  phát hiện owner chết; (b) **lock-free peek** `state` (4 byte, atomic) TRƯỚC khi acquire → thấy QUARANTINED thì
  bỏ qua, không đụng lock poison; (c) **`_pid_is_alive(owner_pid)`** để phân biệt "đang ghi" vs "đã chết".
- **P-2 Quan sát được (observability).** Demo nuốt lỗi im lặng (`except: pass`, `continue`). Production cần
  log cảnh báo (`shm_slot_lock_poisoned`, slot drop, quarantine) — chuẩn vận hành Mỹ+Nhật. (Hạ tầng ở step-08 structlog.)
- **P-3 Đa reader (reader_count pinning).** Demo READING độc quyền 1 reader. Hệ multi-consumer (inference +
  recorder + UI) cần đếm pin nhiều reader. Cần field `reader_count` trong header.
- **P-4 Header quá mỏng cho P-1/P-3.** `<IQQ` (state/gen/pid) thiếu `owner_pid`/`reader_pid`/`lease_deadline`/
  `reader_count`. Production cần header giàu hơn (deep-dive unpack 7 field) → đổi layout + giữ state ở offset 0,
  4-byte aligned để lock-free peek/quarantine atomic.
- **P-5 1-writer/ring (F-4).** generation writer-local. Model "1 camera = 1 process" thường chấp nhận, nhưng
  production nên **ép** (assert/guard) hoặc chuyển generation về ring-global (atomic counter) để an toàn tuyệt đối.
- **P-6 Chính sách backpressure (DROP_OLDEST/force_write).** Khi ring đầy, demo `return None`. Production cần
  chính sách rõ (step-07) + metric. Liên quan nhưng thuộc #07.

### Khuyến nghị (chờ duyệt — design-first, CHƯA code)
1. **Nâng #05 thành protocol production** = (re)thiết kế: header giàu (state@0 4-byte aligned + gen + owner_pid +
   lease_deadline + reader_count...), lease-timeout, QUARANTINED lock-free, pid-alive check, lock-free peek,
   observability hook. **Valid thiết kế trước** (đối chiếu deep-dive + Intel SDM) rồi mới code + test (gồm test
   inject crash writer/reader → quarantine + ring không cạn).
2. Vì spec production đầy đủ KHÔNG có trong repo (E-5) → phần lease tôi sẽ **đề xuất thiết kế mới + gắn nhãn rõ
   [thiết kế mới, cần bạn duyệt]**, KHÔNG nói là "spec chính thức". Phần QUARANTINED/lock-free peek thì grounded từ deep-dive.
3. Giữ bản demo hiện tại (16 test xanh) làm mốc; nâng cấp theo slice, mỗi slice valid thật + test crash-recovery.

> **Trạng thái P-1..P-6: ⬜ chờ duyệt hướng đi.** Đây là mở rộng phạm vi lớn so với step-05 — cần bạn xác nhận
> trước khi tôi (re)thiết kế production protocol.
