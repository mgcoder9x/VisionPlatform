# 01 — Hexagonal Architecture (Ports & Adapters) — Build từ con số 0

## TL;DR (30 giây)

> **Hexagonal Architecture = đặt business logic ở giữa, mọi I/O (DB, API, UI, file...) đẩy ra "rìa" qua interface.** Logic core không biết cụ thể về DB hay UI — nó chỉ biết "interface". Đổi DB không đụng logic.
>
> Tên "Hexagonal" vô nghĩa — Alistair Cockburn (1995) chọn vì vẽ đẹp, không phải có ý nghĩa kỹ thuật. Ý nghĩa thực = **Ports & Adapters**.
>
> Trong Vision Platform: business logic (use case xử lý frame) ở center, các adapter (cv2, ZMQ, Postgres, Qt) ở rìa. **Đổi YOLO sang RTMDet → đổi 1 adapter, không động logic chính.**

---

## Mental hook

Bạn vừa join 1 dự án legacy. Code structure:

```
src/
├── main.py                    # 1500 dòng, đọc DB + chạy inference + serve HTTP
├── helpers.py                 # 800 dòng utility random
├── database.py                # Postgres queries, format SQL
└── api.py                     # Flask endpoints
```

Sếp: "Khách yêu cầu chuyển từ Postgres sang SQLite cho on-premise deploy. Bạn estimate?"

Bạn mở `database.py`. 50 hàm Postgres-specific. Bạn mở `main.py` — `import psycopg2` ở đầu, `psycopg2.connect()` rải khắp 1500 dòng. `helpers.py` cũng có 3 hàm dùng cursor Postgres.

Estimate thật: **2 tuần**, có khả năng vỡ vì `psycopg2.cursor` semantics khác `sqlite3.cursor`.

---

Cùng dự án, nhưng **Hexagonal**:

```
src/
├── domain/                       # Business logic, ZERO I/O
├── ports/                        # Interfaces: ICustomerRepo, IOrderRepo
├── adapters/
│   ├── postgres_customer_repo.py
│   ├── sqlite_customer_repo.py   # ← đã có sẵn vì dùng cho test
│   ├── postgres_order_repo.py
│   └── sqlite_order_repo.py
└── main.py                       # Composition root, 1 dòng wire
```

Estimate: **30 phút** — đã có sqlite adapter dùng cho test, chỉ đổi config.

→ **Cùng task. Cost khác nhau ~50×**. Đó là giá trị Hexagonal.

---

## Câu chuyện: Alistair Cockburn 1995

Cockburn đang gặp vấn đề muôn thuở:
- Test logic phải spin up DB, HTTP server, UI.
- Đổi DB = 2 tuần.
- Cùng business logic phải re-implement cho web app, mobile app, batch script.

Ông quan sát:

> "Dù I/O là DB, file, hay UI, từ góc nhìn business logic — chúng đều là **'cái gì đó bên ngoài'**. Tại sao tôi không treat chúng đồng đều?"

Ý tưởng ngớ ngẩn nhưng cách mạng: **business logic không nên BIẾT** về DB hay UI. Nó chỉ biết "có cái gì đó bên ngoài tôi gọi là `IRepository` và `IPresenter`. Tôi không quan tâm chúng là Postgres hay Mock hay Mobile UI."

Vẽ ra → hình lục giác (vì có 6 cạnh thuận tiện cho 6 loại I/O). Tên "Hexagonal" stuck. Tên kỹ thuật là **Ports & Adapters**:

- **Port**: interface (cổng cắm) ở rìa lục giác.
- **Adapter**: thực hiện cụ thể (cắm vào cổng).
- **Lục giác**: business logic ở giữa.

→ 30 năm sau, mọi clean architecture (DDD onion, Clean Architecture, Hexagonal) đều là biến thể của ý tưởng này.

---

## Vấn đề thực tế Hexagonal giải quyết

### Vấn đề 1: Test khó

```python
# Code thường thấy
def process_order(order_id: int):
    conn = psycopg2.connect("host=localhost...")
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    
    if order.total > 1000:
        # Gửi email VIP
        smtplib.SMTP("smtp.gmail.com").sendmail(...)
    
    return order
```

