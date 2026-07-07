# 🏗️ IMPLEMENTATION TRACKER — chống drift thiết kế

> **Mục đích:** triển khai để KIỂM CHỨNG thiết kế trong `Design/`. File này là "hợp đồng" giữa
> *thiết kế* (Design/) và *code thật* (implement/) — mỗi vấn đề triển khai PHẢI trỏ về nguồn
> Design cụ thể. Lệch khỏi Design mà không ghi lý do = **drift** = phải dừng.

## ⛓️ LUẬT TRIỂN KHAI (bắt buộc — người dùng yêu cầu)
1. **MỘT vấn đề / lần.** Không làm nhiều việc cùng lúc. Đào CỰC SÂU 1 vấn đề tới khi chính xác
   tuyệt đối rồi mới sang vấn đề kế.
2. **Khuyến nghị từng phần.** Mỗi bước: nêu khuyến nghị nhỏ nhất + chờ duyệt. Không tự lao.
3. **Chống bịa (anti-hallucination).** Mọi thứ cụ thể (tên file/hàm/API/lệnh/số liệu) phải KIỂM
   TỒN TẠI (đọc Design/đọc file/chạy lệnh) trước khi khẳng định. Suy luận chưa kiểm → nhãn
   **[suy đoán]/[chưa kiểm]**. Thà nói "chưa chắc" còn hơn nói sai.
4. **Mỗi vấn đề trỏ nguồn Design.** Ghi rõ file Design nào quy định. Không có nguồn → không code.
5. **Validate thật.** "Xong" = test chạy thật PASS (không nói suông). Số test là *kỳ vọng theo
   Design* cho tới khi chạy thật trên máy.
6. **Ghi log.** Mỗi lần triển khai → 1 entry `AI-IMPLEMENTATION-LOG.md` (gốc repo).

## 📐 Nguồn sự thật (đã đọc trực tiếp — độ chắc: cao)
- `Design/module-03-build-along/00-overview.md` — roadmap 10 step + cấu trúc đích + bảng test.
- `Design/reference-cards/folder-structure-blueprint.md` — skeleton 6 layer + quick rules import.
- `Design/module-06-implementation/02-definition-of-done.md` — DoD checklist (~12 mục).
- `Design/module-06-implementation/01-week-by-week-16-weeks.md` — lộ trình dự án thật (Strangler Fig).
- `Design/00-START-HERE.md` — phương pháp; lưu ý "số test = kỳ vọng, không phải artifact".

## 🎯 Cách kiểm chứng thiết kế
Dựng mini Vision Platform theo **Module 03 Step 01→10**. Mỗi step = 1 "vấn đề triển khai" dưới đây.
Build-first: có skeleton chạy được trước, lý thuyết đan xen. Đạt test xanh ở mỗi step = thiết kế
phần đó *kiểm chứng được*. Lệch (phải sửa khác Design) → ghi vào cột "Drift/Ghi chú" + báo.

## 📋 Danh sách VẤN ĐỀ (bám bảng Module 03 — đã verify từ 00-overview)
> Trạng thái: ⬜ chưa làm · 🔵 đang làm · ✅ test xanh thật. Test = *kỳ vọng theo Design* tới khi chạy.

