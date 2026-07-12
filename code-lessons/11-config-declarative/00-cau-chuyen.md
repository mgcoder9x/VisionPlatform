# 11 — Config khai báo (declarative TOML) — CÂU CHUYỆN (vòng cung dạy)

> Bám code THẬT (đã đọc): `kernel/config.py` · `application/config_loader.py` · `profiles/pipeline_factory.py`
> · `profiles/vision_slice_app.py`. Quote nguyên văn ở các mẩu `01-*.md`+ (xem `00-muc-luc.md`).
> Người học: đã qua #01–#04 (layer, DTO, port/adapter, pipeline). Thuật ngữ lạ → link `knowledge-base/00-GLOSSARY.md`.

---

## Nhịp 1 — Tổng quan (thứ này nằm ĐÂU, phục vụ GÌ)

Hệ chạy nhiều **pipeline** (mỗi pipeline = 1 camera: nguồn frame → các stage xử lý → nơi lưu kết quả).
"Config khai báo" = **mô tả các pipeline đó bằng 1 file văn bản `.toml`** thay vì viết code Python dựng tay.

Vị trí trong 6 layer (mỗi mảnh 1 tầng — đây là điểm mấu chốt của bài):

```
   file cam.toml
        │  (đọc)
        ▼
  application/config_loader.py   ── parse + validate CẤU TRÚC ──►  kernel/config.py (DTO bất biến)
        │                                                              (AppConfig / PipelineConfig / ...)
        ▼  (AppConfig)
  profiles/pipeline_factory.py   ── registry: "type"(chuỗi) → hàm dựng object ──►  PipelineRunner sẵn chạy
        ▲
  profiles/vision_slice_app.py   ── entry: đọc file → build → run
```

Một câu: **file TOML → `AppConfig` (DTO) → `build_runner` dựng `PipelineRunner`**. Ba tầng, ba trách nhiệm tách bạch.

---

## Nhịp 2 — VẤN ĐỀ & tại sao nó là vấn đề (Forces — cho thấy *đau* trước)

Tình huống thật: khách có **100 camera**, mỗi cái khác nhau (URL RTSP khác, camera này cần đếm-qua-vạch,
camera kia chỉ phát hiện, ngưỡng khác nhau...). Mai lại thêm 10 camera, đổi vạch đếm 5 camera.

**Cách ngây thơ (naive):** viết code Python cho từng deploy —
```python
src = RtspFrameSource("rtsp://..."); stages = [DetectStage(...), CountStage(), ...]  # sửa tay mỗi lần
```
→ Đau ở đâu?
- **Đổi camera = sửa code + build lại + test lại + deploy lại** → chậm, dễ sinh bug ở bước build.
- Người **vận hành (ops)** chỉ muốn đổi URL/ngưỡng nhưng lại phải biết Python + đụng vào mã nguồn (nguy hiểm).
- 100 camera = 100 khối code gần-giống-nhau (copy-paste) → **phân kỳ** (sửa 1 chỗ quên chỗ khác).

**Các lực giằng nhau (forces):**
- *Linh hoạt* (đổi cấu hình nhanh, không rebuild) ↔ *An toàn* (đổi sai không được làm sập / không được chạy code tuỳ ý).
- *Ai đổi* (ops, không phải dev) ↔ *Ai viết logic* (dev). Ranh giới phải rõ.
- *Dễ đọc/ghi bằng tay* ↔ *Kiểm được máy* (bắt lỗi typo trước khi chạy thật).

> ✋ Đoán thử: nếu cho ops sửa 1 file để đổi camera, **định dạng file nào** vừa người-đọc-được vừa
> máy-parse-được vừa KHÔNG cho nhét code tuỳ ý (khác Python)? (đáp ở nhịp 4)

---

## Nhịp 3 — Khám phá NHIỀU hướng (≥2 cách, ưu/nhược)

**Hướng A — sửa code mỗi deploy** (naive ở trên). Ưu: đơn giản lúc đầu. Nhược: mọi nỗi đau nhịp 2. → LOẠI khi >vài camera.

**Hướng B — config bằng chính Python** (`config.py` chứa dict/list Python, `if` chọn nhánh). Ưu: không cần parser.
Nhược: (a) ops vẫn phải sửa file `.py` (chạy được code tuỳ ý → rủi ro bảo mật + dễ vỡ cú pháp); (b) trộn
*dữ liệu cấu hình* với *code logic* → khó kiểm, khó khoá quyền. → LOẠI (nhập nhèm ranh giới data↔code).

**Hướng C — file khai báo THUẦN DỮ LIỆU (JSON/YAML/TOML) + "registry"** (bảng tra `tên → hàm dựng`). Ưu:
- File chỉ là *dữ liệu* (không chạy code) → an toàn + ops sửa được không cần biết Python.
- Đổi camera = sửa file, KHÔNG build lại.
- Máy validate được (bắt typo/thiếu field trước khi chạy).
Nhược: cần viết parser + validate + registry (công một lần, dùng mãi). → **CHỌN.**

