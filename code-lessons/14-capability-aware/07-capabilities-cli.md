# 14.07 — Lệnh operator `--capabilities` — in JSON năng lực máy TRƯỚC deploy

## 1. Thuộc về đâu
profiles — `vision_slice_app.main` (nhánh `--capabilities`). Lệnh vận hành (operator), không phải chạy pipeline.

## 2. Cần biết trước
mẩu 01 (MachineCapabilities), 04 (probe). `dataclasses.asdict` (DTO→dict). JSON stdout để script parse.

## 3. Code thật (quote nguyên văn — `vision_slice_app.py::main`)
```python
    if args.capabilities:
        import dataclasses, json
        from vision_platform.adapters.capability_probe import probe_capabilities
        caps = probe_capabilities()
        print(json.dumps(dataclasses.asdict(caps), ensure_ascii=False))
        print(f"[capabilities] torch={caps.has_torch} cuda={caps.has_cuda} "
              f"gpu={caps.gpu_name} cv2={caps.has_cv2}", file=sys.stderr)
        return 0
```

## 4. Giải thích từng mẩu nhỏ nhất
- `probe_capabilities()` — dò máy (mẩu 04, an toàn).
- `json.dumps(dataclasses.asdict(caps))` → STDOUT: JSON máy-parse-được (vd `{"has_torch": false, "has_cuda": false, ...}`).
- Dòng `[capabilities] ...` → STDERR: người-đọc-được (tách stdout/stderr → script lấy JSON sạch ở stdout).
- `return 0` — thoát ngay, KHÔNG chạy pipeline.

## 5. Là gì
Lệnh in ra "máy hiện tại có gì" (torch/cuda/gpu/cv2) dạng JSON + dòng người-đọc.

## 6. Tại sao tồn tại / vấn đề nó giải
Nỗi đau đổi-máy GPU↔CPU: TRƯỚC khi deploy config `pt`/GPU lên 1 máy, operator cần biết máy đó CÓ GPU/torch không.
`--capabilities` = 1 lệnh kiểm nhanh (JSON parse được bởi script vận hành/CI). Tránh deploy rồi mới phát hiện thiếu GPU.

## 7. Dùng ở đâu
Operator/CI chạy `python -m vision_platform.profiles.vision_slice_app --capabilities` (hoặc `vp env` gọi gián tiếp).
Máy toann (K-079): in `{"has_torch": false, ..., "has_cv2": true}` → biết ngay torch vắng.

## 8. Không có nó thì sao
Không có → operator phải mở Python REPL gõ `torch.cuda.is_available()` (cần torch cài + biết code) hoặc deploy rồi
đoán. Lệnh CLI = kiểm chuẩn, script-hoá được, không cần biết nội bộ.

## 9. Ví von
Bấm nút "thông tin hệ thống" trên máy trước khi cài phần mềm nặng — biết cấu hình đủ chạy không.

## 10. Liên kết bức tranh lớn
Ứng dụng capability cho TẦNG VẬN HÀNH (operator). Nối probe (04) + DTO (01). STDOUT-JSON / STDERR-người = mẫu chuẩn
cho lệnh script-hoá. Là bằng chứng dùng ở #313/#315 (verify torch máy toann).

## 11. Cạm bẫy
- JSON ra STDOUT, dòng người ra STDERR — đừng trộn (script parse stdout cần sạch).
- Chỉ dò + in + thoát (return 0), KHÔNG chạy pipeline (đặt nhánh này ĐẦU `main`, trước mọi thứ khác).

## 12. Tự kiểm (Feynman)
- `--capabilities` giải nỗi đau vận hành gì? Vì sao JSON ra stdout, text ra stderr?
- Trên máy không torch, lệnh này CRASH hay in has_torch=false? (nối probe không-raise mẩu 04)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`profiles/vision_slice_app.py::main` (đọc thật #324) · D-080 (lệnh --capabilities). Độ chắc: cao (quote trực tiếp).
