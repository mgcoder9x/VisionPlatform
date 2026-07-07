# Design Document

> **Trạng thái:** PHA 1 (design) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục (R1 port · R2 packet dùng port · R3 bằng chứng).
> **Cập nhật lúc:** 2026-07-06.

## Overview

Mục tiêu: đóng **seam K-038** — `MediaPacket.media_ref` đang **cứng kiểu concrete `InMemoryArrayRef`**,
khiến World-A (Stage pipeline chạy in-process trên frame in-memory) và World-B (SHM/ZMQ cross-process)
không hợp qua cùng 1 packet. Giải pháp **bản chất, ADDITIVE**: rút 1 **port `IMediaRef`** (Protocol ở
layer kernel) mô tả *"tham chiếu frame materialize được ra ndarray"*, rồi **nới type hint**
`MediaPacket.media_ref: InMemoryArrayRef → IMediaRef`. `InMemoryArrayRef` **không đổi 1 dòng** (đã có
`.array` → thoả port theo structural typing).

**Vì sao đây là gốc, không phải ngọn (bám yêu cầu user "fix bản chất"):** vấn đề không phải "thiếu 1 impl
SHM", mà là **packet phụ thuộc chiều sai** — data-model cấp cao (packet) trỏ thẳng vào 1 impl cụ thể
(in-memory). Đảo phụ thuộc về 1 port là sửa đúng chỗ gãy. Sau khi có port, thêm `ShmMediaRef` (bước sau)
chỉ là *thêm 1 impl*, KHÔNG phải sửa lại packet/Stage.

**Phạm vi PHA này (giữ bước nhỏ):** CHỈ port + nới type + 1 impl-chứng-minh trong test. `ShmMediaRef`,
`PipelineRunner`, wiring Stage-over-SHM đều là **Non-Goal** (đã ghi ở requirements) — chỉ để lại ghi chú
thiết kế cho bước sau.

**Ràng buộc kiểm chứng (chống bịa — đã verify bằng grep + đọc file):**
- Consumers của `media_ref` trong `src` CHỈ có 2 chỗ, đều dùng `packet.media_ref.array`:
  `runtime/stages/brightness_stage.py` (`frame = packet.media_ref.array`) và
  `profiles/demo_pipeline.py` (`final.media_ref.array.shape`). Không nơi nào gọi API khác của ref.
- kernel **đã** import numpy trực tiếp (`media_packet.py`) → đặt Protocol có `array: np.ndarray` ở kernel
  KHÔNG phá contract import-linter (contract kernel cấm cv2/torch/zmq/multiprocessing/shared_memory... —
  numpy KHÔNG nằm trong danh sách cấm).
- kernel **cấm** `multiprocessing`/`shared_memory` (contract "Kernel chi phu thuoc domain") → `ShmMediaRef`
  (đọc SHM slot ra ndarray) **bắt buộc** sống ở `runtime/ipc`, KHÔNG ở kernel. Đây là lý do kỹ thuật vì
  sao ShmMediaRef là bước sau, không gộp PHA này.

## Architecture

```
                 kernel (đảo phụ thuộc về port)
   ┌─────────────────────────────────────────────┐
   │  IMediaRef (Protocol)   ← MỚI                 │
   │      property array -> np.ndarray             │
   │                                               │
   │  MediaPacket.media_ref: IMediaRef  ← NỚI TYPE │
   │                                               │
   │  InMemoryArrayRef  (KHÔNG đổi — thoả IMediaRef│
   │                     theo structural typing)   │
   └───────────────▲───────────────────▲───────────┘
                   │ implements         │ implements (bước SAU, ngoài PHA này)
       InMemoryArrayRef (kernel)   ShmMediaRef (runtime/ipc) ── đọc SHM slot → ndarray
       [World-A: in-process]       [World-B: cross-process]
```

**Nguyên lý:** packet phụ thuộc **abstraction** (IMediaRef), impl phụ thuộc abstraction. Chiều phụ thuộc
in-mem↔SHM giờ hội tụ tại port ở kernel → Stage viết trên `packet.media_ref.array` chạy được với BẤT KỲ
impl nào, kể cả impl SHM tương lai.

**Đặt Protocol ở đâu — quyết định + lý do:** tạo **file mới `kernel/media_ref.py`** chứa `IMediaRef`
(single-responsibility, dễ đọc, dễ mở rộng docstring), rồi `media_packet.py` import nó. KHÔNG nhét vào
`media_packet.py` để tránh trộn "định nghĩa port" với "định nghĩa DTO + impl". `InMemoryArrayRef` **giữ
nguyên chỗ cũ** (không di dời — di dời sẽ đổi import path của nhiều nơi = KHÔNG còn additive tối thiểu).

