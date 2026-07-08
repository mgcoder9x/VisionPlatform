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


def _contiguity(nums: list[int]) -> tuple[bool, int, list[int], list[int]]:
    """Trả (ok, maxn, duplicates, gaps). ok = không trùng AND đủ 1..max."""
    if not nums:
        return True, 0, [], []
    seen: set[int] = set()
    dups = sorted({n for n in nums if (n in seen) or seen.add(n)})
    mx = max(nums)
    gaps = [i for i in range(1, mx + 1) if i not in seen]
    return (not dups and not gaps), mx, dups, gaps


def check() -> tuple[bool, list[str]]:
    """Trả (ok, dòng-báo-cáo). ok=True nếu MỌI check pass."""
    report: list[str] = []
    ok_all = True

    def line(ok: bool, tag: str, msg: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        report.append(f"[{'PASS' if ok else 'FAIL'}] {tag}: {msg}")

    log_text = _read(LOG)
    index_text = _read(INDEX)
    active_text = _read(ACTIVE)

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
    for prefix, path in JOURNAL_FILES.items():
        file_ids = _ids_from_headings(_read(path), prefix)
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

    return ok_all, report


def test_memory_consistency():
    ok, report = check()
    assert ok, "DRIFT bộ nhớ phát hiện:\n" + "\n".join(report)


if __name__ == "__main__":
    ok, report = check()
    print("=== MEMORY CONSISTENCY (chống drift) ===")
    for r in report:
        print(r)
    print("PASS: bản ghi nhất quán." if ok else "FAIL: có DRIFT — sửa bản ghi trước khi tiếp.")
    sys.exit(0 if ok else 1)