| # | Vấn đề (Step) | Nguồn Design | File mới (kỳ vọng) | Test (kỳ vọng) | TT | Drift/Ghi chú |
|---|---------------|--------------|--------------------|----------------|----|---------------|
| 01 | Project skeleton + venv + pyproject | step-01-project-skeleton.md | 11 | 2 | ✅ | build+validate THẬT: 2 passed · 5 kept/0 broken. Code ở `vision-platform/` (pkg `vision_platform`). **Phát hiện+sửa Design: E-9** (`include_external_packages`) |
| 02 | Domain BBox + Kernel ReadResult + MediaPacket | step-02 | 4 | 20 (16+4) | ✅ | build+validate THẬT: 84 passed/1 skipped tổng · 5 kept/0 broken. Fix B/C (E-11) + Risk3 NORMALIZED (E-12) + **E-16 R1: MediaPacket pickle (__getstate__/__setstate__, mappingproxy không pickle được — verify thật)**. |
| 03 | Port IFrameSource + 2 adapter + contract test | step-03 | 4 | 33 (30+1+2) | ✅ | build+validate THẬT: 86 passed/1 skipped tổng · 5 kept/0 broken. Fix source_id auto-unique (E-13). **E-16 R2#04: thêm context-manager `__enter__/__exit__` cho IFrameSource + 2 adapter** (+2 test) → dùng `with source, executor:`. |
| 04 | StageContract + BaseStage + Executor + 2 stage + composition root | step-04 | 7 | 16 (13+3) | ✅ | build+validate THẬT: 84 passed/1 skipped tổng · 5 kept/0 broken. Risk4 context-manager (E-14). **E-16: R1 traceback string, R3 teardown chỉ stage đã setup + rollback, R6 validate kiểu trả về** (+3 test). R2 (port context-manager) HOÃN chờ duyệt. |
| 05 | SHM frame bus + multi-process | step-05 | 3 | 16 (13+1+2) | ✅ | build+validate THẬT: 80 passed/1 skipped · 5 kept/0 broken. Q1=CÓ (negative-test chứng minh kernel↛multiprocessing), Q2=A (slot kẹt WRITING + F-3b reader kẹt READING — ERRATA E-15). F-4 invariant 1-writer; F-6 dtype +1 test; +2 guard test (re-review); F-8/F-10 cross-process verify thật Windows; 5× run KHÔNG flaky, 0 warning/leaked. |
| 06 | ZMQ inference service | step-06 | 4 | 9 | ✅ | build+validate THẬT: **9 passed** (full 261/1 skipped · lint 5 kept/0 broken). Scope = INLINE (DTO+IDetector+FakeDetector+InlineClient+request_id correlation); ZMQ cross-process = production hoãn. Deviation đã duyệt+verify: **E-06-1** client ở `application/` (contract #5 cấm adapters→runtime); **E-06-2** InferenceRequest nhúng `ShmFrameRefData` (ring_epoch → read_ref stale-check P0-3). 4 file mới: `kernel/inference_protocol.py`, `kernel/ports/detector.py`, `adapters/fake_detector.py`, `application/inline_inference_client.py`. |
| 07 | Backpressure (4 policy) | step-07 | 1 | 11 | ✅ | build+validate THẬT: **11 passed** (full 272/1 skipped · lint 5 kept/0 broken). `kernel/backpressure.py` (BackpressurePolicy enum 4 + BoundedQueue[T] thread-safe: Condition+wait_for, metrics under-lock, get vs get_or_raise). Thiết kế Design giữ NGUYÊN (valid sạch, 0 deviation). **K-016**: thread-safe KHÔNG process-safe (chỉ in-process; cross-process vẫn SHM #05). **K-017**: metrics chưa wire obs (hoãn #08). |
| 08 | Observability (structlog + metrics) | step-08 | 1 | 12 | ✅ | build+validate THẬT: **12 passed** (full 284/1 skipped · lint 5 kept/0 broken). `runtime/observability.py` (setup_logging structlog JSON + log_context contextvars nested-safe + InMemoryMetrics thread-safe counter/gauge/histogram + snapshot copy). Thêm dep `structlog>=24.1` (C-008, cài 26.1.0). Thiết kế Design giữ nguyên (valid sạch) + style `import logging`. K-018 (bỏ production handlers) · K-019 (cardinality) · wiring nguồn→sink (K-017) bước sau. |
| 09 | Shutdown protocol | step-09 | 2 | 6 | ✅ | build+validate THẬT: **6 passed** (full 290/1 skipped · lint 5 kept/0 broken). `application/supervisor.py` (Supervisor + WorkerSpec: spawn/monitor/restart-cap/cascade cooperative-first) + `tests/worker_funcs_for_step_09.py` (worker module riêng). F1/E-10 (cascade cooperative-first) verify THẬT tại #09 (test graceful cleanup pass — không còn chỉ suy luận #40). K-020 (chỉ phát hiện crash, không hang) · K-021 (không backoff). |
| 10 | Package + ship (re-run all) | step-10 | 0 | re-run | ✅ | verify THẬT: full **290 passed/1 skipped** · lint **5 kept/0 broken** · 2 smoke demo đúng (noise→10 processed, fake→5 skipped) · `python -m build` → wheel 0.1.0 (59KB) + sdist + fresh-install `__version__`=0.1.0. README.md (số THẬT không blueprint 110 — C-009) + .gitignore build artifacts + DoD ✅. **🎯 MODULE 03 #01–#10 HOÀN TẤT.** |

**Tổng kỳ vọng:** 111 test (110 pass + 1 skip có chủ đích ở Step 03).

## 📍 Con trỏ HIỆN TẠI
**Cập nhật lúc:** 2026-07-04 (làm mới mỗi lượt — §2.5 per-turn).
- 🎯 **SUB-SPEC `zmq-inference-service` HOÀN TẤT (đóng K-023):** production inference cross-process ZMQ. codec@kernel + IInferenceClient@kernel/ports + ZmqInferenceClient@adapters + InferenceServer@application (switchover-aware) + 10 test (codec/port + cross-process/switchover). Full **300 passed/1 skipped · lint 5 kept/0 broken** · pyzmq 27.1.0/msgpack 1.2.1. Spec `.kiro/specs/zmq-inference-service/` (0 diagnostic). Log #169-171 · D-028 · C-010. Bước kế: PHA 3 bài học zmq (tùy chọn) hoặc hướng mới.
- 🔵 **#10 (package+ship) — HOÀN TẤT 3 PHA. 🎯 MODULE 03 #01–#10 XONG (code + bài học).** PHA 2 verify (290/1, lint 5/0, wheel 0.1.0, 2 demo). PHA 3 bài học `code-lessons/10-package-ship/` (4 mẩu wrap-up + tổng kết Module 03). Log #166/#167 · D-027 · C-009 · K-022. **CÒN MỞ (ngoài AI-làm-được-trên-Windows):** Feynman #01–#10 + 05b (user học sau) · git push (K-007, chờ quyền, ~50 commit) · 🔴 K-001 ARM · K-003 POSIX teardown · K-004 SLA · K-005 AccessDenied · K-014 throughput tải thật.
- ✅ **#01 + #02 + #03 + #04 + #05 XONG** (build thật ở `vision-platform/`, pkg `vision_platform`). Tổng hiện tại: **86 passed, 1 skipped** · 5 kept/0 broken.
  - #01: skeleton. Sửa Design E-9.
  - #02: Domain/Kernel/MediaPacket. Fix B/C (E-11) + Risk3 NORMALIZED (E-12).
  - #03: IFrameSource + Fake/Noise + contract test. Fix source_id auto-unique (E-13).
  - #04: StageContract/BaseStage/SyncLinearExecutor/2 stage/composition root. Demo end-to-end khớp Design.
  - #05: SHM frame bus (DTO kernel + ring/writer/reader runtime/ipc) + 16 test (gồm cross-process). E-15 (F-1 import-linter kernel fix + negative-test, F-3 slot kẹt WRITING + F-3b reader kẹt READING giữ, F-4 invariant 1-writer, F-6 dtype hardening, +2 guard test). Re-review: 5× run KHÔNG flaky, 0 warning/leaked. Cross-process VERIFY THẬT Windows.
- **Tổng hiện tại: 80 passed, 1 skipped · 5 kept/0 broken.**
- **Quy ước A:** mỗi vấn đề có brief (đã có 01-skeleton-layout, 02-data-objects, 03-port-adapters, 04-pipeline, 05-shm-frame-bus).
- Vấn đề kế: **#06 — ZMQ inference service** (`step-06`, kỳ vọng 9). Quy trình 3 PHA. (Code-lessons #05 = PHA 3 của #05, chưa làm.)
- Code project: `e:\VisionPlatform\vision-platform\` (venv `.venv`, đã `pip install -e .[dev]`).

## 📂 Quy ước thư mục
- `implement/` = **CHỈ tài liệu theo dõi** (tracker + brief mỗi vấn đề). **KHÔNG chứa code.**
  - `implement/00-IMPLEMENTATION-TRACKER.md` — file này (chân lý tiến độ + chống drift).
  - `implement/<NN>-<vấn-đề>/00-brief.md` — **CHUẨN (chọn A): MỖI vấn đề (cả 10) có 1 brief** =
    đơn vị học tự đủ (mục tiêu + nguồn Design + quyết định/deviation + findings/ERRATA + bằng chứng
    validate). Giữ cô đọng. Bảng trên = dashboard; brief = lát cắt sâu theo từng vấn đề; log = nhật ký thời gian.
- **Code thật nằm ở FOLDER RIÊNG, bên ngoài `implement/`** (bulkhead): `vision-platform/` (pkg `vision_platform`).
