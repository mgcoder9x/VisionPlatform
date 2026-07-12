# 12.13 — `MotionGateStage` — skip khung tĩnh, frame-đầu cho-đi-tiếp, `max_consecutive_skip` ép chạy

## 1. Thuộc về đâu
runtime/stages — `motion_gate_stage.py`. Đặt ĐẦU chuỗi (trước DetectStage). STATEFUL (nhớ frame trước).

## 2. Cần biết trước
mẩu 11 (`changed_ratio`), 12 (ROI/illumination). `SkipFrameSignal` (bài #04: raise → StageResult.SKIPPED → executor dừng chuỗi → detector KHÔNG chạy).

## 3. Code thật (quote nguyên văn — `motion_gate_stage.py`, phần `_do_process`)
```python
        curr = packet.media_ref.array
        # Frame đầu / đổi shape → thiếu mốc so sánh → CHO ĐI TIẾP (không bỏ nhầm) + lưu mốc.
        if self._prev is None or self._prev.shape != curr.shape:
            self._prev = curr
            self._consecutive_skips = 0
            if self._roi is not None:
                self._mask = roi_mask(curr.shape[0], curr.shape[1], *self._roi)
            return packet.with_artifact("motion_ratio", 1.0)

        ratio = changed_ratio(self._prev, curr, self._pixel_diff_threshold,
                              mask=self._mask, illumination_robust=self._illumination_robust)
        self._prev = curr
        if ratio < self._min_area_ratio:
            if self._max_consecutive_skip > 0 and self._consecutive_skips >= self._max_consecutive_skip:
                self._consecutive_skips = 0
                return packet.with_artifact("motion_ratio", ratio).with_artifact("motion_forced", True)
            self._consecutive_skips += 1
            raise SkipFrameSignal(f"no motion (ratio={ratio:.4f} < {self._min_area_ratio}), ...")
        self._consecutive_skips = 0
        return packet.with_artifact("motion_ratio", ratio)
```

## 4. Giải thích từng mẩu nhỏ nhất
- **Frame đầu / đổi shape**: `self._prev is None` → thiếu mốc so → CHO ĐI TIẾP (return, không skip) + lưu `_prev`
  + dựng `_mask` LAZY (giờ mới biết shape). Triết lý QĐ-3: thiếu mốc thì thà chạy thừa hơn bỏ sót.
- `ratio = changed_ratio(...)` — đo đổi (mẩu 11/12), rồi cập nhật `_prev = curr`.
- `if ratio < min_area_ratio` (TĨNH):
  - đã skip liên tiếp tới hạn (`_consecutive_skips >= max_consecutive_skip`, >0) → ÉP đi tiếp (reset đếm + gắn
    `motion_forced=True`) → detector vẫn chạy định kỳ dù tĩnh lâu (chống bỏ sót vật đứng-yên/xuất-hiện-chậm).
  - chưa tới hạn → `_consecutive_skips += 1` + `raise SkipFrameSignal` → SKIPPED → detector KHÔNG chạy (tiết kiệm).
- có chuyển động → reset đếm, đi tiếp.

## 5. Là gì
Cổng CPU chặn frame tĩnh trước detector, có van an toàn "ép chạy định kỳ".

## 6. Tại sao tồn tại / vấn đề nó giải
Detector (GPU) là khâu ĐẮT nhất; cảnh tĩnh phần lớn thời gian → chạy detector mỗi khung = phí. Motion-gate bỏ
khung tĩnh (rẻ, chỉ trừ 2 array) → giảm mạnh số lần chạy detector. `max_consecutive_skip` chống rủi ro "tĩnh lâu
bỏ sót" (vật đứng yên/xuất hiện chậm) bằng cách ép chạy 1 khung sau N skip.

## 7. Dùng ở đâu
Đầu chuỗi pipeline (mẩu 14 wiring). `skip_rate` (tỉ lệ skip) phơi qua observability (#13). `motion_ratio`/`motion_forced` ghi vào artifacts.

## 8. Không có nó thì sao
Chạy detector mỗi khung → phí GPU (cảnh tĩnh). Hoặc skip mù không van an toàn → tĩnh lâu bỏ sót vật đứng yên.
Frame-đầu skip → bỏ nhầm khung đầu (chưa có mốc). Từng điểm đều được xử.

## 9. Ví von
Bảo vệ chỉ gọi chuyên gia (detector) khi thấy có ĐỘNG TĨNH; nhưng cứ N phút gọi 1 lần "kiểm tra định kỳ" dù yên (max_consecutive_skip) — phòng vật đứng im.

## 10. Liên kết bức tranh lớn
Cắt-tải đầu chuỗi analytics. Dùng domain thuần (mẩu 11/12) + `SkipFrameSignal` (bài #04). Stateful (nhớ `_prev`) như tracking (mẩu 01).

## 11. Cạm bẫy
- Frame đầu PHẢI cho đi tiếp (thiếu mốc) — nếu skip thì mất khung đầu.
- `max_consecutive_skip=0` = KHÔNG giới hạn (skip tự do) — deploy cảnh có-thể-vật-đứng-yên nên đặt >0.
- Đổi shape (đổi độ phân giải giữa luồng) → coi như frame đầu (dựng lại mask). 

## 12. Tự kiểm (Feynman)
- Vì sao frame ĐẦU cho đi tiếp thay vì skip?
- `max_consecutive_skip` giải nỗi lo gì? Đặt =0 nghĩa là gì?
- Motion-gate tiết kiệm cái gì (khâu nào đắt)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/stages/motion_gate_stage.py` (đọc thật phiên này) · spec motion-gate + motion-gate-roi. Độ chắc: cao (quote trực tiếp).
