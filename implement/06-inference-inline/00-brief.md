# Vấn đề #06 — Inference protocol + Detector port + Inline client (PHA 1: valid thiết kế)

> **Nguồn Design:** `Design/module-03-build-along/step-06-add-inference.md` (đã đọc nguyên văn).
> **Trạng thái:** 🔵 PHA 1 (design-validation) — CHỜ user duyệt 2 deviation không tầm thường (F-1, F-2) trước khi code.
> **Cập nhật lúc:** 2026-07-04.

## 1. Mục tiêu #06 (theo Design, đã neo)
Xây tầng inference mức **INLINE** (cùng process, chưa ZMQ):
1. `kernel/inference_protocol.py` — DTO: `InferenceRequest`, `Detection`, `InferenceError`, `InferenceResponse`.
2. `kernel/ports/detector.py` — `IDetector` Protocol (`detect`/`setup`/`teardown`).
3. `adapters/fake_detector.py` — `FakeDetector` deterministic (confidence = brightness/255, box `MODEL_INPUT`).
4. Inline inference client — đọc frame từ SHM ring (#05) → detect → trả `InferenceResponse` echo `request_id`.
5. Test: 9 test (3 detector · 3 DTO · 3 client, gồm **request_id correlation**).

**Bài học lõi Design nhắm tới:** *request_id correlation pattern* trong async IPC (client match response theo `request_id`). ZMQ ROUTER/DEALER cross-process = **production, HOÃN** (Design ghi rõ).

## 2. Đối chiếu Design ↔ CODE THẬT (chống bịa — đã đọc file)
| Design giả định | Code THẬT (đã đọc) | Kết luận |
|---|---|---|
| package `vision_demo` | `vision_platform` | Đổi tên nhất quán (không phải drift) |
| `domain.bbox.BBox(x,y,w,h,space)` + `CoordinateSpace.MODEL_INPUT` | `bbox.py`: đúng có `BBox` + `CoordinateSpace{ORIGINAL_FRAME,MODEL_INPUT,NORMALIZED,DISPLAY}` | ✅ khớp |
| `reader.read(slot, generation) -> frame\|None` | `ShmFrameReader.read(slot_idx, expected_gen, *, ring_epoch=None) -> Optional[np.ndarray]` | ✅ tương thích + có thêm `ring_epoch` |
| — | `ShmFrameReader.read_ref(ref: ShmFrameRefData)` tự kiểm `ring_epoch` (P0-3 stale) | 🎯 đường sạch hơn |
| `writer.write(f)` trả ref có `.slot/.generation/...` | `ShmFrameWriter.write(frame) -> Optional[ShmFrameRefData]` (có thể **None** khi hết slot) | ⚠️ test phải xử lý None |
| DTO frame-ref field: `shm_ring_name/shm_slot/shm_generation` | `ShmFrameRefData{ring_name, slot, generation, height, width, channels, ring_epoch=0}` | ⚠️ thiếu `ring_epoch` ở request |
| `InlineInferenceClient` đặt ở `adapters/` | Contract import-linter #5: **adapters CẤM import runtime** | 🔴 vi phạm (F-1) |

## 3. FINDINGS (rủi ro thiết kế phát hiện ở PHA 1)

### 🔴 F-1 (CRITICAL — kiến trúc): InlineInferenceClient KHÔNG được đặt ở `adapters/`
- **Bằng chứng:** `pyproject.toml` contract #5 `"Adapters la leaf — khong import nguoc len runtime/application/profiles"` → `source_modules=["vision_platform.adapters"]`, `forbidden_modules` chứa `vision_platform.runtime`.
- Client PHẢI import `ShmFrameReader` (ở `runtime.ipc.shm_frame_ring`) → nếu đặt ở `adapters/` thì `lint-imports` sẽ **BROKEN**.
- **Bản chất (không phải fix ngọn):** InlineInferenceClient KHÔNG phải leaf-adapter. Nó là **service điều phối**: ghép `runtime` (SHM reader) + `IDetector` **port** (tiêm DI). Đúng vai `application/` (cùng chỗ với `ring_supervisor.py`, `writer_epoch_coordinator.py`). Layering `domain←kernel←runtime←application` cho phép `application→runtime`; contract #4 chỉ cấm `application→adapters/profiles` (client dùng *port* `IDetector`, không import `FakeDetector` cụ thể → hợp lệ).
- **Khuyến nghị:** đặt `application/inline_inference_client.py`. `FakeDetector` vẫn ở `adapters/` (leaf, chỉ import domain+kernel — hợp lệ).

### 🔴 F-2 (correctness — tích hợp switchover #05): InferenceRequest THIẾU `ring_epoch`
- **Bằng chứng:** `ShmFrameRefData.ring_epoch` (P0-3) + `read()` trả `None` khi `ring_epoch != ring hiện tại` (stale sau switchover). Design `InferenceRequest` chỉ có `shm_generation`, KHÔNG có epoch.
- **Hệ quả nếu giữ nguyên Design:** sau một lần switchover ring (feature #05 vừa xây), request mang slot/gen của epoch cũ có thể trùng slot/gen epoch mới → đọc nhầm frame (không bị stale-detect). Đây là lỗ hổng **bản chất** vì #06 build TRÊN nền ring đã có epoch.
- **Khuyến nghị:** `InferenceRequest` mang đủ trường của `ShmFrameRefData` **gồm `ring_epoch`** (hoặc nhúng thẳng `frame_ref: ShmFrameRefData`); client gọi `reader.read_ref(ref)` để hưởng stale-check sẵn có. Đường sạch, tái dùng invariant #05, không viết lại.

### 🟡 F-3 (API fidelity): dùng `read_ref` thay `read(slot, gen)` trần
- Lý do: `read_ref` tự truyền `ring_epoch` (đóng luôn F-2) + đọc đúng 1 nguồn sự thật `ShmFrameRefData`. Tránh lặp 6 field rời trong request.

### 🟡 F-4 (robustness test): `write()` trả `Optional` → test phải assert khác None
- Design test `refs.append(writer.write(f))` không check None. Ring 3+ slot ghi 3 frame sẽ không None, nhưng test nên `assert ref is not None` để fail-fast đúng nghĩa.

### 🟢 F-5 (scope — ghi nhận, không phải lỗi): #06 = INLINE, KHÔNG phải ZMQ
- Tracker gắn nhãn "ZMQ inference service" nhưng `step-06` Design xây **inline client**; ZMQ ROUTER/DEALER cross-process là **production, hoãn** (giống switchover từng tách sub-spec). #06 giao: DTO + port + FakeDetector + InlineClient + correlation. → cập nhật ghi chú tracker (C-entry).

### 🟢 F-6 (đã kiểm hợp lệ): `kernel/inference_protocol.py` import `domain.bbox` — HỢP LỆ
- Contract #2 (Kernel) `forbidden_modules` KHÔNG chứa `vision_platform.domain` (chỉ cấm I/O ngoài + runtime/application). `numpy` cũng không bị cấm ở kernel → `IDetector` import numpy OK.

## 4. Kế hoạch PHA 2 (TDD) — CHỜ DUYỆT trước khi code
1. `kernel/inference_protocol.py`: 4 DTO frozen. `InferenceRequest` mang `ring_epoch` (F-2). `InferenceError` chỉ giữ string (không giữ Exception — pattern R5 đã dùng ở #04). `InferenceResponse.is_success`.
2. `kernel/ports/detector.py`: `IDetector` Protocol.
3. `adapters/fake_detector.py`: `FakeDetector` (leaf, domain+kernel).
4. `application/inline_inference_client.py` (F-1): DI `ring` + `detector: IDetector`; `infer()` dùng `reader.read_ref` (F-3); lỗi read → `InferenceError(retryable=False)`; exception detect → bọc string.
5. `tests/test_step_06_inference.py`: 9 test + correlation; assert `write() is not None` (F-4). Chạy `pytest` thật + `lint-imports` (kỳ vọng 5 kept/0 broken — nhất là contract adapters/application sau khi dời file).

## 5. Cần user chốt (2 deviation không tầm thường vs Design gốc)
- **F-1:** đồng ý dời `InlineInferenceClient` → `application/` (thay vì `adapters/` như Design)?
- **F-2:** đồng ý thêm `ring_epoch` vào `InferenceRequest` + dùng `read_ref`?

> Cả hai là fix **bản chất** để #06 khớp kiến trúc thật + tích hợp đúng switchover #05. Nếu duyệt "theo khuyến nghị" → tôi làm PHA 2 theo kế hoạch §4.
