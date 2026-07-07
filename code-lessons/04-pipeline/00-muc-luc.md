# Bài #04 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung vấn đề→giải pháp). Rồi tới các mẩu nhỏ nhất dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + tự giải thích lại được.

| Mẩu | File | Nội dung | Trạng thái |
|-----|------|----------|-----------|
| 01 | `01-stagestatus-stageresult.md` | `StageStatus` + `StageResult` — kết quả 1 stage + KHÔNG giữ `Exception` (chống traceback retention) | ✅ đã viết |
| 02 | `02-executionresult.md` | `ExecutionResult` — result-object cho TOÀN pipeline, thay `Optional` (phân biệt SKIPPED vs ERROR) | ✅ đã viết |
| 03 | `03-skipframesignal.md` | `SkipFrameSignal` — exception để skip frame CỐ Ý | ✅ đã viết |
| 04 | `04-istage-basestage.md` | `IStage` (Protocol) + `BaseStage` (ABC + Template Method, tự bắt lỗi → StageResult) | ✅ đã viết |
| 05 | `05-brightness-stage.md` | `BrightnessStage` — stage cụ thể (mean → `with_artifact`, CoW) | ✅ đã viết |
| 06 | `06-dark-filter-stage.md` | `DarkFilterStage` — skip khi tối + yêu cầu artifact `brightness` (thứ tự stage) | ✅ đã viết |
| 07 | `07-sync-linear-executor.md` | `SyncLinearExecutor` — chạy tuyến tính, dừng non-SUCCESS, teardown `reversed` | ✅ đã viết |
| 08 | `08-context-manager-e14.md` | Context manager `__enter__`/`__exit__` (ERRATA E-14) + `__exit__` return False | ✅ đã viết |
| 09 | `09-composition-root.md` | `demo_pipeline` — composition root (lazy import adapter + `from_copy` + try/finally + vòng lặp) | ✅ đã viết |

> ✅ **#04 HOÀN TẤT 9/9 mẩu** (2026-06-21) — baseline hiện tại (2026-06-24, chạy thật): full **86 passed/1 skipped** · `lint-imports` 5 kept/0 broken; **test_step_04 = 16 passed** (13 gốc + 3 review E-16). (Số "64/13" ở các bản ghi cũ là tại thời điểm viết.) Xong #04 → track #05 production (spec `shm-production-hardening`).
> Sơ đồ (drawio nguồn ✅ — **chờ user Export SVG**): [`diagrams/pipeline-flow.drawio`](diagrams/pipeline-flow.drawio) (luồng source→Brightness→DarkFilter→executor→ExecutionResult) + [`diagrams/stage-status-state.drawio`](diagrams/stage-status-state.drawio) (BaseStage.process map exception → StageStatus). Nhúng ảnh `![](*.svg)` đã TẠM GỠ ở cau-chuyen + mẩu 04 + mẩu 07 (8 SVG #02/#03/#04 chưa export → tránh ảnh vỡ); chỉ giữ link `.drawio` + hướng dẫn Export. Sau khi user Export SVG sẽ nhúng lại.
> Ghi chú: #04 = 9 mẩu (bài giàu nhất: 6 file + ABC/Template Method/result-object/context-manager/composition root) — số mẩu theo nội dung.
