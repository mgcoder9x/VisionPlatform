# Module 03 — Build-along: build vision_demo_workspace từ con số 0

## Mục đích

Module 01-02 dạy lý thuyết và pattern. Module 03 = bạn **CODE** một dự án thật. Đến cuối module bạn sẽ có `vision_demo_workspace/` chạy được trên máy bạn.

## 1 thư mục bạn sẽ tạo

| Thư mục | Vai trò | Bạn động vào? |
|---------|---------|--------------|
| `vision_demo_workspace/` | **Workspace của bạn** — bạn tạo từ Step 01, gõ code vào đây từng step. | ✅ Gõ thật, chạy thật. |

→ Mỗi step có hint "Đã verify chạy được" — code mẫu in trong step đã được kiểm tra trước khi viết. Bạn gõ đúng = chạy.

> **Lưu ý:** một số tài liệu cũ nhắc tới `_vision_demo_workspace/` như "reference build có sẵn để peek khi stuck". Snapshot hiện tại **không** đóng gói sẵn folder đó — nguồn đối chiếu duy nhất là code mẫu in đầy đủ trong từng step. Nếu code không chạy, so từng dòng với step tương ứng.

## Lưu ý cực quan trọng

> **Mọi code mẫu trong module này được viết để chạy được khi bạn gõ đúng.** Nếu gõ đúng mà không chạy → so sánh từng dòng với code mẫu in trong step tương ứng.

Step 04 đã chạy thành công với output:

```
[seq=001] brightness=127.33 shape=(240, 320, 3)
[seq=002] brightness=127.47 shape=(240, 320, 3)
...
=== Demo summary ===
  Processed: 5
  Skipped (filter):  0
  EOF: 1
```

## Yêu cầu trước

- ✅ Pass Module 01 + 02 self-check.
- ✅ Có Python 3.11+.
- ✅ Có terminal (PowerShell hoặc CMD trên Windows; bash/zsh trên Linux/Mac).

## Ngày bạn sẽ build gì

| Step | Topic | Files mới | Tests | Time |
|------|-------|-----------|-------|------|
| 01 | Project skeleton + venv + pyproject | 11 | 2 | 1h |
| 02 | Domain BBox + Kernel ReadResult + MediaPacket | 4 | 19 (16+3 E-11/E-12) | 2h |
| 03 | Port IFrameSource + 2 adapter + contract test | 4 | 31 (30+1 E-13) | 2h |
| 04 | StageContract + BaseStage + SyncLinearExecutor + 2 stage + composition root | 7 | 13 (12+1 E-14) | 2.5h |
| 05 | SHM frame bus + multi-process | 3 | 13 | 3h |
| 06 | ZMQ inference service | 4 | 9 | 3h |
| 07 | Backpressure | 1 | 11 | 2h |
| 08 | Observability | 1 | 12 | 2h |
| 09 | Shutdown protocol | 2 | 6 | 2h |
| 10 | Package + ship | 0 (chỉ docs + build) | 0 (re-run all) | 1h |

**Tổng cộng**: **116 test (115 pass + 1 skip** có chủ đích — see step 03)** sau khi step-02 thêm
3 test (E-11/E-12) + step-03 thêm 1 (E-13) + step-04 thêm 1 (E-14). *Baseline gốc của giáo trình là
111 (110+1); các số 111/110 còn ở `step-10` + `00-START-HERE.md` là baseline — xem ERRATA E-11..E-14.*
Chạy `pytest` trong workspace của bạn và **đọc số thật** (đừng tin số có sẵn — E-4).

## Cấu trúc cuối khi xong Module 03