Test `process_order(123)` → cần:
- Postgres chạy.
- Bảng `orders` có row id=123.
- SMTP server (hoặc mock pollution).

→ **Test slow, brittle, phải có infrastructure**.

### Vấn đề 2: Đổi I/O → đổi logic

Khách yêu cầu đổi sang AWS Aurora MySQL. `psycopg2` → `pymysql`. Cursor API khác. SQL syntax khác. **Sửa khắp codebase**.

### Vấn đề 3: Cùng logic, nhiều UI

Cùng "process_order" cần chạy:
- Web app (HTTP request).
- Cron job (scheduled).
- CLI script (manual).

Mỗi UI tự re-implement logic = bug 3 chỗ khác nhau. Hoặc share code → import lẫn nhau loạn.

### Vấn đề 4: Áp dụng vào Vision Platform

Vision Platform có cùng pain points:
- **Test inference logic** không nên cần GPU thật.
- **Đổi YOLOv5 → RTMDet** không nên đụng logic stage/pipeline.
- **Cùng pipeline** chạy real-time M1 / batch M2 / desktop M3 / web M4 — không re-implement 4 lần.

→ Hexagonal là **thuốc** cho 4 pain points này.

---

## Định nghĩa chính xác

### Lục giác = 3 vòng đồng tâm

```
                 ┌─────────────────────────┐
                 │   ADAPTERS (rìa)        │  ← cv2, ZMQ, Postgres, Qt, ...
                 │                         │
                 │   ┌─────────────────┐   │
                 │   │ APPLICATION     │   │  ← Use cases, orchestration
                 │   │ (use cases)     │   │
                 │   │                 │   │
                 │   │  ┌───────────┐  │   │
                 │   │  │  DOMAIN   │  │   │  ← Pure business logic
                 │   │  │ (logic)   │  │   │
                 │   │  └───────────┘  │   │
                 │   └─────────────────┘   │
                 │                         │
                 │   PORTS (interfaces)    │
                 └─────────────────────────┘
```

3 vòng:

1. **Domain** (vòng trong cùng): pure business logic. KHÔNG biết bất cứ I/O nào.
2. **Application**: orchestrate domain + ports để giải task user-facing ("xử lý 1 order").
3. **Adapters** (rìa): I/O thật. Postgres, Qt, ZMQ, ...

**Ports** = interfaces được định nghĩa ở Application layer (hoặc Domain — tuỳ trường phái), Adapters implement.

### 2 loại port

Đây là chỗ nhiều người nhầm. Cockburn phân biệt 2 hướng I/O:

#### Driving ports (inbound, "primary")

User → driving port → app. App là **driven by** outside.

Ví dụ:
- **HTTP request** → handler (driving) → use case `ProcessOrder`.
- **Camera frame arrived** → handler (driving) → use case `ProcessFrame`.

Driving port là "**how outside calls me**". Adapter cho driving port = HTTP server, CLI parser, message consumer.

#### Driven ports (outbound, "secondary")

App → driven port → DB / external service. App **drives** outside.

Ví dụ:
- App cần lưu Order → `IOrderRepository.save(order)` (driven port) → Postgres adapter.
- App cần phát hiện vật thể → `IDetector.detect(frame)` (driven port) → YOLO adapter.

Driven port là "**what I need from outside**". Adapter cho driven port = DB driver, HTTP client, ML library wrapper.

### Sao quan trọng phân biệt?

- **Driving**: app **không khởi tạo**. Adapter (HTTP server, message consumer) khởi tạo và CALL vào app.
- **Driven**: app **khởi tạo bằng dependency injection**. App holds reference, calls adapter.

→ Direction phụ thuộc khác nhau. Nhầm 2 loại = mọi thứ rối.

---

## Build từ con số 0 — Currency Converter

Học bằng cách build. Bạn sẽ tạo 1 dự án mini "currency converter" áp dụng Hexagonal **trước khi** áp vào CV.

### Spec

