# Mẩu 02 — `IInferenceClient`: port chung cho inline + zmq

**(1) Thuộc về đâu:** `kernel/ports/inference_client.py`.

**(2) Cần biết trước:** Protocol (glossary `#protocol`); port/adapter (hexagonal); IDetector (#06 mẩu 07 — cùng ý tưởng port).

**(3) Code thật (quote `kernel/ports/inference_client.py`):**
```python
class IInferenceClient(Protocol):
    """Client gửi InferenceRequest → nhận InferenceResponse (echo request_id).
    Contract:
        - setup() trước infer() đầu (mở transport/nạp detector). Idempotent.
        - infer(request) trả InferenceResponse (SYNC, blocking tới khi có response/timeout).
        - teardown() giải phóng (đóng socket/detector). Idempotent.
    """
    def infer(self, request: InferenceRequest) -> InferenceResponse: ...
    def setup(self) -> None: ...
    def teardown(self) -> None: ...
```

**(4) Giải thích từng dòng:**
- `Protocol` → hợp đồng "vịt": ai có đủ 3 method là 1 inference client hợp lệ.
- `infer(request) -> InferenceResponse` → **SYNC blocking** (chờ tới khi có response hoặc timeout). Cả inline lẫn zmq đều sync ở mức API.
- `setup/teardown` → mở/đóng transport (inline: detector; zmq: socket + thread).

**(5) Là gì:** cổng chuẩn cho MỌI inference client (inline cùng-process HOẶC zmq cross-process).

**(6) Tại sao tồn tại / vấn đề nó giải:** caller (camera pipeline) không cần biết inference là inline
hay ZMQ — chỉ biết "có cái gì đó `infer` được". Đổi inline↔zmq chỉ ở composition root. **Vì sao GIỜ mới
tách port** (không phải ở #06): #06 chỉ có 1 bản (inline) → tách port lúc đó là trừu tượng hóa sớm (D-023
cố ý hoãn). Giờ có bản thứ 2 (zmq) → port mới thật sự cần (2 bản dùng chung).

**(7) Dùng ở đâu trong project:** `InlineInferenceClient` (#06) + `ZmqInferenceClient` (#06b) đều thoả.
Test `test_inline_client_satisfies_port` xác nhận inline khớp.

**(8) Không có port thì sao:** caller phải biết cụ thể inline/zmq → dính chặt; đổi transport phải sửa caller.

**(9) Ví von:** ổ cắm điện chuẩn — máy (caller) cắm được cả quạt (inline) lẫn máy lạnh (zmq) miễn đúng chuẩn ổ.

**(10) Liên kết bức tranh lớn:** cùng họ port `IFrameSource` (#03), `IDetector` (#06). `infer()` sync giữ
API đơn giản; async (asyncio) nếu cần sau chỉ đổi adapter, port không đổi.

**(11) Cạm bẫy:** Protocol không ép lúc import — thiếu method chỉ lộ khi dùng. Nên có test khớp port (đã có). `infer` sync: caller block tới timeout — phải đặt timeout hợp lý.

**(12) Tự kiểm:**
- Vì sao GIỜ mới tách `IInferenceClient` mà không phải ở #06?
- `infer()` sync hay async? Vì sao chọn vậy cho port?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/ports/inference_client.py` · journal D-023/D-028. Độ chắc: cao (quote thật + test khớp port pass).
