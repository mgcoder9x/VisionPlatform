# 02 — Chỗ AI phải ĐỔI so với yêu cầu / thiết kế ban đầu

> Định dạng + quy tắc: xem `README.md` §1. Ghi rõ **TỪ gì → SANG gì** + lý do bản chất.
> Trạng thái: ✅ verify · 🟡 chưa kiểm đủ · 🔴 rủi ro mở · ↩️ đã đảo.

---

### C-001 — 2026-07-02 — Q1 (cách bên đọc tìm ring mới): publish-epoch-rồi-suy-tên → segment tên-cố-định
Status: ✅
Scope: shm-ring-epoch-switchover / design.md
Nguồn: LOG Entry #119 · docstring `new_ring_name` L106-108
Evidence: design.md 0 diagnostic (getDiagnostics, LOG #119); Task 1.1/1.2 verify sau đó (D-001)
Links: D-001
Đổi: TỪ "publish epoch qua ctrl segment rồi suy ra tên ring" → SANG "control-plane segment tên cố định chứa {epoch, ring_name}".
Vì sao: phát hiện khi đọc code thật — `new_ring_name()` sinh tên bằng `uuid4().hex` (ngẫu nhiên) nên KHÔNG thể suy tên từ epoch. Thiết kế đầu sai ở gốc giả định; sửa trước khi code (design-first).

### C-002 — 2026-07-02 — Task 2 ref-count: phương án (A) lock-protected attach_count → (B) OS handle ref-count  ↩️→ fix gốc
Status: ✅
Scope: shm-ring-epoch-switchover / Task 2 (+ design/requirements/tasks đồng bộ)
Nguồn: LOG Entry #123 (A, ban đầu) → Entry #126 (đảo sang B) · thực nghiệm `_shm_lifecycle_probe` Windows
Evidence: full 198 passed/1 skipped; lint 5/0; 3 spec vẫn 0 diagnostic (LOG #126)
Links: D-004, T-002, K-003
Đổi: TỪ "attach_count là RMW u32 DƯỚI `cp_lock` (mp.Lock)" → SANG "bỏ hẳn attach_count/cp_lock; teardown = close-on-migrate + OS giải phóng ở handle cuối".
Vì sao: đây là ĐẢO QUYẾT ĐỊNH (Entry #123 → #126). Khi thiết kế Task 4.2 phát hiện attach_count toàn cục không tách được handle ring cũ + mâu thuẫn nội bộ spec. Thực nghiệm chứng minh OS đã tự làm ref-count → phương án A thừa. Chọn B = xoá nguyên nhân. (Người dùng đã chốt B.)

### C-003 — 2026-06-24 — Kích thước control/ctrl segment nới rộng theo nhu cầu registry
Status: ✅
Scope: shm-production-hardening / Task 2.2, Task 7
Nguồn: LOG Entry #103/#104 (meta 32B→256B slot header), Entry #110 (ctrl 16B→64B)
Evidence: full 133 → 168 passed/1 skipped; lint 5/0; grep HEADER_FMT=0 (LOG #104, #110)
Links: D-006
Đổi: slot header meta 32B → **256B** (chứa owner/lease/reader-registry); ring ctrl segment 16B → **64B** (writer registry + chừa chỗ ring_epoch). Self-describing [:16] GIỮ NGUYÊN.
Vì sao: cần chỗ cho identity/lease/registry để làm recovery + single-writer; giữ 16B đầu để attach cũ không vỡ (fail-fast vẫn đọc đúng magic/version).

### C-004 — 2026-06-24 — Lock acquire timeout 2.0s → 0.1s (tách khỏi lease)
Status: ✅
Scope: shm-production-hardening / Task 4.2
Nguồn: LOG Entry #106 · `LOCK_ACQUIRE_TIMEOUT_S=0.1`
Evidence: full 148 passed/1 skipped; lint 5/0; 16 test #05 không ảnh hưởng (lock uncontended → acquire tức thì) (LOG #106)
Links: D-005
Đổi: TỪ `_LOCK_TIMEOUT_S = 2.0` → tách hằng `LOCK_ACQUIRE_TIMEOUT_S = 0.1` cho đường recovery.
Vì sao: recovery cần phát hiện lock "chết" nhanh để quarantine; 2s quá lâu. Tách hằng riêng, không đụng lease 2s.

### C-005 — 2026-06-24 — 3 test Task 4 phải chỉnh do đổi semantics READING/READY/DONE (không phải bug)
Status: ✅
Scope: shm-production-hardening / Task 5 (multi-reader)
Nguồn: LOG Entry #108
Evidence: regression 36 passed sau sửa + 6 test multi-reader; full 156 passed/1 skipped; lint 5/0 (LOG #108)
Links: T-005
Đổi: READY vào nhánh owner (như WRITING); DONE clear owner/lease; READING recovery dùng reader registry thay vì owner đơn.
Vì sao: chuyển từ single-reader sang multi-reader registry (P-3) làm đổi ngữ nghĩa trạng thái — test cũ phản ánh ngữ nghĩa cũ nên phải cập nhật; đã xác nhận là đổi-đúng, không phải che lỗi.

### C-006 — 2026-07-03 — Chốt H2: switchover đổi "tạo ring mới" → "tái dùng pool ring" (đảo một phần D-002/D-010)
Status: 🟡 (hướng đã chốt + cơ chế nền xong; supervisor/pool variant CHƯA làm)
Scope: shm-ring-epoch-switchover / K-012, Task 6
Nguồn: LOG Entry #132-134 · `K-012-lock-provisioning-analysis.md` §6 · D-011
Links: D-002, D-010, D-011, K-012
Đổi: TỪ mô hình "switchover tạo ring tên mới (uuid) + teardown ring cũ (D-002/D-010, close-on-migrate)" → SANG "pool K ring cố định, switchover = chọn pool[N%K] + `reset_for_reuse(N)` + publish; supervisor GIỮ pool suốt phiên; teardown = shutdown-only".
Vì sao (bản chất): mp.Lock không mở theo tên → không cấp lock cho ring sinh runtime (K-012). Né bằng pool cấp sẵn (lock thừa kế 1 lần). Hệ quả: đảo D-002 (không tạo tên mới) + D-010 (không close-per-migrate). Mặt lợi: moot K-003 (teardown Linux giữa vận hành).
Tiến độ: ✅ `reset_for_reuse` (D-011) · ✅ `RingPool` (D-012) · ✅ RingSupervisor H2 + đảo D-002/D-010 (D-013). CHƯA làm: (3) coordinator dùng make_pool_opener (test in-proc tích hợp) · (4) T-B spawn cross-process THẬT + đo Q2.


### C-007 — 2026-07-04 — #06: InlineInferenceClient adapters→application + InferenceRequest nhúng ShmFrameRefData (vs Design step-06)
Status: ✅ (verify — 9 test #06 pass, lint 5/0; Design ghi ERRATA E-06-1/E-06-2)
Scope: implement/06-inference-inline / Design step-06
Nguồn: LOG Entry #157 · `pyproject.toml` contract #4/#5 · `shm_frame_ring.py` `read_ref` · `implement/06-inference-inline/00-brief.md`
Links: D-023, D-007
Đổi:
- TỪ (Design) `adapters/inline_inference_client.py` → SANG `application/inline_inference_client.py`. Vì contract #5 CẤM adapters import runtime; client bắt buộc import `runtime.ipc.ShmFrameReader`. Bản chất: client là service điều phối, không phải leaf-adapter.
- TỪ (Design) `InferenceRequest` chỉ có `shm_generation` → SANG mang đủ field `ShmFrameRefData` gồm `ring_epoch`; client dùng `reader.read_ref(ref)` (stale-check P0-3).
Vì sao: khớp kiến trúc import-linter thật + tích hợp đúng invariant ring_epoch của switchover #05 (Design step-06 viết TRƯỚC khi có epoch). Ghi nhận thêm: #06 scope = INLINE (không phải "ZMQ inference service" như nhãn tracker); ZMQ cross-process = production hoãn.


### C-008 — 2026-07-04 — #08: thêm dependency `structlog>=24.1` vào [project] dependencies
Status: ✅ (verify — cài structlog 26.1.0, 12 test #08 pass, lint 5/0)
Scope: implement/08-observability / pyproject.toml
Nguồn: LOG Entry #162 · D-025 · `pyproject.toml`
Links: D-025, K-018
Đổi: TỪ `[project] dependencies = [numpy, psutil]` → THÊM `structlog>=24.1`.
Vì sao: `runtime/observability.py` là code production (không phải test) dùng structlog → phải là dependency chính, KHÔNG phải [dev]. Version `>=24.1` theo convention repo (numpy>=/psutil>= đều range). `include_external_packages=true` → phải cài thật trước lint/test (đã cài → 26.1.0). structlog = thư viện logging cấu trúc nổi tiếng, actively maintained (không typosquat).


### C-009 — 2026-07-04 — #10: README/DoD dùng số test THẬT (290/1) thay blueprint Design (110)
Status: ✅ (verify — pytest 290 passed/1 skipped chạy thật)
Scope: implement/10-package-ship / Design step-10
Nguồn: LOG Entry #166 · D-027 · `vision-platform/README.md`
Links: D-027
Đổi: TỪ (Design blueprint) "110 passed, 1 skipped" + per-step breakdown của vision_demo → SANG số THẬT **290 passed, 1 skipped** của vision_platform.
Vì sao: dự án thật đã tiến hoá vượt vision_demo MVP (thêm production-hardening #05: lease/quarantine/multi-reader/single-writer/recovery; switchover sub-spec #05b: control-plane/pool/coordinator/T-B/PBT; #06 inference; #07 backpressure; #08 observability; #09 supervisor). Copy 110 = bịa. README + DoD phải phản ánh bằng chứng chạy thật, ghi rõ "khác blueprint vì production-hardening".


### C-010 — 2026-07-04 — zmq-inference: correlation THREADING (socket-owner-thread) thay asyncio.Future (step-06)
Status: ✅ (verify — 10 test zmq pass, gồm cross-process spawn)
Scope: .kiro/specs/zmq-inference-service / `adapters/zmq_inference_client.py`
Nguồn: LOG Entry #170/#171 · D-028 · design QĐ-1
Links: D-028
Đổi: TỪ (step-06 intent) "client-side correlation map request_id → **asyncio.Future** + async receive task" → SANG **threading**: DEALER + 1 **socket-owner-thread** (send+recv) + map `{request_id: queue.Queue(1)}`; `infer()` SYNC blocking + timeout.
Vì sao (bản chất): (1) repo KHÔNG có asyncio (BoundedQueue #07=threading, supervisor #09=multiprocessing) → threading nhất quán + verify được. (2) ZMQ socket KHÔNG thread-safe → BẮT BUỘC socket-owner-thread (caller đẩy queue, KHÔNG send-from-caller) — đây là refine đúng bản chất, không phải bug. `infer()` sync khớp `IInferenceClient` port + inline #06. Đổi sang asyncio sau chỉ đổi adapter, port không đổi.

### C-011 — 2026-07-04 — full-stack profile: worker-entry đặt TRONG profile module (không ở tests/)
Status: ✅ (verify — 307 passed/1 skipped, lint 5/0, full-stack test PASS)
Scope: .kiro/specs/full-stack-integration-profile / `profiles/vision_fullstack_profile.py`
Nguồn: LOG Entry #180 · D-030 · design.md (Architecture/Components)
Links: D-030
Đổi: TỪ (design PHA-1) "`camera_worker` ở `tests/fullstack_workers.py` + tái dùng `tests/zmq_server_worker.py`" → SANG **worker-entry (`camera_worker` + `inference_server_entry`) đặt NGAY trong `profiles/vision_fullstack_profile.py`** (self-contained).
Vì sao (bản chất): profiles là composition-root SHIPPABLE; module `tests/` KHÔNG ship + `src` KHÔNG được import `tests` (ranh giới đóng gói). Windows spawn re-import module chứa `target` ở process con → hàm module-level trong profile picklable + import được (khác hàm ở test-file). Vẫn tái dùng COMPONENT (InferenceServer/Supervisor/coordinator/client — R3.1), chỉ không tái dùng test-wrapper. Kết quả: profile tự chứa = nền sản phẩm thật.

### C-012 — 2026-07-04 — real-detector Phần B: thêm dep onnxruntime + onnx (optional group `.[onnx]`)
Status: ✅ (verify — cài + chạy thật onnxruntime 1.27.0/onnx 1.22.0; 4 test onnx pass; lint 5/0)
Scope: `vision-platform/pyproject.toml` [project.optional-dependencies] + import-linter forbidden
Nguồn: LOG Entry #184 · D-031 · Q3 user duyệt
Links: D-031, K-029
Đổi: thêm 2 dependency mới `onnxruntime>=1.20` (MIT) + `onnx>=1.16` (Apache-2.0) dưới nhóm OPTIONAL `onnx`
(KHÔNG vào core deps — base install gọn; chỉ deployment dùng ONNX detector mới `pip install .[onnx]`).
Vì sao: OnnxDetector chỉ là 1 lựa chọn adapter (có thể dùng torch/remote-service thay); giữ core lean +
cấm onnxruntime/onnx ở domain+kernel (import-linter, negative-test có răng) để không rò lệ thuộc lên tầng thuần.

### C-013 — 2026-07-04 — 4 quyết định SCOPE của user (định hình hướng sản phẩm)
Status: ✅ (ghi nhận directive user) · CLI "chạy lên xem" verify thật
Scope: hướng sản phẩm thương mại / roadmap
Nguồn: LOG Entry #186 · user chỉ thị trực tiếp
Links: K-029 (license YOLO), C-012 (onnx)
Nội dung (user chốt):
- (1) **Lưu trữ/ghi hình = HOÃN** — chưa làm bây giờ.
- (2) **Camera = user tự lắp phần cứng** — code vẫn cần RTSP adapter (IFrameSource) khi tới bước đó; thiết bị do user lo.
- (3) **Detector = YOLO** — user chọn. ⚠️ K-029: YOLOv8/v11 = AGPL-3.0 → sản phẩm đóng phải mua Enterprise License Ultralytics (hoặc chấp nhận AGPL). AI đã cảnh báo; đây là lựa chọn + trách nhiệm pháp lý của user.
- (4) **Bảo mật (auth/ZMQ CURVE/TLS) = TỪ TỪ** — hoãn.
Hệ quả: bước kế ưu tiên = viết postprocess YOLO-layout (khi có weight .onnx) + RTSP adapter (khi user cắm camera). CLI demo (`python -m vision_platform.profiles.vision_fullstack_profile`) đã có để chạy quan sát chuỗi (Noise+Fake tạm, swap sau).


### C-014 — 2026-07-06 — CHỐT quy mô đích: MULTI-CAMERA ~100 con (không bao giờ 1 camera)
Status: ✅ (user khẳng định rõ) — yêu cầu NỀN, ảnh hưởng toàn kiến trúc.
Nguồn: user "chắc chắn làm hướng nhiều camera, có thể hàng 100 con" · LOG #212.
Links: K-040 (sổ lỗ hổng), K-037 (gap), AGENTS.md §0 (real-time multi-camera).
Nội dung + tác động:
- Trước: mốc học/kiểm-chứng đơn máy, scale để "sau"; lỗ hổng K-040 coi là suy đoán → hoãn.
- Sau (CHỐT): đích = **~100 camera** → K-040 A1(batch)/A2(backpressure)/C2(config)/C1(metrics) từ "suy đoán"
  chuyển thành **BẮT BUỘC**. Bài toán = **PHÂN TÁN, nhiều-GPU, gần như chắc nhiều-host** (ràng buộc VẬT LÝ:
  decode ~2500fps + inference ~1000/s vượt 1 GPU tiêu dùng — [ước lượng cần benchmark]).
- Base hiện tại = "1 NODE đúng" (ports/Stage/SHM-ring/switchover/ZMQ tái dùng được) — THIẾU tầng "CỤM":
  sharding/orchestration · batched multi-GPU inference · shed policy · config khai báo · metrics tập trung · fan-out.
  → THÊM TẦNG, không đập lõi.
- Bước kế (design-first, CHỜ user chốt 4 fork): phần cứng (1-máy-nhiều-GPU vs cụm; on-prem/cloud) · fps
  inference/cam thật · nghiệp vụ đích (ALPR/face/đếm) · lưu trữ+độ trễ. → rồi viết tài liệu "capacity+kiến trúc
  cụm" (bài toán vật lý + sơ đồ shard + lộ trình validate 1→10→100). CHƯA code.


### C-015 — 2026-07-06 — Máy hiện tại (1×RTX2060) = CHỈ DEV/benchmark; đích chạy phần cứng TƯƠNG LAI (scale được)
Status: ✅ (user: "làm để sau này chứ không phải trên máy này; giới hạn thì có nhiều cách sau sẽ phù hợp").
Nguồn: user · LOG #214 · nối tiếp C-014 (đích ~100 cam).
Tác động:
- Gỡ nút thắt K-041: "2060 không kham 100 cam" KHÔNG còn là chặn thiết kế — 2060 chỉ để **đo công suất 1-node**.
- Kiến trúc PHẢI phần-cứng-bất-khả-tri: công suất/node = THAM SỐ ĐO (C_inf/C_dec/V), scale ngang = nhân node.
- "Làm max rồi giảm" hợp lệ khi hiểu là: thiết kế NGÂN SÁCH cố định + config-giảm + shed (không phải max tuyệt đối).
- → mở spec `scale-architecture` (D-040) đặt trên nguyên tắc này.


### C-016 — 2026-07-06 — `_run_from_config` đổi return code: LUÔN 0 → 0 (mọi pipeline ok) / 1 (có ≥1 lỗi)
Status: ✅ (verify — full 423/1, 3 test config cũ vẫn trả 0 vì toàn-thành-công → không phá)
Scope: `profiles/vision_slice_app.py::_run_from_config` (CLI --config)
Nguồn: LOG Entry #229 · D-044 · K-045
Links: D-043 (hành vi cũ), D-044 (bulkhead), K-045
Đổi: TỪ (D-043, #224) `_run_from_config` LUÔN `return 0` → SANG **`return 0` nếu mọi pipeline chạy xong, `return 1` nếu có ≥1 pipeline lỗi** (vẫn chạy hết các pipeline nhờ bulkhead).
Vì sao (bản chất — sản phẩm 24/7): return-0-luôn kết hợp bulkhead sẽ **giấu lỗi** — 50/100 camera chết nhưng CLI báo "thành công" → orchestration/CI/script vận hành KHÔNG phát hiện sự cố một phần. Đổi 0/1 để phía gọi biết "chạy nhưng có camera hỏng" mà vẫn không kéo sập hệ. Mã `1` phân biệt với `2` (argparse/`_validate_config_only` config-sai). Tương thích: 3 test hiện có dùng config toàn-thành-công → vẫn `0` (đã đọc xác nhận trước khi đổi).


### C-017 — 2026-07-06 — `build_runner` + `validate_config` giờ TỪ CHỐI key params lạ (trước: bỏ qua im lặng)
Status: ✅ (verify — full 427/1; mọi config mẫu + test cũ dùng key hợp lệ nên không phá)
Scope: `profiles/pipeline_factory.py` (contract build_runner/validate_config)
Nguồn: LOG Entry #230 · D-045 · K-046
Links: D-045, D-042 (config core), K-046, T-017
Đổi: TỪ (D-042, #223) build_runner/validate_config chỉ kiểm `type`∈registry + key BẮT BUỘC (`_need`), **key params LẠ bị BỎ QUA im lặng** (`params.get` dùng default) → SANG **từ chối key lạ bằng `ConfigError` fail-fast** (mọi key trong params phải ∈ `allowed_params` của builder).
Vì sao (bản chất): hành vi cũ khiến typo cấu hình chạy SAI mà không báo (K-046) — rủi ro vận hành thật cho hệ nhiều-cam (vd `devcie` thay `device` → im lặng chạy CPU). Siết contract để lỗi cấu hình nổi lên SỚM (fail-fast), đúng nguyên tắc "valid trước khi triển khai". Tương thích ngược: builder chưa khai báo allowed_params → vẫn lenient (không vỡ registry bên thứ 3); mọi config/test hiện có nằm trong tập allowed → xanh (đã kiểm trước khi đổi).


### C-018 — 2026-07-07 — `backpressure-cross-process` R2.2 đổi ngữ nghĩa "in-flight cũ nhất" → "frame chờ-gửi (CHƯA gửi) cũ nhất" + tách R1
Status: ✅ (đã sửa requirements.md; grep xác nhận không còn tàn dư "in-flight cũ nhất")
Scope: `.kiro/specs/backpressure-cross-process/requirements.md` — Introduction + Glossary + R1 + R2.2–2.5
Nguồn: LOG Entry #238 · yêu cầu ban đầu #237 (requirements-first, chưa chốt cơ chế)
Evidence: requirements.md = 0 diagnostics; grep "in-flight cũ nhất" = không còn kết quả (LOG #238); R8.4 khớp Mô hình A (giữ frame mới, bỏ frame cũ chưa gửi)
Links: D-048, T-018
Đổi gì (so với requirements ban đầu #237):
- **R2.2:** từ "loại bỏ **yêu cầu in-flight cũ nhất**" → "loại bỏ **frame chờ-gửi (chưa được gửi tới server) cũ nhất**; frame bị loại SHALL KHÔNG được gửi tới server".
- **R1 tách 2 ý:** (R1.2) đưa frame vào hàng đợi outbound non-blocking; (R1.3) flow-control chỉ GỬI khi `In_Flight_Count < window_size` → R1 từ 4 lên **5 AC**.
- **Glossary:** `Submission_Window` định nghĩa lại thành 2 van (flow-control in-flight + hàng đợi outbound có giới hạn); thêm `In_Flight_Count` (số request ĐÃ gửi chưa trả lời) + `Metric_DTO`.
- **Introduction:** thêm đoạn "Mô hình đã chốt — bound-before-send" giải thích bằng chứng server không hủy được request.
Vì sao (bản chất): requirements #237 (WHAT) đúng cho CẢ hai mô hình A/B, nhưng câu chữ "in-flight cũ nhất" ngầm ám chỉ Mô hình B (phản mục tiêu). Đây là **đổi ngữ nghĩa requirement, KHÔNG phải chi tiết vặt** → user đã duyệt hướng (Mô hình A) TRƯỚC khi sửa (không tự ý sửa lén requirement).


### C-019 — 2026-07-08 — Ngữ nghĩa `frames_dropped_backpressure` (artifact profile) = drop client-window + drop SHM-ring (2 tầng)
Status: ✅ (Wave 4 ASSERT bất biến 2-tầng cross-process — `test_zmq_backpressure_overload_conserves` PASS 4x, D-051)
Scope: `camera_worker` artifact · spec backpressure-cross-process (R4.1/R4.3 + design §4.5)
Nguồn: LOG Entry #244 · đọc `camera_worker` (2 tầng backpressure: SHM ring `write()→None` ⊥ client-window BoundedQueue) · design §4.5 (không xử lý nhánh write→None)
Evidence: `_write_result` ghi `frames_dropped_backpressure = client-window + frames_dropped_shm` + tách `frames_dropped_client_window`/`frames_dropped_shm` (đọc code); fullstack pass (4.09s) + full 456/1 + lint 5/0. Bất biến `submitted+dropped==captured` đúng BY-CONSTRUCTION (mỗi captured → shm-drop / client-drop / submitted, loại trừ nhau) — assert bằng test ở Wave 4
Links: D-049, T-020, K-053
Đổi gì (so với design §4.5 ban đầu): design chỉ nói "frames_captured += 1 on has_data" + `metrics_snapshot` đếm drop của client-window. KHÔNG xử lý khi `wcoord.write()` trả None (SHM ring đầy) → frame captured nhưng không submit & không nằm trong drop client-window → "loại thứ ba" làm VỠ bất biến `submitted+dropped==captured`. → CHỐT (user duyệt): coi SHM-ring-đầy CŨNG là backpressure drop; artifact ghi `frames_dropped_backpressure = client_window_drops + frames_dropped_shm`; thêm counter quan sát riêng `frames_dropped_shm` (minh bạch tầng nào bỏ).
Vì sao (bản chất): giữ đúng R4.1 (captured = mọi frame đọc từ source) ĐỒNG THỜI giữ bất biến bảo toàn đúng (mỗi frame captured hoặc submitted hoặc dropped-vì-backpressure). Bỏ qua nhánh write→None = giấu mất-frame im lặng = đúng lỗ A2 mà spec phải đóng → phải đếm, không được lơ.


### C-020 — 2026-07-08 — Khôi phục detail `D-036` bị thiếu trong `01-decisions.md` (INDEX có dòng nhưng file thiếu heading)
Status: ✅ (linter C3-D/C5-D PASS sau khôi phục)
Scope: `ai-decision-journal/01-decisions.md` (chèn `### D-036` giữa D-035 và D-037)
Nguồn: LOG Entry #248 · phát hiện bởi linter D-052 (C3-D THIẾU=[36] + C5-D orphan-INDEX=[36]) · nội dung nguồn = LOG #198
Evidence: `py tests/test_memory_consistency.py` C3-D PASS (51 ID liên tục) + C5-D "khớp INDEX"
Links: D-052, D-036, K-054
Đổi gì: file `01-decisions.md` nhảy D-035 → D-037 (thiếu heading `### D-036`) dù INDEX đã có dòng D-036 (drift bản-ghi, nghi mất khi sync đa-máy). → khôi phục detail D-036 (Yolov5PtDetector) từ nguồn canonical LOG #198 — KHÔNG bịa (mọi dữ kiện: names car/moto/truck, patch weights_only, 364/1 lint 5/0 đều lấy nguyên từ #198).
Vì sao: journal là chỉ-mục-kiểm-chứng; INDEX trỏ D-036 mà không có detail = gãy audit. Khôi phục từ LOG (nguồn sự thật) là fix gốc, không phải xoá dòng INDEX (fix ngọn).


### C-021 — 2026-07-11 — `main`→`_run_from_config` routing: pre-compute smart-default (5s) → truyền RAW cờ CLI; smart-default DỜI vào `_run_from_config` (sau merge TOML)
Status: ✅ (verify — full 623/2, lint 5/0; test #299 cập nhật assertion 5.0→0.0)
Scope: `profiles/vision_slice_app.py::main` (config-branch) + `_run_from_config` · spec config-observability-toml (D-086)
Nguồn: LOG Entry #311 · D-086/#309/#310 · đối chiếu test #299 fail
Evidence: `test_config_observability.py::test_main_routes_metrics_flags_to_config` đổi assert `observe_interval_s` 5.0→0.0; full `vp verify` 623/2·5/0·drift PASS; trace end-to-end runner vẫn nhận emit_interval_s=5.0
Links: D-086, D-082 (#299 hành vi cũ), T-029
Đổi: TỪ (#299) `main` tính `obs_interval=5.0` (smart-default) RỒI truyền xuống `_run_from_config` → SANG `main` truyền **RAW** `args.observe_interval` (0.0 khi không set) + `--metrics-host default None`; **smart-default 5s DỜI vào `_run_from_config`** (áp SAU khi merge với `[observability]` TOML).
Vì sao (bản chất): để merge precedence CLI↔TOML đúng, `_run_from_config` PHẢI biết "CLI có set interval không" (sentinel 0.0) TRƯỚC khi áp smart-default — nếu main pre-compute 5.0 thì mất thông tin "không set" → không merge được với TOML. Hành vi END-TO-END KHÔNG đổi (runner vẫn nhận 5.0 qua smart-default sau-merge); chỉ hợp-đồng-trung-gian đổi. Đường CLI-direct giữ smart-default riêng (không đụng). Backward-compat: test #299 khác duy nhất 1 assertion giá-trị-trung-gian (đã cập nhật + ghi rõ lý do).

### C-022 — 2026-07-14 — C9 design: lệnh đo `behind` SAI HƯỚNG → sửa sang `git rev-list --left-right --count`
Status: ✅ (đã sửa design; verify empiric bằng lệnh git thật)
Scope: `.kiro/specs/drift-check-git-reality/design.md` · `_collect_git_facts`
Nguồn: LOG Entry #380 · probe git read-only trên repo (HEAD 2496e2c)
Evidence: `git rev-list --count HEAD..@{upstream}`=0 (behind); `git rev-list --left-right --count @{upstream}...HEAD`=`0\t0` (behind\tahead); `git status -sb`=`## <b>...origin/<b>` không `[ahead/behind]`
Links: D-107, T-035
Đổi: TỪ `behind = git rev-list --count @{upstream}..HEAD` (draft V1) → SANG `git rev-list --left-right --count @{upstream}...HEAD` parse `behind\tahead`.
Vì sao (bản chất): `@{upstream}..HEAD` đếm commit CÓ ở HEAD mà KHÔNG ở upstream = **ahead**, không phải behind — draft V1 nhầm hướng. `--left-right` với BA chấm cho cả hai số đúng vai (left=behind, right=ahead) trong 1 lệnh. Bắt được nhờ kiểm-chứng-empiric TRƯỚC khi code — minh chứng "valid thiết kế trước khi triển khai" có giá trị thật (nếu code theo V1 thì C9 sẽ báo ngược: local ahead lại tưởng stale).

### C-023 — Task 5 `[detection]`: standalone loader thay vì nhét vào `AppConfig` schema
Trạng thái: ✅ (verify 819/2, #400).
Đổi: tasks.md Task 5 ghi "thêm khoá `[detection]` vào config loader/**schema**" (hàm ý `AppConfig` như `[observability]`). SANG: KHÔNG thêm field `detection` vào `AppConfig`; thay bằng `load_detection_config(path)` standalone + `_parse_detection` dùng chung.
Vì sao (bản chất): `AppConfig`/`parse_app_config` BẮT BUỘC có mảng `[[pipelines]]` (`_require(isinstance(pipelines_raw, list), ...)`). Nhưng consumer của `[detection]` là `vision_web_app` — webcam→detect BESPOKE, KHÔNG theo mô hình pipelines. Nếu nhét vào `AppConfig` thì file config web phải mang `[[pipelines]]` GIẢ (vô nghĩa) mới parse được → sai bản chất + rác. Standalone loader (không đòi pipelines) tôn trọng đúng consumer, vẫn dùng chung parser `_parse_detection` nên KHÔNG drift validate.
Ảnh hưởng: `[detection]` trong một file pipelines (`vision_slice_app --config`) hiện KHÔNG được `parse_app_config` đọc (bị bỏ qua như key lạ). Đây KHÔNG phải mất mát: cadence chỉ wire ở web app (slice_app dùng motion-gate qua Stage). Nếu sau này slice_app cần cadence → thêm field vào AppConfig + gọi `_parse_detection` (parser đã sẵn).
Links: D-121, D-086.

### C-024 — Đảo hành vi ONNX device: fallback-CPU-âm-thầm (D-098) → fail-fast + honor device đường web
Trạng thái: ✅ (verify 868/2 + empiric, #437/D-139).
Đổi so với trước:
- **D-098** (cũ) quy định `_det_onnx` device=cuda → providers `[CUDA, CPU]` → onnxruntime **fallback CPU âm thầm** khi máy không CUDA. SANG (D-139): đi qua `resolve_device` → `cuda` trên máy không CUDA = **CapabilityError fail-fast** (không chạy CPU âm thầm). Cũng: `device` lạ trước raise `ConfigError` → nay `CapabilityError`.
- Đường web/CLI `_build_detector` (nhánh onnx) trước **BỎ QUA `--device`** (luôn CPU) → nay **honor `--device`** qua cùng chính sách (hỗ trợ auto/cuda + log).
Vì sao (bản chất): fallback-âm-thầm che giấu "tưởng GPU mà chạy CPU" — nguy hiểm cho vận hành 24/7 (mất hiệu năng ngầm, không ai biết). Fail-fast + log là hành vi ĐÚNG cho dual-use thương mại (đối xứng `_det_pt`). Default `cpu` KHÔNG đổi → tương thích ngược với mọi cấu hình hiện có; chỉ đổi ca `cuda`/`auto`/device-lạ.
Ảnh hưởng test: `test_onnx_device_gpu.py` viết lại — `device=cuda` giờ cần caps có CUDA (tiêm) mới ra providers; cuda-no-gpu → CapabilityError (test mới). Ai dựa fallback-âm-thầm phải đổi sang `device=auto`.