- App nhận input (amount, from_currency, to_currency).
- Trả ra: amount đã đổi.
- Cần 1 nguồn rate ngoài (giả sử lấy từ API).
- Phải log mỗi conversion.

Đơn giản. Build với Hexagonal.

### Step 1: Domain

```python
# currency_demo/domain/money.py
"""Pure business logic. Không biết về API/DB/log."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("amount must be non-negative")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError("currency must be 3 uppercase letters (ISO 4217)")


@dataclass(frozen=True)
class ExchangeRate:
    """1 from_currency = `rate` to_currency."""
    from_currency: str
    to_currency: str
    rate: Decimal

    def convert(self, money: Money) -> Money:
        if money.currency != self.from_currency:
            raise ValueError(
                f"Rate is {self.from_currency}→{self.to_currency}, "
                f"got money in {money.currency}"
            )
        return Money(
            amount=money.amount * self.rate,
            currency=self.to_currency,
        )
```

**Quan trọng**: file này KHÔNG `import requests`, KHÔNG `import psycopg2`, KHÔNG `import logging`. Pure logic. Test bằng `Money(Decimal("100"), "USD")` — không cần infrastructure.

### Step 2: Driven port

App cần **lấy rate từ đâu đó**. Ai đâu đó? App không quan tâm — nhưng cần định nghĩa interface:

```python
# currency_demo/ports/exchange_rate_provider.py
"""Driven port: app cần dữ liệu từ outside."""
from typing import Protocol
from currency_demo.domain.money import ExchangeRate


class IExchangeRateProvider(Protocol):
    def get_rate(self, from_currency: str, to_currency: str) -> ExchangeRate:
        """Trả về tỷ giá hiện tại. Raise nếu currency không hỗ trợ."""
        ...
```

Cũng cần port để **log conversion** (vì log là I/O):

```python
# currency_demo/ports/conversion_logger.py
from typing import Protocol
from currency_demo.domain.money import Money


class IConversionLogger(Protocol):
    def log_conversion(self, source: Money, result: Money) -> None: ...
```

### Step 3: Application — use case

```python
# currency_demo/application/convert_currency.py
"""Use case: orchestrate domain + driven ports."""
from currency_demo.domain.money import Money
from currency_demo.ports.exchange_rate_provider import IExchangeRateProvider
from currency_demo.ports.conversion_logger import IConversionLogger


class ConvertCurrencyUseCase:
    def __init__(
        self,
        rate_provider: IExchangeRateProvider,
        logger: IConversionLogger,
    ):
        self._rate_provider = rate_provider
        self._logger = logger

    def execute(self, source: Money, to_currency: str) -> Money:
        # Cùng currency → trả luôn, không gọi API.
        if source.currency == to_currency:
            return source

        rate = self._rate_provider.get_rate(source.currency, to_currency)
        result = rate.convert(source)

        self._logger.log_conversion(source, result)
        return result
```

Use case **không** import `requests` hay `logging`. Chỉ port. Bạn có thể test bằng cách inject mock vào constructor.

### Step 4: Adapters

Bây giờ implement port với cụ thể tech.

```python
# currency_demo/adapters/api_rate_provider.py
"""Driven adapter: gọi external API (ECB)."""
import requests
from decimal import Decimal
from currency_demo.domain.money import ExchangeRate


class ECBRateProvider:
    """Implements IExchangeRateProvider via European Central Bank API."""
    def __init__(self, api_url: str = "https://api.exchangerate.host/latest"):
        self._api_url = api_url

    def get_rate(self, from_currency: str, to_currency: str) -> ExchangeRate:
        resp = requests.get(
            self._api_url,
            params={"base": from_currency, "symbols": to_currency},
            timeout=5,
        )
        resp.raise_for_status()
        rate_value = Decimal(str(resp.json()["rates"][to_currency]))
        return ExchangeRate(from_currency, to_currency, rate_value)


# currency_demo/adapters/fixed_rate_provider.py
"""Driven adapter: hardcoded rates (cho test/dev offline)."""
from decimal import Decimal
from currency_demo.domain.money import ExchangeRate


class FixedRateProvider:
    """Implements IExchangeRateProvider with hardcoded rates."""
    def __init__(self, rates: dict[tuple[str, str], Decimal]):
        self._rates = rates

    def get_rate(self, from_currency: str, to_currency: str) -> ExchangeRate:
        key = (from_currency, to_currency)
        if key not in self._rates:
            raise ValueError(f"No fixed rate for {key}")
        return ExchangeRate(from_currency, to_currency, self._rates[key])
```

