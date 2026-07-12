# 12.07 — `domain/geometry.py::orient` — cross-product dấu = "phía nào của đường"

## 1. Thuộc về đâu
Layer **domain** — `domain/geometry.py`. Toán 2D thuần trên điểm `(x,y)`, KHÔNG import BBox/kernel (tầng thấp nhất, tối giản).

## 2. Cần biết trước
điểm = tuple `(x,y)`. "Cross-product" (tích có hướng) 2D → 1 số; DẤU của nó cho biết chiều quay.

## 3. Code thật (quote nguyên văn — `domain/geometry.py`)
```python
def orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """Cross-product (B-A)×(C-A). >0: C bên trái AB · <0: bên phải · =0: thẳng hàng."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
```

## 4. Giải thích từng mẩu nhỏ nhất
- Cho đoạn A→B và điểm C. `orient` = tích có hướng của vector AB và AC.
- **Dấu**: `>0` → C nằm BÊN TRÁI hướng A→B · `<0` → BÊN PHẢI · `=0` → C thẳng hàng A,B.
- Chỉ cần DẤU (không cần độ lớn) → biết "C ở phía nào của đường AB".

## 5. Là gì
Hàm 1 dòng trả số mà DẤU = phía của điểm so với 1 đường có hướng.

## 6. Tại sao tồn tại / vấn đề nó giải
Line-crossing cần 2 thứ, cả 2 đều từ `orient`: (a) "2 đoạn có cắt nhau không" (mẩu 08) và (b) "vật qua vạch theo
HƯỚNG nào" (in/out). Hướng in/out = DẤU orient của tâm so với vạch A→B (quy ước theo thứ tự A,B). 1 phép toán,
2 công dụng → gọn + nhất quán.

## 7. Dùng ở đâu
- `segments_intersect` (mẩu 08) gọi `orient` 4 lần (2 đầu mỗi đoạn so đoạn kia).
- `LineCrossingStage._do_process` (mẩu 09): `direction = "in" if orient(ax,ay,bx,by,cx,cy) > 0 else "out"`.

## 8. Không có nó thì sao
Không có orient → phải tự chế công thức "phía nào" (dễ sai dấu) + "cắt nhau" (phức tạp) rải rác. `orient` gom về
1 nguyên thuỷ hình học đúng, tái dùng.

## 9. Ví von
Đứng ở A nhìn về B: điểm C ở tay TRÁI hay tay PHẢI? `orient` trả dấu = trái/phải.

## 10. Liên kết bức tranh lớn
Nguyên thuỷ hình học @domain, tái dùng cho zone/đa-giác sau (docstring nói vậy). Nền cho mẩu 08 + 09.

## 11. Cạm bẫy
- `=0` (thẳng hàng) là ca biên — mẩu 08 xử collinear bảo thủ (=False). `direction` dùng `>0 else "out"` → điểm
  đúng trên vạch (orient=0) rơi vào "out" (chấp nhận, xác suất ~0 với float thật).
- Thứ tự A,B định nghĩa "trái/phải" → đảo A,B thì in↔out đảo. Quy ước cố định theo config `--line ax,ay,bx,by`.

## 12. Tự kiểm (Feynman)
- `orient>0`/`<0`/`=0` nghĩa là gì về vị trí điểm C?
- Line-crossing dùng `orient` cho 2 việc gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/geometry.py::orient` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp). Ý nghĩa dấu cross-product 2D = toán chuẩn [độ chắc: cao].
