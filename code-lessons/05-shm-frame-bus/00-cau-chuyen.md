# Bài #05 — SHM frame bus: chuyển frame giữa các process KHÔNG copy · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đọc file này TRƯỚC các mẩu chi tiết. Mục tiêu: hiểu **tại sao** frame bus được dựng như vậy (và tại
> sao phải "hardening" cho sản phẩm 24/7), trước khi xem từng dòng. Bám code thật ở
> `vision-platform/src/vision_platform/` (kernel `shm_frame_ref.py`/`shm_layout.py` · runtime/ipc
> `_process_identity.py`/`shm_frame_ring.py`).

---

## 1. Tổng quan — ta đang ở đâu
#01 khung · #02 viên gạch dữ liệu (MediaPacket) · #03 nguồn frame · #04 pipeline (1 process). **Bài #05
cho frame đi QUA RANH GIỚI PROCESS**: camera chạy 1 process, AI/inference chạy process khác — làm sao
đưa ảnh (nặng ~6MB/frame) từ bên này sang bên kia mà KHÔNG chậm.

```
Process A (camera)  ──ghi frame──►  [ SHM ring buffer: N slot ]  ──đọc──►  Process B (inference)
                     ShmFrameWriter            ▲                          ShmFrameReader
                                          ShmFrameRefData (con trỏ nhẹ: slot+generation) đi qua wire
```

Thuật ngữ (gloss 1 dòng — đào sâu ở mẩu):
- **SHM (shared memory / bộ nhớ chia sẻ):** vùng RAM 2 process cùng nhìn thấy → chép 1 lần, cả 2 đọc, khỏi gửi qua ống.
- **zero-copy:** truyền dữ liệu mà KHÔNG copy đi copy lại (chỉ chép vào SHM 1 lần) → nhanh, đỡ RAM.
- **ring buffer (bộ đệm vòng):** N ô (slot) dùng xoay vòng; đầy thì quay lại ô cũ nhất.
- **slot:** 1 ô chứa 1 frame (metadata + vùng data ảnh).
- **generation:** số đếm tăng dần cho mỗi lần ghi 1 slot → chống đọc nhầm frame cũ (xem "ABA" mẩu 6).
- **atomic:** thao tác đọc/ghi "được ăn cả hoặc mất cả", không bị xen giữa → không đọc ra giá trị nửa vời.
- **lock (khoá):** cơ chế để mỗi lúc chỉ 1 process động vào 1 slot → tránh giẫm chân (race condition).

File thật của #05:
| Thành phần | Tầng | File |
|---|---|---|
| `ShmFrameRefData` (DTO + `ring_epoch`) | kernel | `kernel/shm_frame_ref.py` |
| `SlotState`, offsets header v2, ctrl segment, magic | kernel | `kernel/shm_layout.py` |
| `current_identity`, `owner_liveness` (psutil) | runtime/ipc | `runtime/ipc/_process_identity.py` |
| `ShmRingBuffer`, `ShmFrameWriter`, `ShmFrameReader`, recovery, registry, observability | runtime/ipc | `runtime/ipc/shm_frame_ring.py` |

## 2. Vấn đề & TẠI SAO nó là vấn đề
Gửi ảnh 6MB/frame, 30 frame/giây, nhiều camera, giữa các process. Làm ngây thơ (naive):
- **Copy + gửi qua queue/socket:** mỗi frame copy nhiều lần + serialize → CPU/RAM tốn, trễ cao → KHÔNG kịp real-time.
- **Chia SHM nhưng không đồng bộ:** 2 process cùng động 1 slot → **race condition** (reader đọc trúng lúc writer đang ghi → ảnh rách/nửa vời).
- **Đọc nhầm frame cũ (ABA):** reader cầm "con trỏ" tới slot, nhưng writer đã ghi đè slot đó bằng frame mới → reader tưởng vẫn frame cũ.

Và vì đây là **sản phẩm 24/7 (Mỹ+Nhật)**, có thêm nỗi đau **production** mà demo bỏ qua:
- **Process CHẾT giữa chừng khi đang giữ khoá slot** → khoá kẹt vĩnh viễn → slot đó không ai dùng được → dần cạn slot → **cả bus đứng** (bug F-3/F-3b).
- **Nuốt lỗi im lặng** (`except: pass`) → sự cố xảy ra mà không ai biết.
- **Chỉ 1 reader** → không phục vụ được nhiều consumer (inference + recorder + preview...).

**Lực giằng nhau:** *nhanh/zero-copy* ↔ *an toàn khi có sự cố* (process chết, lock poison, đa reader).
(Đoán thử: làm sao vừa zero-copy vừa không bao giờ "đứng bus" khi 1 process chết?)

