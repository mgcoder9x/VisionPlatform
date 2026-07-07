# Bài #03 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung vấn đề→giải pháp). Rồi tới các mẩu nhỏ nhất dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + tự giải thích lại được.

| Mẩu | File | Nội dung | Trạng thái |
|-----|------|----------|-----------|
| 01 | `01-protocol-port.md` | `Protocol` + `IFrameSource` — port theo structural typing | ✅ đã viết |
| 02 | `02-hop-dong-iframesource.md` | Hợp đồng port: setup/read/teardown + is_finite/source_id + idempotent + "read trả ReadResult, không None" | ✅ đã viết |
| 03 | `03-fakeframesource-khung.md` | `FakeFrameSource`: dataclass + `field(init=False)` + setup/teardown idempotent | ✅ đã viết |
| 04 | `04-fakeframesource-read.md` | `.read()`: `np.full` + `frame_count%256` + max_frames→EOF + inject_error→ERROR + check setup | ✅ đã viết |
| 05 | `05-source-id-unique-e13.md` | `source_id` DUY NHẤT — `itertools.count` + `default_factory` (ERRATA E-13) | ✅ đã viết |
| 06 | `06-noiseframesource.md` | `NoiseFrameSource`: `np.random.default_rng` + seed tái lập — vì sao cần ≥2 adapter | ✅ đã viết |
| 07 | `07-contract-test.md` | Contract test: `pytest` parametrize + builder fixture + "1 suite, mọi adapter phải qua" | ✅ đã viết |

> Tạo từng mẩu một. Xong #03 → sang #04 (`04-pipeline`).
> **Sơ đồ (`diagrams/`, nguồn Draw.io — xuất SVG bằng extension để xem nhúng):** `port-adapter-hexagonal.drawio` (tổng quan, nhúng ở cau-chuyen) · `fake-read-flow.drawio` (mẩu 04) · `contract-test-matrix.drawio` (mẩu 07).
> Ghi chú: số mẩu theo nội dung (#03 = 7 mẩu) — không ép bằng bài khác.
