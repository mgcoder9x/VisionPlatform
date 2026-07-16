# Requirements Document

> **Overlay/Tracking Architecture Refactor** — dẫn xuất từ `design.md` (D-126, design-first). CHƯA code — chờ user valid.

## Introduction
User nhìn thấy 2 lỗi VISUAL trên video thật (#411): **S1 — bbox KHÔNG SÁT người** (trễ/lệch/giật khi di chuyển) và **S2 — bbox TẮT CHẬM** khi người đã đi qua (ghost). Đã vá 4 lần ở `DisplayStabilizer` (hysteresis/evict/predict-match/conf, #405-408) mà chưa dứt. Đọc SÂU code THẬT (#412, verify lại #413: `overlay_projection.py` KHÔNG gửi vận tốc; client `_PAGE tick()` vẽ tại vị trí báo-cuối, KHÔNG ngoại suy) → chẩn đoán GỐC: **S1 chủ yếu do client vẽ TĨNH (sample-and-hold)**; **S2 do xoá theo đồng-hồ-lease mù**. Kiến trúc: `DisplayStabilizer` GỘP tracking+display+lifecycle + tồn tại 2 tracker phân kỳ (analytics `iou_tracker` vs display).

Spec định nghĩa yêu cầu cho: (a) client render **bù chuyển động** (ngoại suy vận tốc → fix S1); (b) removal **evidence-based** theo `time_since_update` (fix S2); (c) hợp nhất **1 nguồn track** (`domain/tracker` dùng chung analytics + display) làm NỀN nghiệp vụ. Tất cả **additive** (cờ tắt = hành vi hiện tại). Verify trên máy no-GPU: unit (Python) + browser MCP với **nguồn synthetic (moving-square)** — không cần GPU/webcam/RTSP/model.

Nguồn thiết kế: `.kiro/specs/overlay-tracking-refactor/design.md`. Mỗi Acceptance Criteria được một Correctness Property (P1–P5) đối chiếu qua `**Validates: Requirements X.Y**`.

## Glossary
- **Ngoại suy vận tốc (client extrapolation):** client vẽ box tại `clamp(pos + vel*(now-updatedAt), khung)` mỗi khung `requestAnimationFrame` → bám mượt giữa 2 lần detect thưa.
- **vx, vy:** vận tốc tâm track (chuẩn-hoá/giây) do tracker ước lượng; `updatedAtMs` = mốc cập nhật track gần nhất.
- **time_since_update:** thời gian kể từ lần track được khớp detection gần nhất (căn cứ removal).
- **maxAgeMs:** ngưỡng thời gian removal (nhỏ) — track quá hạn này không update → "lost" (thay giữ tới hết lease 600ms).
- **1 nguồn track:** `domain/tracker` duy nhất cho CẢ analytics (đếm/vạch) lẫn display — đóng phân kỳ 2-tracker.
- Thuật ngữ nền (lease, EMA, IoU, greedy_associate, epoch): xem `web-live-overlay-sync` + `knowledge-base/00-GLOSSARY.md`.

## Requirements

### Requirement 1: Client render bù chuyển động (fix S1 "box không sát")
**User Story:** Là người xem overlay live, tôi muốn box bám sát người ngay cả khi họ di chuyển và detect thưa (CPU), để không thấy box trễ/lệch/giật.

#### Acceptance Criteria
1. WHEN `project_overlay` chiếu một track có vận tốc, THE system SHALL kèm `vx`, `vy` (chuẩn-hoá/giây) và `updatedAtMs` cho track đó; track chưa đủ dữ liệu vận tốc (<2 update) SHALL có `vx=vy=0`.
2. WHILE bật ngoại suy client, WHEN vẽ mỗi khung, THE client SHALL vẽ box tại `clamp(pos + vel*(now-updatedAtMs), [0,1])`; WHEN `vel=0`, THE client SHALL vẽ đứng yên (KHÔNG drift).
3. WHEN cờ ngoại suy tắt, THE client SHALL giữ hành vi hiện tại (vẽ tại vị trí báo-cuối) — additive.

### Requirement 2: Removal evidence-based (fix S2 "tắt chậm")
**User Story:** Là người xem, tôi muốn box biến mất nhanh khi người đã rời đi (kể cả không qua mép, bị che, detect ngừng), để không thấy ghost đọng.

#### Acceptance Criteria
1. WHEN một track không được update quá `maxAgeMs`, THE system SHALL chuyển nó sang "lost" và loại khỏi display trong `<= maxAgeMs`, ĐỘC LẬP với lease dài (600ms).
2. WHEN cờ removal-evidence tắt, THE system SHALL giữ hành vi lease hiện tại — additive.
3. WHEN vị trí dự đoán của track ra ngoài khung, THE system SHALL loại nhanh (giữ nguyên tắc off-frame-evict D-124).

### Requirement 3: Một nguồn track dùng chung (nền nghiệp vụ) — WAVE C, GATED
**User Story:** Là kỹ sư nghiệp vụ, tôi muốn analytics (đếm/vạch/zone) và display dùng CÙNG một tracker, để ID nhất quán và không có 2 nguồn sự thật khi xây nghiệp vụ.

#### Acceptance Criteria
1. WHEN hợp nhất tracker (Wave C), THE system SHALL để analytics và display đọc cùng `domain/tracker` (motion+association+lifecycle), cho ID nhất quán giữa hai consumer.
2. WHEN refactor Wave C, THE system SHALL giữ `web-live-overlay-sync` và `object-tracking-count` test XANH (không phá hành vi hiện có).
3. WHERE Wave C chưa được user duyệt rõ, THE system SHALL KHÔNG đụng analytics (chỉ làm Wave A/B trên display).

### Requirement 4: Additive / backward-compat
**User Story:** Là người đang vận hành, tôi muốn thay đổi không phá hành vi sẵn có, để nâng cấp an toàn.

#### Acceptance Criteria
1. WHEN chạy với mọi cờ mới TẮT (`clientExtrapolate` off, removal-evidence off), THE system SHALL cho hành vi y hệt hiện tại, VÀ baseline test SHALL giữ xanh (không giảm số pass).
2. WHEN thêm trường JSON mới (`vx/vy/updatedAtMs`), THE system SHALL giữ tương thích ngược client cũ (trường thêm, không xoá/đổi trường cũ) và KHÔNG đổi raw truth (Property 10 giữ).

### Requirement 5: An toàn motion clamp (đóng bug #410)
**User Story:** Là người vận hành, tôi muốn hệ không crash khi track di chuyển ra mép, để detect chạy liên tục.

#### Acceptance Criteria
1. WHEN tính vị trí dự đoán (client hoặc server), THE system SHALL clamp về [0,1] TRƯỚC khi dựng BBox/vẽ, để không lặp lại `ValueError NORMALIZED bbox` (#410/#411, K-111).