```
vision_demo_workspace/
├── pyproject.toml
├── .venv/                              ← virtual env riêng
├── src/
│   └── vision_demo/
│       ├── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   └── bbox.py                ← BBox, CoordinateSpace
│       ├── kernel/
│       │   ├── __init__.py
│       │   ├── ports/
│       │   │   ├── __init__.py
│       │   │   └── frame_source.py    ← IFrameSource
│       │   ├── read_result.py         ← ReadResult, ReadStatus
│       │   ├── media_packet.py        ← MediaPacket, InMemoryArrayRef
│       │   ├── shm_frame_ref.py       ← ShmFrameRefData (DTO, Step 05)
│       │   ├── inference_protocol.py  ← Detection(BBox), Inference* (Step 06)
│       │   ├── backpressure.py        ← BoundedQueue, 4 policy (Step 07)
│       │   └── stage_contract.py      ← StageResult, StageStatus, ExecutionResult
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── base_stage.py          ← BaseStage
│       │   ├── sync_linear_executor.py
│       │   ├── observability.py       ← structlog + InMemoryMetrics (Step 08)
│       │   ├── ipc/
│       │   │   ├── __init__.py
│       │   │   └── shm_frame_ring.py  ← ShmRingBuffer/Writer/Reader (Step 05)
│       │   └── stages/
│       │       ├── __init__.py
│       │       ├── brightness_stage.py
│       │       └── dark_filter_stage.py
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── fake_frame_source.py
│       │   ├── noise_frame_source.py
│       │   ├── fake_detector.py       ← FakeDetector (Step 06)
│       │   └── inline_inference_client.py  ← InlineInferenceClient (Step 06)
│       ├── application/
│       │   ├── __init__.py
│       │   └── supervisor.py          ← Supervisor, WorkerSpec (Step 09)
│       └── profiles/
│           ├── __init__.py
│           └── demo_pipeline.py       ← composition root
└── tests/
    ├── test_smoke.py
    ├── test_step_02_domain.py
    ├── test_step_03_frame_source_contract.py
    ├── test_step_04_pipeline.py
    ├── test_step_05_shm.py
    ├── test_step_06_inference.py
    ├── test_step_07_backpressure.py
    ├── test_step_08_observability.py
    ├── test_step_09_shutdown.py
    └── worker_funcs_for_step_09.py    ← worker funcs (spawn-safe, Step 09)
```

**Tổng**: ~600 dòng code production + ~400 dòng test = **mini Vision Platform chạy được**.

> **Lưu ý:** cây trên là trạng thái **cuối Module 03** (sau Step 10). Mỗi step chỉ thêm phần của nó — ví dụ sau Step 04 bạn mới có tới `demo_pipeline.py` + 4 test file đầu; `ipc/`, `inference_protocol.py`, `backpressure.py`, `observability.py`, `supervisor.py` xuất hiện ở Step 05-09.

## Quy tắc khi build

1. **Gõ thật, không copy-paste**. Cảm giác hiểu code khi gõ ≠ khi copy.
2. **Mỗi step xong → run pytest**. Pass = qua step kế.
3. **Sai → đọc lại lý thuyết Module 01-02 liên quan**, không skip.
4. **Mỗi step cuối có `git commit`** (nếu dùng git). Tag step để revert được.

## Trade-offs vs Vision_platform_architecture_design

`vision_demo` là **MINI Vision Platform**. Đơn giản hoá:

| Concept | vision_demo | Vision_platform_architecture_design |
|---------|-------------|-------------------------------------|
| Layer count | 4 (no adapter folder vs no domain — gộp linh hoạt) | 4 strict |
| ArtifactStore | Plain `MappingProxyType` | Typed `ArtifactKey[T]` |
| Wire DTO | Skip (single-process) | Có (Pydantic + msgpack) |
| Backpressure | 4 policy (DROP_OLDEST, DROP_NEWEST, BLOCK, REJECT) — xem Step 07 | 6 policy (thêm SAMPLE, DEGRADE_QUALITY) |
| Shutdown | Basic cascade (SIGTERM→grace→SIGKILL), chưa có cooperative event | Full cascade protocol |
| Observability | structlog + `InMemoryMetrics` (logs + metrics) — xem Step 08; demo CLI in summary ra stderr | structlog + metrics + tracing (OpenTelemetry) |

→ **Đủ pattern**, không đủ feature. Production cần đầy đủ Vision Platform.

## Bắt đầu

➡️ [`step-01-project-skeleton.md`](step-01-project-skeleton.md)
