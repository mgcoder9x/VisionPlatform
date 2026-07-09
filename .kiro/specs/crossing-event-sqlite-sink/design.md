# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · thêm impl `ISink` cho `CrossingEvent` (D-061) · mẫu `CrossingEventJsonlSink`.
> **Cập nhật lúc:** 2026-07-09.

## Overview

Thêm `CrossingEventSqliteSink` — ISink ghi mỗi `CrossingEvent` (`artifacts["crossing_events"]`) thành 1 hàng bảng
SQLite (`sqlite3` stdlib) → lưu trữ TRUY VẤN ĐƯỢC. Song song `CrossingEventJsonlSink` (chọn theo nhu cầu). Cắm qua
config registry + CLI. Additive: KHÔNG sửa LineCrossingStage/CrossingEvent/lõi.

**Vì sao gốc, không ngọn:** đếm/log-flat cho dữ liệu nhưng khó khai thác; vận hành cần TRUY VẤN (report theo
giờ/hướng/camera) = SQL. Dùng `sqlite3` stdlib (zero-dep, 1-file, đủ cho 1 node) đúng mức — không kéo server-DB
(over-engineer khi chưa cần; server-DB là impl `ISink` khác sau, KHÔNG đập kiến trúc).

**Nền đã đọc code thật (chống bịa):**
- `CrossingEventJsonlSink` (adapters): `setup` mkdir+open; `handle` chỉ SUCCESS → duyệt `artifacts.get("crossing_events",())`; `teardown` close. → SQLite sink theo Y lifecycle, đổi backend file→DB.
- `CrossingEvent(track_id,label,direction,source_id,cx,cy,event_ts)` (kernel, D-061).
- `sqlite3` 3.45.1 stdlib (đã kiểm). Registry `pipeline_factory` (sinks + allowed_params). `ISink` Protocol.

## Architecture

```
   ... → LineCrossingStage → sink = CompositeSink([..., CrossingEventSqliteSink(path)?])
   adapters/crossing_event_sqlite_sink.py::CrossingEventSqliteSink  (leaf, I/O sqlite file)
   pipeline_factory: sinks["crossing_events_sqlite"] = _sink_crossing_events_sqlite
   vision_slice_app: --crossing-db <path> (cần --line)
```
**Layer:** sink→adapters (leaf); dùng `sqlite3` (stdlib) + `CrossingEvent` (kernel). Không phá 5 contract.

## Components and Interfaces

### C1 — `adapters/crossing_event_sqlite_sink.py::CrossingEventSqliteSink(path)`
```
import sqlite3
_CREATE = (
    "CREATE TABLE IF NOT EXISTS crossings ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " event_ts TEXT, source_id TEXT, track_id INTEGER, label TEXT,"
    " direction TEXT, cx REAL, cy REAL)"
)
_CREATE_IDX = "CREATE INDEX IF NOT EXISTS ix_crossings_src_ts ON crossings(source_id, event_ts)"
_INSERT = "INSERT INTO crossings (event_ts,source_id,track_id,label,direction,cx,cy) VALUES (?,?,?,?,?,?,?)"

def setup():
    parent = os.path.dirname(path); if parent: os.makedirs(parent, exist_ok=True)
    self._conn = sqlite3.connect(path)          # check_same_thread=True (mặc định): dùng đúng 1 luồng (runner sync)
    self._conn.execute(_CREATE); self._conn.execute(_CREATE_IDX); self._conn.commit()

def handle(result):
    if result.status != SUCCESS or result.packet is None: return
    evs = result.packet.artifacts.get("crossing_events", ())
    if not evs: return
    self._conn.executemany(_INSERT, [(e.event_ts,e.source_id,e.track_id,e.label,e.direction,e.cx,e.cy) for e in evs])
    self._conn.commit()                          # durability: commit sau mỗi frame có event (R2.1)

def teardown():
    if self._conn is not None: self._conn.commit(); self._conn.close(); self._conn = None
```
- INSERT tham số hoá `?` (R2.3, chống injection + đúng kiểu). `executemany` cho nhiều event/frame.
- `CREATE ... IF NOT EXISTS` idempotent (R1.1) — mở DB cũ không hỏng. Index (source_id,event_ts) (R2.2).
- **Thread-safety (trung thực):** `sqlite3.connect` mặc định `check_same_thread=True` → connection dùng 1 THREAD. Sink chạy trong luồng runner (SyncLinearExecutor, 1 thread) → OK. Nếu sau này async/đa-thread → cần connection-per-thread hoặc `check_same_thread=False`+lock (ghi rõ, Non-Goal v1).

### C2 — Đăng ký config (extension point D-042)
`pipeline_factory`: `def _sink_crossing_events_sqlite(params): _need(params,"path",...); return CrossingEventSqliteSink(params["path"])`;
`_sink_crossing_events_sqlite.allowed_params = frozenset({"path"})`; registry `sinks["crossing_events_sqlite"] = ...`.

### C3 — CLI (vision_slice_app)
Cờ `--crossing-db <path>` (cần `--line`, validate fail-fast). Có → append `CrossingEventSqliteSink(path)` vào sinks. Summary in `db → {path}`.

