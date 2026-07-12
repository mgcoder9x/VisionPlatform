# Thiết kế C8 — "Living citation": chống drift TÀI LIỆU ↔ CODE (design-first, chờ VALID)

> Trạng thái: **DESIGN-ONLY** (chưa code). Theo workflow: thiết kế rõ → đọc-lại-valid đối kháng → CHỜ user OK → mới TDD.
> Nguồn code đã đọc THẬT lượt này: `tests/drift_check.py`, `tests/test_memory_consistency.py`, `ai-decision-journal/README.md`.
> Liên quan: D-052 (linter nhất quán bộ nhớ), D-053 (hook + kit), D-085 (self_test meta-test).

## 1. Vấn đề (bản chất, KHÔNG phải ngọn)

drift_check hiện có 3 tầng: [1] C1–C7 nhất quán bộ nhớ · [2] RULES_VERSION sync · [3] self-test guard.
Nhưng **mọi check C1–C7 chỉ đối chiếu BẢN GHI ↔ BẢN GHI** (LOG ↔ INDEX ↔ journal ↔ activeContext).
Không có check nào đối chiếu **BẢN GHI ↔ CODE THẬT**.

Hệ quả (drift class CHƯA phủ): một mục journal đánh dấu `✅ code` — ví dụ `D-073` nói
"`kernel/capabilities.py::resolve_device` đã hiện thực" — nếu về sau ai đó xoá/đổi tên `resolve_device`,
journal vẫn ghi ✅, `AI-IMPLEMENTATION-LOG.md` vẫn ghi ✅, và **drift_check vẫn PASS**. Tài liệu nói một đằng,
code một nẻo, mà máy KHÔNG bắt được. Đây là drift NGUY HIỂM nhất cho sản phẩm thương mại: audit-trail sai
sự thật mà không ai biết.

## 2. Mục tiêu + Non-Goal

**Mục tiêu:** biến các trích dẫn code trong journal thành **assertion máy-kiểm-được** — "symbol tôi nói đã build
thì PHẢI còn tồn tại trong code". Nếu code bị gỡ mà quên cập nhật journal → drift_check FAIL.

**Non-Goal (ghi rõ để không over-engineer):**
- KHÔNG kiểm "symbol có hành vi đúng" (đó là việc của test suite `pytest`, không phải drift-check tĩnh).
- KHÔNG kiểm số dòng (line number) — line trôi liên tục, kiểm line = false-positive = fix ngọn.
- KHÔNG bắt buộc MỌI mục journal phải có trích dẫn code — **opt-in** (xem §4, H1).

## 3. Kiến trúc phải tuân theo (đọc từ code thật)

`test_memory_consistency.check(log_text=None, index_text=None, active_text=None, journal_texts=None)`:
- Mỗi tham số `None` → đọc file thật; tham số tiêm → dùng để META-TEST. **C8 phải giữ đúng khuôn DI này.**
- `self_test()` hiện **thuần in-memory, xác định** ("không đọc file, không flake") — perturb baseline 1 chỗ → assert đúng tag FAIL.
- Mỗi check Cx có ≥1 case trong `self_test` (guard chống regex-rot). **C8 BẮT BUỘC có self-test tương tự.**

## 4. Thiết kế C8 (grounded)

### 4.1 Trường trích dẫn MỚI, có cấu trúc, OPT-IN
Journal entry có thể thêm 1 (hoặc nhiều) dòng trường cố định:

```
Verify-Symbol: <relpath-từ-repo-root>::<tên_symbol>
```

Ví dụ (bám convention `path::symbol` journal ĐÃ dùng, vd `pipeline_factory.py::_det_pt`):
```
Verify-Symbol: vision-platform/src/vision_platform/kernel/capabilities.py::resolve_device
```

- **Opt-in:** mục KHÔNG có `Verify-Symbol:` → C8 bỏ qua (backward-compat tuyệt đối với 219 mục hiện có; giống
  pattern "builder chưa khai báo allowed_params → lenient" D-045, và LEGACY dup C1). Zero gánh nặng hồi tố.
