# Architecture Review — Vision Platform (2026-07-11)

> **Mục đích:** review toàn hệ về thiết kế / pattern / struct / tổ chức code / phân tách, chỉ ra chỗ cần
> sửa & cải tiến, để làm nền đánh giá tổng thể. **Bám CODE THẬT đã đọc** (cite file), KHÔNG bịa, KHÔNG suy
> đoán; chỗ SOUND thì ghi SOUND (không tạo vấn đề giả).
>
> **Đã đọc để review:** `pyproject.toml` · `runtime/pipeline_runner.py` · `runtime/sync_linear_executor.py` ·
> `runtime/base_stage.py` · `kernel/ports/{frame_source,detector,sink,tracker}.py` · `kernel/observability_port.py`
> · `kernel/capabilities.py` · `kernel/config.py` · `application/config_loader.py` · `profiles/pipeline_factory.py`
> · `profiles/vision_slice_app.py` · `application/supervisor.py`.
> **Chưa đọc sâu (trung thực):** từng adapter cụ thể (rtsp/onnx/yolov5_pt), `runtime/ipc/*` (SHM ring nội bộ),
> từng stage — nên các mục dưới KHÔNG kết luận về nội bộ chúng.
>
> Gắn `AI-IMPLEMENTATION-LOG.md` #318. Số liệu sống: `vp verify` / `lint-imports`.

---

## A. Điểm SOUND (thiết kế tốt — giữ nguyên, đừng "sửa cho có")

1. **Ranh giới tầng ÉP BẰNG MÁY** — 5 contract import-linter (`pyproject.toml`): domain/kernel cấm cả lib
   ngoài (cv2/torch/zmq/...) lẫn layer trên. Đây là Dependency-Inversion *cưỡng chế*, không dựa kỷ luật. Hiếm repo làm được. ✅
2. **Ports = `typing.Protocol`** (structural) — adapter không cần kế thừa; seam sạch để thay công nghệ + test tiêm fake. ✅
3. **`PipelineRunner`** — teardown lồng `try/finally` nhiều tầng (LUÔN chạy, thứ tự ngược); observer **cô lập lỗi**
   (`_emit` bọc try/except, đếm `_observer_errors`, không sập pipeline); trả DTO đầy-đủ-trạng-thái (không bóp về None). ✅
4. **`BaseStage`** — exception→`StageResult.error`, **traceback lưu DẠNG CHUỖI** (`format_exc`) để không giữ tham
   chiếu frame/local → chống rò RAM (insight tốt, hiếm ai để ý); fail-fast nếu `_do_process` trả sai kiểu. ✅
5. **`SyncLinearExecutor`** — setup lỗi nửa chừng → rollback teardown ngược; chỉ teardown stage ĐÃ setup; là context manager không nuốt exception. ✅
6. **`Supervisor`** — bulkhead (1 worker/process), cascade shutdown **cooperative-first** (join grace TRƯỚC rồi mới
   terminate→kill), heartbeat/backoff **additive default-TẮT**, backoff **non-blocking** (deadline monotonic, không sleep chặn). ✅
7. **Config** — dataclass `frozen` + `MappingProxyType`/`tuple` (bất biến thật); **registry + `allowed_params`**
   chặn typo im lặng (K-046); **lazy-import** trong builder → không kéo torch/cv2 lúc nạp module. ✅
8. **Phân tách loader↔factory đúng tầng** — `config_loader` (application) chỉ validate CẤU TRÚC; kiểm `type ∈ registry`
   dời về `pipeline_factory` (profiles, nơi biết registry). Không rò adapter lên application. ✅
9. **Bulkhead per-pipeline** trong `_run_from_config` — bắt `Exception` (chừa `BaseException` → Ctrl+C vẫn dừng), log rõ, chạy tiếp cam kế; return 1 nếu có lỗi (không giấu). ✅

→ Tổng: nền kiến trúc **vững**, đúng hexagonal, có kỷ luật vòng đời + cô lập lỗi. Các phát hiện dưới đây phần lớn
là **tổ chức/khử-trùng-lặp**, KHÔNG phải lỗi đúng-sai (không tìm thấy bug logic trong phạm vi đã đọc).

