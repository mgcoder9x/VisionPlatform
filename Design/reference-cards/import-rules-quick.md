# Import Rules Quick Reference

## Layer dependency direction

```
domain  ←  kernel  ←  runtime  ←  application
                         ↑              ↑
                         └── adapters ──┤
                                        │
                                  profiles (composition root)
```

→ Mũi tên đi từ ngoài (right) vào trong (left).

## Allowed imports per layer

### domain/

```python
# OK
from typing import Protocol
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

# NOT OK
import cv2          # Adapter
import torch        # Adapter
from PyQt6 import   # Adapter
from fastapi import # Adapter
from your_package.adapters import  # Wrong direction
```

### kernel/

```python
# OK
from your_package.domain import BBox
from typing import Protocol

# NOT OK
import cv2
from your_package.adapters import     # Wrong direction
from your_package.application import  # Wrong direction
```

### runtime/

```python
# OK
from your_package.domain import ...
from your_package.kernel.ports import ...
from your_package.kernel import MediaPacket

# NOT OK
from your_package.adapters import      # Wrong direction
from your_package.application import   # Wrong direction
```

### application/

```python
# OK
from your_package.domain import ...
from your_package.kernel import ...
from your_package.runtime import ...

# NOT OK
from your_package.adapters import   # Use ports instead
from your_package.profiles import   # Composition root only
```

### adapters/

```python
# OK
from your_package.domain import BBox
from your_package.kernel.ports import IDataSource
import cv2  # adapter implements port using cv2
import torch

# NOT OK
from your_package.runtime import     # Wrong direction
from your_package.application import # Wrong direction
from your_package.adapters.X import  # Cross-adapter (use ports)
```

### profiles/

```python
# OK — composition root
from your_package.domain import ...
from your_package.kernel import ...
from your_package.runtime import ...
from your_package.application import ...
from your_package.adapters.cv2_source import CV2VideoFileSource
from your_package.adapters.yolo_detector import YOLOv5Detector
# ...
```

## Enforcement

```toml
# pyproject.toml — using import-linter
[tool.importlinter]
root_package = "your_package"

[[tool.importlinter.contracts]]
name = "Domain has no I/O imports"
type = "forbidden"
source_modules = ["your_package.domain"]
forbidden_modules = ["cv2", "torch", "PyQt6", "fastapi", "your_package.adapters"]
```

## Quick check

```bash
# Check imports
import-linter check

# Visualize
pydeps your_package --max-bacon 2 --output deps.svg
```

## Common mistakes

- ❌ Use case import adapter directly → use port.
- ❌ Adapter A import adapter B → use composition root or port.
- ❌ Domain `import logging` → use port if needed, but usually skip.
- ❌ Kernel import adapter for "convenience" → defeats hexagonal.
