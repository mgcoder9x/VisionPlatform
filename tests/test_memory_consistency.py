"""Linter NHẤT QUÁN BỘ NHỚ — cơ chế chống-drift "cực mạnh" (kiểm bằng MÁY, không dựa luật văn xuôi).

Vì sao (bản chất): drift trong repo này hay đến từ việc CẬP NHẬT TAY nhiều mirror (LOG / journal INDEX /
activeContext) → dễ quên/đếm sai/để cũ. Luật văn xuôi tự nó cũng drift được. Cách mạnh nhất = biến các bất
biến "bản ghi khớp thực tế" thành TEST khách quan chạy được — giống `test_rules_sync.py` (RULES_VERSION).

Chạy: `py tests/test_memory_consistency.py`  (exit 0 = nhất quán, 1 = có drift → phải sửa trước khi tiếp).
Dùng với pytest qua `test_memory_consistency()`.

Mỗi check nhắm ĐÚNG một loại drift ĐÃ TỪNG xảy ra (xem AI-IMPLEMENTATION-LOG):
- C1  LOG entries liên tục 1..N, không trùng.
- C2  INDEX "Log canonical tới #N" == max entry thật của LOG   (bắt INDEX để cũ, vd ghi #241 khi log #247).
- C3  Mỗi file journal (D/C/T/K): ID liên tục 1..M, không trùng.
- C4  Header INDEX "Tổng M entry (D..·C..·T..·K..)" == đếm THẬT   (bắt tự-đếm-sai, vd 133 vs 137).
- C5  Mọi ID journal có dòng bảng trong INDEX & ngược lại        (bắt orphan / thiếu dòng).
- C6  activeContext có mốc "Cập nhật lúc" + có nhắc #maxEntry     (bắt con trỏ để cũ, không cập nhật per-turn).
- C7  Mọi LOG-# trích trong INDEX đều TỒN TẠI trong LOG          (bắt sync-đè mất đuôi LOG mà INDEX còn trích #phantom).
- C8  Mọi trường OPT-IN `Verify-Symbol: <relpath>::<symbol>` trong journal → symbol PHẢI còn ĐỊNH NGHĨA trong code
      (bắt drift TÀI LIỆU↔CODE: mục ✅ nói đã build symbol X nhưng X bị xoá/đổi tên mà quên cập nhật journal — D-089).
      Đây là drift class DUY NHẤT mà C1–C7 KHÔNG phủ (C1–C7 chỉ đối chiếu bản-ghi↔bản-ghi, C8 đối chiếu bản-ghi↔code).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "AI-IMPLEMENTATION-LOG.md"
JOURNAL = ROOT / "ai-decision-journal"
INDEX = JOURNAL / "00-INDEX.md"
ACTIVE = ROOT / "memory-bank" / "activeContext.md"

# prefix -> file trong ai-decision-journal
JOURNAL_FILES = {
    "D": JOURNAL / "01-decisions.md",
    "C": JOURNAL / "02-requirement-changes.md",
    "T": JOURNAL / "03-tradeoffs.md",
    "K": JOURNAL / "04-things-to-know.md",
}

# LEGACY (đông cứng — append-only CẤM sửa/xoá): #90/#91/#95/#96 mỗi số có 2 entry do va chạm số khi
# HAI AI (Gemini + Kiro) append cùng ngày trong quá khứ (2026-06-21..24). Lịch sử THẬT, không renumber
# (renumber = phá append-only + vỡ mọi tham chiếu chéo). Cho phép ĐÚNG các số này; MỌI dup MỚI → FAIL.
KNOWN_LOG_DUP_ENTRIES = {90, 91, 95, 96}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _ids_from_headings(text: str, prefix: str) -> list[int]:
    """Số ID lấy từ HEADING '### <prefix>-NNN — ...' (không tính các lần nhắc trong nội dung)."""
    return [int(m) for m in re.findall(rf"^###\s+{prefix}-(\d+)\b", text, re.M)]


def _index_row_ids(text: str, prefix: str) -> list[int]:
    """Số ID lấy từ DÒNG BẢNG INDEX '| <prefix>-NNN | ... |'."""
    return [int(m) for m in re.findall(rf"^\|\s*{prefix}-(\d+)\s*\|", text, re.M)]


def _verify_symbol_exists(relpath: str, symbol: str) -> bool:
    """C8: symbol còn ĐỊNH NGHĨA trong file code không? (def / async def / class / hằng module-level).

    Bản chất chống-drift-by-construction: chỉ nhận `relpath::symbol` (KHÔNG line-number → không false-positive
    khi code dịch dòng). File không tồn tại → False. Match rộng (mọi mức thụt) = an toàn cho mục tiêu "còn tồn tại".
    Giới hạn (ghi rõ): `def <symbol>` trong docstring/comment cũng match → false-NEGATIVE của việc-bắt-xoá (hiếm, chấp nhận)."""
    p = ROOT / relpath
    if not p.exists():
        return False
    sym = re.escape(symbol)
    pat = rf"^\s*(async\s+)?def\s+{sym}\b|^\s*class\s+{sym}\b|^{sym}\s*[:=]"
    return re.search(pat, p.read_text(encoding="utf-8"), re.M) is not None


def _contiguity(nums: list[int]) -> tuple[bool, int, list[int], list[int]]:
    """Trả (ok, maxn, duplicates, gaps). ok = không trùng AND đủ 1..max."""
    if not nums:
        return True, 0, [], []
    seen: set[int] = set()
    dups = sorted({n for n in nums if (n in seen) or seen.add(n)})
    mx = max(nums)
    gaps = [i for i in range(1, mx + 1) if i not in seen]
    return (not dups and not gaps), mx, dups, gaps


def check(log_text: str | None = None, index_text: str | None = None,
          active_text: str | None = None, journal_texts: dict | None = None,
          symbol_exists=None) -> tuple[bool, list[str]]:
    """Trả (ok, dòng-báo-cáo). ok=True nếu MỌI check pass.

    Tham số text TIÊM (mặc định None → đọc file thật): cho META-TEST kiểm chính checker (D-085) — feed
    text drift tổng-hợp → assert đúng check FAIL. Gọi `check()` không tham số = HÀNH VI CŨ (đọc file), nên
    `drift_check.py`/`vp` không đổi. `journal_texts` = dict prefix→text (None → đọc từng file journal).
    `symbol_exists` (C8, D-089) = Callable(relpath, symbol)->bool để TIÊM cho self_test (mặc định None →
    `_verify_symbol_exists` đọc file code thật). Tiêm resolver giả giữ self_test thuần-in-memory + xác định."""
    report: list[str] = []
    ok_all = True

    def line(ok: bool, tag: str, msg: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        report.append(f"[{'PASS' if ok else 'FAIL'}] {tag}: {msg}")

    log_text = _read(LOG) if log_text is None else log_text
    index_text = _read(INDEX) if index_text is None else index_text
    active_text = _read(ACTIVE) if active_text is None else active_text

    # ---- C1: LOG entries liên tục (bỏ qua dup LEGACY đã đông cứng; fail dup MỚI) ----
    entries = [int(m) for m in re.findall(r"^###\s+Entry\s+#(\d+)\b", log_text, re.M)]
    _, max_entry, dups, gaps = _contiguity(entries)
    new_dups = [d for d in dups if d not in KNOWN_LOG_DUP_ENTRIES]
    c1_ok = not new_dups and not gaps
    legacy_note = f" · dup-LEGACY(bỏ qua)={sorted(set(dups) & KNOWN_LOG_DUP_ENTRIES)}" if (set(dups) & KNOWN_LOG_DUP_ENTRIES) else ""
    line(c1_ok, "C1-LOG", f"{len(entries)} entry, max #{max_entry}"
         + (f" · TRÙNG-MỚI={new_dups}" if new_dups else "")
         + (f" · THIẾU={gaps}" if gaps else "")
         + legacy_note)

    # ---- C2: INDEX 'Log canonical tới #N' == max_entry ----
    m = re.search(r"Log canonical tới\s*\*{0,2}Entry #(\d+)", index_text)
    if m is None:
        line(False, "C2-INDEX-LOGREF", "KHÔNG tìm thấy 'Log canonical tới **Entry #N**' trong INDEX header")
    else:
        claimed = int(m.group(1))
        line(claimed == max_entry, "C2-INDEX-LOGREF",
             f"INDEX ghi #{claimed} vs LOG max #{max_entry}")

    # ---- C3 + C5: journal per-file contiguity + khớp INDEX rows ----
    counts: dict[str, int] = {}
    verify_syms: list[tuple[str, str]] = []   # C8: (relpath, symbol) từ trường Verify-Symbol (mọi file journal)
    for prefix, path in JOURNAL_FILES.items():
        jtext = _read(path) if journal_texts is None else journal_texts.get(prefix, "")
        file_ids = _ids_from_headings(jtext, prefix)
        verify_syms += [(m[1], m[2]) for m in re.findall(r"^(Verify-Symbol):\s*(\S+?)::(\S+)\s*$", jtext, re.M)]
        ok, mx, dups, gaps = _contiguity(file_ids)
        counts[prefix] = mx
        line(ok, f"C3-{prefix}", f"{len(file_ids)} ID, max {prefix}-{mx:03d}"
             + (f" · TRÙNG={dups}" if dups else "") + (f" · THIẾU={gaps}" if gaps else "") or "")

        # C5: bidirectional file <-> INDEX rows
        row_ids = set(_index_row_ids(index_text, prefix))
        fset = set(file_ids)
        missing_in_index = sorted(fset - row_ids)   # có trong file, thiếu dòng INDEX
        orphan_in_index = sorted(row_ids - fset)    # có dòng INDEX, không có trong file
        c5_ok = not missing_in_index and not orphan_in_index
        line(c5_ok, f"C5-{prefix}",
             ("khớp INDEX" if c5_ok else
              f"thiếu-dòng-INDEX={missing_in_index or '-'} · orphan-INDEX={orphan_in_index or '-'}"))

    # ---- C4: header total ----
    total_actual = sum(counts.values())
    m = re.search(r"Tổng\s*\*{0,2}(\d+)\s*entry\*{0,2}\s*\(D(\d+)·C(\d+)·T(\d+)·K(\d+)\)", index_text)
    if m is None:
        line(False, "C4-INDEX-TOTAL",
             "KHÔNG tìm thấy header 'Tổng **M entry** (D..·C..·T..·K..)' trong INDEX")
    else:
        tM, tD, tC, tT, tK = (int(m.group(i)) for i in range(1, 6))
        claim = (tD, tC, tT, tK, tM)
        actual = (counts["D"], counts["C"], counts["T"], counts["K"], total_actual)
        line(claim == actual, "C4-INDEX-TOTAL",
             f"INDEX ghi (D{tD}·C{tC}·T{tT}·K{tK}=Σ{tM}) vs THẬT "
             f"(D{counts['D']}·C{counts['C']}·T{counts['T']}·K{counts['K']}=Σ{total_actual})")

    # ---- C6: activeContext freshness ----
    has_stamp = "Cập nhật lúc" in active_text
    refs_latest = max_entry == 0 or f"#{max_entry}" in active_text
    line(has_stamp, "C6-ACTIVE-STAMP", "có mốc 'Cập nhật lúc'" if has_stamp else "THIẾU mốc 'Cập nhật lúc'")
    line(refs_latest, "C6-ACTIVE-LATEST",
         f"activeContext nhắc #{max_entry}" if refs_latest else
         f"activeContext KHÔNG nhắc entry mới nhất #{max_entry} (con trỏ để cũ?)")

    # ---- C7: mọi LOG-# trích trong INDEX phải TỒN TẠI trong LOG ----
    # Bắt kịch bản sync-đè đa-máy: mất đuôi LOG nhưng INDEX rows còn trích #cũ/phantom (C2 chỉ kiểm HEADER).
    # Mọi token '#N' trong repo này = tham chiếu LOG entry → phải ∈ tập entry thật.
    entry_set = set(entries)
    cited = [int(x) for x in re.findall(r"#(\d+)", index_text)]
    phantom = sorted({n for n in cited if n not in entry_set})
    line(not phantom, "C7-INDEX-CITES",
         "mọi #N trích ∈ LOG" if not phantom else
         f"INDEX trích LOG #KHÔNG-tồn-tại={phantom} (LOG max #{max_entry}) — sync mất đuôi?")

    # ---- C8: doc↔code — trường OPT-IN Verify-Symbol phải trỏ symbol CÒN ĐỊNH NGHĨA trong code (D-089) ----
    # Đóng drift class cuối: mục journal ✅ nói "đã build symbol X" nhưng X bị xoá/đổi tên mà quên cập nhật.
    resolver = _verify_symbol_exists if symbol_exists is None else symbol_exists
    missing_syms = [f"{p}::{s}" for (p, s) in verify_syms if not resolver(p, s)]
    line(not missing_syms, "C8-DOC-CODE",
         f"{len(verify_syms)} Verify-Symbol khớp code" if not missing_syms else
         f"symbol KHÔNG còn trong code={missing_syms} (code bị xoá/đổi tên mà journal chưa cập nhật?)")

    return ok_all, report


def _fail(report: list[str], tag: str) -> bool:
    """True nếu report có dòng FAIL chứa tag (dùng cho self_test)."""
    return any(r.startswith("[FAIL]") and tag in r for r in report)


def _self_baseline():
    """Bộ text NHẤT QUÁN tối thiểu (mọi check PASS) để META-TEST perturb ĐÚNG 1 chỗ."""
    log = "### Entry #1 — x\n### Entry #2 — x\n"
    journal = {"D": "### D-001 — a\n### D-002 — b\n", "C": "### C-001 — a\n",
               "T": "### T-001 — a\n", "K": "### K-001 — a\n"}
    index = (
        "Log canonical tới **Entry #2**. Tổng **5 entry** (D2·C1·T1·K1).\n"
        "| D-001 | x | #1 |\n| D-002 | x | #2 |\n| C-001 | x | #1 |\n"
        "| T-001 | x | #1 |\n| K-001 | x | #1 |\n"
    )
    active = "Cập nhật lúc: 2026\nnhắc #2\n"
    return log, index, active, journal


def self_test() -> tuple[bool, list[str]]:
    """META-TEST chính checker (D-085): baseline sạch → PASS; mỗi drift tổng-hợp → ĐÚNG tag FAIL.

    GUARD chống regex-rot: nếu ai sửa hỏng 1 check (vd regex sai → luôn PASS), self_test này FAIL →
    `vp check`/CI bắt ngay. Thuần in-memory, xác định (không đọc file, không flake)."""
    report: list[str] = []

    def rec(cond: bool, name: str) -> None:
        report.append(f"[{'PASS' if cond else 'FAIL'}] self:{name}")

    log, index, active, journal = _self_baseline()

    ok0, _ = check(log, index, active, journal)
    rec(ok0, "baseline-clean-PASS")  # baseline phải PASS toàn bộ

    # C1: entry TRÙNG mới (max giữ 2 → cô lập C1)
    _, r = check(log + "### Entry #2 — dup\n", index, active, journal)
    rec(_fail(r, "C1-LOG"), "C1-catch-dup")

    # C2: INDEX header trích #khác max
    _, r = check(log, index.replace("Entry #2**", "Entry #9**"), active, journal)
    rec(_fail(r, "C2-INDEX-LOGREF"), "C2-catch-header-mismatch")

    # C4: tổng sai (5→9)
    _, r = check(log, index.replace("**5 entry**", "**9 entry**"), active, journal)
    rec(_fail(r, "C4-INDEX-TOTAL"), "C4-catch-wrong-total")

    # C5: dòng INDEX orphan (D-009 không có heading trong journal D)
    _, r = check(log, index + "| D-009 | x | #1 |\n", active, journal)
    rec(_fail(r, "C5-D"), "C5-catch-orphan")

    # C6: activeContext thiếu mốc + thiếu nhắc #max
    _, r = check(log, index, "nhắc #2 (thiếu mốc)\n", journal)
    rec(_fail(r, "C6-ACTIVE-STAMP"), "C6-catch-missing-stamp")
    _, r = check(log, index, "Cập nhật lúc: 2026 (thiếu nhắc entry)\n", journal)
    rec(_fail(r, "C6-ACTIVE-LATEST"), "C6-catch-stale-pointer")

    # C7: INDEX trích LOG-# phantom (#99 ∉ {1,2})
    _, r = check(log, index + "| Z | x | #99 |\n", active, journal)
    rec(_fail(r, "C7-INDEX-CITES"), "C7-catch-phantom-cite")

    # C8: doc↔code — tiêm resolver GIẢ (in-memory, KHÔNG đọc file → xác định, không flake)
    fake_ok = lambda pth, s: (pth, s) == ("p.py", "foo")  # noqa: E731 — chỉ biết đúng p.py::foo
    j8 = dict(journal, D=journal["D"] + "Verify-Symbol: p.py::foo\n")
    ok8, _ = check(log, index, active, j8, symbol_exists=fake_ok)
    rec(ok8, "C8-clean-PASS")                                  # symbol tồn tại → toàn bộ PASS
    j8sym = dict(journal, D=journal["D"] + "Verify-Symbol: p.py::ghost\n")
    _, r = check(log, index, active, j8sym, symbol_exists=fake_ok)
    rec(_fail(r, "C8-DOC-CODE"), "C8-catch-missing-symbol")    # symbol không có → FAIL
    j8file = dict(journal, D=journal["D"] + "Verify-Symbol: nope.py::foo\n")
    _, r = check(log, index, active, j8file, symbol_exists=fake_ok)
    rec(_fail(r, "C8-DOC-CODE"), "C8-catch-missing-file")      # file/symbol không có → FAIL

    ok_all = all(line.startswith("[PASS]") for line in report)
    return ok_all, report


def test_memory_consistency():
    ok, report = check()
    assert ok, "DRIFT bộ nhớ phát hiện:\n" + "\n".join(report)


def test_checker_self_test():
    """META: chính checker phải BẮT được mọi lớp drift (chống regex-rot)."""
    ok, report = self_test()
    assert ok, "SELF-TEST checker FAIL (checker hỏng?):\n" + "\n".join(report)


if __name__ == "__main__":
    ok, report = check()
    print("=== MEMORY CONSISTENCY (chống drift) ===")
    for r in report:
        print(r)
    st_ok, st_report = self_test()
    print("\n=== SELF-TEST checker (guard chống regex-rot) ===")
    for r in st_report:
        print(r)
    both = ok and st_ok
    print("\nPASS: bản ghi nhất quán + checker lành." if both else "FAIL: có DRIFT hoặc checker hỏng — sửa trước khi tiếp.")
    sys.exit(0 if both else 1)
