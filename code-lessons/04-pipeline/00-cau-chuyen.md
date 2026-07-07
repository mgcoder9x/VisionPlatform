# Bài #04 — Pipeline: ráp các bước xử lý thành dây chuyền chạy được · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đọc file này TRƯỚC các mẩu chi tiết. Mục tiêu: hiểu **tại sao** pipeline được dựng như vậy, trước
> khi xem từng dòng. Bám code thật ở `vision-platform/src/vision_platform/`.

---

## 1. Tổng quan — ta đang ở đâu
#01 dựng khung · #02 viên gạch dữ liệu (MediaPacket) · #03 nguồn frame (port/adapter). **Bài #04 ráp
mọi thứ thành PIPELINE**: `nguồn → bước xử lý → bước xử lý → kết quả`, chạy end-to-end.

```
source(#03) ─► [BrightnessStage] ─► [DarkFilterStage] ─► kết quả
                      └──────── SyncLinearExecutor lái ────────┘
profiles/demo_pipeline.py = composition root (ráp + chọn adapter + chạy vòng lặp)
```

> 📊 **Sơ đồ luồng pipeline** (nguồn: [`diagrams/pipeline-flow.drawio`](diagrams/pipeline-flow.drawio) — mở bằng Draw.io rồi **Export as SVG** ra `diagrams/pipeline-flow.svg`). _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_
> Thuật ngữ: [pipeline](../../knowledge-base/00-GLOSSARY.md#pipeline-dây-chuyền-xử-lý) ·
> [stage](../../knowledge-base/00-GLOSSARY.md#stage-bước-xử-lý) ·
> [result object](../../knowledge-base/00-GLOSSARY.md#result-object-đối-tượng-kết-quả) ·
> [ABC](../../knowledge-base/00-GLOSSARY.md#abc-abstract-base-class) ·
> [Template Method](../../knowledge-base/00-GLOSSARY.md#template-method-mẫu-thiết-kế) ·
> [context manager](../../knowledge-base/00-GLOSSARY.md#context-manager-with-statement).

File thật của #04:
| Thành phần | Tầng | File |
|---|---|---|
| `StageStatus` `StageResult` `ExecutionResult` `SkipFrameSignal` `IStage` | kernel | `kernel/stage_contract.py` |
| `BaseStage` (ABC + Template Method) | runtime | `runtime/base_stage.py` |
| `SyncLinearExecutor` | runtime | `runtime/sync_linear_executor.py` |
| `BrightnessStage`, `DarkFilterStage` | runtime | `runtime/stages/*.py` |
| Composition root (demo) | profiles | `profiles/demo_pipeline.py` |

## 2. Vấn đề & TẠI SAO nó là vấn đề
Có frame rồi (#03), giờ phải xử lý qua NHIỀU bước (chỉnh sáng → lọc → suy luận AI → gửi). Nếu viết
**một hàm to** gọi tuần tự:
- **Lẫn lỗi:** mỗi bước tự bắt lỗi một kiểu → không nhất quán; lỗi 1 bước làm sập cả hàm.
- **Không phân biệt "bỏ cố ý" vs "lỗi thật":** filter bỏ frame tối (bình thường) và stage lỗi (cần báo động) — nếu cùng trả `None` thì xử lý sai.
- **Rò bộ nhớ (traceback retention):** giữ nguyên `Exception` object lâu → kéo theo cả traceback/khung biến → ngốn RAM (bug thật Module 05).
- **Khó đổi:** thêm/bớt/đổi thứ tự bước phải sửa hàm to.
- **Quên dọn:** lỗi giữa chừng → quên `teardown` → rò tài nguyên.

**Lực giằng nhau:** *linh hoạt* (thêm bước dễ) ↔ *an toàn* (lỗi rõ ràng, không rò, luôn dọn). (Đoán thử:
làm sao để mỗi bước đồng dạng, lỗi không làm sập cả dây, và phân biệt được "bỏ" với "lỗi"?)

## 3. Khám phá nhiều hướng (≥2 cách)
- **Cách A — 1 hàm to tuần tự:** nhanh viết, nhưng cứng + lẫn lỗi + khó đổi. ✗
- **Cách B — mỗi stage tự `raise` exception lên trên:** gọn, nhưng mất phân biệt skip/error + dễ giữ traceback (rò RAM) + 1 lỗi sập cả chuỗi. △
- **Cách C — Hợp đồng stage (`IStage`) + `BaseStage` tự bắt lỗi thành `StageResult` + executor tuyến tính trả `ExecutionResult` (result-object) + composition root ráp:** mỗi bước đồng dạng, lỗi gói thành trạng thái rõ, phân biệt SKIPPED/ERROR, không giữ Exception. ✓ ← chọn.

## 4. Chốt giải pháp + TẠI SAO thắng
- **`IStage` (Protocol)** = hợp đồng "1 bước": `process(packet) → StageResult`. **`BaseStage` (ABC + Template Method)**: viết sẵn khung `process()` bắt `SkipFrameSignal`/`Exception` → `StageResult`; lớp con chỉ điền `_do_process`.
- **Result-object** (`StageResult`/`ExecutionResult`) thay `Optional[MediaPacket]`: phân biệt rõ SUCCESS/SKIPPED/ERROR/CANCELLED → người gọi xử lý đúng từng ca.
- **Không giữ `Exception` object** (chỉ `error_type` + `error_message` + `error_traceback` — TẤT CẢ dạng chuỗi, qua `traceback.format_exc()`; chuỗi không giữ frame) → vừa debug được vừa chống traceback retention (rò RAM). (E-16)
- **`SyncLinearExecutor`**: chạy tuyến tính, dừng ở non-SUCCESS đầu tiên; **context manager** đảm bảo `teardown` luôn chạy (E-14).
- **Composition root** (`profiles/`): chỗ DUY NHẤT biết adapter cụ thể (lazy import) + ráp pipeline.

Thắng vì: tách "khung chạy" (ổn định) khỏi "bước cụ thể" (hay thêm); trạng thái tường minh thay `None`;
an toàn bộ nhớ + luôn dọn. Thêm bước = viết 1 stage mới, executor/composition không đổi.

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự nhỏ nhất → xem `00-muc-luc.md`.

## 6. Nên làm / Nên tránh (cho bài #04)
- **NÊN:** stage KHÔNG sửa input, trả packet mới (CoW `with_artifact`); đặt `BrightnessStage` TRƯỚC `DarkFilterStage`; dùng `with SyncLinearExecutor(...)` để tự teardown; trả result-object có status.
- **TRÁNH:** giữ `Exception` object lâu (traceback retention); trả `None` cho "bỏ frame"; để 1 stage lỗi làm sập cả chuỗi; quên `teardown`.
- **Cạm bẫy (ERRATA):** **E-14** thiếu context manager → quên teardown khi raise giữa chừng (đã thêm `__enter__/__exit__`). R5: result-object thay `Optional` + không giữ Exception (chống traceback retention).

## Tự kiểm (đạt mới qua bài)
- Vì sao dùng result-object (status) thay `None`/exception trần? Phân biệt SKIPPED vs ERROR để làm gì?
- `BaseStage` (Template Method) giúp lớp con đỡ việc gì? Vì sao không giữ `Exception` object?

## Nguồn
- Code thật: `kernel/stage_contract.py`, `runtime/base_stage.py`, `runtime/sync_linear_executor.py`,
  `runtime/stages/*.py`, `profiles/demo_pipeline.py` (đã đọc nguyên văn). · Design: `Design/module-03-build-along/step-04-first-pipeline.md`. · Độ chắc: cao.
