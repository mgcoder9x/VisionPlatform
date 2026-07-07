# #02 · Mẩu 06: `InMemoryArrayRef` — ndarray read-only by contract + `from_owned` vs `from_copy`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` · tầng **kernel** ·
đây là lớp bọc **mảng ảnh** (frame) để chia sẻ an toàn giữa các bước.

## 2. Cần biết trước
- [ndarray (numpy array)](../../knowledge-base/00-GLOSSARY.md#ndarray-numpy-array) ·
  [zero-copy](../../knowledge-base/00-GLOSSARY.md#zero-copy) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [immutable](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến)
- `__setstate__` trong code dưới → để dành **mẩu 07** (pickle/E-11).

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/media_packet.py
@dataclass(frozen=True)
class InMemoryArrayRef:
    """Frame data, read-only BY CONTRACT (không phải immutability tuyệt đối).

    `setflags(write=False)` chặn ghi qua *chính ndarray này*. Nếu còn alias/base array
    writable trỏ vào cùng buffer, dữ liệu vẫn có thể đổi qua alias đó → đây là convention
    "đừng ghi nữa", không phải bảo đảm tuyệt đối.

    - `from_owned_array(arr)`: caller TRAO quyền sở hữu (zero-copy, nhanh).
    - `from_copy(arr)`: defensive copy — caller tự do mutate tiếp; ref giữ snapshot riêng.
    """
    array: np.ndarray

    def __post_init__(self):
        if not isinstance(self.array, np.ndarray):
            raise TypeError(
                f"array phải là numpy.ndarray, nhận {type(self.array).__name__}"
            )
        if self.array.flags.writeable:
            self.array.setflags(write=False)

    # ... (__setstate__ — pickle/E-11, xem mẩu 07) ...

    @classmethod
    def from_owned_array(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Nhận quyền sở hữu array (zero-copy). Caller cam kết KHÔNG mutate nữa."""
        return cls(array=array)

    @classmethod
    def from_copy(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Defensive copy — caller can keep mutating original safely."""
        snapshot = np.ascontiguousarray(array.copy())
        return cls(array=snapshot)
```

## 4. Giải thích từng phần nhỏ nhất
- `@dataclass(frozen=True) class InMemoryArrayRef:` → lớp bất biến bọc đúng 1 trường `array: np.ndarray`.
- Docstring nói thẳng: read-only **BY CONTRACT** (theo cam kết), KHÔNG phải bất biến tuyệt đối — vì numpy có thể còn "alias" khác ghi được vào cùng vùng nhớ.
- `__post_init__`:
  - `if not isinstance(self.array, np.ndarray): raise TypeError(...)` → nếu truyền thứ KHÔNG phải ndarray (vd list) thì báo `TypeError` rõ nghĩa ngay (thay vì lỗi khó hiểu sau này).
  - `if self.array.flags.writeable: self.array.setflags(write=False)` → nếu mảng đang cho ghi thì **khoá lại thành chỉ-đọc**. `flags.writeable` = cờ "có cho ghi không"; `setflags(write=False)` = tắt ghi.
- `from_owned_array(array)` → **nhận quyền sở hữu** mảng caller đưa (không copy = zero-copy, nhanh). Caller cam kết không sửa nữa. (Nó gọi `cls(array=array)` → chính là `__post_init__` khoá mảng đó luôn.)
- `from_copy(array)`:
  - `snapshot = np.ascontiguousarray(array.copy())` → **sao một bản riêng** (liền mạch trong bộ nhớ).
  - `return cls(array=snapshot)` → ref giữ bản sao; caller tự do sửa mảng GỐC mà không ảnh hưởng ref.

## 5. Là gì (1–2 câu)
`InMemoryArrayRef` là lớp bọc mảng ảnh, **khoá nó chỉ-đọc** để chia sẻ an toàn. Có 2 cách tạo: `from_owned_array`
(nhanh, không copy) và `from_copy` (an toàn, giữ bản sao riêng).

## 6. Tại sao tồn tại / vấn đề nó giải
Frame ảnh rất lớn (mẩu cau-chuyen). Hai lực giằng nhau: muốn **chia sẻ nhanh** (đừng copy) nhưng cũng
muốn **an toàn** (đừng để bước sau ghi đè lên ảnh bước trước). Giải: bọc mảng + `setflags(write=False)`
để chặn ghi qua ref này; rồi cho **2 lựa chọn rõ ràng**: `from_owned_array` (zero-copy khi caller chắc
chắn không sửa nữa) vs `from_copy` (trả tiền 1 lần để cách ly hoàn toàn). `isinstance` chặn truyền nhầm kiểu.

## 7. Dùng ở đâu trong project (cụ thể)
- Là trường `media_ref: InMemoryArrayRef` trong `MediaPacket` (mẩu 08) — chính là ảnh mà packet mang theo.
- Test thật `tests/test_step_02_domain.py` (đã CHẠY pass):
  - `test_array_ref_locks_array_readonly`: `ref.array[0,0,0] = 99` → raise `ValueError` (đã khoá).
  - `test_array_ref_default_takes_ownership`: sau khi bọc, **mảng gốc của caller** cũng thành read-only → `arr[0,0,0]=99` raise.
  - `test_array_ref_from_copy_isolates`: `from_copy` rồi `arr[0,0,0]=99` → `ref.array[0,0,0] == 0` (ref không đổi).
  - `test_array_ref_rejects_non_ndarray`: `InMemoryArrayRef([1,2,3])` → raise `TypeError`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Truyền thẳng `np.ndarray` trần khắp pipeline: bước nào cũng ghi đè được → bug "ảnh biến đổi giữa đường", khó lần.
- Luôn copy để an toàn: chậm + ngốn RAM với ảnh lớn. `InMemoryArrayRef` cho chọn đúng chỗ: zero-copy khi an toàn, copy khi cần cách ly.

## 9. Ví von đời thường
- `from_owned_array` = **trao hẳn chìa khóa nhà** cho người giữ hộ rồi dán niêm phong (không copy, nhưng bạn cam kết không vào sửa nữa).
- `from_copy` = **photo một bản** đưa người ta giữ; bản gốc bạn muốn viết gì thì viết.
- `setflags(write=False)` = **dán niêm phong "chỉ đọc"** lên tài liệu.

## 10. Liên kết bức tranh lớn
Đây là mảnh "chia sẻ ảnh zero-copy nhưng an toàn" trong câu chuyện #02. Nó nằm trong `MediaPacket` (mẩu 08),
và là lý do `MediaPacket` "bất biến mà vẫn nhanh": copy metadata nhỏ (CoW, mẩu 09) nhưng **dùng chung media_ref** (không copy ảnh).

## 11. Cạm bẫy / lỗi thường gặp
- **read-only BY CONTRACT, không tuyệt đối:** nếu caller dùng `from_owned_array` rồi VẪN giữ một alias ghi được trỏ cùng buffer, dữ liệu vẫn đổi được qua alias đó. Cam kết "không sửa nữa" là của caller.
- Dùng `from_owned_array` cho mảng mình còn muốn sửa → mảng gốc bị khoá luôn. (`from_owned_array` gọi đúng constructor mặc định `InMemoryArrayRef(arr)`, nên hành vi này được test `test_array_ref_default_takes_ownership` kiểm; KHÔNG có test riêng mang tên `from_owned_array`.) Cần sửa tiếp thì dùng `from_copy`.
- `__post_init__` không chạy lại khi unpickle → cần `__setstate__` re-lock (mẩu 07, E-11).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `setflags(write=False)` làm gì? Khác biệt `from_owned_array` vs `from_copy`?
- Tình huống: bạn có 1 mảng còn muốn chỉnh sửa tiếp nhưng vẫn muốn đưa cho packet — dùng cách nào? Vì sao?
- Giải thích lại bằng LỜI MÌNH: "read-only by contract nghĩa là ... ; from_copy để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 2 cách tạo + khác biệt | 1 tuần → tự viết 1 lớp bọc mảng read-only | 1 tháng → giải thích "by contract ≠ tuyệt đối".

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (đã ĐỌC LẠI nguyên văn `InMemoryArrayRef`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_02_domain.py -k array_ref` → **5 passed** (gồm 4 test trích ở §7; test pickle là của mẩu 07). · Độ chắc: **cao**.
- "read-only by contract, không tuyệt đối": ghi rõ trong docstring code + đúng cơ chế numpy alias; [chưa kiểm bằng thực nghiệm tạo alias writable tại mẩu này] — là cảnh báo thiết kế. · Độ chắc: cao về cơ chế.
