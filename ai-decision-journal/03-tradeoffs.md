# 03 — Trade-off AI phải cân nhắc

> Định dạng + quy tắc: xem `README.md` §1. Ghi rõ **A vs B → chọn X vì ... (cái MẤT là ...)**.
> Trạng thái: ✅ verify · 🟡 chưa kiểm đủ · 🔴 rủi ro mở · ↩️ đã đảo.

---

### T-001 — 2026-07-02 — Well-known segment tên cố định  vs  nhúng epoch vào ctrl segment sẵn có
Status: ✅
Scope: shm-ring-epoch-switchover / Task 1
Nguồn: LOG Entry #119, #121
Links: D-001, C-001
Chọn: **well-known segment riêng** (tên cố định).
Cái mất: thêm 1 segment phải quản vòng đời (tạo/attach/close). Đổi lại: bên đọc tìm ring hiện hành xác định, không phụ thuộc tên uuid ngẫu nhiên.

### T-002 — 2026-07-02 — OS handle ref-count  vs  attach_count u32 RMW dưới lock
Status: ✅
Scope: shm-ring-epoch-switchover / Task 2
Nguồn: LOG Entry #126 · thực nghiệm Windows `_shm_lifecycle_probe`
Links: D-004, C-002, K-003
Chọn: **để OS ref-count handle** (mỗi bên close khi rời epoch).
Cái mất: hành vi teardown khác nhau giữa OS — POSIX MAY unlink sớm; **Linux resource_tracker CHƯA verify** (xem K-003). Đổi lại: bỏ được RMW không-atomic across-process (nguồn race đếm sai → giải phóng ring cũ sớm) — đơn giản + đúng bản chất.

### T-003 — 2026-06-24/07-02 — API explicit + additive  vs  auto/ép-cứng trong __init__
Status: ✅
Scope: #05 Task 7 · switchover Task 4.1
Nguồn: LOG Entry #110, #125
Links: D-003, D-006
Chọn: **explicit** (`register_writer()`, `bootstrap_current_ring()` gọi tường minh).
Cái mất: composition root phải nhớ gọi (không "tự động chống sai"). Đổi lại: zero regression trên baseline, blast-radius nhỏ, không phá test hiện có; race first-register đồng thời là trách nhiệm composition root (documented).

### T-004 — 2026-06-24 — Dependency injection (liveness/obs)  vs  hard-code psutil/logging
Status: ✅
Scope: #05 Task 4.2, Task 6
Nguồn: LOG Entry #106, #109
Links: D-005
Chọn: **injection**, mặc định `owner_liveness` (psutil thật) + `NoOpHook`.
Cái mất: thêm tham số __init__ (bề mặt API rộng hơn). Đổi lại: test recovery/observability deterministic + không tốn khi tắt; structlog đầy đủ để dành spec #08.

### T-005 — 2026-06-24 — Test đa-reader deterministic in-process  vs  đa-process thật
Status: 🟡
Scope: #05 Task 5 · switchover Task 6 (T-B)
Nguồn: LOG Entry #108 · end.md ("switchover cross-process thật chưa chạy → Task 6")
Links: D-002, C-005, K-002
Chọn (tạm): **deterministic in-process** (reader giả đã pin, liveness ALIVE) để không flaky.
Cái mất: CHƯA chứng minh race/switchover thật bằng spawn nhiều process → còn 🔴 K-002. Đổi lại: test ổn định ngay; cross-process thật dời sang Task 6 (kill harness T-B). → Còn 🟡 tới khi T-B chạy.

### T-006 — 2026-06-24 — REBUILD_THRESHOLD default thận trọng  vs  đo SLA thật
Status: 🔴
Scope: #05 Task 10.2
Nguồn: LOG Entry #111
Links: K-004
Chọn (tạm): default `ceil(n_slots/2)` (`max(1,(n+1)//2)`).
Cái mất: CHƯA tuning theo SLA thật → có thể rebuild quá sớm/muộn trong production. Cố ý gắn nhãn 🔴 "cần benchmark", KHÔNG bịa số "đã tối ưu". → Đóng khi có số đo thật.