- **Vì sao trường MỚI, không parse `Nguồn:` cũ** (H1): trường `Nguồn:` hiện free-form (lẫn LOG#, prose, line-number)
  → parse ra symbol sẽ KHÔNG đáng tin → false-positive → checker thành nhiễu → bị phớt lờ → tệ hơn không có.
  Fix gốc = trường CHUYÊN DỤNG, format cứng, chống-drift-by-construction (không chứa line-number).

### 4.2 C8 kiểm gì
Với MỖI dòng `Verify-Symbol: path::symbol` trong 4 file journal:
1. **File tồn tại**: `(ROOT/path).exists()`. Không → FAIL.
2. **Symbol được ĐỊNH NGHĨA trong file đó**: match 1 trong (regex, `re.M`):
   - `^\s*(async\s+)?def\s+<symbol>\b`   (hàm/method, mọi mức thụt)
   - `^\s*class\s+<symbol>\b`            (class)
   - `^<symbol>\s*[:=]`                  (hằng/biến module-level)
   Không match → FAIL (symbol đã bị xoá/đổi tên).

### 4.3 Giữ self_test thuần in-memory (H6 — điểm mấu chốt)
C8 vốn phải ĐỌC file code → phá tính "in-memory" của `self_test`. Giải: **tiêm resolver**.
- `check(..., symbol_exists: Callable[[str,str],bool] | None = None)`.
- `None` (mặc định, `drift_check.py`/`vp` gọi) → dùng impl thật (đọc file + regex §4.2), có cache theo path.
- `self_test` tiêm `symbol_exists` GIẢ (dict trong bộ nhớ) → vẫn thuần-in-memory + xác định, KHÔNG flake.
Đây đúng khuôn DI mà `check()` đã có sẵn cho text → nhất quán kiến trúc, không phát minh cơ chế mới.

### 4.4 Self-test cases thêm cho C8 (guard regex-rot)
Trong `self_test`, thêm (dùng resolver giả `{("p.py","foo"): True}`):
- `self:C8-clean-PASS` — baseline có 1 `Verify-Symbol: p.py::foo` + resolver-giả biết foo → PASS.
- `self:C8-catch-missing-symbol` — `Verify-Symbol: p.py::ghost` (resolver-giả không biết) → C8 FAIL.
- `self:C8-catch-missing-file` — resolver-giả trả False cho file lạ → C8 FAIL.
Baseline `_self_baseline()` giữ NGUYÊN (mục không có Verify-Symbol → C8 im lặng), chỉ thêm nhánh có-trường.

## 5. Tự-review ĐỐI KHÁNG (đọc-lại-valid) — các hố + xử lý

| # | Hố tiềm ẩn | Xử lý (bản chất) |
|---|---|---|
| H1 | Parse `Nguồn:` cũ → false-positive | Trường MỚI chuyên dụng `Verify-Symbol`, opt-in. KHÔNG đụng `Nguồn:`. |
| H2 | "Symbol tồn tại" kiểu gì cho chắc? | `path::symbol` + regex def/class/assign. KHÔNG bao giờ dùng line-number. |
| H3 | Line-number trôi | Format cấm line-number by-construction. |
| H4 | Mục ↩️ (đã đảo, code CỐ Ý gỡ) báo FAIL oan | Quy tắc: khi đảo/gỡ code → GỠ luôn dòng `Verify-Symbol`. Presence của trường = assertion "phải còn sống". Không cần C8 đọc Status → không coupling. |
| H5 | Nhiều symbol/mục | Cho phép nhiều dòng `Verify-Symbol:`; kiểm từng dòng. |
| H6 | self_test đọc file → mất tính in-memory/flake | Tiêm resolver giả (§4.3). |
| H7 | Hiệu năng đọc code mỗi lần | Chỉ đọc file của mục CÓ opt-in (rất ít) + cache theo path. |
| H8 | Symbol trùng tên ở 2 file | Trường ghi `path::symbol` → chỉ kiểm trong ĐÚNG file đó, không nhầm. |
| H9 | Đổi RULES/mirror? | C8 KHÔNG đụng luật văn xuôi → KHÔNG bump RULES_VERSION. Nhưng `test_memory_consistency.template.py` trong `ai-learning-os-kit/` là mirror của checker → PHẢI port C8 sang kit (giữ kit = repo, tránh drift kit — D-083). [CẦN KIỂM ở PHA code: kit có file mirror này không.] |
| H10 | Docstring/comment chứa `def foo` gây match giả | Chấp nhận rủi ro thấp (match rộng hơn = an toàn hơn cho mục tiêu "còn tồn tại"; false-NEGATIVE của việc-bắt-xoá hiếm). Ghi là giới hạn. |

## 6. Phạm vi thay đổi (PHA code, khi được VALID)
1. `tests/test_memory_consistency.py`: thêm C8 trong `check()` (+ tham số `symbol_exists`), thêm 3 self-test case, cập nhật docstring liệt kê C8.
2. `ai-decision-journal/README.md`: mô tả trường `Verify-Symbol` + quy tắc H4 (đảo→gỡ trường).
3. `ai-learning-os-kit/tests/test_memory_consistency.template.py` (nếu tồn tại — H9): port C8 để kit khớp.
4. (tuỳ chọn) thêm `Verify-Symbol` cho vài mục ✅-code giá-trị-cao gần đây (D-073/D-088...) làm ví dụ sống.
- **Verify PHA code:** `py tests/test_memory_consistency.py` self-test 8→11 case PASS · `vp verify` (test+lint+drift) EXIT 0 · thử nghiệm NEGATIVE thật (tạm đổi tên 1 symbol → C8 FAIL đúng → hoàn tác).

## 7. Đánh đổi (trade-off — sẽ thành T-031 nếu code)
- **Được:** đóng drift class doc↔code — assertion audit-trail luôn đúng-với-code; hợp sản phẩm thương mại.
- **Mất:** mỗi mục opt-in phải thêm 1 dòng + kỷ luật H4 (đảo→gỡ trường). Giảm thiểu bằng opt-in (không hồi tố).
- **Vì sao đáng:** đây là drift class DUY NHẤT còn hở của cơ chế "cực mạnh"; chi phí biên gần 0 do opt-in.

## 8. Quyết định CHỜ user
(a) VALID thiết kế → tôi PHA code TDD theo §6 (thêm C8 + self-test, verify negative thật). Hoặc
(b) Thấy chưa cần (opt-in ⇒ lợi ích chỉ hiện khi dùng) → giữ 3 tầng hiện tại, đây là mốc dừng sạch.
