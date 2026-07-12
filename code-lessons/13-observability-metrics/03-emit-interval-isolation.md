# 13.03 — `PipelineRunner._emit` — emit theo-GIỜ ở ĐẦU loop (mất-camera vẫn phát) + CÔ LẬP lỗi observer

## 1. Thuộc về đâu
runtime — `runtime/pipeline_runner.py` (hàm `_emit` nội bộ trong `run()`). Nơi ĐO thực sự phát snapshot.

## 2. Cần biết trước
mẩu 01 (port), 02 (snapshot fps interval). Bài #04 (vòng lặp runner). `emit_interval_s`/`emit_every_n` (tham số runner).

## 3. Code thật (quote nguyên văn — `runtime/pipeline_runner.py`)
```python
        def _emit(is_final: bool) -> None:
            nonlocal last_emit_ns, last_emit_frames
            now = self._clock_ns()
            dt = (now - last_emit_ns) / 1e9
            d_frames = frames_read - last_emit_frames
            last_emit_ns = now
            last_emit_frames = frames_read
            try:
                fps = d_frames / dt if dt > 1e-9 else 0.0
                skip_rate = skipped / frames_read if frames_read > 0 else 0.0
                snap = PipelineSnapshot(source_id=self._source.source_id, frames_read=frames_read, ...)
                self._observer.on_snapshot(snap)
            except Exception:  # noqa: BLE001 — quan sát phụ trợ: cô lập lỗi observer, KHÔNG sập pipeline
                self._observer_errors += 1
                _log.warning("observer_error", is_final=is_final, exc_info=True)
```
Trong loop:
```python
            if self._emit_interval_s > 0 and (self._clock_ns() - last_emit_ns) / 1e9 >= self._emit_interval_s:
                _emit(is_final=False)     # ĐẦU loop, TRƯỚC read → mất-camera vẫn phát
```
Và `finally: _emit(is_final=True)` (bọc ngoài cùng).

## 4. Giải thích từng mẩu nhỏ nhất
- `dt = (now - last_emit_ns)/1e9`, `d_frames = frames_read - last_emit_frames` → `fps = d_frames/dt` = **fps INTERVAL** (mẩu 02).
- Cập nhật `last_emit_ns/frames` TRƯỚC (tránh re-emit dồn).
- **CÔ LẬP lỗi**: toàn bộ dựng+phát bọc `try/except Exception` → observer lỗi/chậm-raise chỉ `_observer_errors += 1` + log warning, KHÔNG raise ra vòng lặp → **pipeline không sập** vì quan sát (quan sát là PHỤ TRỢ).
- **emit theo-GIỜ ở ĐẦU loop** (trước `source.read`): dù camera mất kết nối (read trả no-data → continue), vòng lặp vẫn quay → tới mốc giờ vẫn `_emit` (frames_read đứng yên + source_errors tăng) → THẤY sự cố live (fix Lỗ-A #275).
- `finally: _emit(is_final=True)` — LUÔN phát snapshot CHỐT (kể cả khi thân raise).

## 5. Là gì
Cơ chế phát snapshot định kỳ (theo giờ/theo frame) + tính fps interval + cô lập lỗi observer.

## 6. Tại sao tồn tại / vấn đề nó giải
- emit theo-giờ ĐẦU loop: nếu emit chỉ SAU khi xử frame, camera mất-kết-nối (không có frame) → KHÔNG bao giờ emit
  → dashboard "đứng hình" tưởng ổn. Đặt ĐẦU loop theo giờ → mất-camera vẫn phát (frames_read đứng) = lộ sự cố.
- cô lập lỗi: observer (vd ghi log/mạng) lỗi KHÔNG được kéo sập xử lý frame (nghiệp vụ chính). Quan sát phụ trợ.

## 7. Dùng ở đâu
`run()` gọi `_emit` ở đầu loop (theo giờ), sau cập nhật đếm (theo frame `emit_every_n`), và `finally` (chốt).
Bật qua `--observe`/`--metrics-port` (mẩu 10). Default `NoopObserver` → `_emit` vô hại (opt-in).

## 8. Không có nó thì sao
Emit sau-frame → mất-camera không phát (che sự cố). Không cô lập lỗi → observer lỗi làm sập pipeline (quan sát kéo sập nghiệp vụ — sai).

## 9. Ví von
Y tá đo mạch bệnh nhân MỖI 5 phút DÙ bệnh nhân bất tỉnh (không cử động) — vì "không cử động" chính là dấu hiệu cần
thấy; và nếu máy đo hỏng thì thay máy, KHÔNG để nó làm ngừng cấp cứu.

## 10. Liên kết bức tranh lớn
Trái tim khâu ĐO. Nối observer (mẩu 04) qua port (01). "Cô lập lỗi observer" = 1 trong các điểm SOUND review nêu (`docs/ARCHITECTURE.md` §4).

## 11. Cạm bẫy
- Emit theo-giờ PHẢI ở đầu loop (trước read) — đặt sau read/sau xử-frame thì mất-camera không phát.
- `dt > 1e-9` guard chia 0 (2 lần emit quá sát). `frames_read > 0` guard skip_rate chia 0.

## 12. Tự kiểm (Feynman)
- Vì sao emit theo-giờ đặt ĐẦU loop? Camera mất kết nối thì sao nếu đặt sau read?
- "Cô lập lỗi observer" nghĩa là gì? Observer lỗi có làm sập pipeline không, vì sao?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/pipeline_runner.py::_emit` (đọc thật phiên này/#324) · #275 (Lỗ-A emit theo-giờ). Độ chắc: cao (quote trực tiếp).
