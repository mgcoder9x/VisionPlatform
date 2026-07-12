# 14 — Capability-aware execution (chạy trên máy hỗn tạp GPU/CPU) — CÂU CHUYỆN

> Bám code THẬT (đã đọc): `kernel/capabilities.py` · `adapters/capability_probe.py` · `tests/conftest.py` ·
> `profiles/vision_slice_app.py` (`--capabilities` + `_det_pt` device). Người học: đã qua #06 (detector) + #11 (config/factory).
> Thuật ngữ lạ → `knowledge-base/00-GLOSSARY.md`.

---

## Nhịp 1 — Tổng quan (nằm ĐÂU, phục vụ GÌ)

Cùng 1 codebase chạy trên NHIỀU máy: máy dev (không GPU/không torch), máy CI, máy production (có GPU). "Capability-
aware" = hệ TỰ BIẾT máy hiện tại có gì (torch/CUDA/GPU/cv2) và cư xử đúng — thay vì crash hoặc chạy nhầm. Vị trí:

```
adapters/capability_probe.py  ── DÒ máy thật (import torch?) ──►  MachineCapabilities (DTO @kernel)
                                                                        │
kernel/capabilities.py::resolve_device(requested, caps)  ──────────────┘  (HÀM THUẦN, quyết định device)
    · profiles: _det_pt → resolve_device(...) → detector chạy đúng cpu/cuda
    · tests/conftest.py: @pytest.mark.gpu tự SKIP nếu máy không CUDA
    · CLI: --capabilities in JSON năng lực máy (operator kiểm TRƯỚC deploy)
```

## Nhịp 2 — VẤN ĐỀ & tại sao (Forces — nỗi đau TÁI DIỄN)

Nỗi đau thật lặp đi lặp lại: đổi máy GPU↔không-GPU → code rải `if torch.cuda.is_available(): ... else ...` khắp
nơi → (a) khó test (máy CI không GPU thì nhánh CUDA không chạy được), (b) `import torch` ở tầng thấp làm máy
không-torch CRASH ngay khi nạp, (c) ép `device=cuda` trên máy không GPU → lỗi mù sâu trong torch (khó hiểu).
- *Forces:* chạy-được-mọi-máy ↔ tận-dụng-GPU-khi-có; fail-fast-rõ (ép cuda thiếu GPU) ↔ fallback-êm (auto);
  test-không-cần-GPU ↔ vẫn kiểm được logic chọn device.

> ✋ Đoán thử: làm sao TEST logic "chọn cuda/cpu" mà KHÔNG cần máy có GPU? (đáp nhịp 4)

## Nhịp 3 — Khám phá NHIỀU hướng

- (a) rải `if torch...` khắp nơi — khó test/khó bảo trì, tầng thấp kéo torch. LOẠI.
- (b) 1 biến toàn cục `DEVICE` set lúc khởi động — đỡ rải nhưng vẫn trộn "dò" với "quyết định", khó test tiêm.
- (c) **Tách 3 việc:** DÒ (probe, ở adapters — được chạm torch) → DTO năng-lực (kernel, thuần) → HÀM THUẦN
  quyết-định-device (`resolve_device`, kernel). → test tiêm DTO giả (no-GPU) kiểm được logic; probe an-toàn-không-raise. CHỌN.

## Nhịp 4 — CHỐT giải pháp + tại sao thắng

- **Năng-lực-máy = khái niệm HẠNG NHẤT:** `MachineCapabilities` (DTO @kernel, immutable) — 1 NGUỒN sự thật về "máy có gì".
- **DÒ ở rìa:** `probe_capabilities` @adapters (được `import torch`), **KHÔNG BAO GIỜ raise** (máy no-torch → trả
  False), `has_cuda = is_available() AND device_count()>0` (chống ca lạ). Trả `MachineCapabilities`.
- **QUYẾT ĐỊNH thuần:** `resolve_device(requested, caps)` @kernel — HÀM THUẦN (không I/O, không probe): auto→best,
  cpu→cpu, cuda-thiếu-GPU→**CapabilityError fail-fast**, cuda:N kiểm ordinal, chuẩn hoá lower. → **test tiêm caps
  giả xác định, KHÔNG cần GPU** (đáp nhịp 2).
- **Gate test:** `conftest` auto-SKIP `@pytest.mark.gpu` khi máy không CUDA → CI xanh MỌI máy không giảm phủ.
- **Operator:** `--capabilities` in JSON năng lực → kiểm máy TRƯỚC deploy.
- *Thắng:* tách DÒ (adapters, chạm dep) khỏi QUYẾT-ĐỊNH (kernel, thuần) → test được + không rải if + fail-fast rõ.

## Nhịp 5 — Dạy TRIỂN KHAI (qua mẩu nhỏ nhất)
Xem `00-muc-luc.md`: MachineCapabilities DTO → resolve_device (auto/cpu/cuda/cuda:N + CapabilityError) → probe (không-raise, has_cuda thật) → vì-sao-tách-DTO/policy-khỏi-probe → conftest gate GPU → --capabilities → wiring `_det_pt`+exit-2.

## Nhịp 6 — NÊN LÀM / NÊN TRÁNH
**Nên:** năng-lực = DTO hạng nhất (1 nguồn) · probe KHÔNG raise (no-torch vẫn dò) · resolve THUẦN (test tiêm caps) ·
fail-fast khi ép cuda thiếu GPU (không fail mù) · has_cuda = is_available AND count>0 · gate GPU test (CI xanh mọi máy).
**Tránh:** rải `if torch...` khắp nơi · `import torch` ở kernel/domain (crash máy no-torch + phá contract) · fallback
cuda→cpu IM LẶNG khi user ÉP cuda (giấu lỗi — nên fail-fast) · probe raise (làm sập máy no-torch).

## Tự kiểm (retrieval)
1. Vì sao tách DÒ (probe@adapters) khỏi QUYẾT-ĐỊNH (resolve_device@kernel)? Lợi cho test gì?
2. `probe_capabilities` vì sao KHÔNG BAO GIỜ raise?
3. Ép `device=cuda` trên máy không GPU → điều gì xảy ra, vì sao fail-fast tốt hơn fallback im lặng?
4. `@pytest.mark.gpu` autoskip giúp CI thế nào?

**Mốc ôn:** 1 ngày / 1 tuần / 1 tháng. **Nguồn:** 4 file trên · D-072/D-073 (capability-aware) · K-077/K-079 (torch máy toann) · `docs/ARCHITECTURE.md` §5/§9.
