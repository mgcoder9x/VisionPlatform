# 14.06 — `conftest.py` gate `@pytest.mark.gpu` autoskip — CI xanh MỌI máy không giảm phủ test

## 1. Thuộc về đâu
`vision-platform/tests/conftest.py`. Hook pytest chạy lúc collect test, gate test cần GPU.

## 2. Cần biết trước
mẩu 04 (probe). `@pytest.mark.gpu` = nhãn đánh dấu test cần GPU. `pytest_collection_modifyitems` = hook pytest sửa danh sách test lúc collect.

## 3. Code thật (quote nguyên văn — `tests/conftest.py`)
```python
from vision_platform.adapters.capability_probe import probe_capabilities

_CAPS = probe_capabilities()

def pytest_collection_modifyitems(config, items):
    import pytest
    if _CAPS.has_cuda:
        return  # máy có GPU → để test gpu chạy thật
    skip_gpu = pytest.mark.skip(reason=f"cần CUDA (máy không có CUDA khả dụng: has_torch={_CAPS.has_torch}) — skip tự động")
    for item in items:
        if "gpu" in item.keywords:
            item.add_marker(skip_gpu)
```
(`pyproject.toml` khai marker: `"gpu: test cần CUDA thật — tự SKIP khi máy không có CUDA (conftest gate)"`.)

## 4. Giải thích từng mẩu nhỏ nhất
- `_CAPS = probe_capabilities()` — dò 1 lần lúc collect (probe không-raise → an toàn máy no-torch, mẩu 04).
- `if _CAPS.has_cuda: return` — máy CÓ GPU → không skip gì → test `@pytest.mark.gpu` chạy THẬT.
- máy KHÔNG CUDA → thêm marker `skip` cho mọi item có keyword `"gpu"` → các test đó tự SKIP (không fail, không chạy).

## 5. Là gì
Cổng tự động: test cần GPU chỉ chạy trên máy có GPU; máy không GPU thì SKIP (không xoá test).

## 6. Tại sao tồn tại / vấn đề nó giải
Test nhánh CUDA cần GPU thật. Trên CI/máy dev không GPU: nếu chạy → FAIL (không có CUDA); nếu XOÁ test → mất phủ.
Gate = giải pháp thứ 3: SKIP tự động trên máy không GPU (CI xanh), CHẠY THẬT trên máy GPU (vẫn phủ). Không giảm
phủ, không fail giả. `vp verify` xanh trên MỌI máy.

## 7. Dùng ở đâu
Test detector CUDA / benchmark GPU đánh `@pytest.mark.gpu` → tự skip máy no-GPU (như máy toann, K-079: 2 skipped
gồm test gpu). Chạy thật khi có GPU.

## 8. Không có nó thì sao
Không gate → test gpu FAIL trên CI no-GPU (đỏ giả) → phải xoá test (mất phủ) hoặc CI luôn đỏ. Gate = xanh-mọi-máy + giữ phủ.

## 9. Ví von
Trò chơi cần chiều cao 1m4: máy có GPU (đủ cao) → chơi; máy không → "hẹn dịp khác" (skip) chứ không tính là THUA (fail).

## 10. Liên kết bức tranh lớn
Ứng dụng capability (probe) cho TẦNG TEST. Nối probe (04) + không-raise. Giải thích "2 skipped" trong baseline
628/2 (test gpu skip trên máy no-GPU). Đây là 1 phần "chạy-được-mọi-máy".

## 11. Cạm bẫy
- Probe lúc collect PHẢI không-raise (mẩu 04) — nếu raise thì collect crash cả suite.
- Test đánh `@pytest.mark.gpu` phải THỰC SỰ cần GPU; đánh nhầm test CPU → bị skip oan (mất phủ trên CI).

## 12. Tự kiểm (Feynman)
- 3 cách xử test-cần-GPU trên CI no-GPU (fail / xoá / skip-gate) — vì sao skip-gate thắng?
- "2 skipped" trong baseline nghĩa là gì (liên quan gate)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`tests/conftest.py` + `pyproject.toml` marker (đọc thật phiên này) · D-073. Độ chắc: cao (quote trực tiếp).
