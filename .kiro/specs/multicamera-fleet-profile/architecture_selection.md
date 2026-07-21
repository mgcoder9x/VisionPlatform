# Architecture Selection: multicamera-fleet-profile

> Giải quyết Finding **F7.2** (`architecture-review/design.md`): hợp nhất 2 topology rời (single-view web ⊥ multi-process full-stack) thành 1 profile N-camera có web UI live + bulkhead + supervision.
> **Giả định tường minh (chưa chốt business):** A1 GPU target = x86-64 + NVIDIA rời (nếu Jetson/ARM → kích hoạt K-001, chỉ ảnh hưởng validation phần cứng của component Capture+SHM, KHÔNG đổi phân rã); A2 fleet nhỏ–vừa, N tham số hoá; A3 transport MJPEG (WebRTC = follow-on F4.1).

## Recommended Architecture: Candidate 1 — Lane-oriented (bulkhead dọc per-camera)

### Rationale
Bất biến TRỘI của feature là **INV1 (isolation per-camera bulkhead)**. Lane-oriented biến ranh giới bulkhead thành **ranh giới component hạng nhất** (mỗi camera = 1 process group cô lập) → isolation được cưỡng chế bằng CẤU TRÚC, không bằng kỷ luật nội-bộ. Metric hậu thuẫn: god-object thấp nhất (~25% vs >50% ở Tier-oriented vì state phân hoạch per-lane), cross-cutting invariants thấp nhất (38%), 0 sync cycle, và tái dùng tối đa component đã kiểm chứng (đúng phạm vi "wiring/composition", ít code mới nhất).
**Trade-off:** `InferenceService` có fan-in cao (mọi lane gọi) — điểm ghép chia sẻ / nút cổ chai tiềm tàng. Đây CHÍNH là nơi tích hợp batch-mux GPU (F3.3) về sau, nên chấp nhận có chủ đích.

### Components
| Component | Owned State | Responsibility |
|---|---|---|
| `FleetOrchestrator` (profiles) | Fleet_Config đã parse, lane registry | Parse config, spawn N Camera_Lane, wire, xử lý shutdown có trật tự |
| `CameraLane` (×N) | SHM ring, capture process, infer-client, `ITracker`, `OverlayStateStore` (của camera đó) | Pipeline end-to-end cô lập cho 1 camera (đơn vị bulkhead) |
| `InferenceService` (shared, multi-process) | model / GPU session | Serve inference cross-process (ZMQ) cho mọi lane; điểm tích hợp batch-mux tương lai |
| `WebGateway` | HTTP server, endpoint per-camera, trang index | Phục vụ MJPEG + overlay JSON per-camera READ-ONLY (INV5) |
| `FleetSupervisor` | process registry, heartbeat, backoff | Giám sát + restart process con (per-lane + inference) |

### Information Flow
| From \ To | FleetOrchestrator | CameraLane | InferenceService | WebGateway | FleetSupervisor |
|---|---|---|---|---|---|
| **FleetOrchestrator** | — | → spawn/wire | → khởi tạo | → khởi tạo | → đăng ký |
| **CameraLane** | — | — | → InferenceRequest | — | ← heartbeat |
| **InferenceService** | — | → InferenceResponse (echo id) | — | — | ← heartbeat |
| **WebGateway** | — | ← đọc OverlayStore/health | — | — | — |
| **FleetSupervisor** | — | → restart (per-lane) | → restart | — | — |

(→ gọi/điều khiển · ← đọc/callback). Không có chu trình đồng bộ: `CameraLane→InferenceService` là request/echo-response (ZMQ async), không tạo phụ thuộc vòng.

