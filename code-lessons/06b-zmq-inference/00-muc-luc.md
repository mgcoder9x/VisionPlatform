# Bài #06b — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung: inline→ZMQ, bulkhead + K-023). Rồi mẩu dưới.
> Trạng thái: ✅ đã viết + code verify. Cột Feynman = riêng (user học sau).
> Bám code thật: `kernel/inference_wire_codec.py`, `kernel/ports/inference_client.py`,
> `adapters/zmq_inference_client.py`, `application/inference_server.py` + 3 test file zmq —
> **10 test pass**, full **300 passed/1 skipped** · lint **5 kept/0 broken**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-tach-process.md` | Vì sao tách detector ra process riêng (bulkhead) + K-023 (inline không sống switchover) | cau-chuyen + K-023 | ✅ |
| 02 | `02-iinferenceclient-port.md` | `IInferenceClient` Protocol — inline + zmq cùng hợp đồng (D-023 tách port giờ mới justify) | `kernel/ports/inference_client.py` | ✅ |
| 03 | `03-codec-2-tang.md` | Codec DTO↔dict THUẦN ở kernel (không msgpack) + msgpack ở rìa (QĐ-2, kernel dependency-free) | `kernel/inference_wire_codec.py` | ✅ |
| 04 | `04-client-socket-owner-thread.md` | `ZmqInferenceClient`: DEALER + socket-owner-thread (ZMQ không thread-safe) + correlation map + timeout→retryable | `adapters/zmq_inference_client.py` | ✅ |
| 05 | `05-server-router-loop.md` | `InferenceServer`: ROUTER poller-loop single-thread cooperative (QĐ-3) | `application/inference_server.py` (serve) | ✅ |
| 06 | `06-switchover-aware-k023.md` | Server dùng `ReaderEpochCoordinator` → switchover-aware (K-023a) + retryable đúng (K-023b) | `application/inference_server.py` (_handle) | ✅ |
| 07 | `07-layer-adapters-vs-application.md` | Vì sao client@adapters (leaf) vs server@application; msgpack cấm ở kernel + negative-test | `pyproject.toml` contract + code | ✅ |
| 08 | `08-tests-cross-process.md` | 10 test: codec/port + cross-process (correlation/stale/bulkhead/server-chết) + switchover (Property 2) | 3 test file zmq | ✅ |

> ✅ **ĐỦ 8/8 MẨU** — quote code thật + neo test đã pass (10 zmq, full 300/1). Template 14 mục.
> **Cổng Feynman:** user tự giải thích lại (học sau). AI KHÔNG tự chấm. Không dán lesson vào chat.
