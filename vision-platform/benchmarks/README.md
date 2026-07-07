# benchmarks/ — đo công suất 1-node

Công cụ DEV (ngoài `src/`, không phải runtime dep). Phương pháp: `.kiro/specs/node-capacity-benchmark/`.

## Chạy

```powershell
# VERIFY LOGIC (máy nào cũng chạy, KHÔNG cần torch/GPU) — số là của Fake*, KHÔNG phải capacity:
python -m benchmarks.bench_capacity --mode infer   --device cpu --imgsz 32 --warmup 2 --measure 5
python -m benchmarks.bench_capacity --mode latency --device cpu --warmup 2 --measure 10

# SỐ CAPACITY THẬT (cần GPU + `pip install -e ".[pt]"` → torch + yolov5):
python -m benchmarks.bench_capacity --mode infer   --device cuda --weights models/yolov5s.pt --imgsz 640 --warmup 20 --measure 200
python -m benchmarks.bench_capacity --mode decode  --video clips/sample.mp4 --warmup 20 --measure 200
python -m benchmarks.bench_capacity --mode latency --device cuda --weights models/yolov5s.pt --video clips/sample.mp4
```

## Nguyên tắc TRUNG THỰC (bắt buộc)
- `--device cpu`/fake = **kiểm harness chạy đúng**, KHÔNG phải số capacity. Harness in cảnh báo rõ.
- `--device cuda` khi thiếu torch/GPU → **dừng (exit 3), KHÔNG tạo số giả**.
- Điền số vào `.kiro/specs/node-capacity-benchmark/design.md` (bảng template) CHỈ sau khi chạy `--device cuda` thật;
  ô chưa đo giữ `[chưa đo]`.
- Đo phải: bỏ warmup, cửa sổ steady-state, GPU `cuda.synchronize` trước khi chốt thời gian (đã cài trong harness),
  đo **combined decode+infer** cho số định cỡ (chưa tự động hoá — chạy 2 tiến trình song song + quan sát), gắn header môi trường.

## Batch (lỗ A1)
`IDetector.detect` theo-từng-frame → đo batch>1 phải gọi model nền (`Yolov5PtDetector._model([frames])`). Đây là
bằng chứng batch CHƯA expose qua port (lỗ A1 trong K-040) — không phải hạn chế của harness.