*Vì sao TOML (không JSON/YAML)?* TOML đọc/ghi bằng tay dễ (giống `.ini`), có kiểu rõ ràng, và Python 3.11+
có sẵn `tomllib` trong thư viện chuẩn → **KHÔNG thêm dependency**. YAML mạnh nhưng cú pháp thụt-lề dễ sai +
cần lib ngoài; JSON không cho comment (config cần comment giải thích). [độ chắc: cao — `tomllib` là stdlib 3.11, xem `config_loader.py` import].

---

## Nhịp 4 — CHỐT giải pháp + tại sao nó thắng

**Giải pháp:** file `.toml` khai báo → **DTO bất biến** (`kernel/config.py`) → **registry** ánh xạ `type`(chuỗi)
→ hàm dựng object (`profiles/pipeline_factory.py`). Ba tầng tách bạch:

1. **`kernel/config.py`** — *hình dạng* của config: các `@dataclass(frozen=True)` (`AppConfig`, `PipelineConfig`,
   `SourceConfig`, `StageConfig`, `SinkConfig`, `DetectorConfig`, `ObservabilityConfig`). **Bất biến** → parse
   xong không ai sửa lén được (params bọc `MappingProxyType`, list → `tuple`). KHÔNG đọc file, KHÔNG biết adapter.
2. **`application/config_loader.py`** — đọc TOML (`tomllib`) + validate **CẤU TRÚC** (field bắt buộc, id duy
   nhất, type là chuỗi không rỗng). **KHÔNG** biết `type` nào hợp lệ (đó là việc tầng dưới) → giữ tầng application
   không phụ thuộc adapter (đúng ranh giới import-linter).
3. **`profiles/pipeline_factory.py`** — **registry** `{"sources": {"rtsp": _src_rtsp, ...}, "stages": {...}, ...}`:
   tra `type` → gọi hàm builder dựng adapter thật. Ở tầng `profiles` (composition root) vì nó ĐƯỢC phép import
   adapter. `build_runner(pcfg)` → `PipelineRunner` sẵn chạy.

**Vì sao thắng (trade-off):**
- Tách *dữ liệu* (TOML) khỏi *cách dựng* (registry) khỏi *hình dạng* (DTO) → mỗi thứ 1 tầng, đổi độc lập.
- **Thêm loại mới = đăng ký 1 entry vào registry**, KHÔNG sửa lõi (mở-rộng-không-sửa — Open/Closed).
- An toàn: file chỉ là dữ liệu; validate fail-fast báo lỗi RÕ (kèm id pipeline) trước khi chạy.
- Đây cũng là lý do **F1 (#324)** hợp nhất được đường CLI vào đây: CLI chỉ cần *sinh ra `PipelineConfig`* rồi
  gọi cùng `build_runner` → 1 nguồn lắp-ráp duy nhất (xem mẩu `07-*`).

---

## Nhịp 5 — Dạy TRIỂN KHAI (vào code thật — qua các mẩu nhỏ nhất)

Chi tiết từng-dòng ở các file mẩu (`00-muc-luc.md`): DTO frozen + `MappingProxyType` → `_typed`/`_require`
validate cấu trúc → `_parse_observability` (chặn bool-lọt-int) → registry + `allowed_params` (chặn typo) →
`_lookup`/`_check_params` → `validate_config` (dry-run no-GPU) vs `build_runner` (dựng thật) → lazy-import →
F1: `_args_to_pipeline_config` (CLI → cùng đường).

---

## Nhịp 6 — NÊN LÀM / NÊN TRÁNH

**Nên:**
- Fail-fast + thông điệp kèm *vị trí* (`pipelines[2].source.type`, id pipeline) → ops sửa được ngay.
- Validate **kiểu tường minh** (vd `metrics_port` phải int, chặn `bool` lọt vì `isinstance(True,int)==True`).
- **Typo-guard** (`allowed_params`): key lạ trong params → báo lỗi, KHÔNG nuốt im lặng (K-046).
- **Lazy-import** trong builder → nạp registry KHÔNG kéo dep nặng (torch/cv2) khi chưa dùng.
- Giữ ranh giới: DTO@kernel · parse@application · registry@profiles.

**Tránh:**
- Đặt *logic* trong file config (biến nó thành code) → mất an toàn + khó kiểm.
- Cho `config_loader` (application) biết registry/adapter → phá ranh giới import-linter.
- Validate lỏng (nuốt typo) → config sai chạy tới runtime mới nổ (khó truy).

---

## Tự kiểm (retrieval — trả lời bằng lời mình trước khi qua mẩu)
1. Vì sao chia làm 3 tầng (config.py / config_loader.py / pipeline_factory.py) thay vì gộp 1 file?
2. "Registry" giải quyết nỗi đau gì? Thêm 1 loại sink mới thì đụng vào đâu, KHÔNG đụng vào đâu?
3. Nếu `config_loader` (application) import adapter để kiểm `type` hợp lệ thì vi phạm gì?
4. Vì sao TOML + `tomllib` chứ không YAML?

**Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.
**Nguồn:** code thật (4 file trên) · quyết định D-042 (config schema) · D-088/F1 (#324, hợp nhất đường lắp-ráp) · `docs/ARCHITECTURE.md` §7.
