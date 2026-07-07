# Mẩu 04 — `bootstrap_current_ring`: từ control-plane → mở đúng ring hiện tại

> Bám code thật `runtime/ipc/ring_control_plane.py` (hàm cuối file, đọc nguyên văn khi viết).

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc`. Là **hàm tự do** (không thuộc class) — tiện dùng chung cho writer/reader coordinator.
- **Vai:** bước "khởi động" của 1 process consumer: hỏi control-plane "ring hiện tại là gì?" rồi mở nó.

## 2. Cần biết trước
- Mẩu 03: `RingControlPlane.read_current()` trả `(epoch, tên)`; `epoch == 0` = chưa publish.
- Gloss: **ring_opener** = hàm `(tên) -> ring` được **tiêm từ ngoài** (DI) — người gọi quyết định "mở ring thế nào"
  (mẩu 06 sẽ cấp opener thật từ pool). **additive** = thêm mới, KHÔNG sửa code cũ.

## 3. Code thật (quote nguyên văn — `runtime/ipc/ring_control_plane.py`, cuối file)
```python
def bootstrap_current_ring(cp: "RingControlPlane", ring_opener):
    """Bootstrap ring hiện tại qua control-plane (additive — KHÔNG sửa Writer/Reader cũ).

    Đọc (epoch, ring_name) hiện tại từ control-plane → mở data ring bằng `ring_opener(name)` (tiêm ngoài, DI).
    Trả `(ring, epoch)`. Nếu chưa publish (epoch=0) → RuntimeError (không đoán ring).
    Teardown ring cũ dựa OS handle ref-count (caller `close()` ring cũ khi rời — xem docstring module).
    """
    epoch, name = cp.read_current()
    if epoch == 0:
        raise RuntimeError("control-plane chưa publish ring nào (epoch=0) — không thể bootstrap")
    ring = ring_opener(name)
    return ring, epoch
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `epoch, name = cp.read_current()` — hỏi control-plane "epoch + tên ring hiện tại".
- `if epoch == 0: raise RuntimeError(...)` — nếu **chưa ai publish** → **KHÔNG đoán** ring nào; báo lỗi ngay
  (fail-fast). Tránh mở ring rác/không tồn tại.
- `ring = ring_opener(name)` — gọi hàm tiêm ngoài để **mở** ring theo tên (chi tiết "mở thế nào" ở mẩu 06).
- `return ring, epoch` — trả cả ring đã mở + epoch (để coordinator nhớ "đang ở epoch mấy" — mẩu 09/10).

## 5. Là gì (1–2 câu)
Hàm khởi động: đọc control-plane → mở ring hiện tại qua `ring_opener` (DI) → trả `(ring, epoch)`. Chưa publish
thì báo lỗi thay vì đoán.

## 6. Tại sao tồn tại / vấn đề nó giải
Consumer (writer/reader) khi khởi động **không biết** ring hiện tại tên gì (tên uuid ngẫu nhiên). Hàm này là
"cửa vào" chuẩn: luôn hỏi control-plane trước. `ring_opener` tiêm ngoài để **tách** "biết ring nào" khỏi "mở
ring cách nào" → test được + đổi cách mở (pool) mà không sửa hàm này.

## 7. Dùng ở đâu trong project
- `WriterEpochCoordinator.bootstrap()` và `ReaderEpochCoordinator.bootstrap()` gọi nó (mẩu 09/10).
- `ring_opener` thật do `make_pool_opener(...)` cấp (mẩu 06).

## 8. Không có nó thì sao
Không có bước bootstrap chuẩn → mỗi consumer tự chế cách tìm ring → dễ mở nhầm/đoán tên → hỏng. Không chặn
`epoch==0` → mở ring "chưa tồn tại" → lỗi khó hiểu về sau.

## 9. Ví von
Như **nhân viên mới đến công ty**: việc đầu tiên là ra **bảng tin** (control-plane) đọc "phòng làm việc hôm
nay ở đâu" rồi mới đi tới đó — không tự đoán phòng. Nếu bảng tin trống (`epoch==0`) thì hỏi lại, không đi bừa.

## 10. Liên kết bức tranh lớn
control-plane (mẩu 03) → **bootstrap (mẩu 04)** → coordinator dùng để mở ring lần đầu (mẩu 09/10). `ring_opener`
đến từ pool (mẩu 06) — mắt xích giải K-012.

## 11. Cạm bẫy (+errata)
- **Đoán tên ring khi epoch=0** thay vì báo lỗi → mở ring rác. Code cố tình `raise` — giữ vậy.
- **Nhét logic "mở ring" cứng vào hàm** (không DI) → không test được + kẹt với 1 cách mở. Giữ `ring_opener` tiêm ngoài.

## 12. Tự kiểm (retrieval + Feynman)
- `bootstrap_current_ring` làm đúng mấy bước? Vì sao `epoch==0` phải raise chứ không đoán?
- Vì sao tách "biết ring nào" (read_current) khỏi "mở ring cách nào" (ring_opener)?

## 13. Mốc ôn
- 1 ngày: nhắc lại 3 bước (read → check epoch → open).
- 1 tuần: giải thích vai `ring_opener` (DI) không nhìn code.
- 1 tháng: tự viết lại hàm từ trí nhớ.

## 14. Nguồn
- Code: `runtime/ipc/ring_control_plane.py` (`bootstrap_current_ring`) — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_bootstrap.py` (đọc ring hiện tại · 2 consumer cùng ring ·
  epoch=0 raise) — **3 test pass** (full 242 passed/1 skipped). → đã verify.
- Độ chắc: cao (code + test chạy thật).
