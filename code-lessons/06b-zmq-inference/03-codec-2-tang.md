# Mẩu 03 — Codec 2 tầng: kernel (DTO↔dict thuần) + msgpack ở rìa

**(1) Thuộc về đâu:** `kernel/inference_wire_codec.py`.

**(2) Cần biết trước:** serialize/wire (đóng gói dữ liệu để gửi); msgpack (định dạng nhị phân gọn); dependency-free (không lệ thuộc lib ngoài); Enum `.value`.

**(3) Code thật (quote `kernel/inference_wire_codec.py`):**
```python
"""Wire codec: DTO inference ↔ dict Python thuần (QĐ-2).
Layer: kernel — THUẦN, KHÔNG import msgpack/zmq (kernel dependency-free). Chỉ chuyển DTO ↔ `dict`
(msgpack-friendly: str/int/float/list/dict/None). Mã hoá dict↔bytes (msgpack) làm ở RÌA transport..."""

def bbox_to_dict(b: BBox) -> dict:
    return {"x": b.x, "y": b.y, "w": b.w, "h": b.h, "space": b.space.value}

def dict_to_bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"], space=CoordinateSpace(d["space"]))
```

**(4) Giải thích từng ý nhỏ:**
- Codec chỉ chuyển DTO ↔ `dict` Python (str/int/float/list/dict/None) — **KHÔNG import msgpack**.
- `b.space.value` → Enum `CoordinateSpace` → chuỗi ("model_input"); `CoordinateSpace(value)` → dựng lại Enum.
- msgpack (dict↔bytes) gọi ở **rìa transport** (client adapter + server), KHÔNG ở kernel.

**(5) Là gì:** bộ hàm chuyển DTO inference ↔ dict thuần, để tầng transport đóng gói bytes.

**(6) Tại sao 2 tầng (không nhét msgpack vào kernel):**
- Kernel là tầng DTO thuần → giữ **dependency-free** (không lệ thuộc lib wire). msgpack chỉ là 1 lựa chọn wire; đổi sang protobuf/JSON sau chỉ đổi **rìa**, kernel không động.
- Tách "biết cấu trúc DTO" (kernel) khỏi "mã hoá bytes" (transport) = ranh giới sạch.

**(7) Dùng ở đâu trong project:** `ZmqInferenceClient` (adapters): `msgpack.packb(codec.request_to_dict(req))`; `InferenceServer` (application): `codec.dict_to_request(msgpack.unpackb(payload))`. Test round-trip `test_zmq_codec.py`.

**(8) Không có (nhét msgpack vào kernel) thì sao:** kernel lệ thuộc msgpack → đổi wire phải sửa kernel; vi phạm "kernel thuần". (Đã CẤM bằng import-linter — mẩu 07.)

**(9) Ví von:** thư ký ghi nội dung ra **biểu mẫu chuẩn** (dict) — ai muốn gửi fax/email/bưu điện (msgpack/protobuf/json) thì tự đóng gói biểu mẫu đó theo cách mình. Thư ký không cần biết gửi kiểu gì.

**(10) Liên kết bức tranh lớn:** round-trip PHẢI giữ `ring_epoch` (int) + `CoordinateSpace` (enum) — nếu mất, server đọc nhầm/không transform được toạ độ. Test Property 6 chứng minh.

**(11) Cạm bẫy:** Enum phải qua `.value`↔`Enum(value)` (msgpack không hiểu Enum). Số float (confidence) giữ nguyên. Nested (frame_ref trong request, box trong detection) phải đệ quy đúng.

**(12) Tự kiểm:**
- Vì sao kernel KHÔNG import msgpack? Đổi wire sang protobuf thì file nào đổi?
- `CoordinateSpace` đi qua wire thế nào?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/inference_wire_codec.py` · `test_zmq_codec.py` (round-trip pass) · design QĐ-2. Độ chắc: cao (quote thật + test pass).