---

## B. Phát hiện cần sửa / cải tiến (có cite, có severity)

### F1 — [Medium-High] Trùng lặp ĐƯỜNG LẮP-RÁP pipeline: CLI-direct (main) vs config (factory)
**Bằng chứng:** `vision_slice_app.main()` tự ráp `stages`/`sinks`/`observer` bằng tay (~90 dòng: build source →
motion_gate → detect → count → track → line → sinks), TRONG KHI `pipeline_factory.build_runner()` làm CÙNG việc
qua registry. **Hai nguồn sự thật** về "cách dựng 1 pipeline".

**Hệ quả THẬT (đã đối chiếu code):** đường CLI-direct dựng `MotionGateStage(max_consecutive_skip, roi,
illumination_robust)` — **KHÔNG cho chỉnh** `pixel_diff_threshold`/`min_area_ratio`; nhưng factory
`_stage_motion_gate` CÓ 2 tham số đó. → cùng khái niệm "motion gate" nhưng **năng lực khác nhau** giữa 2 đường.
Thêm stage mới ⇒ phải sửa 2 chỗ; dễ quên → phân kỳ hành vi (đúng loại drift khó phát hiện).

**Đề xuất (fix GỐC, không fix ngọn):** map CLI args → **1 `PipelineConfig` in-memory** rồi gọi `build_runner`
(một đường lắp-ráp DUY NHẤT). CLI trở thành "cú pháp tiện sinh ra config". Xoá ~90 dòng trùng + diệt nguồn phân kỳ.
Rủi ro thấp (build_runner đã có test); cần giữ nguyên thứ-tự-stage suy từ cờ + backward-compat output summary.

### F2 — [Medium] `main()` quá dài, nhiều trách nhiệm (SRP)
**Bằng chứng:** `main()` gồm argparse (~60 dòng) + nhánh `--capabilities` + logic observe-default + route config +
toàn bộ CLI-direct assembly + in summary. Khó test đơn vị (chỉ test được qua `argv`).
**Đề xuất:** tách `build_argparser()`, `_run_cli_direct(args)`, `_print_summary(...)`. Nếu làm F1 thì main tự co lại nhiều.

### F3 — [Medium] Magic number "5.0s" (smart-default observe) ở 2 nơi
**Bằng chứng:** `main()` đặt `obs_interval = 5.0` (đường CLI-direct); `_run_from_config` tính LẠI `m["observe_interval_s"]=5.0`
sau merge. Cùng một chính sách, 2 chỗ. (Journal C-021 đã ghi đường này rối.)
**Đề xuất:** 1 hằng `_DEFAULT_OBSERVE_INTERVAL_S = 5.0` + 1 helper `_smart_default_interval(...)` dùng chung 2 đường.

### F4 — [Low-Medium] Guard backpressure viết xong nhưng CHƯA wire (code chờ)
**Bằng chứng:** `config_loader.assert_policy_allowed_for_source` (cấm BLOCK cho RTSP) đầy đủ + đúng lý, NHƯNG
schema (`SourceConfig`) CHƯA mang `policy` per-source → guard **chưa được gọi ở đường thật** (chỉ "sẵn-sàng-wire",
ghi D-050/K-053). Reviewer dễ tưởng RTSP đang được bảo vệ.
**Đề xuất:** hoặc (a) wire thật: thêm `policy` vào `SourceConfig` + gọi guard trong `_src_rtsp`; hoặc (b) đánh dấu
rõ ràng "future API — chưa hiệu lực" để không hiểu nhầm mức bảo vệ hiện tại.

### F5 — [Low] `_CompositeObserver` nên ở `runtime/observers.py` (tái dùng)
**Bằng chứng:** `_CompositeObserver` (fan-out snapshot tới N observer, cô lập lỗi) là cơ chế RUNTIME tái dùng
được, nhưng đang private trong `profiles/vision_slice_app.py`. `runtime` đã có `CompositeSink` tương tự cho sink.
**Đề xuất:** chuyển vào `runtime/observers.py` cạnh `LoggingObserver`/`MetricsObserver` + test riêng.
(`_TrackSummarySink` đọc artifacts → profile-specific, giữ ở profile là hợp lý.)

