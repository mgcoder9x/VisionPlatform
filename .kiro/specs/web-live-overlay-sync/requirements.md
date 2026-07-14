# Requirements Document

> **Web Live Overlay Freshness and Stability** — dẫn xuất từ `design.md` V3 (design-first).

## Introduction
Web UI hiện tách hai luồng: video MJPEG (`/stream`) và detection overlay (`/boxes`) chạy độc lập. User quan sát bbox nhấp nháy liên tục. Điều tra tĩnh (đối chiếu `vision_web_app.py` — verify 6/6 điểm, LOG #378/#381) xác định **nguyên nhân gốc là semantic freshness / frame identity**, KHÔNG phải data race: detection publish `_boxes` mất `_raw_ver` của frame vào; `/boxes` thiếu generation/timestamp/health; client poll async overlap không loại được kết quả cũ; `HOLD_MS=500` là mitigation mù (blink khi empty-run, giữ ghost vô hạn khi producer đứng).

Spec này định nghĩa yêu cầu cho overlay có **freshness đo được + hết hạn chắc chắn**, tách **raw inference truth** (bất biến, cho analytics) khỏi **display projection** (matching/EMA/lease, chỉ để vẽ). Đây là **freshness/stability**, KHÔNG phải pixel-perfect synchronization — `<img>` MJPEG không cho JavaScript biết multipart frame nào đang hiển thị (giới hạn vật lý, ghi rõ, không over-claim).

Nguồn thiết kế: `.kiro/specs/web-live-overlay-sync/design.md` (V3, 3 vòng adversarial → tự reconcile). Mỗi Acceptance Criteria dưới đây được một Correctness Property trong design đối chiếu qua trường `**Validates: Requirements X.Y**`.

## Glossary
- **Raw inference truth:** kết quả detector bất biến (`RawDetectionSnapshot`): input identity + timestamps + outcome `DETECTED|EMPTY` + boxes. KHÔNG smoothing/hysteresis. Dùng cho analytics nếu cần.
- **Display projection:** trạng thái chỉ để vẽ (`DisplayStabilizer`): matching/EMA/hit-miss/lease per-track. TUYỆT ĐỐI không đi vào tracker/count/event sink.
- **processEpoch / sourceEpoch / eventRevision / inferenceGeneration:** định danh đơn điệu do `OverlayStateStore` cấp (xem design §Authority).
- **Lease (per-track):** hạn hiển thị hữu hạn của một box; hết hạn ⇒ box bị xóa nếu không có `trackRevision` mới khớp.
- **OverlayStateStore:** authority DUY NHẤT cho check-and-commit; giữ một immutable `OverlayViewSnapshot`.
- **/overlay:** endpoint additive mới (JSON, `no-store`) mang raw + display + health + epoch/revision. **/boxes:** endpoint legacy giữ nguyên hành vi cũ.

## Requirements

### Requirement 1: Toàn vẹn freshness và frame identity
**User Story:** Là người vận hành xem overlay live, tôi muốn mỗi lần đọc overlay phản ánh đúng một trạng thái nhất quán và không bao giờ lùi về quá khứ, để box hiển thị luôn khớp một frame xác định thay vì trộn lẫn kết quả cũ/mới.

#### Acceptance Criteria
1. WHEN client gọi `GET /overlay` thành công, THE system SHALL trả về một response là pure projection của ĐÚNG MỘT immutable committed `OverlayViewSnapshot` cộng một serialization timestamp, KHÔNG trộn epoch/raw/display/health, và projection SHALL KHÔNG mutate committed state.
2. WHILE trong cùng một `processEpoch`, WHEN nhận `sourceEpoch` nhỏ hơn hiện hành, THE system SHALL từ chối (reject) nó; WHEN gặp `processEpoch` đã retired, THE system SHALL từ chối; WHEN gặp `processEpoch` chưa từng thấy, THE client SHALL reset trước khi vẽ.
3. WHILE trong cùng epochs, WHEN một inference completion có `sourceFrameVersion` KHÔNG lớn hơn giá trị đã chấp nhận gần nhất, THE system SHALL coi là no-op và tăng bounded reason counter; chỉ version tăng-nghiêm-ngặt SHALL ảnh hưởng inference generation/stabilizer.

### Requirement 2: Ổn định hiển thị và ghost hết hạn có giới hạn
**User Story:** Là người vận hành, tôi muốn box được làm mượt và tự biến mất theo hạn xác định khi không còn dữ liệu mới, để không có box "ma" đọng lại vô hạn và không nhấp nháy khi detector chạy thưa.

#### Acceptance Criteria
1. WHEN client poll lặp lại cùng event/display/track revision, THE system SHALL KHÔNG đổi server state và KHÔNG đổi per-track client deadline (idempotent).
2. WHILE JavaScript event loop đang chạy, WHEN một box không nhận `trackRevision` mới khớp trước hạn của chính nó, THE client SHALL xóa box đó theo đúng deadline riêng của nó; việc một track KHÁC được khớp SHALL KHÔNG gia hạn box này.
3. WHERE `maxMisses >= 1`, WHEN một confirmed track miss lần thứ nhất, THE system SHALL giữ box; WHEN miss đạt `maxMisses + 1`, THE system SHALL xóa track (trừ khi lease hết hạn trước); WHEN track được khớp lại, THE system SHALL reset miss count về 0.
4. WHEN xử lý một accepted result, THE system SHALL thực hiện matching một-một theo cùng label (deterministic, sort ổn định) sao cho cùng input có thứ tự cho ra output y hệt; nhãn KHÁC nhau SHALL KHÔNG bao giờ khớp nhau.
5. WHEN cập nhật toạ độ hiển thị bằng EMA, THE system SHALL đảm bảo mỗi toạ độ smoothed nằm giữa giá trị trước và giá trị mới; input hằng số SHALL KHÔNG gây trôi (drift).
6. WHEN `OverlayExpiryScheduler` phát nhiều `TimerTick` qua cùng một deadline, THE system SHALL có hiệu ứng state exactly-once (tick lặp là no-op); KHÔNG thao tác đọc HTTP nào SHALL mutate state.

### Requirement 3: Trung thực về lỗi và gián đoạn nguồn
**User Story:** Là người vận hành, tôi muốn phân biệt rõ "chưa có dữ liệu", "không phát hiện gì", "detector lỗi" và "nguồn mất kết nối", để chẩn đoán đúng thay vì thấy màn hình trống mơ hồ hoặc box giả.

#### Acceptance Criteria
1. WHEN ở trạng thái initialization, raw `EMPTY`, source degradation, hoặc detector degradation/hang, THE system SHALL phơi các trạng thái này phân biệt được với nhau; lỗi SHALL KHÔNG bịa ra `EMPTY` và SHALL KHÔNG refresh display.
2. WHEN nguồn chuyển từ `LIVE` sang discontinuity lần đầu, THE system SHALL tăng `sourceEpoch` và clear display ĐÚNG MỘT LẦN trước khi retry; mỗi lần retry SHALL tuân clamp `[reconnectMinMs, reconnectMaxMs]`; reopen thành công SHALL KHÔNG tăng epoch thêm lần nữa.

### Requirement 4: Cô lập analytics và bất biến low-latency
**User Story:** Là kỹ sư hệ thống, tôi muốn lớp làm-mượt-hiển-thị KHÔNG làm bẩn dữ liệu analytics và KHÔNG làm chậm video, để tracking/counting vẫn dùng raw truth và video luôn mượt dù detector chậm.

#### Acceptance Criteria
1. WHEN stabilizer hoạt động, THE system SHALL giữ raw snapshot bất biến; display DTO SHALL KHÔNG thoả/không import được analytics input port; bật/tắt stabilizer SHALL để chuỗi raw byte-equivalent.
2. WHILE detector bị chặn (blocked/hang), THE system SHALL vẫn tiếp tục publish video/JPEG (accepted-frame count vẫn tăng) — detector chậm SHALL KHÔNG chặn tiến trình video.

### Requirement 5: Tương thích ngược endpoint legacy
**User Story:** Là người bảo trì, tôi muốn endpoint `/boxes` cũ giữ nguyên hành vi, để mọi consumer hiện có không vỡ khi thêm `/overlay`.

#### Acceptance Criteria
1. WHEN chạy chuỗi success → empty → exception → reconnect, THE system SHALL giữ body/status/content-type/header của `GET /boxes` khớp hành vi trước-spec (legacy best-effort); overlay epochs/gates SHALL KHÔNG điều khiển legacy state.
