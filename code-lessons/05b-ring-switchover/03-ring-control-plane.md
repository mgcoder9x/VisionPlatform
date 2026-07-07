# Mẩu 03 — `RingControlPlane`: ghi/đọc "ring hiện tại" (authority atomic + fail-fast)

> Bám code thật `runtime/ipc/ring_control_plane.py` (đọc nguyên văn khi viết). Mẩu 02 định nghĩa **byte**;
> mẩu này là **hành vi** đọc/ghi vùng nhớ đó qua SHM thật.

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc` (được phép dùng `multiprocessing`/`shared_memory` + import kernel layout).
- **Vai:** tạo/attach control-plane segment; cho supervisor **publish** ring mới, cho writer/reader **read_current**.

## 2. Cần biết trước
- Mẩu 02: layout (magic@0, version@4, epoch@16, ring_name@24, 128B) + `check_cp_header` + `encode/decode_ring_name`.
- Gloss: **attach** = mở vào 1 vùng SHM đã tồn tại · **authority atomic** = "công tắc" mà chỉ khi nó đổi thì
  bản ghi mới được coi là có hiệu lực · **DI (dependency injection / tiêm phụ thuộc)** = truyền hàm/đối tượng
  từ ngoài vào để dễ thay/test. (Link `knowledge-base/00-GLOSSARY.md` nếu cần.)

## 3. Code thật (quote nguyên văn — `runtime/ipc/ring_control_plane.py`)

**(a) Attach fail-fast (trong `__init__`, nhánh `create=False`):**
```python
        else:
            shm = shared_memory.SharedMemory(name=name)
            check_cp_header(bytes(shm.buf[:_HEADER_BYTES]))   # fail-fast nếu magic/version sai
        self._shm = shm
```

**(b) Publish — ghi TÊN trước, EPOCH cuối:**
```python
    def publish(self, epoch: int, ring_name: str) -> None:
        """Công bố ring hiện tại (CHỈ supervisor gọi). Ghi TÊN trước, `current_epoch` CUỐI (authority atomic)."""
        encoded = encode_ring_name(ring_name)
        self._shm.buf[OFFSET_CP_RING_NAME:OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES] = encoded
        struct.pack_into(CP_EPOCH_FMT, self._shm.buf, OFFSET_CP_EPOCH, epoch)   # ghi CUỐI
```

**(c) Read_current — đọc epoch + tên:**
```python
    def read_current(self) -> tuple[int, str]:
        """Trả (current_epoch, current_ring_name) hiện tại. epoch=0 nghĩa là chưa publish."""
        epoch = struct.unpack_from(CP_EPOCH_FMT, self._shm.buf, OFFSET_CP_EPOCH)[0]
        raw = bytes(self._shm.buf[OFFSET_CP_RING_NAME:OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES])
        return epoch, decode_ring_name(raw)
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `shm = shared_memory.SharedMemory(name=name)` — attach vào segment đã có (không tạo mới).
- `check_cp_header(bytes(shm.buf[:_HEADER_BYTES]))` — kiểm magic/version NGAY khi attach; sai → `ValueError`
  (mẩu 02). Đây là "cửa khẩu" chặn segment lạ.
- `encoded = encode_ring_name(ring_name)` — biến tên ring thành đúng 96 byte (null-pad).
- `self._shm.buf[OFFSET_CP_RING_NAME:...] = encoded` — ghi **TÊN trước**.
- `struct.pack_into(CP_EPOCH_FMT, ..., OFFSET_CP_EPOCH, epoch)  # ghi CUỐI` — ghi **EPOCH sau cùng**. Thứ tự
  này là **cốt lõi**: khi bên đọc thấy epoch tăng thì tên chắc chắn đã ghi xong (không đọc tên nửa vời).
- `read_current`: đọc epoch (8B atomic) rồi đọc + giải mã tên. `epoch == 0` nghĩa là "chưa ai publish".

## 5. Là gì (1–2 câu)
`RingControlPlane` là lớp thao tác vùng điều khiển: `publish(epoch, tên)` (chỉ supervisor gọi) và
`read_current() -> (epoch, tên)` (ai cũng gọi). Attach thì fail-fast qua `check_cp_header`.

## 6. Tại sao tồn tại / vấn đề nó giải
Cần 1 API an toàn để "công bố ring hiện tại" cho nhiều process. `publish` ghi theo thứ tự **tên→epoch** giải
đúng bài toán **đọc nửa vời** (torn read): không bao giờ có chuyện đọc được epoch mới nhưng tên chưa kịp ghi.

## 7. Dùng ở đâu trong project
- `RingSupervisor.switchover()` gọi `publish(N+1, tên-pool-ring)` (mẩu 08).
- `bootstrap_current_ring` + coordinator gọi `read_current()` để biết mở ring nào (mẩu 04/09/10).
- Tạo (`create=True`) ở composition root; attach (`create=False`) ở writer/reader process.

## 8. Không có nó thì sao
Không có lớp này → mỗi nơi tự đọc/ghi byte control-plane → dễ sai thứ tự (epoch trước tên) → torn read →
writer/reader mở nhầm/ring rỗng. Không `check_cp_header` → attach nhầm rác mà không biết.

## 9. Ví von
Như **người phát thanh bảng tin**: chỉ 1 người (supervisor) được **đổi thông báo** (`publish`), và họ luôn
**dán nội dung xong rồi mới bật số thứ tự mới** (tên trước, epoch cuối). Mọi người chỉ đọc (`read_current`)
và tin nội dung khi thấy số thứ tự đổi.

## 10. Liên kết bức tranh lớn
kernel layout (mẩu 02) → **RingControlPlane (mẩu 03, transport)** → supervisor publish (mẩu 08) + coordinator
read (mẩu 09/10). `bootstrap_current_ring` (mẩu 04) là hàm dùng `read_current` để mở ring lần đầu.

## 11. Cạm bẫy (+errata)
- **Đảo thứ tự ghi** (epoch trước tên) → torn read. Code cố tình ghi tên trước, epoch cuối — đừng "tối ưu" đổi lại.
- **Nhiều process cùng `publish`** → tranh nhau. Thiết kế: **CHỈ supervisor** publish (1 authority). (Ép ở tầng application.)
- **Quên fail-fast khi attach** (mẩu 02 cạm bẫy) — luôn `check_cp_header`.

## 12. Tự kiểm (retrieval + Feynman)
- `publish` ghi theo thứ tự nào và **vì sao** thứ tự đó quan trọng?
- `read_current` trả `(0, "")` nghĩa là gì?
- Vì sao chỉ supervisor được `publish`, không phải writer/reader?

## 13. Mốc ôn
- 1 ngày: nhắc lại thứ tự ghi tên→epoch + ý nghĩa epoch=0.
- 1 tuần: giải thích torn read + cách publish tránh nó (không nhìn code).
- 1 tháng: tự viết lại chữ ký `publish`/`read_current` + vai fail-fast.

## 14. Nguồn
- Code: `runtime/ipc/ring_control_plane.py` (`__init__`/`publish`/`read_current`) — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_control_plane.py` (publish→read roundtrip, monotonic overwrite,
  cross-handle attach, wrong-magic fail-fast) — **4 test pass** (full 242 passed/1 skipped). → đã verify.
- Độ chắc: cao (code + test chạy thật).