## Data Models
Bảng `crossings` (xem C1). 1 hàng = 1 lượt qua vạch. Query mẫu:
`SELECT direction, COUNT(*) FROM crossings WHERE source_id=? AND event_ts>=? GROUP BY direction`.

## Correctness Properties

### Property 1: Ghi đúng hàng + query lại được
Feed N crossing_events (qua nhiều frame) → bảng `crossings` có N hàng; `SELECT` trả đúng field (direction/track_id/event_ts/cx/cy) từng event.
**Validates: Requirements 1.2, 1.3, 5.1**

### Property 2: setup idempotent + optional
`setup` 2 lần (DB đã có bảng) không lỗi (CREATE IF NOT EXISTS). Không gắn sink → không tạo file DB, pipeline y hệt.
**Validates: Requirements 1.1, 3.3**

### Property 3: Chỉ SUCCESS + không-event an toàn
result non-SUCCESS → không ghi. SUCCESS nhưng không `crossing_events` → không ghi (0 hàng). Backward-compat pipeline không có LineCrossingStage.
**Validates: Requirements 1.4**

### Property 4: Tham số hoá (an toàn) + index
INSERT dùng `?` (không nội suy). Index `(source_id,event_ts)` tồn tại (kiểm qua `sqlite_master`/PRAGMA).
**Validates: Requirements 2.2, 2.3**

### Property 5: Cắm config/CLI + không hồi quy
Config `crossing_events_sqlite` build được sink; `--crossing-db` wire được. 505 test cũ xanh + mới; lint 5/0; 0 diagnostic; additive.
**Validates: Requirements 3.1, 3.2, 4.1, 4.2, 4.3**

## Error Handling
- `setup` không mở được DB (path lỗi/quyền) → sqlite3 raise → fail-fast (không chạy mù). `handle` lỗi ghi → propagate + teardown finally đóng conn.
- Thiếu `crossing_events` → `.get(...,())` → không ghi (an toàn).
- `--crossing-db` thiếu `--line` → parser.error (fail-fast).

## Testing Strategy
`tests/test_crossing_event_sqlite.py` (CI, XÁC ĐỊNH):
1. **P1:** sink → handle packet có 2 CrossingEvent → mở lại DB bằng `sqlite3.connect` → `SELECT * ` = 2 hàng, field khớp.
2. **P2:** setup 2 lần không lỗi; teardown→ file DB tồn tại. Không gắn (không handle) → (test riêng) file không tạo trước setup.
3. **P3:** handle ERROR-result / SUCCESS-không-event → 0 hàng.
4. **P4:** query `PRAGMA index_list(crossings)` có index; INSERT tham số hoá (test bằng label chứa dấu nháy `'` → không vỡ SQL, lưu nguyên).
5. **P5 config/CLI:** `build_runner` với sink `crossing_events_sqlite` → runner chạy; `main(--track --line --crossing-db tmp)` rc0 + file DB tạo. `--crossing-db` thiếu `--line`→SystemExit.
6. **regression:** `scripts\vp.cmd verify` ≥505+mới · lint 5/0 · drift PASS.

## Quyết định thiết kế (lý do)
- **QĐ-1: sqlite3 stdlib** (không server-DB) — zero-dep, 1-file, đủ 1 node; server-DB là ISink khác khi scale (không đập lõi).
- **QĐ-2: commit/frame-có-event** — durability đồng bộ flush JsonlSink; đổi lấy chậm hơn batch-lớn (chấp nhận cho đúng-đắn).
- **QĐ-3: tham số hoá `?` + executemany** — an toàn injection + đúng kiểu + nhanh nhiều-event.
- **QĐ-4: check_same_thread mặc định (1 luồng)** — sink chạy trong runner sync; đa-thread là Non-Goal (ghi rõ để không dùng sai).
- **QĐ-5: sink RIÊNG (không thay JsonlSink)** — 2 backend song song, chọn qua config/CLI (SRP + linh hoạt).

## Self-Review (doubt-driven)
- **Lỗ 1 (đã xử):** injection/kiểu sai → tham số hoá `?` (QĐ-3, P4).
- **Lỗ 2 (đã xử):** dùng cross-thread → check_same_thread mặc định + tài liệu 1-luồng (QĐ-4).
- **Lỗ 3 (đã xử):** mở lại DB cũ hỏng bảng → CREATE IF NOT EXISTS idempotent (P2).
- **Còn mở (sub-spec sau):** server-DB (Postgres) · migration/schema-version · dedupe qua restart · batch-commit tối ưu · đa-thread pool.
**Phán quyết:** đủ sâu để THI CÔNG (schema/transaction/lifecycle/thread rõ + test query lại). Món "còn mở" là sub-spec riêng.

## Glossary
- **CrossingEventSqliteSink** — ISink ghi CrossingEvent vào bảng SQLite. Xem C1.
- **executemany / tham số hoá** — INSERT nhiều hàng an toàn (`?`). Xem QĐ-3.
- **check_same_thread** — cờ sqlite3 (1 connection/1 thread); v1 sync 1-luồng.
