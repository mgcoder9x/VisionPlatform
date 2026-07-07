# Mẩu 08 — `(pid, create_time)` + `owner_liveness`: biết process còn sống hay đã chết

> Bám file: `vision-platform/src/vision_platform/runtime/ipc/_process_identity.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Là "cảm biến" hỏi OS: process X còn sống không? Recovery (mẩu 09) dựa vào đây để
quyết có quarantine slot hay không. `psutil` CHỈ được import ở layer này (import-linter cấm ở domain/kernel).

## 2. Cần biết trước
- pid = số định danh process (OS cấp). `psutil` = thư viện hỏi thông tin process.
- **PID reuse:** OS có thể cấp lại pid cũ cho process KHÁC sau khi process gốc chết.

## 3. Code thật (quote nguyên văn — rút gọn phần docstring)
```python
class Liveness(str, Enum):
    ALIVE = "alive"      # pid tồn tại VÀ create_time khớp
    DEAD = "dead"        # không tồn tại, hoặc create_time lệch (pid bị tái dùng), hoặc pid <= 0
    UNKNOWN = "unknown"  # không xác định được (AccessDenied/Zombie/lỗi OS) → KHÔNG quarantine

def current_identity() -> Tuple[int, int]:
    p = psutil.Process()
    return p.pid, _to_ns(p.create_time())

def owner_liveness(pid, create_time_ns, *, query=_psutil_query) -> Liveness:
    if pid <= 0:
        return Liveness.DEAD
    try:
        is_running, actual_create_time_ns = query(pid)
    except ProcessNotFound:
        return Liveness.DEAD
    except ProcessAccessUnknown:
        return Liveness.UNKNOWN
    if not is_running:
        return Liveness.DEAD
    if actual_create_time_ns != create_time_ns:
        return Liveness.DEAD   # pid trùng nhưng tiến trình KHÁC (PID reuse)
    return Liveness.ALIVE
```
(Nguồn: `runtime/ipc/_process_identity.py` — quote nguyên văn.)

## 4. Giải thích từng ý nhỏ nhất
- **Định danh = `(pid, create_time_ns)`**, KHÔNG chỉ pid. `create_time` = mốc thời gian process khởi tạo → gần như duy nhất → chống PID reuse.
- **3 trạng thái:** `ALIVE` (tồn tại + create_time khớp), `DEAD` (không tồn tại / create_time lệch / pid≤0), `UNKNOWN` (không xác định được).
- **`owner_liveness` an toàn:** `DEAD` chỉ khi CHẮC chết; nghi ngờ (`AccessDenied`/`Zombie`/lỗi) → `UNKNOWN` (recovery sẽ KHÔNG quarantine — tránh loại nhầm process còn sống).
- **`query` injectable:** mặc định `_psutil_query`; test bơm query giả để mô phỏng PID reuse/AccessDenied mà không cần spawn thật.
- **`create_time` lệch → DEAD:** pid tồn tại nhưng là process KHÁC (OS tái dùng pid) → owner cũ coi như chết.

## 5. Là gì (1–2 câu)
Hàm kiểm "chủ của slot còn sống không", trả `ALIVE/DEAD/UNKNOWN`, định danh bằng `(pid, create_time)` để
không bị lừa bởi PID reuse.

## 6. Tại sao tồn tại / vấn đề nó giải
Recovery cần biết owner slot chết chưa để quarantine. Nếu chỉ so pid → OS cấp lại pid → tưởng còn sống (hoặc
ngược lại) → quarantine nhầm/bỏ sót. `create_time` giải chính xác. `UNKNOWN` giải nỗi đau "không chắc thì đừng làm liều".

## 7. Dùng ở đâu trong project
- Writer/Reader cache `current_identity()` ghi vào header slot (mẩu 06/07).
- `quarantine_poisoned_slot` gọi `owner_liveness(pid, ct)` để quyết (mẩu 09).
- `register_writer` dùng để phát hiện writer cũ chết (mẩu 10).

## 8. Không có nó thì sao
Recovery không phân biệt được process chết/sống → hoặc không bao giờ dọn slot kẹt (đứng bus), hoặc dọn nhầm
slot của process còn đang ghi (corrupt dữ liệu).

## 9. Ví von
Như **điểm danh nhân viên bằng CẢ tên LẪN ngày vào làm**: chỉ tên (pid) dễ trùng người mới; thêm ngày vào
làm (create_time) → chắc chắn đúng người. Không rõ (nghỉ phép?) → ghi "UNKNOWN", không kết luận vội.

## 10. Liên kết bức tranh lớn
Đây là "cảm biến sống/chết" cho toàn cơ chế recovery (mẩu 09) + single-writer (mẩu 10). psutil ở runtime/ipc,
không rò lên kernel/domain (import-linter ép — mẩu học #01/#02 về layer).

## 11. Cạm bẫy (+errata)
- **CẠM BẪY LỚN (đã verify thật):** `os.kill(pid, 0)` trên **Windows** = gửi `CTRL_C_EVENT` → chính process gọi nhận `KeyboardInterrupt`. → TUYỆT ĐỐI không dùng `os.kill` kiểu Unix để kiểm process sống trên Windows. Dùng psutil.
- 🔴 `AccessDenied` với process KHÁC QUYỀN trên Windows: nhánh code trả UNKNOWN đã có, nhưng hành vi psutil thật cần môi trường đa-user để kiểm (mới dùng fake query).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao định danh phải là `(pid, create_time)` chứ không chỉ pid? PID reuse là gì?
- Vì sao `UNKNOWN` KHÔNG quarantine? Điều gì tệ nếu quarantine nhầm process còn sống?
- Vì sao KHÔNG dùng `os.kill(pid,0)` trên Windows?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/_process_identity.py` (quote nguyên văn). · `os.kill`=CTRL_C_EVENT: CHẠY THẬT Windows/Python 3.12.10 (KeyboardInterrupt). · Test: `test_hardening_process_identity.py` 100% branch coverage. · Độ chắc: cao.
