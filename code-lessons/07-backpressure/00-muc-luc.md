# Bài #07 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung: producer nhanh > consumer → đầy → 4 policy). Rồi tới mẩu dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + code verify. Cột Feynman = riêng (user học sau).
> Bám code thật: `kernel/backpressure.py` + `tests/test_step_07_backpressure.py` — **11 passed**,
> full **272 passed/1 skipped** · lint **5 kept/0 broken**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-backpressure.md` | Bức tranh: producer nhanh > consumer → hàng đợi → đầy thì sao (Forces) | `kernel/backpressure.py` (docstring) | ✅ |
| 02 | `02-bon-policy.md` | `BackpressurePolicy` enum 4 giá trị + khi nào dùng cái nào | `kernel/backpressure.py` (enum) | ✅ |
| 03 | `03-boundedqueue-cau-truc.md` | `__init__`: deque + maxsize + Lock + 2 Condition + 3 metrics; `maxsize<1`→ValueError | `kernel/backpressure.py` (__init__) | ✅ |
| 04 | `04-put-4-nhanh.md` | `put()`: còn chỗ → append; đầy → 4 nhánh policy; return True/False nghĩa gì | `kernel/backpressure.py` (put) | ✅ |
| 05 | `05-condition-wait-for.md` | `Condition` vs `Event`; `wait_for(predicate,timeout)` chống spurious wakeup; notify() | `kernel/backpressure.py` (put/get) | ✅ |
| 06 | `06-get-vs-get-or-raise.md` | `get` trả None khi timeout vs `get_or_raise` raise queue.Empty (None-ambiguity) | `kernel/backpressure.py` (get/get_or_raise) | ✅ |
| 07 | `07-thread-vs-process-safe.md` | **K-016**: threading.Lock chỉ đồng bộ trong 1 tiến trình; cross-process phải SHM #05 | `kernel/backpressure.py` (docstring) | ✅ |
| 08 | `08-tests-11-concurrent.md` | 11 test: 4 policy + 2 BLOCK (timing) + 1 concurrent 100-item + 4 phụ | `tests/test_step_07_backpressure.py` | ✅ |

> ✅ **ĐỦ 8/8 MẨU** — quote nguyên văn code + neo test đã pass (11 passed, full 272/1). Template 14 mục.
> **Cổng Feynman:** user tự giải thích lại (học sau). AI KHÔNG tự chấm "đã hiểu". Không dán lesson vào chat.