### T-007 — 2026-07-03 — Dựng lại venv (fix gốc)  vs  vá shim interpreter (fix ngọn)
Status: ✅
Scope: môi trường / Task 4.2
Nguồn: LOG Entry #129 · `.venv` cũ trỏ `C:\Users\k.nguyen.manh.toan\...Python311` (không tồn tại trên máy `toann`)
Links: K-013
Chọn: **xoá + dựng lại `.venv`** bằng Python 3.13 máy hiện tại.
Cái mất: tốn mạng/thời gian cài lại + đổi phiên bản lib (numpy 2.4.6→2.5.0, il 2.12→2.13, py 3.11→3.13, xem K-013). Đổi lại: sạch, đúng gốc (venv là artifact gitignore); baseline vẫn 200/1 + lint 5/0 nên tương thích. Vá shim = fix ngọn, để lại venv lai máy khác.


### T-008 — 2026-07-06 — Nới type hint media_ref thành Protocol (mở đa-impl)  vs  giữ concrete (type chặt)
Status: ✅ (đã code + verify: 369/1 · lint 5/0 — nới type KHÔNG phá test/contract nào)
Scope: sub-spec media-ref-port · `kernel/media_packet.py`
Nguồn: design.md media-ref-port · grep consumers · K-038
Links: D-038, K-038
Chọn: **nới `media_ref: InMemoryArrayRef → IMediaRef` (Protocol)**.
- Cái mất: type hint "lỏng" hơn — mypy không còn biết chính xác impl là InMemoryArrayRef, chỉ biết "có
  .array". Mất vài autocomplete field riêng của InMemoryArrayRef ở chỗ dùng packet.
- Đổi lại: packet chạy được với MỌI impl (in-mem + SHM tương lai) → đóng seam K-038 (mục tiêu chính). Vì
  consumers CHỈ dùng `.array` (grep verify) nên "mất autocomplete" không ảnh hưởng thực tế. Additive, 100%
  backward-compat, không phá 364 test.
- Vì sao chấp nhận: "type chặt vào 1 impl" chính là nguyên nhân gãy — giữ nó = giữ bug kiến trúc. Đây là
  đánh đổi ĐÚNG HƯỚNG (mở rộng có kiểm soát qua port), không phải nới lỏng bừa.


### T-009 — 2026-07-06 — ISink là PORT (Protocol)  vs  callback function
Status: 🔵 (design PHA 1, chờ code)
Scope: sub-spec pipeline-runner · `kernel/ports/sink.py`
Nguồn: design.md pipeline-runner QĐ-1 · K-037 Gap-1
Links: D-039
Chọn: **ISink Protocol port** (handle + setup + teardown).
- Cái mất: thêm 1 file + 1 khái niệm so với truyền callback `on_result`.
- Đổi lại: nhất quán kiến trúc (mọi ranh giới là port); sink mang được LIFECYCLE (mở/đóng DB/file/socket) mà
  callback trần không mang; là điểm mở tự nhiên cho nghiệp vụ (IEventSink/DBSink/QueueSink) — hướng lâu dài.
- Vì sao chấp nhận: base thương mại cần ranh giới rõ để "đẻ nghiệp vụ" dễ; callback là tối ưu cục bộ ngắn hạn.

### T-010 — 2026-07-06 — Runner nhận SyncLinearExecutor concrete  vs  tạo IExecutor port
Status: 🔵 (design PHA 1, chờ code)
Scope: sub-spec pipeline-runner · `runtime/pipeline_runner.py`
Nguồn: design.md pipeline-runner QĐ-3
Links: D-039, K-037 Gap-3 (chỉ 1 executor)
Chọn: **concrete SyncLinearExecutor** (chưa trừu tượng IExecutor).
- Cái mất: runner buộc kiểu concrete → sau có executor async phải nới type.
- Đổi lại: KHÔNG over-engineer — chỉ 1 executor tồn tại, chưa "biến thiên" (câu hỏi pattern: what varies?).
  Trừu tượng bây giờ là premature abstraction. Đổi sau rẻ (nới type hint, y như đã làm với media_ref D-038).
- Vì sao chấp nhận: bám nguyên tắc user "fix bản chất, đừng thừa"; trừu tượng đúng LÚC nó thực sự biến thiên.


