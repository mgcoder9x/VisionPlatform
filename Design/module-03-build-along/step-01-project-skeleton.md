# Step 01 — Project skeleton + venv + pyproject + smoke test

## Mục tiêu (1h)

Cuối step này bạn có:
- 1 folder `vision_demo_workspace/` riêng biệt với HeadDetect.
- 1 Python venv hoạt động.
- 1 `pyproject.toml` chuẩn để `pip install -e` package được.
- Skeleton của 5 layer Hexagonal: `domain`, `kernel`, `runtime` (có `runtime/ipc/` cho SHM transport ở Step 05), `application`, `adapters` (+ `profiles/` cho composition root, không tính layer).
- 2 smoke test pass.

**Đến cuối step**: lệnh `pytest` ở terminal **PHẢI** in `2 passed`. Nếu không pass → **đừng** qua Step 02.

---

## Phần 1 — Tạo workspace (5 phút)

```bash
# Mở terminal. Đi vào ~/Desktop hoặc nơi bạn muốn chứa project.
cd ~/Desktop

# Tạo workspace HOÀN TOÀN TÁCH KHỎI HeadDetect — không nhầm lẫn.
mkdir vision_demo_workspace
cd vision_demo_workspace

# Tạo virtual env riêng.
py -m venv .venv

# Activate.
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
# .venv\Scripts\activate.bat
# Linux/Mac:
# source .venv/bin/activate

# Verify Python version.
python --version
# Expected: Python 3.11.x or higher.

# Upgrade pip.
python -m pip install --upgrade pip
```

→ Bạn nên thấy `(.venv)` ở prompt sau khi activate. Nếu không thấy → `Activate.ps1` không chạy. PowerShell có thể block — bạn cần `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force` rồi thử lại.

---

## Phần 2 — `pyproject.toml` (5 phút)

Đây là file metadata cho package. Tạo `pyproject.toml` ở root workspace:

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vision_demo"
version = "0.1.0"
description = "Minimal vision platform demo for the Learning_path"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
]

