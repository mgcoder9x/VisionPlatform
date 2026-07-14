# Design Document — Drift-Check C9: Git-Reality Reconciliation Gate

> **Trạng thái:** PHA 1 — Design-first; CHƯA code. Chờ user đọc-lại-valid.
> **Nguồn:** đọc `tests/drift_check.py` + `tests/test_memory_consistency.py` (C1–C8 + self_test) + `tests/test_rules_sync.py`; lịch sử sự cố drift K-064 (#269), K-085 (#356), K-098 (#373).
> **Cập nhật:** 2026-07-14.

## Overview
Hệ chống-drift hiện tại (C1–C8 + RULES sync + self-test) rất mạnh nhưng đối chiếu **bản-ghi ↔ bản-ghi** (C1–C7) hoặc **bản-ghi ↔ symbol-code** (C8). Không lớp nào đối chiếu **bản-ghi ↔ THỰC TẾ GIT**. Cả ba sự cố drift THẬT trong lịch sử repo (K-064/K-085/K-098) đều thuộc lớp "resume trên nền git stale/diverged" — lớp DUY NHẤT còn thoát máy-kiểm.

Mục tiêu C9: biến bước "đối chiếu git bằng tay" trong luật văn xuôi §0 (dễ quên → đã gây 3 sự cố) thành **cổng máy-kiểm khách quan**, nhưng **không tạo false-positive** trong lúc chỉnh sửa bình thường giữa turn.

Đây là **freshness-vs-git**, KHÔNG phải "đồng bộ nội dung với remote" (cần network) và KHÔNG kiểm số-liệu-test (cần chạy test). Ranh giới hẹp và trung thực.

### Nguyên tắc thiết kế (giữ tính chất đã có của checker)
- **Thuần + tiêm được:** C1–C8 là hàm thuần (text vào → kết quả ra) nên `self_test` tiêm text giả, xác định, không đọc file. C9 cần dữ-liệu-git = KHÔNG thuần. Giải: C9 nhận tham số **`git_facts` (dict) tiêm được**, mặc định `None` → gọi collector thật `_collect_git_facts()` (subprocess read-only). `self_test` tiêm `git_facts` giả → vẫn thuần/xác định. Đây là ĐÚNG pattern đã dùng cho C8 (`symbol_exists` tiêm được).
- **Read-only, offline, zero side-effect:** chỉ đọc trạng thái git đã có cục bộ (`git rev-parse`, `git rev-list --left-right --count`). **KHÔNG `git fetch`/pull/network** trong check (tránh chậm + side-effect + treo khi offline). Giới hạn này ghi rõ (xem Trade-offs).
- **Fail HẸP:** chỉ FAIL trên điều kiện nguy hiểm CHỨNG MINH ĐƯỢC (local behind upstream). Mọi thứ khác = thông tin, KHÔNG fail (chống false-positive giết niềm tin vào checker — checker mà kêu oan sẽ bị phớt lờ = tệ hơn không có).

## Architecture
```text
drift_check.py (entry point)
  ├── [1/3] memory consistency  C1..C8   (bản-ghi↔bản-ghi + bản-ghi↔code)
  │         + C9 git-reality  <── THÊM   (bản-ghi↔git, qua git_facts tiêm-được)
  ├── [2/3] RULES_VERSION sync
  └── [3/3] self_test (guard-the-guard)  + case C9 (baseline + catch-behind)
```
C9 sống TRONG `test_memory_consistency.check()` (cùng chỗ C1–C8) để dùng chung report + self_test. Collector `_collect_git_facts()` là hàm riêng (I/O), tách khỏi logic thuần.

## Components and Interfaces
### 1. `_collect_git_facts() -> dict` (I/O, KHÔNG thuần)
Chạy các lệnh git read-only (subprocess argv-list, cwd=ROOT, timeout ngắn — argv KHÔNG qua shell nên `@{upstream}` an toàn), trả dict.

**Lệnh chính xác (ĐÃ VERIFY empiric trên repo này 2026-07-14, LOG #380):**
- `git rev-parse --short HEAD` → `head` (vd `2496e2c`).
- `git rev-parse --abbrev-ref HEAD` → `branch` (vd `chore/dev-env-launcher-portable-hooks`).
- `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` → nếu exit≠0 ⇒ `has_upstream=False` (nhánh chưa track → SKIP-PASS).
- `git rev-list --left-right --count @{upstream}...HEAD` (BA chấm) → in `"<behind>\t<ahead>"` (**left = behind = commit chỉ có ở upstream; right = ahead = chỉ có ở HEAD**). Verify: repo đồng bộ → `0\t0`.
  - ⚠️ **Đính chính so với draft V1:** V1 ghi `behind = git rev-list --count @{upstream}..HEAD` là SAI HƯỚNG (lệnh đó đếm *ahead*). Bắt được nhờ probe empiric → chốt dùng `--left-right ...` (một lệnh, hai số, không lẫn hướng).

Trả dict:
```
{
  "available": bool,        # git có tồn tại + đây là repo git không
  "head": str,              # HEAD short SHA ('' nếu không)
  "branch": str,            # tên nhánh hiện tại
  "has_upstream": bool,     # có @{upstream} không
  "behind": int,            # số commit local ĐANG SAU upstream (0 nếu không/không có upstream)
  "ahead": int,             # số commit local vượt upstream (thông tin)
  "error": str | None,      # lý do nếu không thu được (git thiếu / không phải repo / timeout)
}
```
Nếu git thiếu / không phải repo / lệnh lỗi → `available=False` + `error` → C9 **SKIP (PASS)** với ghi chú (không chặn máy không có git; ví dụ CI checkout nông có thể thiếu upstream — không được kêu oan).

### 2. `check(..., git_facts=None)` — thêm nhánh C9
- `git_facts is None` → gọi `_collect_git_facts()` (hành vi thật). Có tham số → dùng dict tiêm (self_test).
- Logic C9 (thuần trên dict):
  - `available=False` hoặc `has_upstream=False` → PASS + note "C9 SKIP: <lý do>" (không đủ dữ liệu để kết luận stale → KHÔNG fail).
  - `behind > 0` → **FAIL** "C9-GIT-STALE: local sau upstream N commit — GIT PULL/FETCH + reconcile TRƯỚC khi làm (chống resume nền stale, K-098)".
  - `behind == 0` → PASS, note `ahead`/`head`/`branch` (thông tin để người đọc thấy trạng thái).

## Data Models
`git_facts` dict (ở trên) là hợp đồng DUY NHẤT giữa collector (I/O) và logic (thuần). Mọi field là kiểu cơ bản (bool/int/str) để tiêm/serialize dễ + self_test xác định.

## Error Handling
- Git vắng / không phải repo git / subprocess lỗi / timeout → `available=False`, C9 SKIP-PASS (fail-safe: không chặn công việc vì hạ tầng thiếu git; C1–C8 vẫn chạy). Ghi rõ lý do trong report để không "im lặng bỏ qua".
- `@{upstream}` chưa set (nhánh local mới, chưa track) → `has_upstream=False` → SKIP-PASS (không có mốc so sánh → không kết luận).
- Subprocess: dùng timeout (vd 5s) + bắt mọi exception → không bao giờ làm sập drift_check vì lỗi git.

## Correctness Properties
### Property 1: Fail đúng điều kiện stale
Khi `git_facts.available=True` và `has_upstream=True` và `behind>0` thì và chỉ thì C9 FAIL; mọi trường hợp khác C9 không FAIL.
**Validates: Requirements 1.1**

### Property 2: Fail-safe khi thiếu dữ liệu git
Khi `available=False` hoặc `has_upstream=False`, C9 PASS (SKIP) + ghi lý do; KHÔNG chặn C1–C8 và KHÔNG làm sập checker.
**Validates: Requirements 1.2**

### Property 3: Thuần + tiêm được (không phá self_test)
`check()` gọi không tham số `git_facts` → hành vi cũ (collector thật). Có `git_facts` tiêm → C9 quyết định CHỈ dựa dict, không đọc git thật → self_test xác định, không I/O, không flake.
**Validates: Requirements 2.1**

### Property 4: Không side-effect
C9/collector không ghi file, không network, không đổi trạng thái git (chỉ đọc). Chạy nhiều lần cho cùng kết quả (idempotent) nếu git state không đổi.
**Validates: Requirements 2.2**

### Property 5: Self-test bao phủ C9 (guard-the-guard)
`self_test` có case baseline-clean (behind=0 → PASS) và case catch-stale (behind>0 → phải thấy FAIL tag `C9-GIT-STALE`) — chứng minh C9 thực sự BẮT được drift, chống regex-rot như C1–C8.
**Validates: Requirements 2.3**

## Testing Strategy
- `self_test` thêm: (a) `git_facts` available+upstream+behind=0 → toàn bộ PASS; (b) behind=3 → `_fail(r,"C9-GIT-STALE")` True; (c) available=False → C9 không FAIL (SKIP); (d) has_upstream=False → C9 không FAIL. Tất cả in-memory (tiêm dict), xác định.
- Không thêm test cần network / cần repo thật (giữ CI ổn định).
- Chạy `scripts\vp.cmd check` phải PASS sau khi code (behind=0 ở máy dev khi đã sync).
- Manual: giả lập behind (checkout HEAD~1 tạm) để thấy C9 FAIL thật — chỉ khi user muốn kiểm tay, không đưa vào suite.

## Adversarial Self-Review (đọc-lại-valid TRƯỚC khi đề xuất code)
**Câu hỏi sống-còn 1 — C9 có THỪA so với C1–C8 không?**
- C1–C8 đọc FILE trên đĩa → nếu file nội-bộ-nhất-quán thì PASS **bất kể** local có sau upstream hay không. Ví dụ nguy hiểm: máy A push tới #400; máy B (local #378, chưa pull) resume → file local #378 nội-bộ-nhất-quán → C1–C8 PASS → agent append #379 trên nền #378 stale → khi push = diverge/conflict, và #379 của B đè logic mà #379–#400 của A đã có. **C1–C8 KHÔNG thể thấy điều này** (chúng không chạm git). ⇒ C9 KHÔNG thừa; nó phủ đúng lớp còn hở. (K-098 lần trước MAY được C2 bắt vì file đã ở #372 sau khi pull — nhưng đó là vì đã pull; nếu CHƯA pull thì C1–C8 mù.)

**Câu hỏi sống-còn 2 — false-positive giữa turn?**
- Giữa turn tôi sửa LOG/journal (uncommitted). C9 KHÔNG nhìn uncommitted/dirty để fail (chỉ nhìn `behind`). `behind` chỉ >0 khi local thực sự sau upstream — không xảy ra do việc sửa file. ⇒ không kêu oan giữa turn. (Cố ý KHÔNG fail trên "dirty working tree" vì đó là trạng thái bình thường khi đang làm.)

**Câu hỏi sống-còn 3 — `behind` có thể SAI (stale) vì không fetch?**
- Đúng. Không fetch → `@{upstream}` phản ánh lần fetch/pull gần nhất. Có thể origin đã tiến mà local report behind=0 (false-NEGATIVE, KHÔNG false-positive). Đây là GIỚI HẠN trung thực: C9 bắt được "đã biết mình sau" (rất nhiều case multi-máy sau `git fetch` tự động của IDE), KHÔNG thay thế `git fetch` bằng tay. Không over-claim "chống mọi stale". Fetch chủ động = tùy chọn tương lai (network → cấm auto theo K-078).

**Câu hỏi sống-còn 4 — thêm subprocess có phá tính thuần/xác định của checker?**
- Không, NẾU giữ logic C9 thuần trên `git_facts` (dict) + tách collector I/O + tiêm được cho self_test. Đây chính là ràng buộc thiết kế cứng (Property 3/4). Nếu nhét subprocess thẳng vào logic → phá self_test → BÁC.

**Kết luận review:** C9 phủ lớp drift còn hở (bản-chất, không thừa), fail hẹp (không kêu oan), fail-safe khi thiếu git, giữ được self_test. Giới hạn (không fetch) ghi rõ, không over-claim.

## Trade-offs
- **Thêm C9 (chọn) vs chỉ dựa luật văn xuôi §0:** luật văn xuôi là thứ hay drift (luận điểm gốc). Máy-gate mạnh hơn — cái mất: thêm ~40 dòng + 4 self-test case + phụ thuộc git CLI (đã có sẵn trong repo git).
- **Fail hẹp (chỉ behind) vs fail rộng (dirty/HEAD-mismatch):** chọn hẹp — cái mất: không bắt "unaware WIP cùng máy"; đổi lại: zero false-positive (điều kiện sống còn để checker được tin). Fail rộng dễ kêu oan → bị tắt → mất tác dụng.
- **Không fetch (offline) vs fetch (network):** chọn offline — cái mất: không thấy commit origin chưa pull; đổi lại: nhanh, không treo offline, không side-effect, tuân K-078 (network cần đèn xanh). Fetch = tùy chọn opt-in sau.

## Definition of Done — Design Phase
Chuyển sang code CHỈ khi: user đọc-lại-valid; diagnostics 0; hợp đồng `git_facts` rõ; điều kiện FAIL/SKIP không mơ hồ; mọi Property testable qua self_test tiêm-được. Code TDD sau đó: viết self_test case C9 (RED nếu chưa có C9) → thêm C9 → GREEN → `scripts\vp.cmd check` PASS.