### F6 — [Low] `_build_config_observability` trộn build + start + I/O
**Bằng chứng:** hàm tên "build" nhưng cũng `exporter.start()`, `print(...)` stderr, cảnh báo loopback (side-effect).
**Đề xuất:** tách "build thuần (trả observer/exporter chưa start)" khỏi "start + log". Ưu tiên thấp (mỗi đường 1 call-site).

### F7 — [Low / điều hướng] Nhiều profile entry dễ gây mơ hồ
**Bằng chứng:** `profiles/` có `vision_slice_app` (chính), `vision_demo_app`, `demo_pipeline`, `vision_web_app`,
`vision_fullstack_profile`. Người mới khó biết đâu là entry chính.
**Đề xuất:** đã giảm nhẹ nhờ `docs/ARCHITECTURE.md` + README chỉ rõ `vision_slice_app` là entry chính; nên thêm
1 dòng docstring ở mỗi profile phụ ghi "demo/legacy/web — không phải entry sản phẩm".

---

## C. Ưu tiên đề xuất (nếu làm tiếp — theo giá trị/rủi ro)

| Ưu tiên | Việc | Vì sao | Rủi ro |
|---|---|---|---|
| 1 | **F1** hợp nhất 2 đường lắp-ráp (CLI → PipelineConfig → build_runner) | diệt nguồn phân kỳ hành vi + giảm ~90 dòng; đúng "1 nguồn sự thật" | thấp-vừa (có test build_runner; giữ output summary) |
| 2 | **F2/F3** tách `main()` + gom hằng 5.0s | dễ đọc/test; hệ quả tự nhiên của F1 | thấp |
| 3 | **F4** quyết wire hay đánh dấu guard RTSP | tránh hiểu nhầm mức bảo vệ | thấp |
| 4 | **F5/F6** dời `_CompositeObserver`, tách build/start | gọn + tái dùng | rất thấp |

**Khuyến nghị cách làm (đúng cadence dự án):** mỗi F = 1 spec nhỏ design→review→code TDD; giữ `vp verify` xanh +
`lint-imports` 0-broken sau mỗi bước; ghi sổ journal. F1 nên làm đầu (nền cho F2/F3).

> **Lưu ý phạm vi (trung thực):** review này KHÔNG phủ nội bộ `runtime/ipc/*` (SHM ring/epoch — phần khó nhất),
> từng adapter I/O, và từng stage. Muốn review sâu các phần đó cần đọc thêm — có thể làm ở vòng review sau.


---

## D. Review vòng 2 — phủ IPC / adapter biên / observability runtime (bổ sung 2026-07-11, #319)

**Đã đọc thêm:** `runtime/ipc/shm_frame_ring.py` (TRỌN, gồm reader ABA-path) · `runtime/ipc/ring_control_plane.py`
· `runtime/ipc/ring_pool.py` · `adapters/rtsp_frame_source.py` · `runtime/observability.py`.

### D.1 IPC / SHM ring — SOUND (chất lượng cao, hiếm gặp)
Đọc kỹ, xác nhận **thiết kế concurrent vững**:
- **`state` ghi CUỐI = authority** (`_write_header` pack state sau cùng); reader check `generation` + `ring_epoch`
  → chống ABA + stale-sau-switchover. Peek `state` lock-free (4B aligned) để bỏ QUARANTINED trước khi đụng lock.
