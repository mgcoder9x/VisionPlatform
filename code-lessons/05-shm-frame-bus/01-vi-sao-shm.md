# Mẩu 01 — Vì sao dùng SHM (shared memory) để chuyển frame giữa process

> Bám file: `runtime/ipc/shm_frame_ring.py` + `kernel/shm_frame_ref.py` (trạng thái sau spec hardening).
> Đây là mẩu **động lực** (tại sao cần SHM) — chưa đi vào từng dòng code, chuẩn bị cho mẩu 02+.

## 1. Thuộc về đâu
Tầng **runtime/ipc** (transport — lo việc I/O đưa dữ liệu qua ranh giới process). Nằm SAU #04 (pipeline
1 process): giờ camera và inference ở **2 process khác nhau** → cần "đường ống" chuyển frame.

## 2. Cần biết trước
- [process](../../knowledge-base/00-GLOSSARY.md) = 1 chương trình đang chạy, có vùng nhớ RIÊNG (process A không thấy biến của process B).
- frame = 1 ảnh (mảng numpy `uint8`, ví dụ 1920×1080×3 ≈ 6 MB).
- [MediaPacket](../02-data-objects/08-mediapacket-immutable.md) (#02) = viên gạch dữ liệu đi trong pipeline.

## 3. Code thật (vị trí, chưa đi sâu)
Chưa quote code ở mẩu này. Chỉ cần biết **2 nơi**:
- Transport (đường ống thật): `runtime/ipc/shm_frame_ring.py`.
- "Con trỏ" mô tả frame (đi qua ống): `kernel/shm_frame_ref.py` → `ShmFrameRefData` (mẩu 02).

## 4. Giải thích từng ý nhỏ nhất
- **Process có RAM riêng** → không thể "đưa thẳng biến ảnh" từ A sang B. Phải có cơ chế chung.
- **SHM (shared memory)** = một vùng RAM mà **cả A lẫn B cùng ánh xạ vào** (OS cho phép). A ghi ảnh vào đó 1 lần; B đọc trực tiếp — **không copy qua lại**.
- Cái đi "qua ống" (ZMQ/queue) chỉ là **con trỏ nhẹ** (`ShmFrameRefData`: tên ring + số slot + generation, vài chục byte), KHÔNG phải 6 MB ảnh.

## 5. Là gì (1–2 câu)
SHM frame bus = **vùng RAM chia sẻ + cơ chế đồng bộ** để nhiều process truyền ảnh nặng cho nhau mà chỉ
chép 1 lần (zero-copy), thay vì gửi cả ảnh qua ống.

## 6. Tại sao tồn tại / vấn đề nó giải
Real-time nhiều camera: 6 MB × 30 fps × N camera. Nếu **copy + serialize + gửi socket** mỗi frame →
CPU/RAM/độ trễ tăng vọt → KHÔNG kịp. SHM giải bằng: chép 1 lần vào RAM chung, các process đọc tại chỗ.

## 7. Dùng ở đâu trong project
- Camera process (writer) ghi frame vào ring → trả `ShmFrameRefData`.
- Inference process (reader) nhận ref (qua wire) → đọc frame từ SHM.
- Xem luồng tổng ở `00-cau-chuyen.md` §1.

## 8. Không có nó thì sao
Phải copy toàn bộ ảnh mỗi lần truyền → nghẽn băng thông + trễ → mất tính real-time; hoặc nhét ảnh vào
message queue → serialize/deserialize tốn kém.

## 9. Ví von
SHM giống **bảng trắng chung trong phòng họp**: 1 người viết lên bảng, mọi người CÙNG nhìn — thay vì
photo ra N bản phát cho từng người (copy tốn giấy + thời gian).

## 10. Liên kết bức tranh lớn
`runtime/ipc` là **cửa ra vào giữa các process**. Frame đi: camera(writer) → SHM ring → inference(reader).
`ShmFrameRefData` (kernel, thuần) là "vé gửi đồ" nhẹ đi qua ống; ảnh nặng nằm im trong SHM.

## 11. Cạm bẫy (+errata)
- Bảng trắng chung → 2 người viết/đọc cùng lúc dễ **giẫm chân** (race condition) → phải có **lock** + `generation` (mẩu 05/06).
- Process chết khi đang giữ bảng → kẹt (F-3/F-3b, ERRATA E-15) → cần recovery (mẩu 09).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao gửi ảnh 6 MB qua socket là chậm, còn SHM thì nhanh? Cái gì thực sự "đi qua ống"?
- Hai process có thấy biến của nhau không? SHM giải quyết điều đó thế nào?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng (theo LESSON-RULES §2).

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py`, `kernel/shm_frame_ref.py` (vị trí layer). · Deep-dive:
  `Design/module-04-deep-dives/02-shm-atomicity-explained.md`. · Độ chắc: cao (khái niệm nền + code tồn tại thật).
