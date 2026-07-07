# Decision Trees

Quick decisions cho common questions.

## 1. Có nên tạo port (interface)?

```
Có nên tạo port?
│
├── Có ≥ 2 implementation cần (real + mock test, hoặc 2 real)?
│   ├── YES → tạo port
│   └── NO ↓
│
├── Có cần test logic mà không cần infra (DB, network)?
│   ├── YES → tạo port (mock = test fake)
│   └── NO ↓
│
├── Có cần swap implementation runtime (config)?
│   ├── YES → tạo port
│   └── NO ↓
│
└── 1 implementation đời đời, no test concern → KHÔNG cần port (YAGNI)
```

## 2. Multi-process hay multi-thread?

```
Pick concurrency model
│
├── CPU-bound (numpy heavy, GIL bound)?
│   ├── YES → multi-process (bypass GIL)
│   └── NO ↓
│
├── Cần crash isolation?
│   ├── YES → multi-process (bulkhead)
│   └── NO ↓
│
├── I/O-bound (network, file)?
│   ├── YES → thread pool (~100 thread OK) or asyncio (~10000 task)
│   └── NO ↓
│
└── Default → asyncio for I/O, threads for blocking I/O w/o async lib
```

## 3. Backpressure policy chọn cái nào?

```
Pick policy
│
├── Source = file batch?
│   └── BLOCK (lossless)
│
├── Source = RTSP camera?
│   └── DROP_OLDEST default; SAMPLE for high-FPS; DEGRADE_QUALITY for slow consumer
│   └── ❌ NEVER BLOCK (CR-RT-03)
│
├── Source = HTTP upload?
│   └── REJECT (client retries) or BLOCK with timeout
│
├── Source = webcam local?
│   └── DROP_OLDEST (real-time)
│
└── Default → DROP_OLDEST
```

## 4. Storage choice?

```
Pick storage
│
├── Frame data (binary)?
│   ├── Cross-process same host → SHM
│   ├── Cross-host → ZMQ
│   ├── Persistent → S3/MinIO
│   └── Don't store frame in DB
│
├── Detection events?
│   ├── Streaming → Kafka / MQTT
│   ├── Time-series query → InfluxDB / TimescaleDB
│   ├── Audit + replay → JSONL files (rotated)
│   └── Default → Postgres (small scale)
│
└── Config?
    └── YAML file + env override (no DB)
```

## 5. Log level?

```
Pick log level
│
├── Debug step-by-step → DEBUG (off in prod)
├── Operation completed → INFO
├── Recoverable issue → WARNING
├── Operation failed → ERROR
└── Crash imminent → CRITICAL
```

## 6. Test type?

```
Test type
│
├── Pure logic, no I/O → unit
├── Multiple components together → integration
├── Adapter implementation → contract test (port)
├── Full pipeline real config → E2E
├── Failure injection → chaos
└── Long-running stability → soak (24h)
```

## 7. Sync hay async stage?

```
Pick stage type
│
├── Pure compute (CPU-bound) → sync (BaseSyncStage)
│   └── In async pipeline: `loop.run_in_executor` automatically
│
├── I/O bound (HTTP call, DB query) → async (BaseAsyncStage)
│
├── Mixed → split into 2 stages
│
└── Default → sync (simpler)
```
