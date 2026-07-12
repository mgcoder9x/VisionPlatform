# 12.03 — IoU-greedy + tie-break XÁC ĐỊNH `sort(-iou, ni, pi)` — test lặp-lại-được

## 1. Thuộc về đâu
domain — `domain/tracking.py::greedy_associate` (phần lõi chọn cặp).

## 2. Cần biết trước
mẩu 02. "Greedy" = tham lam: chọn cặp tốt nhất trước, mỗi bên dùng 1 lần. "Xác định" (deterministic) = cùng input → cùng output MỌI lần chạy.

## 3. Code thật (quote nguyên văn — `domain/tracking.py`)
```python
    candidates: list[tuple[float, int, int]] = []
    for ni in range(len(new_boxes)):
        for pi in range(len(prev_boxes)):
            ...
            score = iou(new_boxes[ni], prev_boxes[pi])
            if score >= iou_threshold:
                candidates.append((score, ni, pi))

    # Tie-break XÁC ĐỊNH: iou giảm dần, rồi new_idx tăng, rồi prev_idx tăng.
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))

    used_new: set[int] = set()
    used_prev: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _score, ni, pi in candidates:
        if ni in used_new or pi in used_prev:
            continue
        used_new.add(ni)
        used_prev.add(pi)
        matches.append((ni, pi))
    matches.sort(key=lambda m: m[0])
    return matches
```

## 4. Giải thích từng mẩu nhỏ nhất
- Tạo MỌI cặp ứng viên `(score, ni, pi)` có iou >= ngưỡng.
- `sort(key=lambda c: (-c[0], c[1], c[2]))` — sắp: iou GIẢM dần (`-score`), rồi `ni` TĂNG, rồi `pi` TĂNG. Đây là
  **tie-break**: khi 2 cặp cùng iou, thứ tự vẫn CỐ ĐỊNH (theo index) → không phụ thuộc thứ tự dict/vòng lặp.
- Duyệt cặp tốt-nhất-trước: nếu `ni`/`pi` đã dùng → bỏ; chưa → nhận + đánh dấu dùng. (greedy, mỗi bên 1 lần.)
- `matches.sort(key=m[0])` — trả sắp theo new_idx (đầu ra ổn định).

## 5. Là gì
Ghép tham lam theo iou, với quy tắc phá-hoà (tie-break) cố định → kết quả xác định.

## 6. Tại sao tồn tại / vấn đề nó giải
Không có tie-break cố định: 2 cặp cùng iou → thứ tự chọn phụ thuộc thứ tự duyệt (có thể đổi giữa các lần/Python
version) → cùng input ra kết quả KHÁC → test flaky, khó tin. `sort(-iou, ni, pi)` khoá thứ tự → **test lặp-lại-được**
(chạy 100 lần cùng kết quả) — cực quan trọng cho analytics đếm (số phải ổn định).

## 7. Dùng ở đâu
`IouTracker.update` (mẩu 04) gọi → cặp index xác định → gán track_id ổn định. Test tracking assert số cụ thể được vì xác định.

## 8. Không có nó thì sao
Tie-break không cố định → association đổi giữa lần chạy → `track_id`/`unique_count` dao động → đếm không tin được +
test flaky (như vết K-035 nhưng ở tầng logic). Xác định = nền của "đếm chính xác kiểm chứng được".

## 9. Ví von
Xếp hàng ưu tiên theo điểm; 2 người bằng điểm → xét thêm số thứ tự đăng ký (cố định) → không ai "tranh chỗ" ngẫu nhiên.

## 10. Liên kết bức tranh lớn
"Xác định" là giá trị xuyên suốt repo (test PBT/đếm). Greedy (không Hungarian) = trade-off v1 (đủ + rẻ), nâng ML qua port sau (mẩu cau-chuyen nhịp 3–4).

## 11. Cạm bẫy
- Bỏ `ni`/`pi` khỏi key sort → chỉ sort theo iou → hoà iou thành không-xác-định. PHẢI có `ni, pi` trong key.
- Greedy KHÔNG tối ưu toàn cục: có thể có ghép tổng-iou-cao-hơn (Hungarian) — chấp nhận v1 (ghi rõ docstring).

## 12. Tự kiểm (Feynman)
- Vì sao cần `ni, pi` trong key sort? Bỏ đi thì bug gì?
- "Xác định" quan trọng thế nào cho analytics đếm + test?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/tracking.py::greedy_associate` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp).
