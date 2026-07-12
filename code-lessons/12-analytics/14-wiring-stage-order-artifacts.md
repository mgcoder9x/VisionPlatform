# 12.14 — Wiring: thứ-tự-stage motion_gate→detect→count→track→line + artifacts FAN-OUT

## 1. Thuộc về đâu
Tổng hợp chuỗi analytics: `SyncLinearExecutor` (bài #04) chạy stages theo thứ tự; các stage trao dữ liệu qua `packet.artifacts`.

## 2. Cần biết trước
tất cả mẩu #12 trước + bài #04 (executor dừng chuỗi ở non-SUCCESS; `SkipFrameSignal`→SKIPPED).

## 3. Code thật (quote — thứ tự dựng trong `vision_slice_app._args_to_pipeline_config`, #11.14)
```python
    if args.motion_gate: stages.append(StageConfig("motion_gate", mg))
    stages.append(StageConfig("detect", {}))
    stages.append(StageConfig("count", {}))
    if args.track: stages.append(StageConfig("track", {...}))
    if args.line: stages.append(StageConfig("line_crossing", {...}))
```
Executor (bài #04, `sync_linear_executor.py`): "Stop on first non-SUCCESS" (SKIPPED/ERROR → dừng chuỗi).

## 4. Giải thích luồng (từng mắt xích)
- **motion_gate** (nếu bật, ĐẦU): tĩnh → `SkipFrameSignal` → SKIPPED → executor DỪNG → detect KHÔNG chạy (tiết kiệm). Có chuyển động → đi tiếp.
- **detect**: chạy IDetector → ghi `artifacts["detections"]`.
- **count**: đọc `detections` → đếm/khung (stateless).
- **track** (nếu bật): đọc `detections` (FAN-OUT: cùng nguồn với count) → tracker → ghi `artifacts["tracks"]`+`unique_count`.
- **line_crossing** (nếu bật): đọc `artifacts["tracks"]` → cắt vạch → ghi `crossings_*`+`crossing_events`.
- **artifacts FAN-OUT**: DetectStage ghi `detections` MỘT LẦN; count + track cùng đọc → không tính lại (R3.1).
- **phụ thuộc thứ tự**: track cần detect trước (guard raise nếu thiếu `detections`); line cần track trước (cần `tracks`). Thứ tự dựng bảo đảm điều đó.

## 5. Là gì
Cách các stage nhỏ ghép thành pipeline analytics qua artifacts + thứ tự, executor điều phối dừng-sớm.

## 6. Tại sao tồn tại / vấn đề nó giải
Chia analytics thành stage nhỏ đơn-trách-nhiệm (SRP) + nối bằng artifacts (không stage nào biết stage khác trực
tiếp) → dễ thêm/bớt/đổi thứ tự qua config. motion_gate đầu chuỗi + executor dừng-sớm = cắt tải TRƯỚC khâu đắt (detect).

## 7. Dùng ở đâu
Cả đường CLI (`_args_to_pipeline_config`, #11.14) lẫn config TOML (`build_runner`, #11.13) dựng cùng thứ tự này
(stages theo list). `SyncLinearExecutor.execute` chạy.

## 8. Không có nó thì sao
Sai thứ tự (track trước detect) → guard raise (ERROR). Không fan-out (detect chạy 2 lần cho count+track) → phí.
motion_gate KHÔNG ở đầu → detector chạy cả khung tĩnh → mất lợi cắt-tải.

## 9. Ví von
Dây chuyền: lọc phôi (motion_gate) → gia công (detect) → đếm (count) → dán mã (track) → kiểm cổng (line). Mỗi
trạm để lại "phiếu" (artifact) cho trạm sau; lọc-phôi loại sớm để trạm gia công đắt tiền không chạy phôi rỗng.

## 10. Liên kết bức tranh lớn — CỔNG ĐÓNG #12
Đây là bức tranh tổng: domain thuần (02/03/07/08/11/12) → runtime stateful (04/06/09/13) → kernel DTO (05/10) →
ghép qua artifacts + executor (bài #04). Toàn hệ analytics = stage nhỏ + artifacts + thứ tự, cắt tải đầu chuỗi.

## 11. Cạm bẫy
- Thứ tự bắt buộc: motion_gate(đầu) · detect trước track · track trước line. Sai → guard raise.
- SKIPPED dừng CẢ chuỗi → khi motion_gate skip, count/track/line KHÔNG chạy khung đó (đúng ý: khung tĩnh bỏ hẳn).

## 12. Tự kiểm (Feynman — cổng đóng #12)
- Kể lại luồng 1 khung qua chuỗi motion_gate→detect→count→track→line, chỉ rõ artifact nào ghi/đọc ở đâu.
- "Fan-out" nghĩa là gì (ai ghi `detections`, ai đọc)? Vì sao không tính lại?
- Vì sao motion_gate đặt ĐẦU + executor dừng-sớm = cắt tải hiệu quả?
- **Tổng hợp #12:** vẽ 3 tầng (domain/runtime/kernel) của analytics + chỉ rõ mỗi mảnh ở tầng nào, VÌ SAO tách vậy.

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`vision_slice_app.py`/`pipeline_factory.py` (thứ tự stages) · `sync_linear_executor.py` (bài #04) · các stage #12. Độ chắc: cao (quote + logic đã đọc).