### T-011 — 2026-07-06 — Vertical slice TRƯỚC  vs  Xây scale-out hạ tầng trước
Status: 🔵 (ghi trong design scale-architecture, chờ user valid lộ trình)
Scope: spec scale-architecture · lộ trình
Nguồn: design.md scale-architecture §Roadmap · nguyên tắc user (tránh over-engineer + giá trị thật)
Links: D-040, C-014
Chọn: **vertical slice (1 cam → detect → analytics → sink/optional-store) TRƯỚC**, rồi mới scale-out (batch/
scheduler/config/metrics).
- Cái mất: chưa có throughput 100 cam ngay; phải làm lại 1 phần khi scale (nhưng ports/Stage giữ).
- Đổi lại: chứng minh LUỒNG NGHIỆP VỤ thật chạy (sink/event/storage đang trống) → tránh xây hạ tầng scale rỗng
  cho nghiệp vụ chưa tồn tại (chính là over-engineer user cảnh báo). Có slice thật → benchmark + scale có căn cứ.
- Vì sao chấp nhận: giá trị thương mại đến từ nghiệp vụ chạy được, không từ hạ tầng scale trừu tượng. Scale-out
  là nhân bản slice đã đúng — làm sau, rẻ hơn làm trước rồi phát hiện slice sai.

### T-012 — 2026-07-06 — Để-NGỎ công nghệ (transport/config/metrics/Triton)  vs  chốt ngay trong design
Status: 🔵 (design scale-architecture)
Scope: spec scale-architecture · Open Decisions
Nguồn: design.md §Open Decisions
Links: D-040, K-040
Chọn: **để-ngỏ + nêu tiêu chí**, chốt ở sub-spec khi tới.
- Cái mất: design chưa "đóng" hoàn toàn; còn nhánh mở.
- Đổi lại: chốt sớm khi chưa có số benchmark + chưa tới bước = đoán liều (vi phạm "không suy đoán"). Tiêu chí rõ
  (độ trễ/durability/ops/license) đủ để quyết đúng LÚC cần.
- Vì sao chấp nhận: giữ tính đúng-đắn-có-thể-kiểm-chứng; tránh khoá công nghệ sai từ đầu.


