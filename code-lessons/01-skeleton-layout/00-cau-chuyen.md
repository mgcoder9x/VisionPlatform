# Bài #01 — Bộ khung & cách sắp xếp dự án (Skeleton & Layout) · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đây là file "vòng cung" (đọc TRƯỚC các mẩu chi tiết). Mục tiêu: hiểu **tại sao** dự án lại sắp xếp
> như vậy, trước khi xem từng dòng. Bám code thật ở `vision-platform/`.

---

## 1. Tổng quan — ta đang ở đâu
`vision-platform/` là một **dự án Python thật** xử lý hình ảnh từ camera. Vấn đề #01 mới chỉ dựng
**bộ khung rỗng** (thư mục + file lý lịch), CHƯA có logic. Sơ đồ thư mục thật (rút gọn):

```
vision-platform/
├── pyproject.toml          ← "lý lịch" dự án (tên, thư viện cần, luật)
└── src/
    └── vision_platform/    ← package code chính
        ├── domain/         ┐
        ├── kernel/         │  6 "tầng" (layer) — sẽ giải thích
        ├── runtime/        │
        ├── application/    │
        ├── adapters/       │
        └── profiles/       ┘
```
> Thuật ngữ: [pyproject.toml](../../knowledge-base/00-GLOSSARY.md#pyprojecttoml) ·
> [src layout](../../knowledge-base/00-GLOSSARY.md#src-layout) · [package](../../knowledge-base/00-GLOSSARY.md#package-thư-viện--library).

**6 thư mục đó làm gì (lướt nhanh 1 dòng/cái — đào sâu ở mẩu 05):**
| Thư mục | Làm gì (lời thường) | File thật đã có |
|---|---|---|
| `domain` | logic/giá trị thuần, KHÔNG đụng camera/mạng | `domain/bbox.py` |
| `kernel` | "hợp đồng": gói dữ liệu (DTO) + **cổng** (port) | `kernel/read_result.py`, `media_packet.py`, `ports/frame_source.py` |
| `runtime` | bộ máy chạy pipeline + các bước xử lý (stage) | `runtime/sync_linear_executor.py`, `stages/*` |
| `application` | điều phối/use-case — **hiện rỗng**, Supervisor ở #09 | (chỉ `__init__.py`) |
| `adapters` | bản cài CỤ THỂ nối thế giới ngoài (ở "rìa") | `adapters/fake_frame_source.py` |
| `profiles` | "bàn ráp" duy nhất nối mọi thứ + chọn adapter | `profiles/demo_pipeline.py` |

**Hướng phụ thuộc:** `domain ← kernel ← runtime ← application`; `adapters → kernel`; `profiles → mọi thứ`.

> 📌 **Lưu ý đọc bảng (Codex P2-1):** cột "File thật đã có" ở trên là **snapshot HIỆN TẠI** (sau khi đã build #01→#04+).
> Ở thời điểm #01 ban đầu, các folder mới chỉ có `__init__.py` rỗng — các file `bbox.py`/`sync_linear_executor.py`/
> `demo_pipeline.py` xuất hiện ở các vấn đề #02/#04. Bài #01 chỉ dạy phần **bộ khung**.
**Lõi ứng dụng = CẢ 4 tầng** `domain`/`kernel`/`runtime`/`application` — cả 4 KHÔNG biết `adapters`/`profiles`
(ở "rìa"). Đừng hiểu nhầm chỉ domain/kernel mới là lõi: import-linter cấm `runtime`/`application` import
adapters/profiles (mẩu 06). (pyproject ghi "4-layer Hexagonal + adapters/profiles ở rim" → 4 tầng lõi
xếp hướng phụ thuộc + 2 thư mục rìa = 6; luật repo gọi gọn "6 layer".)

## 2. Vấn đề & TẠI SAO nó là vấn đề
Một hệ camera thật có nhiều việc: **đọc** frame từ camera → **xử lý** → **suy luận** (AI) → **gửi**
kết quả. Nếu nhét tất cả vào một đống file lẫn lộn:
- Sửa 1 chỗ (vd đổi loại camera) → **vỡ lan** sang chỗ khác (logic dính chặt I/O).
- **Khó test**: muốn test phần tính toán lại bị kéo theo camera/mạng thật.
- **Khó đổi**: đổi camera/đổi cách gửi → phải đụng vào tận lõi nghiệp vụ.

**Các lực giằng nhau (forces):** muốn *viết nhanh lúc đầu* ↔ muốn *bền/đổi-được/test-được về sau*.
→ Chính sự "dính nhau" (coupling) là gốc của mọi đau. (Đoán thử: theo bạn nên tách theo cái gì?)

## 3. Khám phá nhiều hướng (≥2 cách)
- **Cách A — Flat (mọi file 1 chỗ):** nhanh lúc đầu, nhưng lớn lên là rối, không chặn được dính nhau. ✗
- **Cách B — Chia theo TÍNH NĂNG** (folder cho mỗi feature): đỡ hơn, nhưng vẫn dễ để lõi nghiệp vụ
  lỡ gọi thẳng camera/mạng → vẫn dính. △
- **Cách C — Chia theo TẦNG + ép HƯỚNG PHỤ THUỘC** (Hexagonal/6 layer): lõi (domain/kernel) KHÔNG
  được biết tới I/O cụ thể; cái hay-đổi (camera, mạng) nằm ở rìa (adapters). ✓ ← **chọn cách này**.

## 4. Chốt giải pháp + TẠI SAO thắng
Dùng **src layout + 6 layer + ép bằng công cụ**:
- `pyproject.toml`: khai báo dự án + thư viện + **luật import 6 layer** cho `import-linter`.
- `src/vision_platform/<layer>/`: tách lõi khỏi rìa.
- `import-linter`: **trọng tài tự động** chặn "tầng lõi lỡ import tầng rìa" — sai là báo đỏ ngay.

Thắng vì: nó **vật lý hóa** nguyên tắc *"cái ổn định không phụ thuộc cái hay đổi"* — không chỉ nhắc
miệng mà máy ép. (2 câu hỏi gốc của mọi kiến trúc: *cái gì hay đổi?* + *mũi tên phụ thuộc chỉ hướng nào?*)
> Học sâu pattern này: (sẽ tạo) `knowledge-base/hexagonal-architecture/`.

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự (mỗi mẩu 1 file, nhỏ nhất): xem `00-muc-luc.md`.
1. `01-package-va-init.md` — package & `__init__.py` là gì.
2. (kế tiếp) `pyproject.toml` từng phần · `src layout` · 6 layer · `import-linter` · venv + `pip install -e`.

## 6. Nên làm / Nên tránh (cho bài #01)
- **NÊN:** đặt code trong `src/` (tránh import nhầm); mỗi tầng 1 thư mục; chạy `lint-imports` sau mỗi thay đổi.
- **TRÁNH:** để lõi `domain/`, `kernel/` import `cv2/torch/zmq/multiprocessing` hay tầng ngoài — đó là vi phạm hướng phụ thuộc.
- **Cạm bẫy (ERRATA E-9):** contract import-linter có module ngoài thì pyproject PHẢI có `include_external_packages = true`, không là `lint-imports` lỗi config.

## Tự kiểm (đạt mới qua bài)
- Nói bằng lời mình: vì sao chia theo TẦNG tốt hơn để chung 1 đống? "Hướng phụ thuộc" nghĩa là gì?
- `import-linter` đóng vai gì trong việc giữ kiến trúc?

## Nguồn
- Code thật: `vision-platform/pyproject.toml`, `vision-platform/src/vision_platform/` (đã đọc). ·
  Design: `Design/module-03-build-along/step-01-project-skeleton.md` + `Design/reference-cards/folder-structure-blueprint.md`. · Độ chắc: cao.
