# Mẩu 11 — T-B: bằng chứng CROSS-PROCESS THẬT rằng H2 giải được K-012

> Bám code thật `tests/test_switchover_cross_process.py` (đọc nguyên văn khi viết). Đây là "cổng chấp nhận":
> chứng minh worker process RIÊNG khoá được ring đích switchover bằng khoá thừa kế (crux K-012).

## 1. Thuộc về đâu
- **Loại:** test tích hợp cross-process (spawn thật). Nằm ở `tests/`.
- **Vai:** bằng chứng cuối cho toàn bộ #05b — điều mà test in-process (mẩu 06–10) KHÔNG phủ được.

## 2. Cần biết trước
- Mẩu 05 (K-012), 06 (RingPool + `slot_locks_map`), 08–10 (supervisor + coordinator).
- Gloss: **spawn** = tạo process con · **inherit qua `Process(args=)`** = con nhận đối tượng (khoá) lúc sinh ·
  **ack-queue** = hàng đợi "gật đầu" để 2 bên đi từng bước (serialize) · **flaky** = lúc pass lúc fail (không ổn định).

## 3. Code thật (quote nguyên văn — `tests/test_switchover_cross_process.py`)

**(a) Worker (process riêng) ghi frame + báo ref qua queue:**
```python
        i = 0
        while True:
            token = ack_q.get()                      # chờ lệnh: "WRITE" ghi tiếp, "STOP" dừng
            if token == "STOP":
                break
            val = (i % 250) + 1                       # 1..250 (tránh 0)
            ref = wc.write(np.full((h, w, c), val, dtype=np.uint8))
            if ref is None:
                ref_q.put(("NONE", None, None, None))
            else:
                ref_q.put((ref.ring_epoch, ref.slot, ref.generation, val))
            i += 1
    except Exception as e:  # báo lỗi thật về parent (không nuốt)
        ref_q.put(("ERROR", repr(e), None, None))
```

**(b) Truyền TOÀN BỘ khoá pool cho worker lúc spawn:**
```python
    proc = mp.Process(
        target=_writer_worker,
        args=(cp_name, pool.slot_locks_map(), _N, _H, _W, _C, ref_q, ack_q, ready_q),
```

**(c) Guard nền tảng (chỉ chạy Windows):**
```python
@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="T-B verify trên Windows (nền hiện tại); POSIX spawn/teardown ở T-C (K-003).",
)
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `token = ack_q.get()` — worker chờ parent "gật đầu" (`WRITE`) mới ghi frame kế → **serialize** (không lapping
  slot → deterministic, chống flaky). `STOP` → dừng.
- `ref = wc.write(...)` — worker ghi qua `WriterEpochCoordinator` (mẩu 09); coordinator **tự chuyển ring** khi parent switchover.
- `ref_q.put((ref.ring_epoch, ref.slot, ref.generation, val))` — báo về parent: frame vừa ghi ở **epoch nào**, slot/gen, giá trị.
- `except Exception as e: ref_q.put(("ERROR", ...))` — lỗi worker **báo thật** về parent (không nuốt) → test thấy.
- `args=(..., pool.slot_locks_map(), ...)` — **điểm mấu chốt**: truyền `slot_locks_map()` (toàn bộ khoá K ring)
  cho worker **lúc spawn** → worker khoá được **bất kỳ** ring pool nào, kể cả ring đích switchover.
- `skipif platform != "win32"` — chỉ chạy trên Windows (nền hiện tại); POSIX để T-C (K-003) → **không claim sai** ngoài Windows.

## 5. Là gì (1–2 câu)
Test spawn 1 worker writer THẬT (nhận khoá pool qua thừa kế). Parent (supervisor + reader) switchover giữa
stream; **parent đọc được frame epoch 2 do worker ghi cross-process** → chứng minh worker khoá được ring mới.

## 6. Tại sao tồn tại / vấn đề nó giải (crux K-012)
Test in-process (mẩu 06–10) chia sẻ khoá qua object trong 1 process → **không** chứng minh được khoá THỪA KẾ
qua spawn hoạt động cho ring đích. T-B là **bằng chứng duy nhất** cho điều đó: nếu `slot_locks_map` KHÔNG phủ
ring 2, worker sẽ lỗi/deadlock khi ghi ring 2 → `got_epoch2 == 0` → test FAIL. Test PASS ⇒ **H2 giải đúng K-012 cross-process**.

## 7. Dùng ở đâu trong project
- `tests/test_switchover_cross_process.py::test_switchover_cross_process_writer_reader` — cổng chấp nhận sub-spec.
- Neo mọi mẩu 05–10: chứng minh chúng đúng khi chạy **thật** ở nhiều process.

## 8. Không có nó thì sao
Không có T-B → mọi khẳng định "switchover cross-process chạy được" chỉ là **suy luận từ test in-process** — CHƯA
verify điều bản chất nhất (khoá thừa kế phủ ring đích). Với sản phẩm 24/7, đó là lỗ hổng niềm tin.

## 9. Ví von
Như **diễn tập cháy THẬT** (không phải nói lý thuyết): cho nhân viên (worker) đang trực ở xa, hệ thống đổi lối
thoát (switchover), và kiểm **nhân viên có mở được cửa lối mới bằng chìa đã phát lúc nhận việc** (khoá thừa kế)
— nếu mở được ⇒ phương án phát-chìa-sẵn (H2) đúng.

## 10. Liên kết bức tranh lớn
K-012 (mẩu 05) → H2 (mẩu 06/07) → điều phối (mẩu 08–10) → **T-B (mẩu 11) chứng minh tất cả chạy cross-process**.
→ Mẩu 11 là "chốt niềm tin" cho cả #05b.

## 11. Cạm bẫy (+errata)
- **Test spawn dễ flaky** → dùng ack-queue serialize (không lapping) + chạy lặp kiểm (đã chạy **5/5 không flaky**).
- **Nuốt lỗi worker** → test "xanh giả". Code `except → ref_q.put(("ERROR",...))` để lỗi nổi lên parent.
- 🔴 **Chỉ Windows**: guard skip non-win32; POSIX (spawn+teardown) chưa verify (K-003).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao test in-process KHÔNG đủ, phải có T-B? (nêu: khoá thừa kế qua spawn.)
- `got_epoch2 >= 1` chứng minh điều gì về K-012? Nếu H2 sai thì test hỏng ra sao?
- Vì sao dùng ack-queue serialize thay vì cho worker ghi tự do?

## 13. Mốc ôn
- 1 ngày: nhắc "worker nhận toàn bộ khoá pool qua spawn → khoá được ring đích".
- 1 tuần: giải thích vì sao `got_epoch2>=1` = bằng chứng K-012 (không nhìn code).
- 1 tháng: tự phác lại kịch bản T-B (spawn → switchover giữa chừng → đọc epoch 2).

## 14. Nguồn
- Code: `tests/test_switchover_cross_process.py` — **đọc nguyên văn khi viết** (quote khớp worker + spawn args + skipif).
- Kết quả: **chạy thật 1 passed; lặp 5/5 không flaky** (LOG #138); full 242 passed/1 skipped. → đã verify.
- Giải K-012: `ai-decision-journal/` D-015. · Độ chắc: cao (spawn thật, chạy nhiều lần).
