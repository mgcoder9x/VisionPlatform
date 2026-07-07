# Glossary VI-EN

## Architecture

| VI | EN | 1-line meaning |
|----|----|----------------|
| Kiến trúc | Architecture | Quyết định khó đảo ngược về components, boundaries, contracts |
| Ranh giới | Boundary | Đường biên qua đó dữ liệu phải dịch chuyển với cost |
| Hợp đồng | Contract | Luật giao tiếp khi đi qua ranh giới |
| Liên kết | Coupling | Mức độ A phụ thuộc B |
| Gắn kết | Cohesion | Mức độ các phần TRONG 1 module gắn theo cùng mục đích |
| Cổng | Port | Interface (Protocol) tại boundary |
| Bộ chuyển | Adapter | Implementation của port |
| Khoang | Bulkhead | Process boundary cho crash isolation |
| Áp lực ngược | Backpressure | Cơ chế producer chậm lại khi consumer overload |

## Vision Platform

| VI | EN | 1-line meaning |
|----|----|----------------|
| Khung hình | Frame | 1 image (np.ndarray) |
| Gói phương tiện | MediaPacket | Frame + metadata + artifacts immutable DTO |
| Phát hiện | Detection | Bbox + label + confidence |
| Tracker (theo dõi) | Tracker | Stateful object track ID across frames |
| Sao chép khi ghi | Copy-on-Write (CoW) | Mutate → return new instance |
| Bộ nhớ chia sẻ | Shared Memory (SHM) | Cross-process bytes buffer |
| Slot | Slot | Đơn vị metadata + data trong SHM ring |
| Thế hệ | Generation | ABA prevention counter cho slot |
| Sự kiện | Event | Output emitted to sink |
| Mục tiêu drop | DLQ (Dead Letter Queue) | Storage for failed events |

## Concurrency

| VI | EN | 1-line meaning |
|----|----|----------------|
| Tiến trình | Process | OS process, address space riêng |
| Luồng | Thread | OS thread, share address space |
| Coroutine | Coroutine | Cooperative async unit |
| GIL | Global Interpreter Lock | Python: 1 thread bytecode tại 1 lúc |
| Đồng bộ | Sync | Block until complete |
| Bất đồng bộ | Async | Yield control via await |

## Patterns

| VI | EN | 1-line meaning |
|----|----|----------------|
| Hexagonal | Hexagonal Architecture | Logic ở giữa, I/O rìa |
| Khoang ngăn | Bulkhead | 1 component fail không kéo cả |
| Cầu chì | Circuit Breaker | Skip calls to dead service |
| Trang trí | Decorator | Wrap class, add behavior |
| Hợp căn | Composition Root | Chỗ duy nhất biết cụ thể adapter |
| Cây sự kiện | Event-driven | Components communicate via events |

## Operations

| VI | EN | 1-line meaning |
|----|----|----------------|
| Triển khai | Deploy | Push code to env |
| Ra mắt | Rollout | Gradual deploy |
| Lùi lại | Rollback | Revert deploy |
| Theo dõi | Observability | Logs + metrics + traces |
| Báo động | Alert | Notification on threshold breach |
| Sống lâu | Soak test | Long-running stability test |
| Hỗn loạn | Chaos test | Failure injection |
| Áp lực | Load test | High traffic test |

## Tools

| Tool | Purpose |
|------|---------|
| `pytest` | Test runner |
| `mypy` | Type checker |
| `ruff` | Lint + format |
| `import-linter` | Layer dependency enforcement |
| `pydeps` | Visualize import graph |
| `tracemalloc` | Memory profiling |
| `py-spy` | Sampling profiler |
| `cProfile` | Function profiler |
| `pytest-benchmark` | Perf regression |
| `objgraph` | Object reference visualization |
