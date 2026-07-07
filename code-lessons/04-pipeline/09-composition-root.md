# #04 · Mẩu 09: `demo_pipeline` — composition root (ráp adapter + stage + vòng lặp + dọn)

## 1. Thuộc về đâu
Vấn đề #04 · file code thật: `vision-platform/src/vision_platform/profiles/demo_pipeline.py` ·
tầng **profiles** (composition root) · đây là chỗ DUY NHẤT biết adapter cụ thể + ráp toàn pipeline chạy end-to-end.

## 2. Cần biết trước
- Mẩu 05/06 (Brightness/DarkFilter stage) + mẩu 07 (`SyncLinearExecutor`) + mẩu 02 (`ExecutionResult.status`) — đọc trước.
- #03 adapter `FakeFrameSource`/`NoiseFrameSource` + `ReadResult`/`ReadStatus`; #02 `MediaPacket`/`InMemoryArrayRef.from_copy`.
- [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
  [port](../../knowledge-base/00-GLOSSARY.md#port-cổng--hexagonal)
- "composition root" = chỗ duy nhất lắp ráp các mảnh cụ thể lại (→ giải ở §6).

## 3. Code thật (quote NGUYÊN VĂN — trích phần lõi, dấu `# ...` = bỏ phần giữa)
```python
# vision-platform/src/vision_platform/profiles/demo_pipeline.py
    # ===== Composition root: chỗ DUY NHẤT chọn cụ thể adapter. =====
    if args.source == "fake":
        from vision_platform.adapters.fake_frame_source import FakeFrameSource
        source = FakeFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    elif args.source == "noise":
        from vision_platform.adapters.noise_frame_source import NoiseFrameSource
        source = NoiseFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    else:
        parser.error(f"Unknown source: {args.source}")

    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=args.threshold),
    ])

    # ===== Run loop =====
    # ... (khởi tạo bộ đếm seq/n_processed/n_skipped/...)
    # Context manager (R2#04 / ERRATA E-16): `with source, executor:` tự setup lúc vào +
    # teardown lúc ra (kể cả khi raise). Thứ tự ra: executor.teardown_all() → source.teardown().
    with source, executor:
        while True:
            r = source.read()
            if r.status == ReadStatus.EOF:
                n_eof += 1
                break
            if r.status == ReadStatus.ERROR:
                n_error += 1
                print(f"[seq={seq}] source ERROR: {r.error}", file=sys.stderr)
                continue
            if not r.has_data:
                continue
            packet = MediaPacket(
                packet_id=f"pkt_{seq}",
                source_id=source.source_id,
                media_ref=InMemoryArrayRef.from_copy(r.data),
                capture_time_ns=time.monotonic_ns(),
            )
            seq += 1
            result = executor.execute(packet)
            if result.status == StageStatus.SUCCESS:
                n_processed += 1
                final = result.packet
                # ... print brightness + shape
            elif result.status == StageStatus.SKIPPED:
                n_skipped += 1
            elif result.status == StageStatus.ERROR:
                n_stage_error += 1
                # ... print failed_stage + error_type + error_message
            else:  # CANCELLED
                n_cancelled += 1
```

## 4. Giải thích từng phần nhỏ nhất
- **Lazy import adapter:** `from vision_platform.adapters... import ...` đặt **TRONG nhánh `if`**, không ở đầu file → chỉ nạp adapter thật sự dùng. Đây là chỗ DUY NHẤT biết `FakeFrameSource`/`NoiseFrameSource` cụ thể.
- `parser.error(...)` → tên source lạ → báo lỗi CLI rõ.
- `executor = SyncLinearExecutor([BrightnessStage(), DarkFilterStage(threshold=...)])` → ráp pipeline; **Brightness TRƯỚC DarkFilter** (đúng thứ tự mẩu 06 yêu cầu).
- `with source, executor:` (R2#04/E-16) → vào: `source.__enter__()` (setup) → `executor.__enter__()` (setup_all); ra: `executor.__exit__()` (teardown_all) → `source.__exit__()` (teardown) — **LUÔN dọn** dù lỗi/break giữa chừng, không cần `try/finally` thủ công.
- `while True:` đọc từng frame:
  - `r = source.read()` → trả `ReadResult` (#03).
  - `EOF` → hết nguồn → `break`. `ERROR` → đếm + in stderr + `continue`. `not r.has_data` → bỏ qua (không có data lần này).
  - tạo `MediaPacket(...)` với `InMemoryArrayRef.from_copy(r.data)` → **copy** mảng vào packet (an toàn, #02), gắn `source_id` + `capture_time_ns`.
  - `result = executor.execute(packet)` → chạy qua chuỗi (mẩu 07) → `ExecutionResult`.
  - **switch theo `result.status`:** SUCCESS → đếm processed + in brightness/shape · SKIPPED → đếm skipped · ERROR → đếm + in `failed_stage`/`error_type`/`error_message` · else → CANCELLED. → đúng 4 ca của mẩu 02.

## 5. Là gì (1–2 câu)
`demo_pipeline.main()` là **composition root**: nơi duy nhất chọn adapter cụ thể, ráp stage thành
executor, chạy vòng lặp đọc→xử lý→thống kê, và đảm bảo dọn tài nguyên qua `with source, executor:`.

## 6. Tại sao tồn tại / vấn đề nó giải — FIX TẬN GỐC (gom phụ thuộc cụ thể về 1 chỗ)
- **composition root** = điểm lắp ráp duy nhất, nơi "code trừu tượng" (port/stage) gặp "thứ cụ thể" (adapter, ngưỡng, kích thước). Vì sao gom về 1 chỗ?
- **Vấn đề:** nếu rải `import FakeFrameSource` khắp nơi → lõi/stage bị dính cứng vào adapter cụ thể → khó đổi nguồn, khó test, vi phạm hướng phụ thuộc 6 layer.
- **Fix tận GỐC:** chỉ `profiles/` được biết adapter. Lõi + runtime chỉ thấy port/`IStage`. Đổi từ `fake` sang `noise` (hay sau này camera thật) = đổi ở DUY NHẤT composition root, không đụng stage/executor.
- **`from_copy` + `with`:** copy frame vào packet (không chia sẻ buffer nguồn) + context manager luôn teardown → an toàn dữ liệu + không rò tài nguyên.

## 7. Dùng ở đâu trong project (cụ thể)
- Chạy thật: `python -m vision_platform.profiles.demo_pipeline --source fake --frames 20 --threshold 50`.
- Là bản "ráp end-to-end" minh hoạ toàn bộ #04 (source #03 → stage #04 → result-object #04).
- **Đã CHẠY THẬT lệnh demo (2026-06-21), kiểm cả 3 nhánh status:**
  - `--source fake --threshold 0` → `Processed: 4`, in `[seq=001] brightness=0.00 shape=(240, 320, 3)` ... `brightness=3.00` (fake tăng dần) → nhánh **SUCCESS** + đúng format print quote ở §3.
  - `--source noise --threshold 50` → `Processed: 4`, `brightness≈127` → SUCCESS với nguồn khác (đổi adapter chỉ ở composition root).
  - `--source fake --threshold 50` → `Skipped (filter): 6`, `Stage errors: 0`, `EOF: 1` → nhánh **SKIPPED** (fake tối < 50).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Không có composition root: phụ thuộc cụ thể rải khắp → lõi dính adapter → khó test/đổi nguồn → vỡ kiến trúc 6 layer.
- Không `with`/`finally`: lỗi giữa vòng lặp → quên teardown → rò.
- Trả `Optional` thay `ExecutionResult`: switch 4 ca không làm được → đếm skip/error lẫn lộn.

## 9. Ví von đời thường
Composition root như **bản vẽ lắp ráp cuối** của nhà máy: chọn đúng máy (adapter), xếp trạm theo thứ
tự (stage), bật dây chuyền, đếm sản phẩm theo từng kết cục, và **luôn tắt máy khi xong** (finally).

## 10. Liên kết bức tranh lớn
Đây là đỉnh của #04: gom #02 (MediaPacket) + #03 (source port/adapter) + #04 (stage/executor/result-object).
`profiles/` là tầng trên cùng được phép phụ thuộc mọi tầng — đúng quy tắc import 6 layer (#01).

## 11. Cạm bẫy / lỗi thường gặp
- Import adapter ở đầu file (không lazy) → lõi/khu khác vô tình kéo theo adapter → rò phụ thuộc.
- Đặt DarkFilter trước Brightness trong list → ERROR (mẩu 06).
- Bỏ `with` (tự gọi setup/teardown thủ công) → dễ quên teardown khi break/raise.
- Dùng `InMemoryArrayRef(r.data)` (không `from_copy`) → chia sẻ buffer nguồn → nguồn ghi đè frame sau làm hỏng packet trước.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao import adapter nằm TRONG nhánh `if` (lazy) chứ không ở đầu file?
- Tình huống: muốn đổi từ nguồn `fake` sang camera thật — phải sửa ở đâu, KHÔNG đụng đâu? vì sao chỉ 1 chỗ?
- Giải thích lại bằng LỜI MÌNH: "composition root là ... ; nó gom thứ cụ thể về 1 chỗ để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại vai trò composition root + 4 ca switch status | 1 tuần → tự ráp 1 pipeline mới | 1 tháng → giải thích vì sao chỉ profiles biết adapter.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/profiles/demo_pipeline.py` (đã ĐỌC nguyên văn; trích lõi, dấu `# ...` đánh dấu phần bỏ). · Độ chắc: **cao**.
- Hành vi pipeline (stage/executor/result-object): đã CHẠY THẬT `pytest tests/test_step_04_pipeline.py` → **13 passed**. · Độ chắc: **cao**.
- Hành vi CHÍNH lệnh demo: đã CHẠY THẬT `python -m vision_platform.profiles.demo_pipeline` (fake th=0 → Processed 4; noise th=50 → Processed 4; fake th=50 → Skipped 6, 0 error) trong phiên 2026-06-21. · Độ chắc: **cao**.
