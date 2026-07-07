# 📌 ERRATA — Đính chính & lưu ý đa nền tảng

> File này ghi lại các **chỗ đã sửa** và **cạm bẫy môi trường** trong giáo trình, để người
> học (và các bản copy sau này của `Design/`) tránh lặp lỗi. Mỗi mục có: vị trí, vấn đề,
> cách đúng, và (nếu có) lệnh tự kiểm chứng. Cập nhật lần cuối: 2026-05-31.

---

## E-1 — Jitter circuit breaker: KHÔNG dùng `hash()` của string

- **Vị trí**: `module-04-deep-dives/05-circuit-breaker-math.md` — `StaggeredCircuitBreaker`.
- **Vấn đề (đã sửa trong file)**: bản gốc dùng `random.Random(hash(camera_id))` và tuyên bố
  "deterministic/reproducible per camera". Sai: Python bật **hash randomization**
  (PYTHONHASHSEED) cho `str` từ 3.3 → `hash("cam_1")` **khác nhau mỗi process**. Vì mỗi
  camera là 1 process riêng, jitter sẽ khác nhau mỗi lần restart và không reproducible.
- **Cách đúng** (đã áp dụng): seed bằng hàm hash ổn định cross-process —
  `int.from_bytes(hashlib.sha256(camera_id.encode()).digest()[:8], "big")` hoặc
  `zlib.crc32(camera_id.encode())`.
- **Tự kiểm chứng**:
  ```bash
  python -c "print(hash('cam_1'))"   # chạy 2 lần → 2 giá trị KHÁC nhau (xấu)
  python -c "import hashlib;print(int.from_bytes(hashlib.sha256(b'cam_1').digest()[:8],'big'))"  # 2 lần → GIỐNG nhau (đúng)
  ```
  Đã verify thật: `hash()` cho 2 giá trị khác nhau giữa 2 process; `hashlib` cho cùng 1 giá trị.

---

## E-2 — `MediaPacket` KHÔNG hashable (chứa ndarray)

- **Vị trí**: `module-03-build-along/step-02-first-mediapacket.md` — `MediaPacket`.
- **Vấn đề**: `@dataclass(frozen=True)` tự sinh `__hash__` từ **mọi field**. `MediaPacket`
  chứa `InMemoryArrayRef(array=ndarray)`, mà `ndarray` **không hashable** → `hash(packet)`,
  `set.add(packet)`, hoặc `dict[packet]` đều raise `TypeError`.
- **Cách đúng** (đã ghi note trong file): khóa theo `packet.packet_id` (str, hashable). Nếu
  thật sự cần packet hashable thì cân nhắc `@dataclass(frozen=True, eq=False)` (identity-hash),
  chấp nhận mất value-equality.

---

## E-3 — SHM (`shared_memory`) khác nhau giữa Windows và Linux/macOS

- **Vị trí**: `module-03-build-along/step-05-add-shm.md`.
- **Vấn đề**:
  - **Windows**: segment SHM gắn với lifetime của handle → **giải phóng khi process tạo nó
    thoát**. Linux/macOS: tồn tại tới khi `unlink()`. → **creator (parent) phải còn sống**
    suốt thời gian child đọc/ghi.
  - CPython hay in `resource_tracker` warning "leaked shared_memory objects" — thường **vô hại**
    nếu `cleanup_all()` đã `close()` + `unlink()` đúng.
- **Cách đúng** (đã ghi cảnh báo trong file): để parent làm creator; tự chạy
  `pytest tests/test_step_05_shm.py -v` trên **chính máy bạn** và đọc kết quả thật — con số
  "13 test pass" trong giáo trình là kỳ vọng (môi trường tác giả), không phải bảo đảm cho mọi OS.

---

## E-4 — Số benchmark là KỲ VỌNG, không phải bảo đảm

- **Vị trí**: `module-04-deep-dives/01-gil-truth.md`, `06-traceback-memory-retention.md`,
  `module-03-build-along/*` (các con số "X test pass", "296.7 MB", "0.94x/4x").
- **Lưu ý**: các số này đo trên môi trường tác giả (thường Python 3.11). Trên máy khác (OS,
  CPU, bản Python khác) số sẽ khác. **Pattern kết luận vẫn đúng**; chỉ con số tuyệt đối thay đổi.