## Components and Interfaces

### C1 — `kernel/media_ref.py` (MỚI): `IMediaRef`
- Là `typing.Protocol`, đánh dấu `@runtime_checkable` để test có thể `isinstance(x, IMediaRef)` kiểm
  structural (runtime_checkable chỉ kiểm SỰ TỒN TẠI thuộc tính `array`, không kiểm kiểu trả về — đủ cho R3.2).
- Khai báo **1 thành viên tối thiểu**: `array: np.ndarray` (property/attribute) — "materialize frame ra
  ndarray read-only". Docstring nêu contract read-only-by-convention (giống InMemoryArrayRef hiện tại).
- KHÔNG thêm method thừa (no `.shape`, no `.close()`...) — YAGNI. Consumers hiện chỉ cần `.array`. Mở rộng
  khi có impl thật cần (vd `ShmMediaRef` có thể thêm `.release()` sau, nhưng KHÔNG ép vào port bây giờ).
- Import: chỉ `numpy` + `typing`. KHÔNG import gì trong `vision_platform` (port là đỉnh phụ thuộc).

### C2 — `kernel/media_packet.py` (SỬA TỐI THIỂU): nới type hint
- Thêm `from vision_platform.kernel.media_ref import IMediaRef`.
- Đổi annotation field: `media_ref: InMemoryArrayRef` → `media_ref: IMediaRef`.
- **KHÔNG đổi runtime behavior**: `__post_init__`/`__getstate__`/`__setstate__`/CoW giữ nguyên (chúng thao
  tác trên object nói chung, không gọi API riêng của InMemoryArrayRef). `InMemoryArrayRef` vẫn định nghĩa
  tại file này (không di dời).
- Backward-compat: mọi caller `MediaPacket(media_ref=InMemoryArrayRef(...))` vẫn hợp lệ (InMemoryArrayRef
  *là* một IMediaRef). Chỉ là type hint rộng hơn → không ai gãy.

### C3 — `InMemoryArrayRef` (KHÔNG SỬA)
- Đã có `array: np.ndarray` → thoả `IMediaRef` theo structural typing. Không thêm base-class, không thêm
  decorator. Giữ nguyên `from_owned_array`/`from_copy`/`__post_init__`/`__setstate__`.

### C4 — Ghi chú thiết kế `ShmMediaRef` (KHÔNG code PHA này — chỉ định hướng)
- Sẽ ở `runtime/ipc/` (kernel cấm shared_memory). Cầm `ShmFrameRefData` (đã có) + 1 cách map slot→ndarray
  (qua reader/coordinator hiện có ở `runtime/ipc/shm_frame_ring.py`). Property `array` sẽ đọc slot, verify
  `generation`/`ring_epoch` (stale → raise/None theo chính sách bước sau). Ghi ra đây để chứng minh port
  ĐỦ RỘNG cho SHM, nhưng KHÔNG hiện thực bây giờ.

## Data Models

Không có DTO mới ngoài **Protocol** `IMediaRef` (interface, không phải struct dữ liệu). `MediaPacket` giữ
nguyên các field; chỉ đổi *kiểu khai báo* của `media_ref`. `ShmFrameRefData` (đã có) không đổi.

Bề mặt port (chốt tối thiểu):

| Thành viên | Kiểu | Ý nghĩa | Ai cần |
|---|---|---|---|
| `array` | `np.ndarray` (read-only by contract) | materialize frame hiện tại ra ndarray | brightness_stage, demo_pipeline, mọi Stage tương lai |

## Correctness Properties

### Property 1: Structural conformance (InMemoryArrayRef thoả port, không sửa)
`InMemoryArrayRef` phải thoả `IMediaRef` mà KHÔNG cần thay đổi định nghĩa của nó. Kiểm được bằng
`isinstance(InMemoryArrayRef.from_copy(arr), IMediaRef)` (nhờ `@runtime_checkable`) trả `True`, và mypy/type
hint chấp nhận nó ở vị trí `IMediaRef`.
**Validates: Requirements 1.2**