### Requirement Allocation
| Requirement | Component(s) |
|---|---|
| R1 (config đa-camera TOML) | FleetOrchestrator |
| R2 (bulkhead isolation) | CameraLane (ranh giới) + FleetOrchestrator (cấp SHM riêng) + FleetSupervisor (restart cô lập) |
| R3 (inference multi-process) | CameraLane (infer-client, tracker) + InferenceService |
| R4 (web live overlay per-camera) | WebGateway |
| R5 (supervision/recovery) | FleetSupervisor + FleetOrchestrator (shutdown) |
| R6 (observability per-camera) | CameraLane (emit, label Camera_Id) + WebGateway (/metrics aggregate) |
| R7 (layering hexagonal) | FleetOrchestrator (composition root duy nhất) + import-linter (toàn cục) |

### Key Design-Induced Invariants
Các bất biến SINH RA từ quyết định phân rã này (không trực tiếp từ requirement):
- **DI-INV-A:** Ranh giới `CameraLane` = ranh giới process group → INV1 (isolation) và INV8 (no cross-lane lock dep) trở thành hệ quả cấu trúc, không cần enforce thủ công. (Ràng buộc: KHÔNG được đặt tài nguyên dùng chung tháo-gỡ-lẫn-nhau giữa 2 lane; SHM ring cấp per-lane.)
- **DI-INV-B:** `WebGateway` chỉ đọc `OverlayStateStore` (không giữ tham chiếu process/ring của lane) → INV5 (read-only) + INV3 (freshness) cô lập trong cặp Lane.OverlayStore↔Gateway; gateway sập không kéo lane.
- **DI-INV-C:** `InferenceService` là điểm chia sẻ DUY NHẤT giữa các lane → mọi coupling cross-camera (kể cả batch-mux tương lai) PHẢI đi qua đây; identity (INV2) enforce bằng `request_id` echo per-lane. Nếu inference cần bulkhead cứng hơn → tách pool per-nhóm-lane (không đổi các component khác).
- **DI-INV-D:** `Camera_Id` là khoá tương quan bất biến xuyên FleetOrchestrator→Lane→metrics/log/endpoint; mọi label/route dùng đúng khoá này (INV4 unique ở config).

### Alternatives Considered
| Candidate | Strength | Weakness | Why Not Selected |
|---|---|---|---|
| C2 Tier-oriented (tầng ngang chia sẻ) | Đường dữ liệu tuyến tính rõ; batching cross-camera tự nhiên ở InferenceTier | **God-object CaptureTier >50%** (giữ mọi ring+capture); INV1 phải giữ BÊN TRONG tier chia sẻ → không cưỡng-chế-bằng-ranh-giới → phá mục tiêu bulkhead | Vi phạm bất biến TRỘI (isolation) + red-flag god-object |
| C3 Event-driven + ResultRepository (persistence) | Tách producer↔consumer; ResultRepository = điểm đọc duy nhất, dễ thêm consumer (analytics/alert/replay); 0 chu trình | Bus = **SPOF fleet-wide** (đối nghịch INV1); fan-in Bus cao; thêm hạ tầng event trong khi SHM đã là transport frame (R3.1) = indirection thừa cho v1 | Chưa có nhu cầu persistence/nhiều-consumer; SPOF mâu thuẫn bulkhead. **Xét lại nếu** cần lưu lịch sử/replay hoặc ≥3 loại consumer |

### Metrics Summary
| Metric | Selected (C1 Lane) | Alt A (C2 Tier) | Alt B (C3 Event+Repo) |
|---|---|---|---|
| Cross-cutting reqs % | 57% (bản chất isolation+supervision) | 71% | 43% |
| Cross-cutting invariants % | **38%** | 50% | 50% |
| Flow density | **0.30** | 0.30 | ~0.38 |
| God object score | **~25%** | >50% 🚩 | ~40% |
| Sync cycles | 0 | 0 | 0 |
| Max fan-in | 3 (Lane); Inference N-instance (điểm ghép có chủ đích) | ResultStore | Bus N 🚩 |
| Max fan-out | 4 (Orchestrator) | 3 | Bus |
| Evolvability cost | ~1.3 | ~2.0 | ~1.2 |