- **Cách đúng**: khi tới step có `bench_*.py`, tự chạy và lấy số thật. Không trích số có sẵn.

---

## E-5 — Tham chiếu `Vision_platform_architecture_design/` có thể vắng mặt

- **Vị trí**: cuối hầu hết các file (mục "Production:" + link).
- **Lưu ý**: `00-START-HERE.md` đã nói folder này KHÔNG được đóng gói trong snapshot. Nếu bản
  copy `Design/` của bạn không có nó, hãy coi các link "Production:" là **tham chiếu khái niệm**,
  không phải nguồn kiểm chứng được.

---

## E-6 — Đổi tên package khi tự build

- **Lưu ý**: code mẫu Module 03 dùng package `vision_demo` và path `src/vision_demo/...`. Nếu
  bạn build với tên package khác (ví dụ `vision`), phải đổi **đồng loạt** `vision_demo → <tên
  của bạn>` ở mọi file code lẫn test, nếu không sẽ `ImportError` hoặc import-linter báo sai package.

---

## E-7 — DoD Module 06 cần thêm công cụ chưa có trong pyproject Step 01

- **Vị trí**: `module-06-implementation/02-definition-of-done.md` (mục Code + Tests).
- **Lưu ý**: DoD yêu cầu `ruff`, `mypy --strict`, coverage ≥80% (`pytest-cov`). Nhưng
  `pyproject.toml` dựng theo Step 01 chỉ có `pytest` + `import-linter` trong extra `[dev]`.
  → Khi áp DoD Module 06, cần bổ sung vào `[project.optional-dependencies] dev`:
  `ruff`, `mypy`, `pytest-cov`. Không phải lỗi giáo trình — chỉ là DoD nâng cao hơn skeleton
  ban đầu; thêm khi tới giai đoạn đó.

---

## E-8 — Số lượng test step 09 (đã sửa: 6, không phải 5)

- **Vị trí**: `module-03-build-along/step-09-add-shutdown.md`.
- **Vấn đề (đã sửa)**: phần mở đầu từng ghi "5 test", nhưng phần Tests có **6** test
  (5 cơ bản + `test_supervisor_graceful_worker_runs_cleanup_on_shutdown`). `00-overview.md`
  và README Step 10 đã ghi đúng "6". Đã đồng bộ tiêu đề step-09 thành 6 để khớp tổng
  **110 passed + 1 skipped (111 collected)**.

---

> Các đính chính E-1, E-2, E-3 đã được áp/ghi chú trực tiếp trong file giáo trình tương ứng.
> E-4, E-5, E-6 là lưu ý vận hành — không sửa nội dung dạy, chỉ nhắc.

---

## E-9 — `pyproject.toml` Step 01 thiếu `include_external_packages` cho import-linter

- **Vị trí**: `module-03-build-along/step-01-project-skeleton.md` — block `[tool.importlinter]`.
- **Vấn đề (phát hiện khi build thật `vision-platform/`, import-linter 2.x / Python 3.12)**: các
  contract `forbidden` liệt kê module NGOÀI repo (`cv2`, `torch`, `zmq`, `multiprocessing`,
  `PyQt6`, `fastapi`). Với cấu hình đó, `lint-imports` **dừng với lỗi**:
  `"The top level configuration must have include_external_packages=True when there are external forbidden modules."`
  → chạy y nguyên pyproject của Step 01 sẽ KHÔNG lint được (0 contract chạy).
- **Cách đúng** (đã sửa trong file): thêm vào `[tool.importlinter]`:
  ```toml
  [tool.importlinter]
  root_package = "vision_demo"
  include_external_packages = true
  ```
- **Tự kiểm chứng** (đã verify thật): sau khi thêm dòng trên, `lint-imports` in
  `Contracts: 5 kept, 0 broken`. Trước khi thêm → lỗi config, 0 contract chạy.
- **Ghi chú**: TOML boolean viết thường (`true`), dù thông báo lỗi của tool viết `True`.

---

## E-10 — Shutdown cascade sai thứ tự: `terminate()` ngay → cooperative cleanup bị race (flaky trên Windows)

