# #02 · Mẩu 07: `__setstate__` — pickle KHÔNG giữ `write=False` (ERRATA E-11)

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (trong `InMemoryArrayRef`) ·
tầng **kernel** · đây là chốt giữ "read-only" của mảng ảnh **khi đi qua ranh giới tiến trình** (pickle).

## 2. Cần biết trước
- [pickle](../../knowledge-base/00-GLOSSARY.md#pickle) ·
  [ndarray (numpy array)](../../knowledge-base/00-GLOSSARY.md#ndarray-numpy-array) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue)
- Mẩu 06 (`InMemoryArrayRef` + `setflags(write=False)`) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)

> **🖼 Sơ đồ E-11 (nguồn Draw.io):** [pickle-e11.drawio](diagrams/pickle-e11.drawio) — so sánh ndarray trần (mất read-only) vs `InMemoryArrayRef` (`__setstate__` re-lock).
> Xem nhúng: Draw.io → **Export as → SVG** → lưu `diagrams/pickle-e11.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

```python
# vision-platform/src/vision_platform/kernel/media_packet.py  (trong class InMemoryArrayRef)
    # ... (__post_init__ — xem mẩu 06) ...

    def __setstate__(self, state):
        # pickle KHÔNG chạy lại __post_init__, và numpy KHÔNG giữ cờ write=False qua
        # pickle (verify thật numpy 2.4.6 → writeable=True sau round-trip). Re-lock tại
        # đây để giữ contract read-only qua ranh giới process/pickle. (ERRATA E-11)
        object.__setattr__(self, "array", state["array"])
        if self.array.flags.writeable:
            self.array.setflags(write=False)
```

## 4. Giải thích từng phần nhỏ nhất
- `def __setstate__(self, state):` → hàm **đặc biệt cho pickle**: khi bung (`pickle.loads`) một đối tượng, Python gọi hàm này để **khôi phục trạng thái** — thay cho việc chạy `__init__`/`__post_init__` (vốn KHÔNG chạy lúc unpickle).
- `state` → dict chứa các trường đã lưu (ở đây có key `"array"`).
- `object.__setattr__(self, "array", state["array"])` → gán trường `array` trở lại. Vì lớp là `frozen=True` (cấm gán thường), phải dùng `object.__setattr__` để **vượt khoá** — đây là cách hợp lệ duy nhất bên trong setstate.
- `if self.array.flags.writeable: self.array.setflags(write=False)` → **khoá lại read-only**. Cần thiết vì numpy bung mảng ra ở trạng thái ghi-được (xem §6).

## 5. Là gì (1–2 câu)
`__setstate__` là điểm Python gọi khi **bung một đối tượng từ pickle**. Ở đây nó dùng để **khoá lại**
mảng thành read-only, vì cờ đó bị mất qua quá trình pickle.

## 6. Tại sao tồn tại / vấn đề nó giải
Đây là bug thật **ERRATA E-11**. Hệ sau này chạy **đa tiến trình**: `MediaPacket` (chứa `InMemoryArrayRef`)
được **pickle** để gửi sang process khác. Nhưng:
1. Khi unpickle, Python **KHÔNG chạy lại `__post_init__`** → đoạn khoá `setflags(write=False)` ở đó không chạy.
2. numpy **KHÔNG giữ cờ `write=False`** qua pickle → mảng bung ra lại **ghi được**.
→ Mảng đáng lẽ read-only bỗng ghi được ở process nhận → vỡ cam kết, dữ liệu có thể bị sửa lén.
`__setstate__` vá đúng chỗ đó: bung xong thì **khoá lại ngay**.

## 7. Dùng ở đâu trong project (cụ thể)
- Đảm bảo `InMemoryArrayRef` (và `MediaPacket` chứa nó) giữ read-only khi truyền giữa process — nền cho #05 (SHM/đa tiến trình).
- **Kiểm chứng thật (đã CHẠY phiên này, numpy 2.4.6):**
  - ndarray trần `write=False` → pickle round-trip → `writeable = True` (numpy KHÔNG giữ cờ).
  - `InMemoryArrayRef` → pickle round-trip → `writeable = False` (giữ được nhờ `__setstate__`).
  - Test `test_array_ref_stays_readonly_after_pickle` → **1 passed** (`pytest -k pickle`).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Bỏ `__setstate__`: gửi packet sang process khác, mảng bung ra **ghi được** → process nhận lỡ sửa frame →
bug "ảnh đổi sau khi truyền", chỉ xảy ra ở chế độ đa tiến trình → cực khó tái hiện/khó lần. E-11 đã bắt đúng cái này.

## 9. Ví von đời thường
pickle như **chuyển nhà**: đồ đạc tháo ra đóng thùng, sang nhà mới mở lại. Nhưng cái **niêm phong "chỉ
đọc"** dán trên tài liệu bị bong trong lúc vận chuyển → `__setstate__` là người **dán lại niêm phong ngay
khi mở thùng** ở nhà mới.

## 10. Liên kết bức tranh lớn
Đây là mảnh làm cho "bất biến + zero-copy" của #02 **sống sót qua ranh giới tiến trình** — điều kiện cần
để #05 (frame bus đa process) an toàn. Cùng cặp đôi: `__post_init__` lo lúc tạo (mẩu 06), `__setstate__` lo lúc unpickle (mẩu này).

## 11. Cạm bẫy / lỗi thường gặp
- Tưởng `__post_init__` đủ để giữ read-only → SAI trong tình huống pickle (nó không chạy lại). Đây chính là gốc E-11.
- Trong `frozen=True`, gán trường bình thường sẽ lỗi → phải `object.__setattr__` (chỉ trong `__post_init__`/`__setstate__`).
- "Số trùng khớp" không phải bằng chứng: phải tự chạy round-trip mới biết — và đã chạy thật ở §7.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao `__post_init__` KHÔNG đủ để giữ read-only qua pickle? `__setstate__` chạy khi nào?
- Tình huống: gửi `MediaPacket` sang process khác mà KHÔNG có `__setstate__` — process nhận có sửa được frame không? Vì sao nguy hiểm?
- Giải thích lại bằng LỜI MÌNH: "pickle làm mất ... ; __setstate__ để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 2 lý do mảng mất read-only qua pickle | 1 tuần → tự pickle 1 object + khôi phục trạng thái | 1 tháng → giải thích E-11 bằng lời mình.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (đã ĐỌC LẠI nguyên văn `__setstate__`). · Độ chắc: **cao**.
- Hành vi E-11: đã CHẠY THẬT phiên này (numpy **2.4.6**): ndarray trần → pickle → `writeable=True`; `InMemoryArrayRef` → pickle → `writeable=False`; `pytest -k pickle` → **1 passed**. · Độ chắc: **cao** (bằng chứng trực tiếp, không suy đoán).
- E-11 ghi trong `Design/00-ERRATA.md`. · Độ chắc: **cao**.