- **Reader registry đa-reader** (reader_count dẫn xuất từ ô active) + **reap reader chết** (lease quá hạn ∧ DEAD).
- **Double-snapshot recovery** (`quarantine_poisoned_slot`: 2 snapshot header giống nhau mới hành động → tránh torn).
- **Single-writer invariant** cưỡng chế (`register_writer` reject writer sống/UNKNOWN, KHÔNG takeover writer chết → yêu cầu rebuild).
- **Drain-before-reuse CƯỠNG CHẾ** (`reset_for_reuse` refuse nếu còn reader hiệu lực) + TOCTOU được ghi rõ + ràng
  buộc CHỈ gọi qua `RingPool(pool_size>=2)` (ring reset ≠ ring hiện hành). Cold-start dùng uuid name (không attach segment sót).
→ Đây là phần khó nhất và **làm tốt** (có PBT + test cross-process hậu thuẫn). KHÔNG có đề xuất sửa.

### D.2 [Low-Medium] Giới hạn lock-poison LẦN-2 (chính CODE đã tự ghi — E-15/E-15b)
**Bằng chứng (docstring + code):** nếu writer acquire-lock LẦN 2 (commit READY) timeout → slot kẹt `WRITING`
vĩnh viễn; đối xứng ở reader (mark DONE timeout → kẹt `READING`). Owner=self còn sống nên KHÔNG tự quarantine.
Code GHI RÕ đây là giới hạn demo (production cần lease-timeout + QUARANTINED recovery). Trung thực, không giấu.
**Đề xuất:** đây là hố GPU/production thật — khi làm nhánh production, wire lease-deadline (field v2 đã có sẵn
`OFFSET_LEASE_DEADLINE_NS`) + recovery cho slot self-owned-timeout. Không phải bug ở phạm vi hiện tại (demo/no-GPU).

### D.3 [Low] RTSP `_reconnects` là ngân sách TRỌN-ĐỜI, không reset khi đọc lại thành công
**Bằng chứng (`rtsp_frame_source.py`):** `read()` khi mở lại → `self._reconnects += 1`; khi đọc FRAME thành công
KHÔNG reset `_reconnects` về 0. `setup()` mới reset. → với `max_reconnect` đặt số hữu hạn, camera chớp-tắt lai
rai qua phiên dài sẽ TÍCH LUỸ tới ngưỡng rồi báo `ERROR` VĨNH VIỄN dù hiện đang khoẻ. (Deploy thường dùng
`max_reconnect=None` = vô hạn → hố này LATENT, chưa cắn.)
**Đề xuất (fix bản chất):** reset `self._reconnects = 0` khi `read()` trả FRAME thành công → biến `max_reconnect`
thành "số lần rớt LIÊN TIẾP" (ngữ nghĩa thường mong đợi) thay vì trọn-đời. Nhỏ, 1 dòng, đúng ý niệm self-heal.

### D.4 [Low / quan sát] Observability phân mảnh 4 cơ chế
**Bằng chứng:** `ObservabilityHook` (sự kiện SHM ở ipc) · `structlog` (logs) · `InMemoryMetrics` (metrics) ·
`IPipelineObserver`/`PipelineSnapshot` (số liệu pipeline). Mỗi cái đúng-mục-đích-riêng (không sai), nhưng người
review cần biết "observability" trải 4 nơi. `InMemoryMetrics` SOUND (thread-safe, labelset có cấu trúc chống
parse-lossy, getter `.get` không tạo key rác, cardinality cảnh báo K-019).
**Đề xuất:** không gộp (khác tầng/mục đích); chỉ nên 1 mục trong `docs/ARCHITECTURE.md` liệt kê 4 kênh để điều hướng.

### D.5 Cập nhật phạm vi
Vòng 2 đã phủ IPC + RTSP + observability runtime. **Vẫn CHƯA đọc sâu:** `onnx_detector`/`yolov5_pt_detector`
(detector adapter), các sink (jsonl/sqlite), phần lớn `runtime/stages/*`, `zmq_inference_client`/`inference_server`.
Đánh giá tổng thể tới đây: **kiến trúc + phần khó (IPC) vững; các phát hiện đều Low→Medium, không có lỗi đúng-sai
nghiêm trọng trong phạm vi đã đọc.** Ưu tiên hành động không đổi: **F1** (hợp nhất 2 đường lắp-ráp) vẫn là số 1.