```python
# currency_demo/adapters/stdout_logger.py
"""Driven adapter: log ra stdout."""
import sys
from currency_demo.domain.money import Money


class StdoutLogger:
    """Implements IConversionLogger to stdout."""
    def log_conversion(self, source: Money, result: Money) -> None:
        print(
            f"[CONVERT] {source.amount} {source.currency} "
            f"→ {result.amount} {result.currency}",
            file=sys.stderr,
        )


# currency_demo/adapters/file_logger.py
from pathlib import Path
from currency_demo.domain.money import Money


class FileLogger:
    """Implements IConversionLogger to file."""
    def __init__(self, path: Path):
        self._path = path

    def log_conversion(self, source: Money, result: Money) -> None:
        with open(self._path, "a") as f:
            f.write(
                f"{source.amount}|{source.currency}|"
                f"{result.amount}|{result.currency}\n"
            )
```

### Step 5: Driving adapter (CLI)

CLI là **driving adapter** — cách user gọi vào app.

```python
# currency_demo/adapters/cli.py
"""Driving adapter: CLI."""
import argparse
from decimal import Decimal
from currency_demo.application.convert_currency import ConvertCurrencyUseCase
from currency_demo.domain.money import Money


def run_cli(use_case: ConvertCurrencyUseCase) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("amount", type=Decimal)
    parser.add_argument("from_currency", type=str.upper)
    parser.add_argument("to_currency", type=str.upper)
    args = parser.parse_args()

    source = Money(args.amount, args.from_currency)
    result = use_case.execute(source, args.to_currency)

    print(f"{result.amount} {result.currency}")
    return 0
```

### Step 6: Composition root

```python
# currency_demo/__main__.py
"""Composition root — chỗ DUY NHẤT biết cụ thể adapter nào."""
import sys
from decimal import Decimal
from pathlib import Path

from currency_demo.application.convert_currency import ConvertCurrencyUseCase
from currency_demo.adapters.api_rate_provider import ECBRateProvider
from currency_demo.adapters.fixed_rate_provider import FixedRateProvider
from currency_demo.adapters.stdout_logger import StdoutLogger
from currency_demo.adapters.file_logger import FileLogger
from currency_demo.adapters.cli import run_cli


def main():
    # Đây là chỗ DUY NHẤT chọn implementation.
    # Production:
    rate_provider = ECBRateProvider()
    logger = StdoutLogger()

    # Dev offline:
    # rate_provider = FixedRateProvider({
    #     ("USD", "VND"): Decimal("24000"),
    #     ("EUR", "USD"): Decimal("1.08"),
    # })
    # logger = FileLogger(Path("conversions.log"))

    use_case = ConvertCurrencyUseCase(rate_provider, logger)
    sys.exit(run_cli(use_case))


if __name__ == "__main__":
    main()
```

### Step 7: Test

```python
# tests/test_convert_currency.py
"""Test logic không cần API thật, không cần file thật."""
from decimal import Decimal
from currency_demo.application.convert_currency import ConvertCurrencyUseCase
from currency_demo.adapters.fixed_rate_provider import FixedRateProvider
from currency_demo.domain.money import Money


class FakeLogger:
    """Test double — capture log calls."""
    def __init__(self):
        self.logs = []
    def log_conversion(self, source, result):
        self.logs.append((source, result))


def test_convert_usd_to_vnd():
    rate_provider = FixedRateProvider({
        ("USD", "VND"): Decimal("24000"),
    })
    logger = FakeLogger()
    uc = ConvertCurrencyUseCase(rate_provider, logger)

    result = uc.execute(Money(Decimal("100"), "USD"), "VND")

    assert result.amount == Decimal("2400000")
    assert result.currency == "VND"
    assert len(logger.logs) == 1


def test_same_currency_no_call():
    """Same currency → không gọi rate provider, không log."""
    rate_provider = FixedRateProvider({})  # rỗng — sẽ raise nếu gọi
    logger = FakeLogger()
    uc = ConvertCurrencyUseCase(rate_provider, logger)

    result = uc.execute(Money(Decimal("100"), "USD"), "USD")

    assert result.amount == Decimal("100")
    assert len(logger.logs) == 0   # short-circuit, không log
```

