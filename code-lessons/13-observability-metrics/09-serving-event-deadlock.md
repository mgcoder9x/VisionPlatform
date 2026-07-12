# 13.09 — `_serving` Event chống DEADLOCK `stop()` (K-071)

## 1. Thuộc về đâu
adapters — `metrics_http_server.py` (`_serving` + `start`/`stop`). Xử vòng đời server an toàn.

## 2. Cần biết trước
mẩu 08 (exporter chạy `serve_forever` trong thread nền). `threading.Event` = cờ chờ giữa thread. `BaseServer.shutdown()` (stdlib).

## 3. Code thật (quote nguyên văn — `metrics_http_server.py`)
```python
        self._serving = threading.Event()   # set NGAY TRƯỚC serve_forever (chống deadlock stop-sớm, K-071)

    def start(self) -> int:
        ...
        def _serve():
            self._serving.set()                # báo "sắp serve_forever" cho stop()
            srv.serve_forever(poll_interval=0.2)
        self._thread = threading.Thread(target=_serve, name="metrics-exporter", daemon=True)
        self._thread.start()
        return self._port

    def stop(self) -> None:
        if self._srv is None: return
        self._serving.wait(timeout=5.0)        # BaseServer.shutdown yêu cầu serve_forever ĐANG chạy
        self._srv.shutdown()
        self._srv.server_close()
        if self._thread is not None: self._thread.join(timeout=5.0)
        self._srv = None; self._thread = None; self._serving.clear()
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_serving = threading.Event()` — cờ báo "serve_forever đã bắt đầu".
- Trong `_serve` (thread nền): `self._serving.set()` NGAY TRƯỚC `srv.serve_forever(...)`.
- `stop()`: `self._serving.wait(timeout=5.0)` — CHỜ tới khi `_serving` được set (tức serve_forever đã chạy) RỒI mới
  `srv.shutdown()`. `poll_interval=0.2` để `serve_forever` kiểm cờ dừng thường xuyên.
- Sau shutdown: `server_close()` + `thread.join()` + reset. `if self._srv is None: return` → idempotent (gọi stop 2 lần vô hại).

## 5. Là gì
Cơ chế đảm bảo `stop()` chỉ gọi `shutdown()` KHI `serve_forever()` ĐÃ thực sự chạy.

## 6. Tại sao tồn tại (DEADLOCK K-071)
`BaseServer.shutdown()` (stdlib) CHỜ tới khi `serve_forever()` thoát vòng lặp; nhưng nó chỉ hoạt động NẾU
`serve_forever()` ĐANG chạy. Nếu gọi `stop()` NGAY sau `start()` (thread nền chưa kịp vào `serve_forever`) →
`shutdown()` chờ 1 vòng lặp CHƯA tồn tại → **treo mãi mãi (deadlock)**. `_serving.wait()` chặn `stop()` cho tới khi
serve_forever chắc chắn đã bắt đầu → shutdown hoạt động đúng. Đây là fix GỐC (đồng bộ 2 thread bằng Event).

## 7. Dùng ở đâu
`_build_config_observability` / `main` gọi `exporter.stop()` trong `finally` (đóng cổng, không rò) — kể cả khi
pipeline raise hoặc process dừng nhanh sau start. `_serving.wait` bảo đảm không deadlock.

## 8. Không có nó thì sao
`start()` rồi `stop()` ngay (test/chạy ngắn) → `shutdown()` treo (serve_forever chưa chạy) → process không thoát được
→ hang. K-071 đúng bẫy này. `_serving` Event bịt.

## 9. Ví von
Muốn TẮT máy chỉ khi máy đã KHỞI ĐỘNG XONG; bấm tắt lúc đang khởi động → kẹt. Đợi đèn "sẵn sàng" (Event) rồi mới bấm tắt.

## 10. Liên kết bức tranh lớn
Vòng đời khâu SERVE. Đảm bảo `stop()` sạch (không rò cổng/thread, không deadlock) — quan trọng cho service chạy dài
+ test lặp (start/stop nhiều lần). Nối `exporter.stop()` finally (mẩu 08/10).

## 11. Cạm bẫy
- Gọi `shutdown()` mà không chờ `_serving` → deadlock nếu stop-sớm. Luôn `wait` trước.
- `timeout` ở `wait`/`join` tránh treo vô hạn nếu có sự cố (fail-safe).

## 12. Tự kiểm (Feynman)
- Vì sao `stop()` NGAY sau `start()` có thể deadlock nếu không có `_serving`?
- `_serving.set()` đặt Ở ĐÂU, vì sao ngay trước `serve_forever`?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`adapters/metrics_http_server.py` (đọc thật phiên này) · K-071/#290. Độ chắc: cao (quote trực tiếp).