## 3. Khám phá nhiều hướng (≥2 cách)
- **Cách A — queue/socket copy:** đơn giản, an toàn, nhưng CHẬM + tốn RAM ở 6MB×30fps×N-cam. ✗ real-time.
- **Cách B — SHM + 1 lock toàn ring:** zero-copy nhưng 1 lock chung → nghẽn cổ chai + 1 process chết giữ lock = cả ring kẹt. △
- **Cách C — SHM ring N slot + LOCK MỖI SLOT + `generation` (chống ABA) + đọc `arr.copy()` trước khi nhả:** zero-copy, song song nhiều slot, đọc đúng frame. ✓ ← nền demo.
- **Hardening (production, cách C+):** thêm **lock-free peek trạng thái** (đọc `state` 4-byte atomic không cần lock) + **QUARANTINED** (loại vĩnh viễn slot có owner chết) + **lease + liveness (psutil)** để phát hiện process chết + **reader registry** (đa reader) + **observability** + **1-writer invariant** + **ring epoch** (đổi ring khi hỏng nhiều). ✓✓ ← #05 hiện tại.

## 4. Chốt giải pháp + TẠI SAO thắng
- **Per-slot lock + generation**: mỗi slot serialize riêng (song song tốt); reader chỉ tin data khi `generation` khớp → chống đọc nhầm frame đè (ABA).
- **`state` 4-byte @offset 0, aligned → đọc/ghi ATOMIC không cần lock** (x86-64: store ≤8 byte aligned là atomic — Intel SDM §8.1.1). Nhờ vậy writer/reader **peek** trạng thái slot TRƯỚC khi đụng lock → thấy slot hỏng (QUARANTINED) thì bỏ qua, **không bao giờ đụng khoá chết**.
- **Recovery không "đứng bus":** owner của slot **chết** (kiểm bằng `psutil`, định danh `(pid, create_time)` chống trùng pid) **VÀ** lease (hạn cam kết) quá hạn → đánh slot **QUARANTINED (terminal — loại vĩnh viễn)**. KHÔNG tái dùng vì khoá của OS không "robust" (owner chết thì khoá kẹt ở mức OS — không giải được). Bù lại ring **giảm dần capacity** + phát cảnh báo; hỏng quá ngưỡng → dựng lại ring mới (epoch).
- **Đa reader** qua **reader registry** (mảng ô trong header) — `reader_count` là số ô đang active; reader chết được "reap" (dọn) mà không loại cả slot nếu còn reader sống.
- **Quan sát được:** mọi sự cố phát qua `ObservabilityHook.emit(event, ...)` thay vì nuốt lỗi.
- **1 writer/ring** ép bằng writer registry ở control segment → `generation` không trùng.

Thắng vì: giữ tốc độ zero-copy của demo, NHƯNG thêm các lớp an toàn để chạy 24/7 không đứng — mỗi lớp
giải đúng 1 nỗi đau production cụ thể, có test chứng minh (kể cả **kill process thật** cross-process).

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự nhỏ nhất → xem `00-muc-luc.md`. (Mẩu chi tiết quote nguyên văn code + cite path.)

## 6. Nên làm / Nên tránh (cho bài #05)
- **NÊN:** reader `arr.copy()` xong mới nhả slot; ghi trường `state` CUỐI CÙNG (authority); peek lock-free trước khi acquire; định danh process bằng `(pid, create_time)`; đặt tên ring theo uuid mỗi phiên (cold-start).
- **TRÁNH:** dùng `os.kill(pid, 0)` để kiểm process sống trên **Windows** (= gửi CTRL_C_EVENT → tự nhận `KeyboardInterrupt`, đã kiểm chứng thật!); 2 writer/ring (trùng generation → vỡ ABA); tái dùng slot QUARANTINED (khoá OS không robust); nuốt lỗi `except: pass`.
- **Cạm bẫy (ERRATA):** **E-15** slot kẹt WRITING/READING khi owner chết (F-3/F-3b) → giải bằng lease + quarantine terminal. Chi tiết atomicity: `knowledge-base` + `Design/module-04-deep-dives/02-shm-atomicity-explained.md`.
- **Giới hạn đã ghi rõ (chưa verify):** ARM (chỉ claim x86-64) · ring switchover đầy đủ (sub-spec `shm-ring-epoch-switchover`) · REBUILD_THRESHOLD chưa tuning SLA.

## Tự kiểm (đạt mới qua bài)
- Vì sao SHM + generation nhanh hơn gửi-copy, mà vẫn đọc đúng frame (không ABA)?
- Process chết đang giữ khoá slot → hệ thống làm gì để KHÔNG "đứng bus"? Vì sao QUARANTINED phải là "terminal"?
- Vì sao `state` đặt 4-byte @offset 0? "peek lock-free" giải quyết điều gì?

## Nguồn
- Code thật: `kernel/shm_frame_ref.py`, `kernel/shm_layout.py`, `runtime/ipc/_process_identity.py`,
  `runtime/ipc/shm_frame_ring.py` (đã đọc nguyên văn + test thật: full 180 passed/1 skipped · lint 5 kept/0 broken).
- Spec hardening: `.kiro/specs/shm-production-hardening/` (design + requirements + tasks). Deep-dive atomicity:
  `Design/module-04-deep-dives/02-shm-atomicity-explained.md`. · Độ chắc: cao (code + test chạy thật).