→ Test chạy < 1ms. **Không cần Postgres, API, file system. Pure logic test.**

### Cấu trúc cuối cùng

```
currency_demo/
├── domain/
│   └── money.py                    ← Pure logic
├── ports/
│   ├── exchange_rate_provider.py   ← Driven port
│   └── conversion_logger.py        ← Driven port
├── application/
│   └── convert_currency.py         ← Use case
├── adapters/
│   ├── api_rate_provider.py        ← Driven adapter (real)
│   ├── fixed_rate_provider.py      ← Driven adapter (test/dev)
│   ├── stdout_logger.py            ← Driven adapter
│   ├── file_logger.py              ← Driven adapter
│   └── cli.py                      ← Driving adapter
└── __main__.py                     ← Composition root
```

**~150 dòng code**. Bạn vừa build hexagonal architecture đủ.

---

## Áp dụng vào Vision Platform

Cùng pattern cho dự án CV:

| Vai trò | Currency demo | Vision Platform |
|---------|---------------|-----------------|
| **Domain** | `Money`, `ExchangeRate` | `BBox`, `CoordinateSpace`, `DetectionEvent` |
| **Driven port** | `IExchangeRateProvider`, `IConversionLogger` | `IDataSource`, `IDetector`, `IEventSink`, `ITrackerFactory` |
| **Driven adapter** | `ECBRateProvider`, `FileLogger` | `CV2RTSPSource`, `YOLOAdapter`, `KafkaSink`, `ByteTracker` |
| **Application use case** | `ConvertCurrencyUseCase` | `ProcessStreamUseCase`, `BatchProcessUseCase` |
| **Driving adapter** | `cli.py` | `SupervisorApp` (M1), `QtDesktopApp` (M3), FastAPI handler (M4) |

→ **Cùng pattern, scale up**.

### Hexagonal trong file `Vision_platform_architecture_design/`

Tham khảo:
- `02-architecture/01-4-layer-package-tree.md` — package tree (3 vòng đồng tâm + adapter rìa).
- `02-architecture/02-dependency-direction.md` — mũi tên từ adapter vào core.
- `03-data-contracts/01-ports-overview.md` — bảng tất cả port.

---

## Mental model: ổ điện và phích cắm

Bạn có ổ điện trên tường (port). Nhiều thiết bị (adapter) cắm vào:
- Đèn bàn cắm vào → sáng.
- Máy sấy tóc cắm vào → khô tóc.
- Sạc điện thoại cắm vào → sạc.

**Tường KHÔNG biết** thiết bị là gì. Tường chỉ biết "điện 220V, 50Hz qua 2 cọc". Đó là **port spec**.

Mỗi thiết bị KHÔNG biết tường lấy điện từ đâu (nhà máy nhiệt điện? Năng lượng mặt trời?). Thiết bị chỉ biết "ờ tôi thấy 220V, OK tôi work".

→ **Bạn muốn đổi từ điện lưới sang pin dự phòng?** Cắm pin vào ổ. Mọi thiết bị work tiếp. Không thiết bị nào biết.

→ Đó là Hexagonal. Logic = thiết bị. I/O = nguồn điện. Port = ổ cắm.

---

## Code-along (30 phút)

Bạn vừa đọc 7 step. Giờ **code lại từ đầu**.

```bash
mkdir -p currency_demo_workspace
cd currency_demo_workspace
py -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/Mac

mkdir -p currency_demo/{domain,ports,application,adapters}
touch currency_demo/{domain,ports,application,adapters}/__init__.py
touch currency_demo/__init__.py

mkdir tests
pip install pytest requests
```

