# Mẩu 09 — Vì sao `InlineInferenceClient` ở `application/` (KHÔNG phải `adapters/`) — ERRATA E-06-1

**(1) Thuộc về đâu:** `application/inline_inference_client.py`. **Điểm này là chỗ ta SỬA thiết kế gốc**
(Design đặt client ở `adapters/`).

**(2) Cần biết trước:** 6 layer + hướng phụ thuộc (`knowledge-base/hexagonal-architecture/`);
import-linter (công cụ ép luật import — bài #01 mẩu 06); "leaf/lá" = tầng ngoài rìa, không ai phụ
thuộc ngược lại.

**(3) Code thật — hai mảnh ghép:**

Client import runtime (quote `application/inline_inference_client.py`):
```python
from vision_platform.kernel.ports.detector import IDetector
from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameReader
```

Luật cấm (quote `vision-platform/pyproject.toml`):
```toml
[[tool.importlinter.contracts]]
name = "Adapters la leaf — khong import nguoc len runtime/application/profiles"
type = "forbidden"
source_modules = ["vision_platform.adapters"]
forbidden_modules = [
    "vision_platform.runtime", "vision_platform.application", "vision_platform.profiles",
]
```

**(4) Giải thích từng ý nhỏ:**
- Client **bắt buộc** import `ShmFrameReader` (ở `runtime`) để đọc frame từ SHM.
- Contract #5 nói: module trong `adapters` **cấm** import `runtime`.
- ⇒ Nếu để client ở `adapters/` → nó import runtime → `lint-imports` báo **BROKEN**. Đặt ở
  `application/` thì hợp lệ (contract #4 "Application dung ports" chỉ cấm application→adapters/profiles,
  KHÔNG cấm application→runtime).

**(5) Là gì:** đây là quyết định **chỗ đặt file** dựa trên luật kiến trúc, không phải sở thích.

**(6) Tại sao ở application đúng bản chất:** client KHÔNG phải "một loại thiết bị ngoài" (adapter). Nó
là **service điều phối**: cầm `ShmFrameReader` (runtime) + `IDetector` (port) rồi *dàn xếp* luồng
đọc→detect→trả. Đúng vai `application` (cùng chỗ `ring_supervisor.py`, `writer_epoch_coordinator.py`).

**(7) Dùng ở đâu / bằng chứng:** sau khi đặt ở `application/`, chạy `lint-imports` → **5 kept, 0
broken** (contract #5 vẫn KEPT). Đây là bằng chứng chỗ đặt đúng.

**(8) Không sửa (để ở adapters) thì sao:** `lint-imports` fail → CI đỏ → không build được. Hoặc tệ
hơn: phải nới luật (cho adapters gọi runtime) → phá ranh giới layer toàn hệ. Đó là "fix cái ngọn".

**(9) Ví von:** thợ điều phối kho (application) được phép vào kho (runtime) lấy hàng. Còn "ổ cắm thiết
bị" (adapter) chỉ là đầu nối ngoài rìa, không được tự ý đi vào kho.

**(10) Liên kết bức tranh lớn:** giữ hướng phụ thuộc `domain←kernel←runtime←application`; adapters ở
rìa. `FakeDetector` (adapter) chỉ chạm domain+kernel; client (application) mới được chạm runtime.

**(11) Cạm bẫy (và điểm tầm xa):** đừng vội tạo port `IInferenceClient` bây giờ — chỉ có 1 bản
(inline) nên là trừu tượng hoá sớm. Khi làm bản **ZMQ** (2 bản) mới tách port chung. (Ghi ở nhịp 6
cau-chuyen + journal.)

**(12) Tự kiểm:**
- Vì sao đặt client ở `adapters/` làm `lint-imports` broken? Trích đúng contract.
- Client khác `FakeDetector` ở chỗ nào khiến chúng ở 2 layer khác nhau?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/inline_inference_client.py` · `vision-platform/pyproject.toml` (contract
#4/#5, đã đọc trực tiếp) · Design step-06 ERRATA E-06-1 · journal D-023/C-007. Độ chắc: cao (lint
5 kept/0 broken verify thật).
