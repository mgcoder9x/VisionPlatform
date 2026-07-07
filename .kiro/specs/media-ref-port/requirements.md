# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid trước design/code.
> **Mục đích:** đóng seam K-038 — trừu tượng `MediaPacket.media_ref` thành **port `IMediaRef`** để 1 packet
> mang được frame in-memory HOẶC frame SHM → Stage pipeline chạy được trên CẢ HAI → nghiệp vụ scale đa-tiến-trình dễ.
> **Cập nhật lúc:** 2026-07-06.

## Introduction

Audit base (K-038) phát hiện: `MediaPacket.media_ref` **cứng kiểu `InMemoryArrayRef`** (concrete), trong khi
sản phẩm là **real-time multi-camera** (AGENTS.md §0) cần chạy đa-tiến-trình chia sẻ frame qua SHM. Hệ quả:
World-A (Stage pipeline + InMemoryArrayRef, in-process) và World-B (SHM/ZMQ cross-process, dùng ShmFrameRefData)
**không hợp qua packet** — nghiệp vụ viết bằng Stage không chạy được trên hạ tầng SHM.

**Ranh giới nguồn (chống bịa):** verify bằng grep toàn `src` — consumers CHỈ dùng `packet.media_ref.array`
(brightness_stage, demo_pipeline) + construct `InMemoryArrayRef.from_copy/from_owned_array`. Vậy abstraction
tối thiểu = 1 thuộc tính `.array -> np.ndarray`. Đây là thay đổi **ADDITIVE, backward-compat** (InMemoryArrayRef
đã có `.array`), KHÔNG rebuild — chỉ mở rộng type + thêm 1 Protocol.

## Requirements

### Requirement 1: Port `IMediaRef` (kernel)
**User Story:** Là kiến trúc sư, tôi muốn 1 port trừu tượng cho "tham chiếu frame", để packet không phụ thuộc cụ thể in-memory hay SHM.
#### Acceptance Criteria
- 1.1 — PHẢI có `IMediaRef` (Protocol, layer kernel) khai báo tối thiểu thuộc tính `array: np.ndarray` (materialize frame ra ndarray read-only).
- 1.2 — `InMemoryArrayRef` (đã có) PHẢI thoả `IMediaRef` KHÔNG cần sửa (đã có `.array`) — structural typing.
- 1.3 — numpy được phép ở kernel (đã có tiền lệ read_result/ports); Protocol KHÔNG import multiprocessing/shared_memory.

### Requirement 2: `MediaPacket.media_ref` dùng port (additive, không phá)
**User Story:** Là kỹ sư, tôi muốn packet mang bất kỳ `IMediaRef` nào, để cùng 1 Stage pipeline chạy in-mem lẫn SHM.
#### Acceptance Criteria
- 2.1 — `MediaPacket.media_ref` PHẢI có kiểu `IMediaRef` (nới type hint từ `InMemoryArrayRef`). Runtime KHÔNG đổi hành vi.
- 2.2 — MỌI usage hiện tại (`packet.media_ref.array`, `InMemoryArrayRef.from_*`, pickle `__getstate__/__setstate__`) PHẢI giữ nguyên chạy đúng.
- 2.3 — 364 test cũ PHẢI xanh; lint 5/0 giữ nguyên (Protocol ở kernel không phá contract).

### Requirement 3: Bằng chứng abstraction hoạt động (không chỉ type-hint)
**User Story:** Là kỹ sư, tôi muốn test chứng minh 1 `IMediaRef` KHÁC InMemoryArrayRef cắm được vào packet + Stage đọc được.
#### Acceptance Criteria
- 3.1 — Test: 1 impl `IMediaRef` giả (vd wrap ndarray khác cách) bỏ vào `MediaPacket` → `BrightnessStage`/đọc `.array` chạy đúng.
- 3.2 — Test: `InMemoryArrayRef` vẫn thoả `IMediaRef` (isinstance/duck) + round-trip pickle giữ read-only.

## Non-Goals (HOÃN — giữ bước nhỏ, chống phình)
- **ShmMediaRef** (impl đọc SHM slot → ndarray, ở runtime/ipc) — bước SAU (cần reader coordinator). Chỉ GHI chú thiết kế.
- **PipelineRunner** (source→stages→sink loop + backpressure, Gap-1 K-037) — bước SAU riêng.
- **Stage-over-SHM wiring** end-to-end — sau khi có ShmMediaRef + PipelineRunner.
- KHÔNG đổi logic SHM/ZMQ hiện có; KHÔNG rebuild gì.

## Tiêu chí ĐẬU (Definition of Done)
`IMediaRef` port + `MediaPacket.media_ref: IMediaRef` + InMemoryArrayRef thoả port (không sửa) + test chứng minh
impl khác cắm được + 364 test cũ xanh + lint 5/0 + 0 diagnostic. Additive thuần, không phá gì.

## Glossary
- **IMediaRef** — port (Protocol, kernel) trừu tượng cho "tham chiếu frame materialize ra ndarray".
- **InMemoryArrayRef** — impl in-process (đã có), ôm ndarray read-only; thoả IMediaRef theo structural typing.
- **ShmMediaRef** — impl tương lai đọc frame từ SHM slot (Non-Goal PHA này, sống ở runtime/ipc).
- **media_ref** — field của MediaPacket trỏ tới dữ liệu frame; hiện cứng kiểu concrete → nới thành port.
- **seam K-038** — điểm gãy khiến World-A (in-process Stage) và World-B (SHM cross-process) không hợp qua packet.