Tự gõ lại từng file ở Step 1-6. **KHÔNG copy-paste**. Lúc gõ sẽ phát hiện chỗ chưa hiểu.

Sau khi xong:

```bash
py -m currency_demo 100 USD VND
# Expected: rate hiện tại × 100, in stdout
# Log dòng [CONVERT] ... ra stderr

py -m pytest tests/
# Expected: cả 2 test pass
```

### Bài tập mở rộng (15 phút)

Implement 3 thứ MỚI:

**1. Adapter mới — `RedisCacheRateProvider`**:
- Wrap quanh `ECBRateProvider`.
- Cache rate trong Redis 1 giờ.
- Implement `IExchangeRateProvider` cùng interface.

```python
# Hint
class RedisCacheRateProvider:
    def __init__(self, inner: IExchangeRateProvider, redis_client, ttl_s=3600):
        self._inner = inner
        self._redis = redis_client
        self._ttl = ttl_s
    
    def get_rate(self, from_c, to_c) -> ExchangeRate:
        key = f"rate:{from_c}:{to_c}"
        cached = self._redis.get(key)
        if cached:
            return parse_cached(cached)
        rate = self._inner.get_rate(from_c, to_c)
        self._redis.setex(key, self._ttl, serialize(rate))
        return rate
```

→ Đây gọi là **Decorator pattern** (đã thấy ở Vision Platform: DLQDecoratorSink).

**2. Driving adapter mới — HTTP API**:

```python
# adapters/http_api.py
from fastapi import FastAPI
from currency_demo.application.convert_currency import ConvertCurrencyUseCase
from currency_demo.domain.money import Money
from decimal import Decimal


def make_app(use_case: ConvertCurrencyUseCase) -> FastAPI:
    app = FastAPI()
    
    @app.post("/convert")
    def convert(amount: float, from_c: str, to_c: str):
        result = use_case.execute(Money(Decimal(str(amount)), from_c.upper()), to_c.upper())
        return {"amount": float(result.amount), "currency": result.currency}
    
    return app
```

→ Cùng `ConvertCurrencyUseCase`, không sửa logic, thêm 1 driving adapter mới. **Cùng business logic phục vụ cả CLI lẫn HTTP.**

**3. Test với fake driven port**:

Viết 1 test verify:
- Gọi `convert(100 USD, "USD")` → KHÔNG gọi rate provider.
- Gọi `convert(100 USD, "VND")` → CÓ gọi rate provider 1 lần, log 1 lần.

(Hint: dùng `FakeLogger` đếm số call, dùng `FakeRateProvider` raise nếu bị gọi.)

→ Test pass = bạn hiểu pattern.

---

## Checkpoint (10 phút)

Mở `_my_answers.md`:

1. **Định nghĩa**: Driving port khác driven port thế nào? Cho ví dụ trong Vision Platform mỗi loại.

2. **Vẽ diagram**: hexagon của 1 use case "phát hiện vật thể trong frame, lưu event ra DB". Đánh dấu Domain, Application, Driven ports, Driving ports, Adapters.

3. **Trace code**: Khi user gọi `py -m currency_demo 100 USD VND`, **mũi tên call** đi qua những file nào, theo thứ tự nào? Ai gọi ai?

4. **Phản ví dụ**: Đoạn code sau VI PHẠM Hexagonal — tại sao?

```python
# domain/order.py
import psycopg2

class Order:
    def __init__(self, id, items):
        self.id = id; self.items = items
    
    def total(self):
        return sum(i.price for i in self.items)
    
    def save_to_db(self, conn_str: str):
        conn = psycopg2.connect(conn_str)
        conn.execute(...)
```

5. **YAGNI check**: Khi nào KHÔNG nên dùng Hexagonal?

<details>
<summary>Đáp án</summary>