- **Vị trí**: `module-03-build-along/step-09-add-shutdown.md` — `Supervisor._cascade_shutdown()`.
- **Vấn đề (phát hiện qua review thiết kế, đối chiếu code)**: bản cũ làm
  `shutdown_event.set()` rồi **gọi `p.terminate()` NGAY cho mọi worker**, phần `join(grace)`
  lại nằm SAU `terminate()`. Trên Windows `multiprocessing.Process.terminate()` =
  `TerminateProcess` (kill cứng, KHÔNG chạy `finally`/handler). Vì không có khoảng nghỉ giữa
  `set()` và `terminate()`, worker cooperative (`graceful_worker` poll event để tự thoát +
  cleanup trong `finally`) bị **race**: kill ập tới trước khi `finally` kịp chạy. Test
  `test_supervisor_graceful_worker_runs_cleanup_on_shutdown` (assert `"cleanup_done" in content`)
  vì thế **flaky** — pass khi máy rảnh (TerminateProcess bất đồng bộ chừa khe vài ms), fail khi
  máy tải nặng. Mâu thuẫn chính ý định "cooperative graceful" mà step-09 tuyên bố.
- **Cách đúng** (đã sửa trong file): cascade **cooperative-FIRST** —
  (0) set event → (1) **JOIN worker cooperative với grace TRƯỚC** (cho `finally` chạy) →
  (2) `terminate()` worker còn sống (non-cooperative / hang) → (3) `kill()` stragglers.
  Worker non-cooperative KHÔNG poll event → bỏ qua bước join (khỏi chờ vô ích), terminate ngay ở (2).
- **Tự kiểm chứng** (sẽ chạy khi build tới Step 09): `pytest tests/test_step_09_shutdown.py -v`
  lặp nhiều lần (vd 20×) phải PASS ổn định, không flaky. [chưa kiểm bằng chạy thật — Step 09 chưa build]
- **Ghi chú**: severity "rò rỉ SHM" chỉ đúng ở production (worker thật cleanup SHM/lock trong
  `finally`); trong demo `graceful_worker` chỉ ghi log → hậu quả chính là **flaky test + dạy sai
  thứ tự cascade**. Vẫn đáng sửa vì step này dạy pattern shutdown.

---

## E-11 — `InMemoryArrayRef`: immutability rò rỉ qua pickle + thiếu type check (Step 02)

- **Vị trí**: `module-03-build-along/step-02-first-mediapacket.md` — `InMemoryArrayRef`.
- **Vấn đề B (đã VERIFY bằng chạy thật — numpy 2.4.6)**: `__post_init__` gọi `setflags(write=False)`
  để khoá mảng. Nhưng khi `MediaPacket`/`InMemoryArrayRef` đi qua `pickle` (multiprocessing):
  (1) numpy **KHÔNG giữ** cờ `write=False` — mảng quay lại `writeable=True` ở process nhận;
  (2) `pickle` dựng lại dataclass **KHÔNG chạy `__post_init__`**. → mảng ghi đè được ở process
  nhận = vỡ contract read-only. Bằng chứng chạy thật: `before=False → after pickle=True`, mutate thành công.
