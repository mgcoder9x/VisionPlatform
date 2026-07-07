# #04 · Mẩu 08: Context manager `__enter__`/`__exit__` (ERRATA E-14) — luôn `teardown`, không nuốt lỗi

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/runtime/sync_linear_executor.py` ·
tầng **runtime** · đây là phần cho phép viết `with SyncLinearExecutor([...]) as ex:` để **tự dọn** dù có lỗi.

## 2. Cần biết trước
- Mẩu 07 (`SyncLinearExecutor` + `setup_all`/`teardown_all`) — đọc trước.
- [context manager (with statement)](../../knowledge-base/00-GLOSSARY.md#context-manager-with-statement)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/runtime/sync_linear_executor.py
    # Context manager (ERRATA E-14, Risk 4): đảm bảo teardown tự động kể cả khi raise giữa chừng.
    # `with SyncLinearExecutor([...]) as ex: ...` → setup_all() lúc vào, teardown_all() lúc ra.
    def __enter__(self) -> "SyncLinearExecutor":
        self.setup_all()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown_all()
        return False  # KHÔNG nuốt exception của thân `with`
```

## 4. Giải thích từng phần nhỏ nhất
- `__enter__(self)` → chạy khi **vào** khối `with`: gọi `self.setup_all()` (mở mọi stage) rồi `return self` → biến sau `as` chính là executor.
- `__exit__(self, exc_type, exc, tb)` → chạy khi **ra** khối `with` (kể cả khi thân `with` raise):
  - 3 tham số `exc_type, exc, tb` = thông tin exception nếu thân `with` ném lỗi (None nếu không lỗi).
  - `self.teardown_all()` → dọn mọi stage (thứ tự ngược, mẩu 07) — **LUÔN chạy**.
  - `return False` → **KHÔNG nuốt** exception: nếu thân `with` có lỗi thì lỗi đó vẫn tiếp tục nổ ra ngoài (chỉ dọn xong rồi mới để lỗi bay lên).

## 5. Là gì (1–2 câu)
Hai method này biến `SyncLinearExecutor` thành **context manager**: `with` tự gọi `setup_all` lúc vào,
`teardown_all` lúc ra — kể cả khi giữa chừng có lỗi — mà vẫn để lỗi nổ ra cho người gọi biết.

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (ERRATA E-14, quên teardown)
- **Vấn đề (E-14):** nếu phải tự gọi `setup_all()` rồi `... execute ...` rồi `teardown_all()`, mà giữa chừng raise → dòng `teardown_all()` **bị nhảy qua** → stage không được dọn → **rò tài nguyên**.
- **Fix cái NGỌN (sai):** dặn "nhớ bọc try/finally mọi nơi gọi executor" → người dùng sẽ quên.
- **Fix tận GỐC (đã làm):** đưa `setup`/`teardown` vào `__enter__`/`__exit__`. Python **bảo đảm** `__exit__` chạy khi rời `with` dù có lỗi → không thể quên dọn. (`teardown_all` reversed + try/except ở mẩu 07 là nền.)
- **`return False` — chi tiết tinh tế:** `__exit__` trả `True` sẽ **nuốt** exception (giấu lỗi). Ở đây chủ ý `False` → chỉ DỌN, KHÔNG che lỗi → lỗi thật vẫn được báo lên.

## 7. Dùng ở đâu trong project (cụ thể)
- Cách dùng khuyến nghị: `with SyncLinearExecutor([...]) as ex: ex.execute(packet)` → khỏi tự nhớ setup/teardown.
- Test thật (đã CHẠY pass — `pytest test_step_04_pipeline.py` → **13 passed**):
  - `test_executor_context_manager_setup_teardown`:
    - vào `with` → `calls == ["setup"]`; ra `with` bình thường → `calls == ["setup", "teardown"]`.
    - thân `with` `raise RuntimeError("boom")` → `pytest.raises(RuntimeError)` bắt được (lỗi KHÔNG bị nuốt) **và** `calls == ["setup", "teardown"]` (vẫn dọn).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Tự gọi `setup_all`/`teardown_all`: raise giữa chừng → quên dọn → rò (đúng bug E-14).
- `__exit__` trả `True`: lỗi thật bị **nuốt** âm thầm → người gọi tưởng chạy ổn → bug ẩn rất nguy hiểm.

## 9. Ví von đời thường
`with` như **cửa tự đóng có khoá an toàn**: vào thì đèn bật (`setup`), ra — kể cả khi chạy vội vì báo
cháy (raise) — cửa **vẫn tự đóng** (`teardown`). Và chuông báo cháy **vẫn reo** (return False), không bị tắt lén.

## 10. Liên kết bức tranh lớn
Đây là lớp an toàn cuối cho vòng đời stage: `setup_all`/`teardown_all` (mẩu 07) + bảo đảm của `with`.
`demo_pipeline` (mẩu 09) NAY dùng `with source, executor:` (R2#04/E-16) — đồng bộ vòng đời cả nguồn lẫn executor, gọn hơn `try/finally` thủ công, cùng mục đích "luôn dọn".

## 11. Cạm bẫy / lỗi thường gặp
- `__exit__` trả `True` (hoặc quên `return`, mặc định `None` ~ falsy thì OK, nhưng `True` thì sai) → nuốt lỗi. Chủ ý `return False`.
- Trộn vừa dùng `with` vừa tự gọi `setup_all` → setup 2 lần (tuy `test_executor_idempotent_setup` cho thấy không vỡ, vẫn nên chọn 1 cách).
- Tưởng `__exit__` chỉ chạy khi không lỗi — sai: nó chạy CẢ khi có lỗi (đó là điểm mạnh).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `__enter__` làm gì? `__exit__` làm gì? vì sao `return False`?
- Tình huống: thân `with` ném lỗi giữa chừng — teardown có chạy không? lỗi có bị giấu không? vì sao?
- Giải thích lại bằng LỜI MÌNH: "context manager ở đây đảm bảo ... ; return False nghĩa là ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại `__enter__`/`__exit__` + return False | 1 tuần → tự viết 1 context manager | 1 tháng → giải thích E-14 (vì sao try/finally thủ công dễ quên).

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/runtime/sync_linear_executor.py` (đã ĐỌC nguyên văn `__enter__`/`__exit__`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed** (gồm `test_executor_context_manager_setup_teardown` — kiểm cả ca raise). · Độ chắc: **cao**.
- E-14: ghi trong ERRATA/Design Module 03 (context manager bổ sung). · Độ chắc: cao về cơ chế `with`.