1. **Driving port** = "outside calls IN to me". Adapter cho driving port = HTTP server, CLI, message consumer. **Driven port** = "I call OUT to outside". Adapter cho driven port = DB driver, HTTP client, ML wrapper.
   
   Vision Platform examples:
   - **Driving**: SupervisorApp lifecycle (driven by SIGTERM), HTTP handler (M4), Qt window event (M3).
   - **Driven**: `IDataSource` (camera tells us frames), `IDetector`, `IEventSink`, `ITrackerFactory`.

2. ```
   ┌──────────────────────────────────┐
   │  HTTP/CLI (driving adapter)      │
   │       │                          │
   │       ▼                          │
   │  ┌──────────────────────────┐    │
   │  │  ProcessFrameUseCase     │    │
   │  │  (application)           │    │
   │  │   ├── IDataSource (driven port)
   │  │   ├── IDetector (driven port)
   │  │   └── IEventSink (driven port)
   │  │                          │    │
   │  │  ┌──────────────────┐    │    │
   │  │  │ Domain: BBox,    │    │    │
   │  │  │ DetectionEvent   │    │    │
   │  │  └──────────────────┘    │    │
   │  └──────────────────────────┘    │
   │                                   │
   │  CV2 / YOLO / Postgres            │
   │  (driven adapters)                │
   └──────────────────────────────────┘
   ```

3. **Trace flow**:
   ```
   __main__.py           ← composition root, parse argv (qua argparse trong CLI)
   adapters/cli.py       ← driving adapter, gọi use_case.execute()
   application/convert_currency.py  ← use case
       ↓ gọi rate_provider.get_rate()
   adapters/api_rate_provider.py    ← driven adapter, làm HTTP call
       ↓ trả về ExchangeRate
   application/convert_currency.py  ← compute Money
       ↓ gọi logger.log_conversion()
   adapters/stdout_logger.py        ← driven adapter, print ra stderr
   adapters/cli.py       ← in result
   ```

4. **Vi phạm**: Domain `Order` import `psycopg2`. Domain không được biết về DB. Đây là **vi phạm Stable Dependencies** + **vi phạm Hexagonal layering**.
   
   **Sửa**:
   ```python
   # domain/order.py — không I/O
   class Order:
       def total(self): ...
   
   # ports/order_repo.py
   class IOrderRepository(Protocol):
       def save(self, order: Order) -> None: ...
   
   # adapters/postgres_order_repo.py
   class PostgresOrderRepo:
       def save(self, order: Order) -> None: ...   # implementation
   ```

5. **Không nên Hexagonal khi**:
   - **Throw-away script** 100 dòng — over-engineering.
   - **CLI tool đơn giản** không có business logic phức tạp.
   - **Performance critical hot path** — extra abstraction layer = virtual dispatch overhead. Nhưng Vision Platform vẫn dùng được vì virtual dispatch ~1ns vs frame budget 33ms.
   - **MVP cực sớm** — chưa biết product fit.

</details>

---

## Trade-offs

### "Hexagonal có quá nhiều file, đọc khó"

**Có** với dự án nhỏ. Nhưng:
- Khi dự án lớn, cùng business logic dùng cho 3 UI + 5 adapter = giảm code.
- Test nhanh hơn → dev cycle ngắn hơn → bù lại.
- Onboarding dev mới: clear structure → dễ tìm hơn 1 file 1500 dòng.

**Pivot point**: dự án ~500-1000 LOC trở lên đáng đầu tư Hexagonal.

### "Mọi adapter phải có port?"

**KHÔNG**. Quy tắc:

- **Có port nếu**: ≥2 implementation (real + mock test, hoặc 2 real). Hoặc cần test logic không cần infra.
- **KHÔNG cần port nếu**: 1 implementation đời đời + adapter ở leaf (ví dụ: `JsonFormatter` chỉ format string).

YAGNI: thêm port khi có lý do **hôm nay**, không "có thể cần".

### "Performance overhead?"

Virtual dispatch (gọi method qua interface) cost ~1-3ns trên Python (CPython với caching). Frame budget 33ms = 33,000,000ns. **Không đáng kể**.

Nếu hot path thật sự cần loại bỏ: dùng concrete type cho hot path, port cho boundaries. Nhưng 99% case không cần.

