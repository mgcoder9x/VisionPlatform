# Bài #06b — ZMQ inference (cross-process): câu chuyện (vòng cung vấn đề → giải pháp)

> Đọc file này TRƯỚC. Kể *tại sao cần tách inference ra process riêng qua ZMQ* và *tại sao thiết kế
> như vậy*, trước khi xem từng dòng ở các mẩu `01..08`. "b" = tiến hoá của #06 (inline → ZMQ production).
> Bám code thật: `kernel/inference_wire_codec.py`, `kernel/ports/inference_client.py`,
> `adapters/zmq_inference_client.py`, `application/inference_server.py` + test cross-process
> (trạng thái: **10 test zmq pass**, full 300 passed/1 skipped, lint 5/0; pyzmq 27.1.0 + msgpack 1.2.1).

---

## Nhịp 1 — Tổng quan: từ inline (#06) lên ZMQ (#06b)

Bài #06 xây `InlineInferenceClient` — detector chạy **cùng process** với camera (đơn giản, học pattern
`request_id`). Bài #06b tiến lên bản **production**: detector chạy **process RIÊNG**, camera nói chuyện
với nó qua **ZMQ** (thư viện gửi tin giữa các tiến trình — glossary `#zmq`).

```
 CAMERA PROCESS                              INFERENCE PROCESS (riêng — bulkhead)
 ┌─────────────────────────┐                ┌───────────────────────────────────┐
 │ writer → SHM ring        │                │ InferenceServer (ROUTER)            │
 │ ZmqInferenceClient(DEALER)│──req(msgpack)─►│  đọc SHM (switchover-aware) → detect│
 │  ◄────── resp ────────────│                │  → gửi response                     │
 └─────────────────────────┘                └───────────────────────────────────┘
```

Vé vẫn mỏng: client gửi `InferenceRequest` (có `frame_ref` trỏ SHM) — KHÔNG gửi pixel. Server đọc frame
từ SHM (cùng cơ chế #05b), detect, trả kết quả kèm `request_id`.

> **Layer:** `IInferenceClient` + codec ở `kernel`; `ZmqInferenceClient` ở `adapters`; `InferenceServer` ở `application`.

---

## Nhịp 2 — Vấn đề & TẠI SAO (Forces)

**Nỗi đau 1 — inline không cách ly.** Detector chạy cùng process camera → detector/GPU crash (CUDA OOM)
kéo sập luôn camera. Nhiều camera dùng chung GPU cũng khó. Cần **bulkhead**: detector ở process riêng.

**Nỗi đau 2 (chính bài này tìm ra — K-023) — inline không sống sót switchover.** `InlineInferenceClient`
giữ **reader cố định**. Sau khi ring switchover (#05b) sang epoch mới, inline đọc ring cũ → luôn stale →
inference **chết thầm** (an toàn không đọc nhầm, nhưng không tự hồi phục). Production KHÔNG chấp nhận.

**Nỗi đau 3 — phân loại lỗi sai.** Inline trả mọi lỗi `retryable=False`. Nhưng stale (ring vừa đổi) là
**tạm thời** — retry sẽ được. Circuit-breaker hiểu nhầm "vĩnh viễn" → **bỏ camera oan**.

**Nỗi đau 4 — gửi qua wire.** Async + đa client → response về **không đúng thứ tự** → cần `request_id`
(như #06) + phải **đóng gói DTO thành bytes** (msgpack) để đi qua socket.

→ 🤔 **Đoán thử:** làm sao server đọc được frame trong SHM của *process khác*? (gợi ý: #05b đã giải cho switchover)

---

## Nhịp 3 — Khám phá nhiều hướng

**Server đọc SHM cross-process:**
- *Hướng 1 — gửi cả pixel qua ZMQ:* nặng (mỗi frame MB) → nghẽn mạng. Loại.
- *Hướng 2 — gửi `frame_ref`, server đọc SHM:* nhẹ (vé nhỏ). Nhưng server (process khác) cần **khoá** của
  ring → tái dùng cơ chế **lock thừa kế** #05b T-B (`make_pool_opener` + `slot_locks_map` qua spawn). **Chọn.**

**Đọc switchover-aware (đóng K-023):**
- *Hướng 1 — reader cố định (như inline):* stale vĩnh viễn sau switchover. Loại cho production.
- *Hướng 2 — `ReaderEpochCoordinator`:* poll control-plane, epoch đổi → tự chuyển ring. **Chọn** (đã có sẵn từ #05b).

**Correlation qua async:**
- ZMQ socket **KHÔNG thread-safe** → không được send (caller) + recv (thread khác) trên cùng socket.
- *Hướng — socket-owner-thread:* caller đẩy request vào queue; 1 thread sở hữu socket làm cả send+recv. **Chọn.**

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO thắng

1. **ROUTER (server) / DEALER (client)** + wire **msgpack** — cặp socket async chuẩn ZMQ; msgpack đóng gói DTO gọn.
2. **Server dùng `ReaderEpochCoordinator`** (không reader cố định) → **switchover-aware** → đóng **K-023(a)**.
   Đây là điểm khác cốt lõi vs inline #06.
3. **retryable đúng loại**: stale/timeout/queue-đầy=True; detector-lỗi/bad-input=False → đóng **K-023(b)**.
4. **socket-owner-thread** ở client (ZMQ không thread-safe) — caller đẩy queue, 1 thread sở hữu DEALER.
5. **Codec 2 tầng**: kernel làm DTO↔dict **thuần** (không msgpack → kernel dependency-free); msgpack (dict↔bytes) ở rìa transport.
6. **Layer**: `ZmqInferenceClient` là **leaf-adapter thật** (chỉ transport, không đọc SHM) — khác inline phải ở
   application (vì inline đọc SHM). `InferenceServer` ở application (đọc SHM + điều phối).

> Đổi so với intent step-06: dùng **threading correlation** thay `asyncio.Future` (repo không async) — C-010.

---

## Nhịp 5 — Triển khai (vào code)

Đọc các mẩu (`00-muc-luc.md`): vì-sao tách process → port → codec 2 tầng → client socket-owner-thread →
server ROUTER → switchover-aware (K-023) → layer adapters-vs-application + negative-test → test cross-process.

## Nhịp 6 — Nên làm / nên tránh

- ✅ **NÊN:** gửi `frame_ref` (vé mỏng) qua ZMQ, server đọc SHM (không gửi pixel).
- ✅ **NÊN:** server switchover-aware (ReaderEpochCoordinator) → sống sót ring đổi epoch.
- ✅ **NÊN:** phân loại retryable đúng (stale/timeout=True) để circuit-breaker không bỏ camera oan.
- ✅ **NÊN:** 1 thread sở hữu 1 socket (ZMQ không thread-safe).
- ⛔ **TRÁNH:** send từ caller-thread + recv từ thread khác trên CÙNG socket (undefined).
- ⛔ **TRÁNH:** dùng inline client cho hệ có switchover (stale vĩnh viễn — K-023).
- ⛔ **TRÁNH:** để kernel import msgpack/zmq (đã cấm bằng import-linter + negative-test).
