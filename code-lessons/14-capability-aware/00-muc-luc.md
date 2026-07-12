# 14 — Capability-aware — MỤC LỤC (các mẩu nhỏ nhất)

> Đọc `00-cau-chuyen.md` trước. Mỗi mẩu = 1 ý nhỏ nhất, quote code thật + cite path. Tạo DẦN. Trạng thái: ⬜/🔵/✅.

| # | Mẩu (ý nhỏ nhất) | File code thật | Trạng thái |
|---|---|---|---|
| 01 | Năng-lực-máy = khái niệm HẠNG NHẤT: `MachineCapabilities` DTO (@kernel, frozen, tiêm được) | `kernel/capabilities.py` | ⬜ |
| 02 | `resolve_device` — HÀM THUẦN (auto/cpu/cuda/cuda:N); fail-fast `CapabilityError` khi ép cuda thiếu GPU | `kernel/capabilities.py` | ⬜ |
| 03 | Chi tiết resolve: `has_cuda` gate · `cuda:N` kiểm ordinal (`_parse_ordinal`) · chuẩn hoá lower | `kernel/capabilities.py` | ⬜ |
| 04 | `probe_capabilities` (@adapters) — KHÔNG BAO GIỜ raise; `has_cuda = is_available AND device_count>0` | `adapters/capability_probe.py` | ⬜ |
| 05 | Vì sao TÁCH DÒ (probe@adapters, chạm torch) khỏi QUYẾT-ĐỊNH (resolve@kernel, thuần) — ranh giới + test | `capabilities.py` vs `capability_probe.py` | ⬜ |
| 06 | `conftest.py` gate `@pytest.mark.gpu` autoskip — CI xanh MỌI máy không giảm phủ test | `tests/conftest.py` | ⬜ |
| 07 | Lệnh operator `--capabilities` — in JSON năng lực máy TRƯỚC deploy (đổi máy GPU/không-GPU) | `profiles/vision_slice_app.py::main` | ⬜ |
| 08 | Wiring: `_det_pt` resolve device + `main` bắt `CapabilityError` → exit 2 (thông báo gọn, không traceback) | `pipeline_factory.py::_det_pt` + `vision_slice_app.py` | ⬜ |

**Ghi chú:** #14 = capability-aware-execution (spec D-072/D-073, sau #10). Đọc kèm #06 (detector) + #11 (factory/`_det_pt`).
Đây là chủ đề CUỐI của chương trình lấp khoảng-trống deep-dive (sau #10): #11 config · #12 analytics · #13 observability · #14 capability.
