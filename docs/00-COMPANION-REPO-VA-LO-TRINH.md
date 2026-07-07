# 🧭 Companion: Repo "kho kiến thức" để HỌC · GIẢI THÍCH · TỔNG HỢP

> File này KHÔNG phải repo code dự án, cũng KHÔNG phải repo công cụ/phương pháp (xem
> `docs/00-REPO-CONG-CU-PHUONG-PHAP.md`). Đây là **repo kiến thức** để học khái niệm, được
> giải thích, và tổng hợp — phục vụ mục tiêu **hiểu sâu để TỰ VIẾT LẠI hệ thống**.
>
> *(Tái tạo 2026-06-13 từ lịch sử — bản gốc bị mất do chưa commit khi repo tái cấu trúc.)*

## 0. Ba mục đích → ba loại repo (đừng trộn)
| Mục đích | Loại repo | Cách dùng |
|----------|-----------|-----------|
| **HỌC** (hiểu sâu 1 khái niệm) | repo dạy bằng *code chạy được* | đọc 1 lát cắt → tự gõ lại → so sánh |
| **GIẢI THÍCH** (nắm "tại sao") | repo *trực quan* (diagram/prose) | đọc → tự vẽ lại sơ đồ từ trí nhớ |
| **TỔNG HỢP** (kết nối mảnh) | repo *curated/primer/roadmap* | quét bản đồ lớn → đánh dấu lỗ hổng |

> ⭐ = độ-nên-đọc theo đánh giá của tôi, KHÔNG phải sao GitHub.

## 1. Catalog (nhóm theo mục đích)

### NHÓM A — TỔNG HỢP: bản đồ lớn để không "học mù"
- ⭐⭐⭐⭐⭐ [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) —
  Donne Martin (ex-Google/Apple/Amazon). System design + **Anki flashcard** (hợp nhu cầu nhớ lâu).
- ⭐⭐⭐⭐⭐ [ByteByteGoHq/system-design-101](https://github.com/ByteByteGoHq/system-design-101) —
  Alex Xu. Giải thích khái niệm khó bằng **diagram một trang**.
- ⭐⭐⭐⭐ [kamranahmedse/developer-roadmap](https://github.com/kamranahmedse/developer-roadmap) —
  bản đồ kỹ năng → định vị mình đang ở đâu, còn thiếu gì.

### NHÓM B — HỌC SÂU bằng code (đúng "tự xây lại từng dòng")
- ⭐⭐⭐⭐⭐ [cosmicpython/code](https://github.com/cosmicpython/code) (+ sách free cosmicpython.com) —
  Harry Percival & Bob Gregory. **#1 kiến trúc Python**: ports/adapters, repository, DI. Khớp Module 01–02.
- ⭐⭐⭐⭐⭐ [faif/python-patterns](https://github.com/faif/python-patterns) — design pattern,
  mỗi cái **1 file ngắn chạy được** → gõ lại từ trí nhớ.
- ⭐⭐⭐⭐⭐ [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) —
  xây lại công cụ (db, git, shell...) từ số 0. Khớp 100% triết lý tự-viết-lại.
- ⭐⭐⭐⭐ [pingcap/talent-plan](https://github.com/pingcap/talent-plan) — PingCAP (TiDB).
  Distributed systems **hands-on** (mini KV store, Raft). Hợp Module 04.

### NHÓM C — GIẢI THÍCH gốc rễ (chiều sâu)
- ⭐⭐⭐⭐ [papers-we-love/papers-we-love](https://github.com/papers-we-love/papers-we-love) —
  đọc chính các paper nền tảng (đã chọn lọc).
- ⭐⭐⭐⭐ [aphyr/distsys-class](https://github.com/aphyr/distsys-class) — Kyle Kingsbury (Jepsen).
  Vì sao "mạng không tin cậy" đổi mọi quyết định. Nền cho Module 04/07.
- ⭐⭐⭐⭐ *Patterns of Distributed Systems* — Unmesh Joshi (ThoughtWorks, martinfowler.com).
  Catalog pattern phân tán (WAL, Leader-Follower, Heartbeat, Quorum...).

### NHÓM D — TỔNG HỢP nghề nghiệp
- ⭐⭐⭐⭐⭐ [charlax/professional-programming](https://github.com/charlax/professional-programming) —
  kho curated tư duy kỹ sư trưởng thành (design, debugging, trade-off).
- ⭐⭐⭐⭐ [ossu/computer-science](https://github.com/ossu/computer-science) — giáo trình CS đầy đủ,
  để vá lỗ hổng nền (OS/network/concurrency) khi cần.

## 2. Lộ trình ghép repo vào module (đừng đọc song song hết)
| Giai đoạn | Học (Design/) | Repo ghép | Mục đích |
|-----------|---------------|-----------|----------|
| Khởi động | trước Module 01 | developer-roadmap | TỔNG HỢP: vạch lỗ hổng |
| Tuần 1–2 | Module 01–02 | cosmicpython + python-patterns | HỌC sâu bằng code |
| Tuần 3–6 | Module 03 | python-patterns (tra) + build-your-own-x | HỌC qua xây lại |
| Khi cần "tại sao" | Module 02/04 | system-design-primer + 101 | GIẢI THÍCH trực quan |
| Tuần 9–12 | Module 04 | papers-we-love + distsys-class + Patterns of Distributed Systems | GIẢI THÍCH gốc rễ |
| Hands-on phân tán | sau Module 04 | pingcap/talent-plan | HỌC distributed bằng code |
| Xuyên suốt | mọi module | professional-programming, ossu/cs | TỔNG HỢP + vá nền |

> Quy tắc: **một khái niệm → một lát cắt repo → một bài ép-nghĩ → ghi knowledge-base.**

## 3. Checklist "đã hiểu thật chưa?" (mỗi khái niệm)
- [ ] Gọi tên + vấn đề nó giải quyết (HỌC lớp 1).
- [ ] Tự viết lại bản tối giản từ trí nhớ (HỌC lớp 2).
- [ ] Nói được trade-off + khi nào KHÔNG nên dùng (HỌC lớp 3).
- [ ] Giải thích cho người mới bằng 3 câu không thuật ngữ (TỔNG HỢP — Feynman).
- [ ] Chỉ được 1 repo thật trình bày nó + khác cách hiểu của tôi ở đâu.

Đủ 5 tick = khái niệm thành **intuition**, không còn là kiến thức mượn.