---

## Pitfalls (bug điển hình khi áp dụng sai)

### Pitfall 1: Domain leak qua import

```python
# domain/order.py
from sqlalchemy import Column   # ← LEAK — SQLAlchemy là infrastructure
```

**Phát hiện**: chạy `import-linter` với rule `domain forbidden imports = sqlalchemy, requests, fastapi, ...`. Vision Platform có CI rule này.

### Pitfall 2: Driving adapter pollute use case

```python
# Sai
class ProcessOrderUseCase:
    def execute(self, request: HttpRequest) -> HttpResponse:
        order = parse_order(request.body)   # ← biết về HTTP
        ...
```

Use case **không được** nhận HTTP request. Nó nhận **domain object** (Order, Money, ...). Driving adapter chịu trách nhiệm parse HTTP → domain.

```python
# Đúng
# adapters/http_handler.py
def http_handler(request: HttpRequest):
    order = parse_order(request.body)   # adapter parse
    response_data = use_case.execute(order)   # call use case với domain
    return HttpResponse(json.dumps(response_data))


# application/process_order.py
class ProcessOrderUseCase:
    def execute(self, order: Order) -> OrderResult: ...   # pure
```

### Pitfall 3: God port

```python
# Sai
class IRepository(Protocol):
    def save_user(self, u): ...
    def save_order(self, o): ...
    def save_product(self, p): ...
    def find_user(self, id): ...
    def find_order(self, id): ...
    # ... 30 method ...
```

→ Cohesion thấp. Test mock 1 method = phải implement 30. Đổi 1 method = mọi adapter đổi.

**Sửa**: tách port theo aggregate. `IUserRepo`, `IOrderRepo`, `IProductRepo` riêng.

### Pitfall 4: Composition root rải rác

```python
# Sai
# main.py
def main():
    app = create_app()

# create_app.py
def create_app():
    return FastAPI(routes=[...])

# routes.py
@app.post("/convert")
def convert():
    use_case = ConvertCurrencyUseCase(    # ← composition ở đây
        ECBRateProvider(),
        StdoutLogger(),
    )
    ...
```

→ "Wire" của adapter rải khắp. Đổi adapter = sửa nhiều chỗ.

**Sửa**: 1 file `composition_root.py` (hoặc `profiles/`). Mọi `use_case = XxxUseCase(adapter1, adapter2)` ở đó. Routes/handlers nhận `use_case` đã wire.

### Pitfall 5: Port quá generic

```python
# Sai
class IDataAccess(Protocol):
    def execute(self, query: str, params: tuple) -> Any: ...
```

→ Port nhận SQL string = port leak SQL semantics. Đổi sang NoSQL = port không match.

**Đúng**: port theo **business operation**, không theo storage detail.

```python
class IUserRepo(Protocol):
    def find_by_email(self, email: str) -> Optional[User]: ...
    def save(self, user: User) -> None: ...
```

Adapter Postgres dùng SQL bên trong. Adapter MongoDB dùng find filter. Use case không biết.

---

## Liên kết

- File 02 (`02-ports-and-adapters-build-one.md`) — code Vision Platform port + 2 adapter, có test.
- Production: `Vision_platform_architecture_design/02-architecture/01-4-layer-package-tree.md` — package tree áp dụng Hexagonal cho Vision.
- Production: `Vision_platform_architecture_design/03-data-contracts/01-ports-overview.md` — 11 port của Vision Platform.
- Sách:
  - "Hexagonal Architecture, there are always two sides to every story" — Alistair Cockburn (paper gốc 2005).
  - "Get Your Hands Dirty on Clean Architecture" — Tom Hombergs. Practical implementation.

---

## Tóm tắt 1 câu

> **Hexagonal = đặt logic ở giữa, I/O ra rìa, giao tiếp qua interface (port). Logic không biết I/O cụ thể. Driving = "outside calls in"; driven = "I call out". Composition root là chỗ duy nhất biết cụ thể adapter.**

➡️ Tiếp theo: [`02-ports-and-adapters-build-one.md`](02-ports-and-adapters-build-one.md)
