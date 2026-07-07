# Folder Structure Blueprint

Copy paste skeleton cho dự án mới.

```
your_project/
├── pyproject.toml
├── README.md
├── .gitignore
├── src/
│   └── your_package/
│       ├── __init__.py
│       ├── domain/                   # Pure logic, no I/O
│       │   └── value_objects.py
│       ├── kernel/                   # DTOs + ports
│       │   ├── ports/
│       │   │   ├── data_source.py    # IDataSource
│       │   │   ├── detector.py       # IDetector
│       │   │   └── event_sink.py     # IEventSink
│       │   ├── media_packet.py
│       │   ├── read_result.py
│       │   └── stage_contract.py
│       ├── runtime/                  # Executors, batchers
│       │   ├── base_stage.py
│       │   ├── sync_linear_executor.py
│       │   ├── batcher.py
│       │   └── stages/
│       │       └── ...
│       ├── application/              # Use cases, orchestrators
│       │   ├── use_cases/
│       │   └── orchestrators/
│       │       └── supervisor.py
│       ├── adapters/                 # Concrete implementations
│       │   ├── sources/
│       │   ├── detectors/
│       │   ├── sinks/
│       │   └── ui/
│       └── profiles/                 # Composition roots
│           ├── realtime_multicam.py
│           ├── batch.py
│           └── desktop.py
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── configs/                          # Config files
│   ├── dev.yaml
│   └── prod.yaml
└── examples/                         # Demo scripts
```

## Setup script

```bash
mkdir -p src/your_package/{domain,kernel/ports,runtime/stages,application/{use_cases,orchestrators},adapters/{sources,detectors,sinks},profiles}
mkdir -p tests/{unit,contract,integration,e2e}
mkdir -p configs examples

find src/your_package -type d -exec touch {}/__init__.py \;
find tests -type d -exec touch {}/__init__.py \;
```

## Quick rules

- **Domain**: pure Python + numpy. NO cv2/torch/ZMQ.
- **Kernel**: ports + DTOs. NO concrete adapters.
- **Runtime**: depends on kernel only.
- **Application**: depends on kernel + runtime.
- **Adapters**: depends on kernel.
- **Profiles**: depends on everything (composition root).
