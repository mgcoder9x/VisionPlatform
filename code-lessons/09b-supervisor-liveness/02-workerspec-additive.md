# Mẩu 02 — WorkerSpec: 4 field additive (default TẮT → giữ 6 test #09)

**(1) Thuộc về đâu:** `application/supervisor.py`, `WorkerSpec` (dataclass) — các field thêm.

**(2) Cần biết trước:** WorkerSpec (#09 mẩu 02); "additive" (thêm không phá); default value = backward-compat.

**(3) Code thật (quote `application/supervisor.py`):**
```python
    uses_heartbeat: bool = False
    """True nếu `target` nhận `heartbeat: mp.Value('d')` để cập nhật nhịp (K-020). ..."""
    heartbeat_timeout_s: float = 2.0
    """Quá hạn này (giây, wall-clock) mà không có nhịp → coi HANG (chỉ khi uses_heartbeat)."""
    restart_backoff_base_s: float = 0.0
    """0 = KHÔNG backoff (respawn ngay như #09). >0 = giãn `base·2^(n-1)` giữa restart (K-021)."""
    restart_backoff_cap_s: float = 30.0
    """Trần backoff."""
```

**(4) Giải thích từng field:**
- `uses_heartbeat=False` → mặc định TẮT heartbeat (worker cũ không đổi).
- `heartbeat_timeout_s=2.0` → ngưỡng coi treo (chỉ dùng khi bật).
- `restart_backoff_base_s=0.0` → **0 = không backoff** (respawn ngay như #09); >0 mới giãn.
- `restart_backoff_cap_s=30.0` → trần thời gian chờ.

**(5) Là gì:** 4 tuỳ chọn thêm vào WorkerSpec để bật heartbeat + backoff — mặc định TẮT.

**(6) Tại sao default TẮT (bản chất — additive):** phải **không phá #09** (6 test đang xanh). Nếu default
BẬT, mọi worker cũ (không đập nhịp) sẽ bị coi treo → restart sai → vỡ test + hành vi. Default TẮT →
`uses_heartbeat=False`+`backoff=0` → hành vi Y HỆT #09. Bật là **opt-in** cho worker cần.

**(7) Dùng ở đâu trong project:** test liveness dùng `WorkerSpec(..., uses_heartbeat=True, heartbeat_timeout_s=0.5)`;
worker #09 (ok/crash/graceful) KHÔNG set → chạy như cũ. 6 test #09 giữ xanh (verify).

**(8) Không có default TẮT thì sao:** thêm heartbeat sẽ phá worker cũ (bị coi treo) → regression #09 → vi phạm additive.

**(9) Ví von:** thêm "chế độ báo động chuyển động" cho camera — mặc định TẮT để camera cũ không kêu loạn;
ai cần thì bật. Bật mặc định = mọi camera cũ kêu inh ỏi.

**(10) Liên kết bức tranh lớn:** cùng triết lý additive như #05b (Wave 3 không sửa Writer/Reader), #06 (port hoãn),
zmq (thêm không phá inline). "Thêm năng lực, zero regression" là văn hoá dự án.

**(11) Cạm bẫy:** đừng đổi default sang BẬT. `heartbeat_timeout_s` phải > chu kỳ đập nhịp của worker (nếu
timeout < chu kỳ → báo treo oan). backoff=0 phải giữ nghĩa "respawn ngay" (mẩu 06).

**(12) Tự kiểm:**
- Vì sao 4 field mặc định TẮT? Điều gì vỡ nếu default BẬT?
- `restart_backoff_base_s=0.0` nghĩa là gì về hành vi restart?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (WorkerSpec) · test #09 giữ 6 pass (regression). Độ chắc: cao (quote thật + regression pass).
