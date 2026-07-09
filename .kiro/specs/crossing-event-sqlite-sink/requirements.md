# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — design-first, CHỜ user đọc-lại-valid trước khi code.
> **Gắn với:** thêm 1 impl `ISink` (lưu trữ QUERYABLE) cho `CrossingEvent` (D-061). Song song `CrossingEventJsonlSink`
> (flat log) — chọn theo nhu cầu: JSONL để stream/append đơn giản, SQLite để TRUY VẤN (report BI).
> **Cập nhật lúc:** 2026-07-09.

## Introduction

`CrossingEventJsonlSink` ghi flat JSONL — tốt để stream/append, NHƯNG khó truy vấn (đếm theo giờ/hướng/camera phải
tự parse cả file). Vận hành/BI thương mại cần **lưu trữ QUERYABLE**: "bao nhiêu lượt IN của cam0 trong giờ qua?"
= 1 câu SQL. Thêm `CrossingEventSqliteSink` (dùng `sqlite3` **stdlib — KHÔNG dep mới**) ghi mỗi `CrossingEvent`
thành 1 hàng bảng → query bằng SQL.

**Nguyên tắc nền (bám "fix bản chất, không rebuild"):** tái dùng `CrossingEvent` (D-061), `ISink`, mẫu lifecycle
`CrossingEventJsonlSink` (setup/handle/teardown, chỉ SUCCESS, `.get("crossing_events",())`). **THÊM** 1 adapter +
đăng ký registry config (extension point D-042) + tuỳ chọn CLI. KHÔNG sửa LineCrossingStage/lõi.

**Chống bịa:** `sqlite3` đã KIỂM có (3.45.1, py3.11.9, stdlib). Schema + transaction thiết kế tường minh (không giả
định). Test query lại DB bằng chính `sqlite3` (kiểm chứng được, no-GPU).

**Non-Goal (v1):** KHÔNG ORM · KHÔNG migration/versioning schema · KHÔNG connection-pool/đa-thread (1 sink/1 luồng
runner sync, như camera-affinity) · KHÔNG server DB (Postgres...) — sqlite file là đủ cho 1 node, server-DB là impl sau.

## Requirements

### Requirement 1: Ghi CrossingEvent vào bảng SQLite queryable
**User Story:** Là vận hành/BI, tôi muốn mỗi lượt qua vạch là 1 hàng trong DB, để truy vấn bằng SQL (theo giờ/hướng/camera).
#### Acceptance Criteria
- 1.1 — `CrossingEventSqliteSink(path)` (ISink): `setup` mở/kết nối DB + `CREATE TABLE IF NOT EXISTS` (idempotent — chạy lại không hỏng bảng cũ).
- 1.2 — Bảng `crossings` cột: `id INTEGER PK AUTOINCREMENT`, `event_ts TEXT`, `source_id TEXT`, `track_id INTEGER`, `label TEXT`, `direction TEXT`, `cx REAL`, `cy REAL`.
- 1.3 — `handle`: chỉ khi `result.status == SUCCESS`; mỗi `CrossingEvent` trong `artifacts["crossing_events"]` → 1 INSERT (tham số hoá `?`, chống SQL-injection).
- 1.4 — `teardown`: commit + đóng kết nối (idempotent). Không mở DB / thiếu key → không ghi (backward-compat pipeline không có LineCrossingStage).

### Requirement 2: Bền vững + truy vấn được
**User Story:** Là vận hành, tôi muốn dữ liệu không mất khi tắt + truy vấn nhanh, để làm report.
#### Acceptance Criteria
- 2.1 — Commit sau MỖI frame có event (durability: mất tối đa 1 frame khi crash cứng — đồng bộ triết lý flush của JsonlEventSink).
- 2.2 — Có index trên `(source_id, event_ts)` (query theo camera + thời gian nhanh).
- 2.3 — INSERT tham số hoá (`execute(sql, tuple)`) — KHÔNG nội suy chuỗi (an toàn + đúng kiểu).

### Requirement 3: Cắm qua config + CLI (deploy-by-config)
**User Story:** Là kỹ sư triển khai, tôi muốn bật SQLite-sink qua config/CLI mà không đổi code.
#### Acceptance Criteria
- 3.1 — Đăng ký builder `crossing_events_sqlite` (params `path`) vào registry `pipeline_factory` (+ `allowed_params`).
- 3.2 — Tuỳ chọn CLI `--crossing-db <path>` (cần `--line`) trong `vision_slice_app`.
- 3.3 — Không gắn = không tạo DB, pipeline y hệt (lưu trữ optional — C-013).

### Requirement 4: Tái dùng nền, không phá lõi + không hồi quy
**User Story:** Là maintainer, tôi muốn thêm sink SQLite mà không sửa stage/pipeline/sink cũ, để không hồi quy.
#### Acceptance Criteria
- 4.1 — Chỉ THÊM: `CrossingEventSqliteSink`@adapters + đăng ký registry + cờ CLI. KHÔNG sửa LineCrossingStage/CrossingEvent/PipelineRunner/JsonlSink.
- 4.2 — Baseline **505 passed/1 skipped · lint 5/0** giữ (chỉ tăng test).
- 4.3 — Không phá import-linter: sink→adapters (leaf, I/O). `sqlite3` stdlib (không thêm dep [project]).

### Requirement 5: Kiểm chứng được KHÔNG cần GPU/camera
**User Story:** Là kỹ sư, tôi muốn test sink SQLite xác định trên máy dev, để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test: feed packet có `crossing_events` (dựng tay) → sink ghi vào DB `tmp_path` → mở lại bằng `sqlite3` query `SELECT` → assert số hàng + nội dung cột.
- 5.2 — Test xác định (không random/không giờ thật — event_ts từ CrossingEvent dựng tay).

## Non-Goals
- KHÔNG ORM/migration/schema-version · KHÔNG đa-thread/pool · KHÔNG server-DB · KHÔNG dedupe qua restart (append thuần, như JSONL).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` có: schema bảng + lifecycle (connect/create/insert/commit/close) + transaction/durability + thread-safety
(sync 1-luồng) + đăng ký registry + CLI + Correctness Properties (map Requirements) + Testing no-GPU (query lại DB). **0 diagnostic.**

## Glossary
- **CrossingEventSqliteSink** — ISink ghi CrossingEvent vào bảng SQLite (queryable).
- **queryable storage** — lưu trữ truy vấn được bằng SQL (đối lập flat JSONL phải parse).
- **check_same_thread** — cờ sqlite3: mặc định connection dùng 1 thread; sink dùng trong luồng runner sync (1 thread).
