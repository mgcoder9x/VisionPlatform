# 12.10 — `CrossingEvent` DTO — wall-clock ISO-8601 "Z", vì sao KHÔNG giữ BBox

## 1. Thuộc về đâu
Layer **kernel** — `kernel/crossing_event.py`. DTO thuần frozen, chỉ str/int/float (json/msgpack-friendly).

## 2. Cần biết trước
mẩu 09 (LineCrossingStage tạo event). "wall-clock" = giờ đồng hồ THẬT (khác `monotonic` chỉ để đo khoảng).

## 3. Code thật (quote nguyên văn — `kernel/crossing_event.py`)
```python
@dataclass(frozen=True)
class CrossingEvent:
    track_id: int
    label: str
    direction: str      # "in" | "out" (theo dấu phía so vạch A→B)
    source_id: str
    cx: float
    cy: float
    event_ts: str        # ISO-8601 UTC, hậu tố "Z"
```

## 4. Giải thích từng mẩu nhỏ nhất
- `track_id`/`label` — vật nào (từ Track).
- `direction` — "in"/"out" (mẩu 09, từ dấu orient).
- `source_id` — camera nào (phân biệt khi nhiều camera đổ chung sink).
- `cx, cy` — TÂM lúc qua vạch (đủ cho event; KHÔNG giữ cả BBox).
- `event_ts` — chuỗi ISO-8601 UTC hậu tố "Z" (vd `2026-07-12T01:23:45.678Z`) = giờ THẬT.
- `frozen=True` — bất biến (event là sự-thật-đã-xảy-ra, không sửa).

## 5. Là gì
Bản ghi 1 lượt vật băng qua vạch — đơn vị dữ liệu ghi vào sink (JSONL/SQLite) để report.

## 6. Tại sao chỉ str/int/float + wall-clock (2 quyết định)
- **Chỉ kiểu nguyên thuỷ (không BBox):** event để LƯU + TRUY VẤN (report theo giờ/hướng/camera). `cx,cy` đủ định
  vị; BBox đầy đủ (4 số + space) là thừa cho event (còn ở detections nếu cần). → DTO gọn, serialize thẳng json/sqlite.
- **wall-clock UTC "Z" (không monotonic):** đọc LẠI event sau này cần giờ THẬT ("xe qua lúc 01:23"). `monotonic` chỉ
  có nghĩa trong 1 tiến trình đang chạy (đo khoảng), đọc lại vô nghĩa. Hậu tố "Z" = chuẩn UTC rõ ràng (đồng bộ QĐ-4 với JsonlEventSink).

## 7. Dùng ở đâu
`LineCrossingStage` tạo `CrossingEvent` → ghi `artifacts["crossing_events"]` → `CrossingEventJsonlSink`/
`CrossingEventSqliteSink` đọc + lưu (SQLite: `event_ts, source_id, track_id, label, direction, cx, cy` — param-hoá).

## 8. Không có nó thì sao
Ghi dict thô → sink đoán key, dễ lệch schema, khó query. DTO frozen kiểu-hoá = hợp đồng ổn định giữa stage↔sink.
Nếu dùng monotonic thay wall-clock → log "qua vạch lúc 1234567 ns" (vô nghĩa khi đọc lại).

## 9. Ví von
Vé ghi lượt qua trạm: mã xe, chiều (vào/ra), trạm nào, toạ độ, GIỜ THẬT — đủ để tra cứu sau, không cần ảnh đầy đủ.

## 10. Liên kết bức tranh lớn
Đầu ra nghiệp vụ của analytics → sink → report. kernel DTO json-friendly = ranh giới sạch giữa "tính toán" (stage)
và "lưu trữ" (sink adapter). Nối SQLite sink (review §E.1: param-hoá + durability).

## 11. Cạm bẫy
- Đừng nhét BBox/np.array vào event (không json-friendly + thừa). Chỉ nguyên thuỷ.
- `event_ts` phải wall-clock UTC (clock tiêm được để test giờ cố định — xem LineCrossingStage `clock`).

## 12. Tự kiểm (Feynman)
- Vì sao `event_ts` là wall-clock UTC chứ không `monotonic`?
- Vì sao event chỉ giữ `cx,cy` mà không giữ cả BBox?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/crossing_event.py` (đọc thật phiên này) · spec crossing-event-log (QĐ-4). Độ chắc: cao (quote trực tiếp).