### T-013 — 2026-07-06 — `tomllib` (stdlib)  vs  thư viện config ngoài (PyYAML / pydantic / tomlkit)
Status: ✅ (đã code + verify phiên trước — 25 test config pass, không thêm dep nào; LOG #221–#223)
Scope: sub-spec config-declarative · `application/config_loader.py`
Nguồn: LOG Entry #219, #222 · design.md config-declarative · pyproject.toml (KHÔNG thêm dependency)
Links: D-042, K-040 (C2)
Chọn: **`tomllib` (stdlib, có sẵn từ Python 3.11)** để đọc file cấu hình `.toml`.
- Cái mất: (a) chỉ đọc TOML, KHÔNG YAML/JSON (một số ops quen YAML hơn); (b) `tomllib` chỉ **đọc** (không ghi — nếu sau cần sinh file config phải thêm `tomli-w`/`tomlkit`); (c) KHÔNG có validation-schema giàu như `pydantic` (phải TỰ viết `parse_app_config` validate cấu trúc tay); (d) **buộc Python ≥ 3.11** (tomllib mới vào stdlib từ 3.11 — [đã kiểm: tài liệu chính thống Python `tomllib`, độ chắc cao]).
- Đổi lại: **ZERO dependency mới** → base install lean, không tăng bề mặt bảo mật/typosquat, không lệ thuộc version bên ngoài; validate tay lại KIỂM SOÁT được thông điệp lỗi fail-fast (ConfigError kèm pipeline id) tốt cho ops.
- Vì sao chấp nhận (bản chất): repo đã có kỷ luật "core lean, dep optional" (C-012 onnx optional). Thêm pydantic/PyYAML vào core cho việc mà stdlib làm được = phình dep không cần thiết. Schema dự án còn nhỏ + đã frozen-dataclass ở kernel → validate tay đủ. Khi schema phức tạp lên (nhiều biến thể) mới cân nhắc pydantic — chốt LÚC nó thực sự cần (đúng nguyên tắc "không over-engineer").

### T-014 — 2026-07-06 — `validate_config` KHÔNG dựng object (chỉ kiểm type∈registry)  vs  dựng-thật để validate
Status: ✅ (đã code + verify phiên trước — 8 test config_validate pass; LOG #226)
Scope: sub-spec config-declarative · `profiles/pipeline_factory.py::validate_config` + `--validate`
Nguồn: LOG Entry #226 · đóng lỗ review #1 (doubt-driven)
Links: D-043, K-041 (capacity), K-047 (không verify được trên máy no-GPU)
Chọn: **validate TĨNH — chỉ kiểm `type`∈registry + ràng buộc cấu trúc (detect-phải-có-detector), KHÔNG gọi builder / KHÔNG dựng detector/source thật.**
- Cái mất: KHÔNG bắt được lỗi RUNTIME của builder — vd file weights `.pt` không tồn tại, RTSP URL sai, GPU hết VRAM, cv2 mở video fail. `--validate` PASS không đảm bảo `--config` chạy được trên máy GPU.
- Đổi lại: `--validate` chạy được **NGAY trên máy dev no-GPU/no-torch** (không import torch/cv2 vì lazy-import chỉ xảy ra trong builder, mà validate không gọi builder) → bắt sớm lỗi cấu hình rẻ tiền (sai tên type/thiếu detector) trước khi tốn công mang lên máy GPU.
- Vì sao chấp nhận (bản chất): đúng nguyên tắc user "valid thiết kế trước khi triển khai" ở tầng KHẢ THI — validate cái kiểm được ở môi trường hiện tại, KHÔNG giả vờ kiểm cái cần GPU. Ranh giới trung thực: validate cấu trúc ≠ nghiệm thu end-to-end (cái sau vẫn phải chạy máy GPU — D-043 ghi rõ 🔴). Muốn validate sâu hơn (file tồn tại, URL reachable) là lớp kiểm riêng, thêm khi cần.

### T-015 — 2026-07-06 — Đa-pipeline chạy TUẦN TỰ (v1)  vs  song song (đa tiến trình / GPU-budget)
Status: ✅ (v1 tuần tự đã code; song song HOÃN sang scale-architecture) — LOG #224
Scope: sub-spec config-declarative · `vision_slice_app._run_from_config`
Nguồn: LOG Entry #224 · roadmap scale-architecture (D-040)
Links: D-043, D-040, C-014 (~100 cam), K-041 (capacity), K-045 (bulkhead)
Chọn: **v1 chạy các pipeline trong config TUẦN TỰ (sync, 1 vòng lặp)**, chưa song song.
- Cái mất: KHÔNG đạt throughput nhiều-camera-đồng-thời (chạy pipeline A xong mới tới B) → chưa dùng được cho ~100 cam thực; 1 pipeline treo sẽ chặn phần còn lại (liên quan K-045 bulkhead).
- Đổi lại: đơn giản + đúng + ADDITIVE (không đụng base, test cũ xanh); chứng minh chuỗi config→build→run ĐÚNG trước, để dành phần khó (song song đa tiến trình + ngân sách GPU + shed) cho `scale-architecture` — nơi có capacity model + benchmark làm căn cứ (K-041), không đoán liều.
- Vì sao chấp nhận (bản chất): song song 100 cam là bài toán PHÂN BỔ TÀI NGUYÊN (GPU budget/scheduler/shed) — làm ĐÚNG cần số benchmark 1-node TRƯỚC (T-011). Nhét song song vào v1 giờ = xây hạ tầng scale khi chưa có căn cứ = over-engineer + có thể sai. Tuần tự trước = nền đúng để nhân bản sau.


### T-016 — 2026-07-06 — Bulkhead bắt `except Exception` (rộng)  vs  bắt loại lỗi cụ thể (hẹp)
Status: ✅ (đã code + verify — full 423/1, 2 test bulkhead pass; LOG #229)
Scope: `profiles/vision_slice_app.py::_run_from_config` · K-045 bulkhead
Nguồn: LOG Entry #229 · D-044 · K-045
Links: D-044, C-016, K-045
Chọn: **`except Exception`** (bắt rộng) quanh mỗi pipeline — KHÔNG bắt `BaseException`.
- Cái mất: bắt rộng có thể che BUG lập trình (typo biến, AttributeError...) thành "pipeline lỗi" thay vì phơi ra ngay → khó phát hiện lỗi code trong lúc dev.
- Giảm thiểu: in `type(e).__name__: <message>` ra stderr cho MỖI lỗi (không nuốt im lặng) → vẫn thấy để debug; + return code 1 (C-016) báo có sự cố. Test đơn vị đã phủ nhánh lỗi.
- Vì sao chấp nhận (bản chất): mục tiêu bulkhead cho hệ nhiều-camera 24/7 = **1 camera KHÔNG được giết cả hệ**. Kiểu lỗi runtime của 1 camera cực đa dạng (CUDA/cv2/ffmpeg/disk/network/config) — liệt kê hẹp sẽ SÓT loại chưa lường → vách ngăn thủng. Bắt rộng ở đúng RANH GIỚI khoang là pattern bulkhead chuẩn (giống K-024 InferenceServer per-request, K-036 detect-thread). Chừa `BaseException` để KeyboardInterrupt/SystemExit vẫn dừng được toàn hệ (không nuốt tín hiệu dừng) — đây là ranh giới tinh tế nhưng quan trọng.


### T-017 — 2026-07-06 — Key lạ: `ConfigError` fail-fast (siết)  vs  cảnh báo log rồi chạy tiếp (lỏng); + builder chưa khai báo → lenient
Status: ✅ (đã code + verify — full 427/1, 4 test K-046 pass; LOG #230)
Scope: `profiles/pipeline_factory.py::_check_params` · K-046 strict-key
Nguồn: LOG Entry #230 · D-045 · K-046
Links: D-045, C-017, K-046
Chọn: **fail-fast `ConfigError`** khi key params lạ (KHÔNG chỉ warning); **builder chưa khai báo `allowed_params` → BỎ QUA (lenient)**.
- Cái mất (fail-fast): 1 typo làm config KHÔNG chạy được (thay vì chạy với default + cảnh báo). Khắt khe hơn — user phải sửa mới chạy.
- Cái mất (lenient cho builder chưa khai báo): builder tùy biến bên thứ 3 (registry ngoài) không được bảo vệ typo cho tới khi khai báo `allowed_params`.
- Đổi lại: (a) fail-fast bắt sai-cấu-hình SỚM (dev/CI) thay vì phát hiện muộn khi 1 camera "trông như config đúng" mà chạy sai âm thầm — an toàn hơn nhiều cho 24/7; đồng bộ với fail-fast toàn bộ config_loader (nhất quán, không nửa vời). (b) lenient cho builder chưa khai báo = không siết cái mình KHÔNG biết (tránh vỡ mở rộng bên thứ 3) — 9 builder mặc định đã khai báo đủ nên đường chính vẫn nghiêm.
- Vì sao chấp nhận (bản chất): với sản phẩm thương mại, "sai config báo NGAY" > "chạy với giá trị sai âm thầm". Cảnh báo-log dễ bị bỏ qua trong biển log 24/7 → không đủ răng. Fail-fast + thông điệp liệt kê key hợp lệ = vừa an toàn vừa chỉ đúng chỗ sửa.


### T-018 — 2026-07-07 — Mô hình A (bound TRƯỚC khi gửi, 2 van)  vs  Mô hình B (bound in-flight ĐÃ gửi, đúng câu chữ R2.2 cũ)
Status: ✅ (chốt A bằng bằng chứng đọc code; chưa code → hành vi runtime [chưa kiểm])
Scope: spec backpressure-cross-process · cơ chế backpressure cốt lõi
Nguồn: LOG Entry #238 · đọc THẬT `inference_server.py` (ROUTER single-thread) + `zmq_inference_client.py` (`_outbound` không giới hạn, `_io_loop` gửi hết ngay)
Links: D-048, C-018, K-040 (A2)
Chọn: **Mô hình A — bound TRƯỚC khi gửi** (hàng đợi outbound giới hạn + flow-control in-flight).
- Cái mất: phức tạp hơn — thêm 1 knob `queue_maxsize` + logic flow-control trong `_io_loop` (Mô hình B chỉ cần giới hạn dict `_pending`, đơn giản hơn và đúng câu chữ R2.2 gốc).
- Đổi lại: Mô hình A GIẢM TẢI SERVER THẬT — frame bị bỏ chưa từng gửi qua ZMQ nên server không tốn inference. Mô hình B chỉ bỏ tracking slot; request đã tới server (ROUTER single-thread KHÔNG hủy được) → server VẪN chạy inference trên frame lẽ ra bị bỏ → không giảm tải, không đóng gốc A2 (mất frame im lặng ở RCVHWM tràn).
- Vì sao chấp nhận (bản chất): Mô hình B thỏa mãn câu chữ nhưng PHẢN mục tiêu ("chủ động bỏ frame để giảm tải" + "camera không bị chặn") — đó chính là "fix ngọn" mà user cấm. Chọn A = fix đúng gốc dù tốn thêm một chút phức tạp.

### T-019 — 2026-07-07 — Tái dùng `kernel/backpressure.py::BoundedQueue` (đã có)  vs  viết cấu trúc hàng đợi outbound mới
Status: ✅ (quyết định thiết kế; chưa code → [chưa kiểm] runtime)
Scope: spec backpressure-cross-process · van outbound của client
Nguồn: LOG Entry #238 · `kernel/backpressure.py` (4 policy DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT + đếm drops/rejects) · K-016 (thread-safe, không process-safe)
Links: D-048, K-016
Chọn: **tái dùng `BoundedQueue` sẵn có** làm hàng đợi outbound trong client.
- Cái mất: `BoundedQueue` THREAD-safe (threading.Lock) chứ KHÔNG process-safe (K-016) → chỉ đúng khi dùng TRONG 1 process.
- Đổi lại: client ZMQ là 1 process với thread capture ⊥ thread io (chia sẻ bộ nhớ trong process) → ràng buộc "chỉ trong 1 process" của K-016 được thỏa → tái dùng hợp lệ + đã có sẵn 4 policy + đếm drops/rejects (khớp thẳng metric cần) → không phát minh lại, không thêm bề mặt lỗi.
- Vì sao chấp nhận (bản chất): backpressure ở đây là điều tiết GIỮA HAI THREAD trong client trước khi gửi, KHÔNG phải cross-process (khác ngữ cảnh K-016 cảnh báo). Đúng công cụ cho đúng ngữ cảnh — tái dùng cái verified thay vì viết mới.


### T-020 — 2026-07-08 — SHM-ring-đầy tính là DROP (gộp vào `frames_dropped_backpressure` + counter riêng)  vs  `frames_captured` chỉ đếm frame ghi-SHM-thành-công
Status: ✅ (chọn A — bất biến 2-tầng đã ASSERT cross-process ở Wave 4, D-051)
Scope: `camera_worker` hạch toán · spec backpressure-cross-process Wave 3.1
Nguồn: LOG Entry #244 · design §4.5 · R4.1
Links: D-049, C-019, K-053
Chọn: **coi SHM-ring-đầy là một dạng backpressure drop** — `frames_captured` đếm mọi `has_data` (R4.1 nguyên văn); `write()→None` → `frames_dropped_shm += 1`; artifact `frames_dropped_backpressure = client_window_drops + frames_dropped_shm`; thêm counter quan sát `frames_dropped_shm`.
- Cái mất: `frames_dropped_backpressure` gộp 2 tầng (SHM ⊥ client-window) → cần counter phụ `frames_dropped_shm` để tách khi phân tích; `metrics_snapshot()` (chỉ biết client-window) KHÔNG phải nguồn duy nhất cho số dropped ghi ra artifact (camera_worker phải cộng thêm).
- Phương án B (bác): `frames_captured` = chỉ frame ghi-SHM-thành-công (có ref) → bất biến đúng tự nhiên, `metrics_snapshot` đủ. Nhưng VI PHẠM R4.1 (captured phải là "nhận từ source") + GIẤU số frame mất ở tầng SHM (đúng lỗ A2) → không minh bạch cho hệ 24/7.
- Vì sao chấp nhận A (bản chất): mục tiêu tối thượng của spec = KHÔNG mất frame im lặng. Frame bị bỏ vì SHM đầy cũng là mất-vì-quá-tải → phải đếm + phơi ra. Gộp vào dropped giữ bất biến; counter riêng giữ minh bạch. Đây là "nhìn bản chất" (mọi mất-mát do backpressure đều phải kế toán), không phải "fix ngọn" (lơ nhánh khó).


### T-021 — 2026-07-08 — R3 (cấm BLOCK+RTSP): hàm guard THUẦN sẵn-sàng-wire  vs  bơm field `policy` vào schema TOML + parse + wire ngay
Status: ✅ (chọn guard thuần — verify 8 test + full 464/1 + lint 5/0)
Scope: spec backpressure-cross-process Wave 3.2 · `config_loader.assert_policy_allowed_for_source`
Nguồn: LOG Entry #245 · đọc `kernel/config.py` + `pipeline_factory` (không đường nào gắn policy vào RTSP)
Links: D-050, C-018, K-053, T-015
Chọn: **hàm guard THUẦN** `assert_policy_allowed_for_source(source_type, policy)` + test — KHÔNG thêm field `policy` vào `SourceConfig`/schema TOML lúc này.
- Cái mất: R3 chưa được gọi trong 1 đường config THẬT (vì config chưa mang policy per-source) → là guard "sẵn-sàng-wire", chưa chặn ở runtime end-to-end. Khi config có policy phải nhớ gọi guard tại nơi map config→client.
- Phương án B (bác): thêm `policy` vào SourceConfig + parse TOML + validate + wire vào ZmqInferenceClient. Đầy đủ hơn NHƯNG: (a) config-declarative path hiện dựng PipelineRunner in-process, KHÔNG dùng ZMQ client → field policy không có nơi tiêu thụ; (b) = xây hạ tầng cho khả năng chưa tồn tại = over-engineer (trái nguyên tắc user + T-015 "làm khi thực sự cần").
- Vì sao chấp nhận A (bản chất): R3 về BẢN CHẤT = "ngăn tổ hợp rtsp+BLOCK nguy hiểm (TCP Zero Window)". Guard thuần + test nắm trọn bản chất đó, kiểm chứng được (P7), zero-schema-bloat. Bơm schema khi chưa ai tiêu thụ = fix phần ngọn (hình thức "có field") thay vì phần gốc (logic cấm). Wire đầy đủ để dành khi config-declarative thực sự tích hợp ZMQ client (spec sau).


### T-022 — 2026-07-09 — Hook interpreter: LAUNCHER capability-test  vs  swap `python`→`py`  vs  chỉ-venv-path
Status: ✅ (chọn launcher — verify EXIT 0, cross-machine robust)
Scope: `tests/drift_check.cmd` (điểm vào hook drift-check)
Nguồn: LOG Entry #254 · bằng chứng 2 máy interpreter khác nhau
Links: D-056, K-057, K-055
Chọn: **launcher `.cmd` capability-test 3 tầng** (`py -3` → venv → `python`).
- Cái mất: thêm 1 file `.cmd` (~30 dòng) + Windows-only (Linux cần `.sh` sau); phức tạp hơn 1 dòng lệnh.
- Phương án B (bác) — swap `python`→`py`: 1 dòng, nhưng VỠ trên máy scoop (thường thiếu `py` launcher) → chỉ dời lỗi = fix NGỌN.
- Phương án C (bác) — chỉ dùng venv python path: đúng khi venv dựng, nhưng VỠ khi fresh-clone chưa dựng venv → dùng làm fallback #2, không phải duy nhất.
- Vì sao chấp nhận A (bản chất): đã QUAN SÁT 2 setup thật không tương thích (k.nguyen cần `py`, toann cần `python`) → không tên đơn nào đúng cả hai. Launcher capability-test là mức TỐI THIỂU chạy đúng trên cả hai + mọi máy khác, kiểm chứng được (EXIT 0). Không over-engineer: đúng tầm vấn đề thực đã thấy.


### T-023 — 2026-07-09 — Dev-env: dispatcher `.cmd` tự-viết  vs  Makefile/just/nox  vs  giữ lệnh tay
Status: ✅ (chọn .cmd thuần — verify env/setup/verify EXIT 0)
Scope: `scripts/vp.cmd`
Nguồn: LOG Entry #256 · yêu cầu cross-machine
Links: D-057, D-056, K-058
Chọn: **dispatcher `.cmd` thuần** (auto-detect + env-var override).
- Cái mất: Windows-only (Linux cần `vp.sh` sau — YAGNI); ~90 dòng batch phải bảo trì.
- Phương án B (bác) — Makefile/just/nox: mạnh + cross-OS, NHƯNG thêm dependency (make/just/nox chưa chắc có trên máy sạch Windows) → mâu thuẫn chính mục tiêu "chạy ngay mọi máy không cần cài thêm". `.cmd` chạy trên mọi Windows sạch.
- Phương án C (bác) — giữ lệnh tay + ghi doc: zero-code nhưng KHÔNG xóa ma sát (vẫn gõ tay, vẫn sai interpreter/extras mỗi máy) = fix ngọn (doc) không phải gốc (tự động hóa).
- Vì sao chấp nhận A (bản chất): mục tiêu = "đổi máy chạy được NGAY, không cài thêm gì". `.cmd` thuần thỏa trọn (Windows có sẵn cmd) + tái dùng pattern capability-test đã verify. Cross-OS là mở rộng, không phải yêu cầu hiện tại.


### T-024 — 2026-07-09 — CI runner: windows-latest  vs  ubuntu-latest
Status: ✅ (chọn windows-latest — chờ verify CI run)
Scope: `.github/workflows/verify.yml`
Nguồn: LOG Entry #257 · D-058
Links: D-058, K-059
Chọn: **windows-latest**.
- Cái mất: Actions-minutes đắt hơn ubuntu (~2×); khởi động runner chậm hơn.
- Phương án B (bác) — ubuntu-latest: rẻ + nhanh, NHƯNG baseline 465/1 gồm test cross-process guard `sys.platform=='win32'` → trên ubuntu chúng SKIP → cổng CI KHÔNG phủ đúng phần đã dev/verify trên Windows = cổng yếu hơn thực tế.
- Vì sao chấp nhận A (bản chất): mục tiêu CI = chặn regression ĐÚNG cái baseline đang bảo vệ (465/1 gồm win32). Chạy môi trường khác baseline = tự lừa mình (xanh CI nhưng bỏ sót path). Parity > tiết kiệm minutes. Nếu ngân sách minutes ép buộc → ubuntu + ghi rõ "win32 tests skip" (chưa cần).

### T-025 — 2026-07-09 — Metric bền-illumination: mean-subtraction (numpy@domain) vs background-model MOG2 (cv2@adapters)
Status: ✅ chốt cho v1 (design)
Nguồn: LOG Entry #270 · D-066
Links: D-066, K-063
Chọn: **mean-subtraction (numpy thuần, ở `domain`)** cho v1.
- Cái mất: chỉ triệt đổi-sáng ĐỀU (uniform-shift); KHÔNG xử-lý đổi-sáng-KHÔNG-đều (mây loang, đèn quét), bóng-đổ, camera rung. Ghi rõ R2.5 + Non-Goal (không over-claim).
- Phương án B (bác cho v1) — MOG2/KNN background-subtraction (cv2): mô hình nền thích nghi mạnh hơn (xử được đổi-sáng dần + đa-modal), NHƯNG cần `cv2` → thuộc `adapters` (KHÔNG được vào `domain` theo luật 6-layer) + nặng hơn + khó test xác định no-GPU.
- Vì sao chấp nhận A (bản chất): đổi-sáng-đều là NGUYÊN NHÂN GỐC của K-063 và mean-subtraction TRIỆT nó CHỨNG-MINH-ĐƯỢC bằng đại số (`curr=prev+c` → mean-sub → d=0), test numpy xác định no-GPU, giữ domain sạch (numpy). MOG2 mạnh hơn nhưng là bài toán KHÁC (đổi-sáng-không-đều) → tách sub-spec cv2/adapters khi thật cần (YAGNI, không kéo cv2 vào domain sớm). Trừu tượng đúng chỗ = tham số metric (raw vs mean-sub), không phải class-hierarchy.

### T-026 — 2026-07-10 — Phơi metrics: hand-roll renderer (zero-dep) vs `prometheus_client` (chuẩn, +dep)
Bối cảnh: spec `metrics-exposition` (D-071) — cần biến `InMemoryMetrics` → Prometheus text exposition 0.0.4.
- **Phương án A (CHỌN) — hand-roll `render_prometheus(samples)` @adapters:** dữ liệu ĐÃ có trong InMemoryMetrics → chỉ cần format (nhỏ, THUẦN, xác định, test byte-khớp được no-GPU); giữ đường-ghi hiện tại (`MetricsObserver`→`InMemoryMetrics`) nguyên vẹn — renderer là NGƯỜI-ĐỌC; zero-dep (nhất quán triết lý dự án).
- **Phương án B (bác cho v1) — `prometheus_client`:** chuẩn, robust (multiprocess mode, bucket histogram, escaping sẵn) NHƯNG có REGISTRY RIÊNG → dùng nó nghĩa là BỎ `InMemoryMetrics` hoặc bắc-cầu (phức tạp + parse lại) + thêm dependency; tính năng mạnh (multiprocess/bucket) v1 CHƯA cần.
- **Vì sao A (bản chất):** format 0.0.4 nhỏ + ổn định nhiều năm → tự bảo trì rủi ro thấp; A giữ 1 nguồn-sự-thật metrics (InMemoryMetrics) + layer sạch (renderer thuần @adapters nhận DTO thuần). Cái mất: nếu chuẩn đổi phải tự cập nhật (hiếm); histogram bucket phải tự thiết kế sau (Non-Goal v1). Đổi lấy: zero-dep + kiểm-soát-format + verify byte-khớp.
- Kèm quyết định con: lấy dữ liệu qua accessor CÓ-CẤU-TRÚC `iter_metrics()` (fix gốc) thay vì parse-ngược chuỗi key `name{k=v}` (lossy) — xem D-071.
