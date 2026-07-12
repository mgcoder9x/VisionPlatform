# 12.08 — `segments_intersect` — 2 đoạn cắt nhau; collinear/điểm-suy-biến = False (vì sao)

## 1. Thuộc về đâu
domain — `domain/geometry.py::segments_intersect`. Dùng `orient` (mẩu 07) 4 lần.

## 2. Cần biết trước
mẩu 07 (`orient` + dấu). "Proper intersection" = 2 đoạn cắt nhau THẬT (mỗi đoạn nằm 2 phía đoạn kia).

## 3. Code thật (quote nguyên văn — `domain/geometry.py`)
```python
def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    d1 = orient(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = orient(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = orient(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = orient(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))
```

## 4. Giải thích từng mẩu nhỏ nhất
- `d1`, `d2` = phía của `p1`, `p2` so đoạn `[p3,p4]`. `d3`, `d4` = phía của `p3`, `p4` so đoạn `[p1,p2]`.
- `(d1 > 0) != (d2 > 0)` — `p1` và `p2` ở HAI phía KHÁC nhau của đường `p3p4` (một cái trái, một cái phải).
- `and ((d3>0) != (d4>0))` — đối xứng: `p3`,`p4` ở hai phía của `p1p2`.
- Cả hai đúng → 2 đoạn cắt nhau THẬT → `True`.

## 5. Là gì
Kiểm 2 đoạn thẳng `[p1,p2]` và `[p3,p4]` có cắt nhau (proper) không, bằng 4 phép `orient`.

## 6. Tại sao tồn tại / vấn đề nó giải
Line-crossing: đường-đi-tâm giữa 2 khung là đoạn `[prev, curr]`; vạch đếm là đoạn `[A, B]`. Vật "qua vạch" ⟺ 2
đoạn cắt nhau. `segments_intersect` cho câu trả lời hình học chính xác (thay vì so tâm 2 phía — dễ sai ca biên).

## 7. Dùng ở đâu
`LineCrossingStage._do_process` (mẩu 09): `if prev is not None and segments_intersect(prev, curr, self._a, self._b): +1`.

## 8. So-sánh STRICT `>0` → xử ca biên bảo thủ (điểm quan trọng)
Dùng `d>0` (strict, KHÔNG `>=`):
- **collinear** (mọi orient=0, vật đi DỌC vạch): `(0>0)!=(0>0)` = `False!=False` = `False` → KHÔNG coi là cắt.
  Đúng nghiệp vụ: đi DỌC vạch ≠ QUA vạch.
- **đoạn suy biến thành ĐIỂM** (`p1==p2`, vật đứng yên): không có chuyển động → `False`. Đúng: đứng yên không qua vạch.
- chạm đúng 1 mép hiếm (1 orient=0) có thể trả `True` — chấp nhận v1 (xác suất ~0 với float thật; docstring ghi rõ).

## 9. Không có nó thì sao
So tâm "khung trước bên này, khung này bên kia" (không dùng đoạn cắt) → sai khi vật nhảy xa/ca biên; hoặc tự chế
kiểm cắt → dễ sai dấu. `segments_intersect` chuẩn hoá.

## 10. Ví von
2 que diêm bắt chéo: cắt nhau ⟺ mỗi que có 2 đầu nằm 2 phía que kia. Song song/nối đuôi (collinear) → không bắt chéo.

## 11. Cạm bẫy
- `>=` thay `>` sẽ coi chạm-mép/collinear là cắt → đếm oan khi vật lướt DỌC vạch. Giữ strict `>`.
- Đoạn `[prev,curr]` chỉ có khi đã có `prev` (khung trước của track) → mẩu 09 kiểm `prev is not None`.

## 12. Tự kiểm (Feynman)
- Giải thích `(d1>0)!=(d2>0)` nghĩa là gì về vị trí p1,p2.
- Vì sao dùng `>` (strict) chứ không `>=`? Ca "đi dọc vạch" ra True hay False, và vì sao đúng?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/geometry.py::segments_intersect` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp).
