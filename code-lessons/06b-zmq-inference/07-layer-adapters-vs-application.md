# Mẩu 07 — Layer: client@adapters (leaf) vs server@application + msgpack cấm ở kernel

**(1) Thuộc về đâu:** quyết định đặt file theo layer + contract import-linter (`pyproject.toml`).

**(2) Cần biết trước:** 6 layer + hướng phụ thuộc; import-linter (#01); leaf-adapter; E-06-1 (#06: inline client phải ở application vì đọc SHM).

**(3) Bằng chứng thật:**
- `ZmqInferenceClient` (adapters) import: `kernel` (DTO+codec+port) + `zmq` + `msgpack` — KHÔNG runtime.
- `InferenceServer` (application) import: `runtime` (make_pool_opener) + `ReaderEpochCoordinator` + `kernel` + `zmq` + `msgpack`.
- Contract kernel (quote `pyproject.toml`): `forbidden_modules = [... "zmq", ... "msgpack", ...]`.

**(4) Giải thích từng ý nhỏ:**
- **ZmqInferenceClient ở `adapters`** vì nó CHỈ transport (gửi/nhận bytes) — **KHÔNG đọc SHM** → không cần
  runtime → thoả "adapters là leaf". Đây là điểm ĐẸP: khác `InlineInferenceClient` (phải ở application vì
  inline ĐỌC SHM → cần runtime — E-06-1). Cùng port, khác layer, vì khác việc chạm.
- **InferenceServer ở `application`** vì nó ĐỌC SHM (runtime) + điều phối coordinator → đúng application.
- **kernel cấm `zmq` + `msgpack`** → codec/DTO/port ở kernel KHÔNG được lệ thuộc lib wire → giữ kernel thuần.

**(5) Là gì:** quyết định chỗ đặt file dựa luật layer, không phải sở thích — mỗi file ở layer khớp việc nó chạm.

**(6) Tại sao (bản chất):** hexagonal ép hướng phụ thuộc `domain←kernel←runtime←application`, adapters/profiles ở
rìa. "Chạm runtime (SHM)" → application; "chỉ transport" → adapters (leaf). Cấm zmq/msgpack ở kernel để tầng
DTO không dính công nghệ wire (đổi msgpack→protobuf không đụng kernel).

**(7) Dùng ở đâu / bằng chứng (negative-test):** thêm tạm `import msgpack` vào `kernel/inference_wire_codec.py`
→ `lint-imports` báo **BROKEN** ("vision_platform.kernel is not allowed to import msgpack") → gỡ → **5 kept, 0
broken**. Chứng minh luật CƯỠNG CHẾ thật (không chỉ lời dặn). (Cùng pattern #05 E-15 với multiprocessing.)

**(8) Không có luật này thì sao:** kernel có thể lỡ import zmq/msgpack → tầng DTO dính transport → đổi wire
phải sửa kernel; hoặc client zmq lỡ đọc SHM → phá bulkhead layer. Lint bắt ngay.

**(9) Ví von:** phân vai nhân sự: nhân viên "giao nhận" (adapters client — chỉ chuyển gói) khác "thủ kho"
(application server — vào kho lấy hàng). Quy định "phòng thiết kế biểu mẫu (kernel) không được dùng máy fax
(msgpack)" — có bảo vệ (lint) chặn ở cửa.

**(10) Liên kết bức tranh lớn:** nối E-06-1 (#06 client ở application vì đọc SHM) — giờ thấy rõ: đọc-SHM
quyết định layer. import-linter là "hàng rào" giữ kiến trúc không rữa theo thời gian.

**(11) Cạm bẫy:** đừng để client zmq đọc SHM (sẽ thành application, mất tính leaf). Đừng import zmq/msgpack ở
kernel/domain (lint chặn). Nhớ `include_external_packages=true` để lint phân tích lib ngoài.

**(12) Tự kiểm:**
- Vì sao `ZmqInferenceClient` ở adapters còn `InlineInferenceClient` ở application (cùng port)?
- Negative-test msgpack chứng minh điều gì? Nếu bỏ luật cấm, rủi ro gì?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `pyproject.toml` (contract kernel/adapters/application) · `adapters/zmq_inference_client.py` · `application/inference_server.py` · LOG #171 (negative-test). Độ chắc: cao (lint BROKEN→kept verify thật).
