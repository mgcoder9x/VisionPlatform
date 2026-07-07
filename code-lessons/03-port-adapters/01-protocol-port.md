# #03 · Mẩu 01: `Protocol` + `IFrameSource` — port theo structural typing

## 1. Thuộc về đâu
Vấn đề #03 · file code thật: `vision-platform/src/vision_platform/kernel/ports/frame_source.py` · tầng **kernel** (thư mục `ports/`) ·
đây là **cổng (port)** đầu tiên: hợp đồng "nguồn cung cấp frame".

## 2. Cần biết trước
- [port](../../knowledge-base/00-GLOSSARY.md#port-cổng--hexagonal) ·
  [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
  [Protocol](../../knowledge-base/00-GLOSSARY.md#protocol-typingprotocol) ·
  [ReadResult](../02-data-objects/04-readresult-status.md)
- Mẩu 05 bài #01 (6 tầng) — port nằm ở `kernel`, adapter ở `adapters`.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/ports/frame_source.py
"""IFrameSource — driven port cho nguồn cung cấp frame."""
from typing import Protocol
import numpy as np
from vision_platform.kernel.read_result import ReadResult


class IFrameSource(Protocol):
    """Inbound source of frames (np.ndarray).

    Contract:
        - setup() MUST be called before first read(). Idempotent.
        - read(timeout_ms) returns ReadResult — KHÔNG return None.
        - teardown() releases resources. Idempotent.
        - is_finite True for batch (file ends → EOF), False for stream.
        - source_id unique cho logging/metrics.
        - Context manager: `with source as s:` → setup() lúc vào, teardown() lúc ra
          (kể cả khi raise). `__exit__` trả False (KHÔNG nuốt exception). (R2#04 / ERRATA E-16)
    """
    def setup(self) -> None: ...

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]: ...

    def teardown(self) -> None: ...

    def __enter__(self) -> "IFrameSource": ...

    def __exit__(self, exc_type, exc, tb) -> bool: ...

    @property
    def is_finite(self) -> bool: ...

    @property
    def source_id(self) -> str: ...
```

## 4. Giải thích từng phần nhỏ nhất
- `from typing import Protocol` → lấy công cụ khai báo "hợp đồng theo hình dạng".
- `class IFrameSource(Protocol):` → khai báo `IFrameSource` là một **Protocol**: bất kỳ lớp nào CÓ ĐỦ các method/property dưới đây (đúng tên + đúng dạng) thì được coi là "khớp" — **KHÔNG cần kế thừa**.
- Docstring liệt kê **hợp đồng** (contract) — luật mọi nguồn phải theo (chi tiết ở mẩu 02).
- `def setup(self) -> None: ...` → khai báo method `setup`, thân là `...` (Ellipsis = "chưa cài, chỉ mô tả chữ ký"). Protocol chỉ nói "phải có method này", không cài.
- `def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]: ...` → đọc 1 frame, trả `ReadResult[np.ndarray]` (mẩu #02-04/05), mặc định chờ 100ms.
- `def teardown(self) -> None: ...` → giải phóng tài nguyên.
- `def __enter__(self) -> "IFrameSource": ...` / `def __exit__(self, exc_type, exc, tb) -> bool: ...` → context manager (R2#04/E-16): cho phép `with source as s:` tự gọi setup lúc vào / teardown lúc ra (kể cả khi raise); adapter cài 2 method này (mẩu 03/06).
- `@property def is_finite(self) -> bool: ...` và `source_id(self) -> str: ...` → 2 thuộc tính đọc.
- `kernel/ports/frame_source.py` import `ReadResult` (cùng tầng kernel) + `numpy` — **KHÔNG** import adapter cụ thể (đúng hướng phụ thuộc).

## 5. Là gì (1–2 câu)
`IFrameSource` là **bản mô tả "một nguồn frame phải làm được gì"** (setup/read/teardown + is_finite/source_id),
KHÔNG nói làm bằng gì. `Protocol` cho phép lớp khác "khớp" chỉ bằng cách có đủ method đúng dạng.

## 6. Tại sao tồn tại / vấn đề nó giải
Lõi pipeline cần frame nhưng KHÔNG nên biết frame đến từ camera RTSP, file, hay nguồn giả. Tách thành
**port**: lõi chỉ phụ thuộc hợp đồng `IFrameSource` (ổn định), còn nguồn cụ thể là adapter ở rìa. Dùng
`Protocol` (structural) thay vì bắt kế thừa lớp cha → adapter (kể cả mock test) chỉ cần "đúng hình dạng",
không bị buộc vào cây kế thừa → linh hoạt, dễ test.

## 7. Dùng ở đâu trong project (cụ thể)
- `FakeFrameSource`, `NoiseFrameSource` (mẩu 03–06) **khớp** `IFrameSource` mà KHÔNG kế thừa nó.
- **Kiểm chứng thật (đã CHẠY phiên này):** `FakeFrameSource.__bases__` = `['object']` (KHÔNG kế thừa IFrameSource), nhưng `hasattr` đủ 5 thành phần `setup/read/teardown/is_finite/source_id` = `True`; `IFrameSource._is_protocol` = `True`. → đúng structural typing.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Không có port: pipeline gọi thẳng `cv2.VideoCapture` → dính OpenCV/camera, không test offline được, thêm
nguồn phải sửa lõi. Port `IFrameSource` cắt sợi dây đó: đổi/​thêm nguồn = viết adapter mới, lõi không đụng.

## 9. Ví von đời thường
`IFrameSource` như **ổ cắm điện chuẩn**: nhà sản xuất thiết bị (adapter) chỉ cần làm phích đúng chuẩn là
cắm dùng được; ổ cắm (lõi) không cần biết đó là quạt hay đèn. `Protocol` = "đúng chuẩn phích thì cắm được", không cần giấy phép dòng họ.

## 10. Liên kết bức tranh lớn
Đây là cặp port→adapter ĐẦU TIÊN, hiện thực pattern Hexagonal (bài #01 mẩu 05). `read()` trả `ReadResult`
(bài #02) → 2 viên gạch nối nhau. Bài #04 (pipeline) sẽ tiêu thụ nguồn qua chính cổng này.

## 11. Cạm bẫy / lỗi thường gặp
- `IFrameSource` ở đây KHÔNG `@runtime_checkable` → gọi `isinstance(x, IFrameSource)` sẽ **raise `TypeError`** ("Instance and class checks can only be used with @runtime_checkable protocols" — đã CHẠY kiểm). Protocol kiểu này chỉ kiểm lúc static (mypy), không kiểm lúc chạy. Đừng dựa `isinstance` để kiểm khớp.
- Tưởng adapter phải `class Fake(IFrameSource)` → KHÔNG cần; chỉ cần đủ method đúng dạng.
- Để `kernel/ports/` import adapter cụ thể → vi phạm hướng phụ thuộc (import-linter chặn).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `Protocol` khác kế thừa lớp cha ở chỗ nào? `...` trong thân method nghĩa là gì?
- Tình huống: muốn thêm nguồn RTSP — phải kế thừa `IFrameSource` không? Cần làm gì để nó "khớp" port?
- Giải thích lại bằng LỜI MÌNH: "port để ... ; Protocol cho phép ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại port vs adapter | 1 tuần → tự viết 1 Protocol nhỏ + 1 lớp khớp (không kế thừa) | 1 tháng → giải thích structural vs nominal typing.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/ports/frame_source.py` (đã ĐỌC LẠI nguyên văn). · Độ chắc: **cao**.
- Structural typing: đã CHẠY THẬT — `FakeFrameSource.__bases__=['object']` + đủ 5 thành phần + `IFrameSource._is_protocol=True` (đọc output). · Độ chắc: **cao**.
- `isinstance` với Protocol không `@runtime_checkable` báo lỗi: đã CHẠY THẬT — `isinstance(FakeFrameSource(), IFrameSource)` → raise `TypeError` ("...only be used with @runtime_checkable protocols"). · Độ chắc: **cao** (bằng chứng trực tiếp).