[project.optional-dependencies]
cv2 = ["opencv-python>=4.8"]
dev = ["pytest>=7.4", "import-linter>=2.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

# ---- Layer boundary enforcement (import-linter) ----
# Chạy: `lint-imports` (sau khi `pip install -e .[dev]`).
# 4-layer Hexagonal: domain ← kernel ← runtime ← application; adapters/profiles ở rim.
[tool.importlinter]
root_package = "vision_demo"
# BẮT BUỘC với import-linter 2.x khi contract 'forbidden' liệt kê module NGOÀI
# (cv2/torch/zmq/multiprocessing...). Thiếu dòng này → `lint-imports` lỗi:
# "top level configuration must have include_external_packages=True". (ERRATA E-9)
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Domain khong import I/O hay layer ngoai"
type = "forbidden"
source_modules = ["vision_demo.domain"]
forbidden_modules = [
    "cv2", "torch", "PyQt6", "fastapi", "zmq", "multiprocessing",
    "vision_demo.kernel", "vision_demo.runtime", "vision_demo.application",
    "vision_demo.adapters", "vision_demo.profiles",
]

[[tool.importlinter.contracts]]
name = "Kernel chi phu thuoc domain (DTO + ports thuan)"
type = "forbidden"
source_modules = ["vision_demo.kernel"]
forbidden_modules = [
    "cv2", "torch", "zmq",
    "vision_demo.runtime", "vision_demo.application",
    "vision_demo.adapters", "vision_demo.profiles",
]

[[tool.importlinter.contracts]]
name = "Runtime khong import application/adapter/profiles"
type = "forbidden"
source_modules = ["vision_demo.runtime"]
forbidden_modules = [
    "vision_demo.application", "vision_demo.adapters", "vision_demo.profiles",
]

[[tool.importlinter.contracts]]
name = "Application dung ports, khong import adapter"
type = "forbidden"
source_modules = ["vision_demo.application"]
forbidden_modules = ["vision_demo.adapters", "vision_demo.profiles"]

[[tool.importlinter.contracts]]
name = "Adapters la leaf — khong import nguoc len runtime/application/profiles"
type = "forbidden"
source_modules = ["vision_demo.adapters"]
forbidden_modules = [
    "vision_demo.runtime", "vision_demo.application", "vision_demo.profiles",
]
```

**Decisions giải thích**:

- `[build-system]` nói pip dùng setuptools để build. `>=68` cho `pyproject.toml` modern syntax.
- `requires-python = ">=3.11"` — chúng ta dùng `match/case` (3.10+) và `dict[str, ...]` (3.9+).
- `numpy` là **required** vì frame là ndarray. Numpy được phép trong Domain (math infrastructure) per ADR-022.
- `opencv-python` là **optional extra** — dùng cho real video adapter. Test chính không cần.
- `pytest` + `import-linter` là **dev extra** — test framework + layer-boundary enforcer.
- `[tool.setuptools.packages.find] where = ["src"]` — chuẩn "src layout". Tránh import lẫn lộn module và test.
- `addopts = "-v --tb=short"` — pytest verbose output, traceback ngắn.

### Tại sao import-linter ngay từ Step 01?

Dependency direction (Module 01 file 03) là **invariant kiến trúc quan trọng nhất** — nếu vi phạm, Hexagonal sụp đổ. Test pytest + đọc review thủ công **không đủ**: chúng không catch được "kernel lỡ import multiprocessing" hay "use case lỡ import adapter cụ thể". `import-linter` là static analysis chuyên dụng, chạy mỗi lần qua một step → bắt vi phạm **ngay khi nó xuất hiện**, không để tích luỹ tới cuối.

> **Cách dùng:** sau mỗi step có thêm code, chạy `lint-imports`. Phải in `Contracts: N kept, 0 broken`. Nếu broken → bạn vừa vi phạm layer boundary, sửa trước khi đi tiếp.

> **Lưu ý Step 05 (SHM):** transport SHM dùng `multiprocessing`/`shared_memory` là **I/O concern** → phải nằm ở `runtime/`, KHÔNG ở `kernel/` (contract "Kernel chỉ phụ thuộc domain" cấm `multiprocessing` trong kernel). Step 05 sẽ đặt nó ở `runtime/ipc/` cho đúng — xem chi tiết ở step đó.

---

## Phần 3 — Tạo cấu trúc folder (10 phút)

**Quan trọng**: dùng `src/` layout. Tránh "flat layout" (`vision_demo/` ở root) vì:
- `import vision_demo` từ test có thể accidentally pick up local folder thay vì installed package.
- Khi `pip install -e .`, src layout buộc bạn install đúng chỗ.

Tạo folder:

```bash
# Linux/Mac/Git Bash:
mkdir -p src/vision_demo/domain
mkdir -p src/vision_demo/kernel/ports
mkdir -p src/vision_demo/runtime/stages
mkdir -p src/vision_demo/runtime/ipc
mkdir -p src/vision_demo/application
mkdir -p src/vision_demo/adapters
mkdir -p src/vision_demo/profiles
mkdir -p tests
```

```powershell
# Windows PowerShell:
mkdir -p src/vision_demo/domain, src/vision_demo/kernel/ports, src/vision_demo/runtime/stages, src/vision_demo/runtime/ipc, src/vision_demo/application, src/vision_demo/adapters, src/vision_demo/profiles, tests
```

Tạo `__init__.py` cho mỗi package (Python yêu cầu):

```bash
# Linux/Mac:
touch src/vision_demo/{__init__,domain/__init__,kernel/__init__,kernel/ports/__init__,runtime/__init__,runtime/stages/__init__,runtime/ipc/__init__,application/__init__,adapters/__init__,profiles/__init__}.py
touch tests/__init__.py
```

```powershell
# Windows PowerShell — tạo từng file:
$initFiles = @(
    "src/vision_demo/__init__.py",
    "src/vision_demo/domain/__init__.py",
    "src/vision_demo/kernel/__init__.py",
    "src/vision_demo/kernel/ports/__init__.py",
    "src/vision_demo/runtime/__init__.py",
    "src/vision_demo/runtime/stages/__init__.py",
    "src/vision_demo/runtime/ipc/__init__.py",
    "src/vision_demo/application/__init__.py",
    "src/vision_demo/adapters/__init__.py",
    "src/vision_demo/profiles/__init__.py",
    "tests/__init__.py"
)
$initFiles | ForEach-Object { New-Item -ItemType File -Path $_ -Force | Out-Null }
```

Edit `src/vision_demo/__init__.py` thêm version:

```python
"""vision_demo - Minimal vision platform from Learning_path Module 03."""

__version__ = "0.1.0"
```

Để các `__init__.py` còn lại **rỗng** — chúng chỉ làm marker package.

Verify cấu trúc:

```bash
# tree command (Linux/Mac/Windows Git Bash):
tree src/vision_demo

# Hoặc PowerShell:
Get-ChildItem -Recurse src/vision_demo | Select-Object FullName
```

Expected:
```
src/vision_demo/
├── __init__.py            ← có __version__
├── adapters/__init__.py
├── application/__init__.py
├── domain/__init__.py
├── kernel/
│   ├── __init__.py
│   └── ports/__init__.py
├── profiles/__init__.py
└── runtime/
    ├── __init__.py
    ├── ipc/__init__.py      ← SHM transport (Step 05)
    └── stages/__init__.py
```

---

## Phần 4 — Smoke test (5 phút)

Tạo `tests/test_smoke.py`:

```python
"""Smoke test: verify package importable + version present."""
import vision_demo


def test_package_importable():
    """Package phải import được sau khi pip install -e."""
    assert vision_demo.__version__ == "0.1.0"


def test_package_has_layers():
    """All layer subpackages phải tồn tại (4 layer + adapter rim + profiles)."""
    import vision_demo.domain
    import vision_demo.kernel
    import vision_demo.kernel.ports
    import vision_demo.runtime
    import vision_demo.application
    import vision_demo.adapters
    import vision_demo.profiles
```

**Tại sao `test_package_has_layers`?** Vì:
- Catch lỗi `__init__.py` quên (Python import sẽ fail).
- Document cấu trúc layer rõ ràng — đọc test biết project có gì.
- Verify `pip install -e` đã install đúng cấu trúc.

---

## Phần 5 — Install + run test (5 phút)

```bash
# Cài package ở chế độ editable (dev mode).
# `pip install -e .` = "install package từ ./, chế độ dev — code change phản ánh ngay không cần reinstall".
python -m pip install -e .

# Cài dev dependency (pytest).
python -m pip install pytest
```

→ Output expected:
```
Successfully built vision_demo
Installing collected packages: vision_demo
Successfully installed vision_demo-0.1.0
```

Run test:

```bash
pytest
```

→ Expected output:
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\.../vision_demo_workspace
configfile: pyproject.toml
collecting ... collected 2 items

tests/test_smoke.py::test_package_importable PASSED                      [ 50%]
tests/test_smoke.py::test_package_has_layers PASSED                      [100%]

============================= 2 passed in 0.21s ==============================
```

→ **2 passed** = step 01 done.

---

## Troubleshoot

### "ModuleNotFoundError: No module named 'vision_demo'"

Bạn quên `pip install -e .`. Run:
```bash
python -m pip install -e .
```

Hoặc chưa activate venv. Verify:
```bash
which python      # Linux/Mac
where python      # Windows
```
Path **phải** trỏ vào `.venv/`. Nếu không → activate lại.

### "ImportError: cannot import 'vision_demo.kernel.ports'"

`__init__.py` thiếu trong subpackage. Verify:
```bash
ls src/vision_demo/kernel/ports/__init__.py
```
Nếu không tồn tại → `touch` (Linux/Mac) hoặc `New-Item` (PowerShell).

### "pytest: command not found"

Bạn chưa install pytest, HOẶC venv chưa activate. Run `python -m pytest` (luôn work nếu pytest in venv).

### "ExecutionPolicy" trên PowerShell

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

Rồi `.venv\Scripts\Activate.ps1` lại.

---

## Self-check trước khi qua Step 02

Trả lời:

1. **Tại sao src layout** thay vì flat?
2. **`pyproject.toml [tool.setuptools.packages.find] where = ["src"]`** — nếu xoá dòng này, lệnh nào sẽ fail?
3. **Optional dependencies `[cv2]` và `[dev]`** — install bằng cú pháp nào? Khi nào dùng?
4. **`.venv/`** có nên commit vào git không? Tại sao?
5. **`__init__.py` rỗng** có ý nghĩa gì? Có thể chứa code không?

<details>
<summary>Đáp án</summary>

1. Src layout: `import vision_demo` từ test buộc qua **installed package**, không phải local folder. Tránh "magic import" lẫn lộn dev và test. Industry standard cho Python package.

2. `pip install -e .` sẽ fail không tìm package. Setuptools default scan ở root, không tìm thấy `vision_demo/` ở đó (nó ở `src/`).

3. `pip install -e .[cv2]` cài thêm `opencv-python`. `pip install -e .[dev]` cài thêm `pytest`. Cũng có `pip install -e .[cv2,dev]` cho cả hai. Dùng khi: dev cần test → `[dev]`; chạy với real camera → `[cv2]`.

4. **KHÔNG commit `.venv/`**. Lý do:
   - Có cụ thể OS/Python version → không portable.
   - Vài chục MB. Bloat repo.
   - Có thể chứa wheel cache.
   - Mỗi dev tự `python -m venv .venv` riêng.
   - Add vào `.gitignore`.

5. **Rỗng** = "package marker". Python yêu cầu để treat folder là package importable. **Có thể chứa code** (e.g. re-export public API: `from .bbox import BBox`). Nhưng best practice: keep nó **rỗng** để tránh circular import + side-effect lúc import.

</details>

---

## Output verification

Tạo `.gitignore` (optional):

```gitignore
# .gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
build/
dist/
```

Cấu trúc cuối cùng:
```
vision_demo_workspace/
├── .venv/                            ← bị gitignore
├── .gitignore
├── pyproject.toml
├── src/vision_demo/
│   ├── __init__.py
│   ├── domain/__init__.py
│   ├── kernel/
│   │   ├── __init__.py
│   │   └── ports/__init__.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   └── stages/__init__.py
│   ├── application/__init__.py
│   ├── adapters/__init__.py
│   └── profiles/__init__.py
└── tests/
    ├── __init__.py
    └── test_smoke.py
```

```bash
pytest    # → 2 passed
```

→ ✅ Step 01 done.

---

## Liên kết

- Module 02 file 01 (`hexagonal-architecture-from-scratch.md`) — folder structure phản ánh Hexagonal layers.
- Module 01 file 03 (`dependency-direction.md`) — folder layout này enforce dependency direction.

---

## Tóm tắt 1 câu

> **Step 01 = setup môi trường chuẩn (venv, src layout, pyproject) + 2 smoke test verify package import được. Đây là nền cho mọi step sau.**

➡️ Tiếp theo: [`step-02-first-mediapacket.md`](step-02-first-mediapacket.md)