- **Cách đúng (đã sửa)**: thêm `__setstate__` để re-lock khi unpickle:
  ```python
  def __setstate__(self, state):
      object.__setattr__(self, "array", state["array"])
      if self.array.flags.writeable:
          self.array.setflags(write=False)
  ```
  Verify thật sau fix: `after pickle=False`, mutate **BLOCKED**. (Lưu ý: vẫn là "read-only by
  contract" — alias writable khác buffer vẫn có thể đổi; nhưng nay giữ được qua pickle.)
- **Vấn đề C (robustness)**: `array: np.ndarray` không được kiểm runtime → truyền `list`/`PIL.Image`
  sẽ ném `AttributeError: 'list' object has no attribute 'flags'` tối nghĩa trong `__post_init__`.
  → đã thêm `isinstance(self.array, np.ndarray)` ném `TypeError` rõ nghĩa.
- **Vấn đề D (KHÔNG phải lỗi)**: thiếu `without_metadata` là **có chủ đích** — metadata nguồn
  (camera_id/timestamp) bất biến, không nên xoá. Giữ nguyên.
- **Ảnh hưởng số test**: step-02 thêm 2 test (`test_array_ref_stays_readonly_after_pickle`,
  `test_array_ref_rejects_non_ndarray`) → step-02 = **18** (16+2); tổng curriculum **113** (112 pass
  + 1 skip). Các số `111`/`110` còn trong `step-10-package-and-ship.md` + `00-START-HERE.md` là
  **baseline gốc** — khi chạy thật sẽ là 113/112 (đây là con số kỳ vọng, luôn đọc số thật khi chạy — E-4).

---

## E-12 — Step 02 post-implementation: 3 rủi ro kiến trúc (1 sửa, 2 ghi nhận)

- **Vị trí**: `module-03-build-along/step-02-first-mediapacket.md` — `BBox`, `MediaPacket`, `InMemoryArrayRef`.
- **Nguồn**: review sau triển khai #02 (Antigravity) — đã đối chiếu code + **chạy thật** từng claim.

- **Risk 3 (ĐÃ SỬA): `BBox` NORMALIZED không validate [0,1].** Code cũ chỉ check `w,h >= 0` →
  `BBox(100.0, 0, 0.5, 0.5, NORMALIZED)` được chấp nhận (verify thật: ACCEPTED). Sai logic normalized.
  → Thêm validate trong `__post_init__`: với `space == NORMALIZED`, mọi `x,y,w,h` phải trong [0,1].
  *Hệ quả phụ:* `test_bbox_immutable` cũ dùng `NORMALIZED` với (10,20,100,50) — chính là data sai →
  đã đổi sang `ORIGINAL_FRAME`. Thêm test `test_bbox_normalized_out_of_range_rejected`. step-02: 18→19.

- **Risk 1 (GHI NHẬN, không auto-fix): immutability NÔNG.** `MappingProxyType(dict(...))` chỉ khoá
  mức nông → nested mutable (list/dict con) trong metadata/artifacts **vẫn sửa được** (verify thật:
  `packet.metadata["lst"].append(3)` SUCCEEDED; caller mutate nested leak vào packet). KHÔNG auto
  `deepcopy` (tốn + artifacts hay chứa ndarray/object không deepcopy được; production dùng typed
  `ArtifactKey`). **Quy ước**: không đặt nested-mutable cần bảo vệ vào metadata/artifacts; caller tự
  copy hoặc dùng giá trị immutable. (Đã thêm note "Giới hạn đã biết" trong step-02.)

- **Risk 2 (GHI NHẬN, design đã có cơ chế): buffer reuse tearing.** Camera SDK ghi đè tuần hoàn 1
  buffer → `setflags(write=False)` không chặn ghi native lên cùng buffer ở frame kế. Design ĐÃ có
  `from_copy` vs `from_owned_array` + hướng dẫn. **Contract cho Step 03**: adapter camera dùng
  `from_copy` (hoặc SHM frame bus Step 05). Không phải bug step-02.

- **Ảnh hưởng số test**: step-02 = **19** (16+3); tổng curriculum **114** (113 pass + 1 skip).
  Số 111/110 ở step-10/START-HERE là baseline (xem E-11). Luôn đọc số thật khi chạy (E-4).

---

## E-13 — Step 03 post-implementation: 4 rủi ro adapter (1 sửa, 3 ghi nhận contract)

- **Vị trí**: `module-03-build-along/step-03-first-port.md` — `FakeFrameSource`, `NoiseFrameSource`.
- **Nguồn**: review sau triển khai #03 (Antigravity) — đối chiếu code + chạy thật.

- **Risk 3 (ĐÃ SỬA): `source_id` default trùng.** Default cố định `"fake_0"`/`"noise_0"` → 2 instance
  cùng id, mâu thuẫn docstring port "source_id unique" → log/metrics gộp/đè khi multi-source.
  → đổi sang `field(default_factory=...)` dùng `itertools.count()` (unique trong 1 process). Vẫn cho
  truyền id tường minh. Thêm test `test_source_id_unique_by_default`. step-03: 30→31 test.
  *Caveat:* cross-process (spawn) mỗi process reset counter → vẫn nên để composition root gán id tường minh.

- **Risk 1 (GHI NHẬN — contract): adapter KHÔNG thread-safe.** State (`_frame_count`/`_rng`/`_is_setup`)
  không khoá. Kiến trúc dùng **1 process/nguồn, single-thread** (bulkhead) → không cần lock. Contract:
  đừng gọi `read()`/`teardown()` đa luồng; cần thì bọc `threading.Lock`.
- **Risk 2 (GHI NHẬN — contract): contract test chưa kiểm timeout/blocking.** Fake/Noise non-blocking.
  Khi thêm adapter blocking thật (RTSP) → bổ sung test latency-injection + assert `ReadStatus.TIMEOUT`.
- **Risk 4 (GHI NHẬN — contract): `setup()` thất bại nửa chừng.** Fake/Noise không mở tài nguyên nên
  không leak. Adapter phần cứng thật phải `try/finally` thu hồi fd/socket/camera bus nếu setup lỗi.
- Đã thêm note "Giới hạn & contract cho adapter THẬT" trong step-03.

- **Ảnh hưởng số test**: step-03 = **31** (30+1); tổng curriculum **115** (114 pass + 1 skip).
  Số 111/110 ở step-10/START-HERE là baseline (xem E-11). Luôn đọc số thật khi chạy (E-4).

---

## E-14 — Step 04 post-implementation: 1 hallucination + 1 fix (context manager) + 2 ghi nhận

- **Vị trí**: `module-03-build-along/step-04-first-pipeline.md` — `SyncLinearExecutor`.
- **Nguồn**: review sau triển khai #04 (Antigravity) — đối chiếu code thật.

- **Risk 1(a) — SAI / HALLUCINATION (không sửa):** review nói `teardown_all` chạy thứ tự XUÔI
  (`for s in self._stages`). **ĐỌC CODE THẬT: đã dùng `for s in reversed(self._stages)`.** Không có
  bug này. (Ghi để cảnh báo: review của AI khác có thể bịa code — luôn tự đọc nguồn, §5.)
- **Risk 4 (ĐÃ SỬA): thiếu context manager.** Thêm `__enter__`/`__exit__` cho `SyncLinearExecutor`
  → `with SyncLinearExecutor([...]) as ex:` tự `setup_all` vào / `teardown_all` ra (kể cả khi raise),
  an toàn hơn quên `try/finally`. `__exit__` trả `False` (không nuốt exception). Thêm test. step-04: 12→13.
- **Risk 1(b) — GHI NHẬN:** `teardown_all` nuốt lỗi `except: pass` không log. Là lựa chọn "shutdown
  robust" có chủ đích; **bổ sung log cảnh báo ở Step 08** (structlog) khi có hạ tầng observability.
- **Risk 2 — GHI NHẬN (by design):** `SyncLinearExecutor` chạy 1 luồng → stage chậm block luồng đọc.
  Đúng tên "Sync"; async/multiprocess + bounded queue ở Step 05/07. Không phải bug.
- **Risk 3 — GHI NHẬN:** temporal coupling (DarkFilter cần artifact `brightness`). Design dùng
  **fail-fast** (raise lỗi rõ + đã test). Pipeline schema-validation lúc khởi động = production
  (`ProfileValidator`, Module 06), không thêm vào demo.
- **Ảnh hưởng số test**: step-04 = **13** (12+1); tổng curriculum **116** (115 pass + 1 skip). Số 111/110
  ở step-10/START-HERE là baseline (xem E-11). Luôn đọc số thật khi chạy (E-4).


---

## E-15 — Step 05 implementation: import-linter chưa ép "kernel cấm multiprocessing" + slot kẹt WRITING + ABA 1-writer

- **Vị trí**: `module-03-build-along/step-05-add-shm.md`; code thật `vision-platform/` (`kernel/shm_frame_ref.py`,
  `runtime/ipc/shm_frame_ring.py`, `pyproject.toml`). **Nguồn**: Pha-1 design-validation #05 (brief F-1..F-11) + Pha-2 build thật.

- **F-1 (ĐÃ SỬA — fix tận gốc enforcement):** step-05 tuyên bố đặt transport ở `runtime/ipc` vì import-linter
  contract "Kernel" *cấm `multiprocessing` trong kernel*. **Đọc `pyproject.toml`: SAI** — contract Kernel chỉ cấm
  `cv2/torch/zmq/runtime/application`, **THIẾU `multiprocessing`/`shared_memory`** (chỉ Domain có). → ranh giới chỉ
  là quy ước trên giấy. **Đã thêm** `"multiprocessing", "shared_memory", "PyQt6", "fastapi"` vào `forbidden_modules`
  của contract Kernel. **Kiểm chứng thật (negative test):** tạm `import multiprocessing` vào `kernel/shm_frame_ref.py`
  → `lint-imports` BROKEN ("vision_platform.kernel is not allowed to import multiprocessing"); gỡ ra → 5 kept/0 broken.

- **F-3 (= Finding F2, GHI NHẬN — demo giản lược, đã chọn hướng A):** writer mark WRITING → ghi data ngoài lock →
  **acquire lock lần 2 commit READY**; nếu lần 2 timeout → `return None`, slot **kẹt WRITING vĩnh viễn** (writer chỉ
  tái dùng FREE/DONE). Rollback cũng cần lock → không giải được nếu lock poison. **Fix tận gốc THẬT = lease-timeout +
  QUARANTINED state** (production), CỐ Ý hoãn — coi là 1 vấn đề riêng. Đã ghi rõ trong docstring `shm_frame_ring.py`.

- **F-3b (ĐỐI XỨNG — phát hiện khi RE-REVIEW Pha 2, Pha 1 đã BỎ SÓT):** `ShmFrameReader.read` cũng có ca tương tự —
  acquire lock LẦN 2 (mark DONE) timeout → `return frame_copy` nhưng slot **kẹt READING vĩnh viễn** (writer không tái
  dùng READING). Cùng GỐC + cùng cách giải (lease/quarantine production) như F-3. Đã ghi docstring + comment inline.
  Bài học: Pha-1 validation ban đầu chỉ soi writer, bỏ sót reader đối xứng → re-review bắt được (minh chứng giá trị doubt-driven).

- **F-4 (GHI NHẬN — invariant): generation là WRITER-LOCAL** (`_next_generation` mỗi `ShmFrameWriter` đếm riêng từ 1).
  → 1 ring an toàn với DUY NHẤT 1 writer (model "1 camera = 1 process"). Nhiều writer/ring → trùng gen → vỡ ABA.
  Đã ghi invariant trong docstring DTO + writer. KHÔNG dùng 1 ring cho >1 writer.

- **F-6 (ĐÃ THÊM — hardening, +1 test so với Design):** writer Design chỉ check `frame.shape`, KHÔNG check `dtype`
  → `np.copyto(uint8_buf, float_frame)` ép/cắt ÂM THẦM. Đã thêm `if frame.dtype != np.uint8: raise ValueError` +
  test `test_writer_rejects_wrong_dtype`. → step-05 = **14** test (13 Design + 1 hardening).

- **F-8/F-10 (ĐÃ VERIFY THẬT trên máy này — Windows, Python 3.12.10):** cross-process test (writer subprocess,
  reader parent, lock-passing qua `Process(args=)`, SHM attach `create=False`) **PASS**. Không thấy warning
  resource_tracker. (E-3 cảnh báo Windows lifetime — thoả vì parent=creator còn sống.)

- **F-2/E-6 (lệch tên):** code Design dùng `vision_demo`; build thật dùng `vision_platform` (đồng loạt).

- **Ảnh hưởng số test**: step-05 = **16** (13 Design + 1 dtype hardening F-6 + 2 defensive guard re-review). Tổng hiện tại chạy thật: **80 passed, 1 skipped**
  (`lint-imports` 5 kept/0 broken). Số 111/110 ở step-10/START-HERE là baseline (xem E-11) — luôn đọc số thật (E-4).
- **RE-REVIEW Pha 2 (doubt-driven, 2026-06-21):** chạy test_step_05 **5 lần liên tiếp → 14/14 mỗi lần, KHÔNG flaky**;
  grep `failed|error|warning|leaked|resource_tracker|Traceback` → **0 match** (xác nhận không rò SHM / không warning).
  `struct.calcsize("<IQQ")=20` verify bằng chạy thật. Sau khi thêm 2 guard test: 16/16 passed.


---

## E-16 — Review code-lessons #02/#03/#04 (Antigravity): 5 issue MỚI sửa, 6 đã documented

- **Nguồn**: `review/code_lessons_02_03_review.md` + `review/code_lessons_04_review.md`. ĐÃ kiểm chứng TỪNG claim
  với code thật + chạy thử (không tin review suông — §5). Mục tiêu: nâng #02/#04 lên chuẩn thương mại Mỹ+Nhật.

### Issue MỚI — đã SỬA + verify thật
- **R1#02 [CHÍ TỬ — VERIFY THẬT]: `MediaPacket` KHÔNG pickle được.** `metadata`/`artifacts` là `MappingProxyType`
  → `pickle.dumps(MediaPacket)` ném `TypeError: cannot pickle 'mappingproxy' object` (chạy thật xác nhận).
  Hệ đa tiến trình gửi MediaPacket qua IPC → crash. **Fix:** thêm `__getstate__` (convert proxy→dict thô) +
  `__setstate__` (re-wrap `MappingProxyType` giữ bất biến). Test `test_packet_pickle_roundtrip_preserves_immutability`.
- **R1#04 [MỚI]: ERROR vứt sạch traceback → mất khả năng debug.** `StageResult.error` chỉ giữ type+message.
  **Fix:** thêm field `error_traceback: Optional[str]` = `traceback.format_exc()` (CHUỖI — giữ thông tin debug
  nhưng KHÔNG giữ tham chiếu frame/biến → không rò RAM, vẫn đúng tinh thần chống traceback retention). Map sang
  `ExecutionResult`. Test `test_stage_error_keeps_traceback_string`.
- **R3#04 [MỚI]: teardown gọi lên stage chưa setup.** `teardown_all` lặp MỌI stage → nếu `setup_all` lỗi nửa
  chừng, teardown gọi cả stage chưa khởi tạo. **Fix:** `SyncLinearExecutor` theo dõi `_setup_done`; `setup_all`
  rollback (teardown ngược các stage đã mở) rồi raise khi lỗi; `teardown_all` chỉ dọn `_setup_done`. Test
  `test_executor_setup_failure_rolls_back_only_setup_stages`.
- **R6#04 [MỚI]: không validate kiểu trả về `_do_process`.** Lớp con trả `None`/ndarray → lọt downstream crash xa.
  **Fix:** `BaseStage.process` check `isinstance(result_packet, MediaPacket)` → TypeError → thành ERROR fail-fast.
  Test `test_stage_wrong_return_type_becomes_error`.

### Issue review nêu nhưng ĐÃ DOCUMENTED trước đó (không phải mới)
- R2#02 shallow immutability = E-12 R1. R3#02 buffer reuse = E-12 R2. R4#03 timeout contract = E-13 R2.
  R5#03 setup leak = E-13 R4. R4#04 nuốt lỗi teardown im lặng = E-14 R1b (hoãn step-08 observability).
  R5#04 thread-safety = E-14 R2 (by design Sync).

### Issue MỚI — R2#04 ĐÃ SỬA (context-manager uniformity)
- **R2#04 [ĐÃ SỬA]: vòng đời tài nguyên không đồng bộ.** demo_pipeline dùng try/finally thủ công; `IFrameSource`
  + adapter thiếu `__enter__`/`__exit__` → không dùng được `with source, executor:`. **Fix tận gốc:** thêm
  `__enter__`(→setup)/`__exit__`(→teardown, return False) vào (a) Protocol `IFrameSource` (vào hợp đồng), (b) 2
  adapter `FakeFrameSource`/`NoiseFrameSource`, (c) đổi `demo_pipeline` sang `with source, executor:`. Thứ tự ra
  `with A, B:` = B→A → executor.teardown_all() rồi source.teardown() (đúng như try/finally cũ). Test
  `test_source_context_manager` (parametrize Fake+Noise: vào setup, ra teardown kể cả khi raise). VERIFY THẬT:
  demo `with` chạy noise 3 frames OK; 86 passed.

### Sơ đồ
- `data-bricks-overview.drawio`: review sửa mũi tên `e-data` (ReadResult→media_ref thay vì →MediaPacket) cho đúng
  bản chất `ReadResult[ndarray]`. **[chưa kiểm]** — sẽ verify well-formed XML + đúng nghĩa.
- Đề xuất Mermaid inline thay SVG (vì SVG chưa export → ảnh vỡ): GHI NHẬN, chờ quyết (giữ workflow drawio→SVG hiện tại hay chuyển Mermaid).

### Ảnh hưởng số test
- step-02: 19→**20** (+pickle). step-03: 31→**33** (+context-manager Fake/Noise). step-04: 13→**16** (+traceback
  +wrong-type +setup-rollback). Tổng chạy thật: **86 passed, 1 skipped** · `lint-imports` 5 kept/0 broken
  (numpy 2.4.6, Python 3.12.10, Windows).
- Lessons đã đồng bộ quote: #02 mẩu 08; #03 mẩu 01/03/06 (context-manager); #04 mẩu 01/02/04/07/08/09. Đối chiếu byte khớp source.