### Property 2: Substitutability (Liskov — impl khác cắm được vào packet + Stage)
Một impl `IMediaRef` KHÁC `InMemoryArrayRef` (vd `_FakeMediaRef` wrap ndarray theo cách khác) khi đặt vào
`MediaPacket.media_ref` phải khiến `BrightnessStage.process(packet)` / mọi consumer đọc `.array` chạy đúng
Y HỆT như với InMemoryArrayRef. Đây là bằng chứng abstraction THẬT (không chỉ type-hint).
**Validates: Requirements 2.1, 3.1**

### Property 3: Behavioral invariance (không hồi quy)
Sau thay đổi, toàn bộ hành vi runtime cũ giữ nguyên: 364 test cũ xanh, lint 5 kept/0 broken (contract layer
không đổi vì numpy không bị cấm ở kernel), pickle round-trip `MediaPacket`/`InMemoryArrayRef` vẫn giữ
`array` read-only (đã có `__setstate__` re-lock).
**Validates: Requirements 2.2, 2.3**

### Property 4: Read-only contract được giữ qua port
Đọc `packet.media_ref.array` trả ndarray read-only-by-convention giống trước (InMemoryArrayRef set
`write=False`). Port KHÔNG làm yếu contract này (impl chịu trách nhiệm materialize read-only).
**Validates: Requirements 1.1, 3.2**

## Testing Strategy

**File test mới:** `tests/test_media_ref_port.py`.

1. **P1 — conformance:** `isinstance(InMemoryArrayRef.from_copy(np.zeros((4,4))), IMediaRef) is True`;
   dùng nó ở chỗ nhận `IMediaRef` không lỗi type (kiểm bằng chạy thật + để mypy tương lai bắt).
2. **P2 — substitutability (bằng chứng cốt lõi R3.1):** định nghĩa `_FakeMediaRef` (materialize `.array`
   theo cách khác InMemoryArrayRef, vd giữ ndarray riêng), gói vào `MediaPacket`, chạy `BrightnessStage`
   → `StageResult.SUCCESS` + `artifacts["brightness"]` khớp `frame.mean()` kỳ vọng.
3. **P3/P4 — invariance + read-only (R3.2):** round-trip pickle `MediaPacket` mang `InMemoryArrayRef` →
   sau unpickle `media_ref.array.flags.writeable is False` + dữ liệu bằng nhau; `InMemoryArrayRef` vẫn
   `isinstance IMediaRef`.
4. **Regression toàn cục:** chạy `.venv\Scripts\python.exe -m pytest -q` kỳ vọng **365 passed/1 skipped**
   (364 cũ + file mới) + `.venv\Scripts\lint-imports.exe` kỳ vọng **5 kept/0 broken** +
   `get_diagnostics` trên spec = 0.

**Định nghĩa DONE:** cả 4 nhóm trên có bằng chứng (lệnh + output thật) → mới đổi ✅. Chưa chạy = [chưa kiểm].

## Error Handling

- **Impl không có `.array` hợp lệ:** đây là lỗi lập trình (vi phạm port). `MediaPacket` KHÔNG tự validate
  `media_ref` (giữ nguyên hành vi hiện tại — packet không kiểm kiểu media_ref runtime). Consumer gọi
  `.array` sẽ `AttributeError` fail-fast — chấp nhận được vì đây là bug wiring, không phải input runtime.
- **`array` trả ndarray writable (impl ẩu):** port ghi contract read-only-by-convention nhưng KHÔNG ép ở
  runtime (giống InMemoryArrayRef hiện tại chỉ set write=False cho chính nó). Trách nhiệm thuộc impl. Test
  P4 kiểm InMemoryArrayRef giữ read-only; impl SHM tương lai tự chịu.
- **PHA này KHÔNG thêm exception type mới, KHÔNG đổi luồng lỗi Stage/Executor hiện có** (StageResult.error
  vẫn như cũ). Không có failure mode mới phát sinh vì thay đổi thuần là nới type hint + thêm Protocol.

## Glossary

- **IMediaRef** — port (Protocol) trừu tượng cho "tham chiếu frame materialize ra ndarray". Xem C1.
- **InMemoryArrayRef** — impl in-process của IMediaRef, ôm ndarray read-only (đã tồn tại). Xem C3.
- **ShmMediaRef** — impl tương lai đọc frame từ SHM slot (Non-Goal PHA này). Xem C4.
- **structural typing** — thoả Protocol nhờ CÓ đúng thành viên (`array`), không cần kế thừa tường minh.
- **seam K-038** — điểm gãy: packet cứng kiểu concrete khiến World-A/World-B không hợp. Xem `04-things-to-know.md`.
