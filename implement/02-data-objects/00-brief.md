# Vấn đề #02 — Domain BBox + Kernel ReadResult + MediaPacket

> Nguồn Design: `Design/module-03-build-along/step-02-first-mediapacket.md`. (Brief backfill — chọn A.)

## Mục tiêu
3 thành phần cốt lõi: `BBox` (value object + CoordinateSpace tag), `ReadResult[T]` (6 status explicit),
`MediaPacket`/`InMemoryArrayRef` (immutable container + CoW).

## File (4) — ở `vision-platform/`, pkg `vision_platform`
- `domain/bbox.py`, `kernel/read_result.py`, `kernel/media_packet.py`, `tests/test_step_02_domain.py`.

## Concept cốt lõi (để học/viết lại)
- **CoordinateSpace tag bắt buộc** (no default) → chống bug "bbox lệch sau resize".
- **ReadResult 6 status** thay `Optional[Frame]` → caller buộc handle EOF/TIMEOUT/ERROR... rõ ràng.
- **Immutable container + CoW**: `MappingProxyType(dict(...))` (defensive copy nông) + `setflags(write=False)`;
  `with_*` trả packet mới. `MediaPacket` KHÔNG hashable (chứa ndarray).
- **2 factory** `from_owned_array` (zero-copy) vs `from_copy` (defensive) — ý định ownership.

## Findings (ERRATA) — phát hiện + xử lý
- **E-11 (B+C):** pickle làm mất `write=False` (numpy 2.4.6 verify thật) → thêm `__setstate__` re-lock;
  thêm `isinstance` type-check (TypeError rõ nghĩa).
- **E-12 (Risk 3):** `BBox` NORMALIZED chưa validate [0,1] → thêm validate. (Risk1 shallow-immut + Risk2
  buffer-reuse: GHI NHẬN, không auto-fix — xem ERRATA.)

## Validate (thật)
- `pytest` → **21 passed** (2 smoke + 19 step-02) · `lint-imports` → **5 kept/0 broken**.

## Trạng thái: ✅ XONG.
