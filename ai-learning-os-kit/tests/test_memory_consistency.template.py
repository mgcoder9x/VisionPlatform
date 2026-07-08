"""TEMPLATE — Linter NHẤT QUÁN BỘ NHỚ (chống-drift bằng MÁY). Copy sang `tests/test_memory_consistency.py`.

Vì sao: drift hay đến từ CẬP-NHẬT-TAY nhiều mirror (LOG / decision-journal INDEX / activeContext) → luật
văn xuôi tự nó drift. Cách mạnh nhất = biến bất biến "bản ghi khớp thực tế" thành TEST khách quan chạy được.

Chạy: `py tests/test_memory_consistency.py`  (exit 0 = nhất quán, 1 = có drift → SỬA trước khi tiếp).
Dùng với pytest qua `test_memory_consistency()`.

GIẢ ĐỊNH CẤU TRÚC (điều chỉnh theo dự án của bạn nếu khác):
- `AI-IMPLEMENTATION-LOG.md` (gốc repo): entries `### Entry #N — ...` (liên tục từ 1).
- `ai-decision-journal/{01-decisions,02-requirement-changes,03-tradeoffs,04-things-to-know}.md`:
  heading `### <D|C|T|K>-NNN — ...`.
- `ai-decision-journal/00-INDEX.md`: header "Log canonical tới **Entry #N**" + "Tổng **M entry** (D..·C..·T..·K..)"
  + bảng mỗi ID `| <prefix>-NNN | ... |`.
- `memory-bank/activeContext.md`: có mốc "Cập nhật lúc" + nhắc #maxEntry (con trỏ per-turn).

6 CHECK (mỗi cái nhắm 1 loại drift): C1 LOG liên tục · C2 INDEX↔LOG max · C3 journal liên tục ·
C4 total đếm-thật · C5 ID⇄INDEX · C6 activeContext freshness.
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

JOURNAL_FILES = {
    "D": JOURNAL / "01-decisions.md",
    "C": JOURNAL / "02-requirement-changes.md",
    "T": JOURNAL / "03-tradeoffs.md",
    "K": JOURNAL / "04-things-to-know.md",
}

# Dự án MỚI: để RỖNG. Chỉ thêm số vào đây khi có dup LEGACY đông cứng (append-only cấm renumber) +
# GHI RÕ lý do (vd 2 AI append cùng số trong quá khứ). MỌI dup ngoài allowlist → FAIL.
KNOWN_LOG_DUP_ENTRIES: set[int] = set()


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _ids_from_headings(text: str, prefix: str) -> list[int]:
    return [int(m) for m in re.findall(rf"^###\s+{prefix}-(\d+)\b", text, re.M)]


def _index_row_ids(text: str, prefix: str) -> list[int]:
    return [int(m) for m in re.findall(rf"^\|\s*{prefix}-(\d+)\s*\|", text, re.M)]


def _contiguity(nums: list[int]) -> tuple[bool, int, list[int], list[int]]:
    if not nums:
        return True, 0, [], []
    seen: set[int] = set()
    dups = sorted({n for n in nums if (n in seen) or seen.add(n)})
    mx = max(nums)
    gaps = [i for i in range(1, mx + 1) if i not in seen]
    return (not dups and not gaps), mx, dups, gaps


def check() -> tuple[bool, list[str]]:
    report: list[str] = []
    ok_all = True

    def line(ok: bool, tag: str, msg: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        report.append(f"[{'PASS' if ok else 'FAIL'}] {tag}: {msg}")

    log_text = _read(LOG)
    index_text = _read(INDEX)
    active_text = _read(ACTIVE)

    entries = [int(m) for m in re.findall(r"^###\s+Entry\s+#(\d+)\b", log_text, re.M)]
    _, max_entry, dups, gaps = _contiguity(entries)
    new_dups = [d for d in dups if d not in KNOWN_LOG_DUP_ENTRIES]
    c1_ok = not new_dups and not gaps
    line(c1_ok, "C1-LOG", f"{len(entries)} entry, max #{max_entry}"
         + (f" · TRÙNG-MỚI={new_dups}" if new_dups else "") + (f" · THIẾU={gaps}" if gaps else ""))

    m = re.search(r"Log canonical tới\s*\*{0,2}Entry #(\d+)", index_text)
    if m is None:
        line(False, "C2-INDEX-LOGREF", "KHÔNG tìm thấy 'Log canonical tới **Entry #N**' trong INDEX")
    else:
        line(int(m.group(1)) == max_entry, "C2-INDEX-LOGREF", f"INDEX #{m.group(1)} vs LOG max #{max_entry}")

    counts: dict[str, int] = {}
    for prefix, path in JOURNAL_FILES.items():
        file_ids = _ids_from_headings(_read(path), prefix)
        ok, mx, dups, gaps = _contiguity(file_ids)
        counts[prefix] = mx
        line(ok, f"C3-{prefix}", f"{len(file_ids)} ID, max {prefix}-{mx:03d}"
             + (f" · TRÙNG={dups}" if dups else "") + (f" · THIẾU={gaps}" if gaps else ""))
        row_ids = set(_index_row_ids(index_text, prefix))
        fset = set(file_ids)
        missing = sorted(fset - row_ids)
        orphan = sorted(row_ids - fset)
        line(not missing and not orphan, f"C5-{prefix}",
             "khớp INDEX" if (not missing and not orphan) else f"thiếu-INDEX={missing or '-'} · orphan={orphan or '-'}")

    total_actual = sum(counts.values())
    m = re.search(r"Tổng\s*\*{0,2}(\d+)\s*entry\*{0,2}\s*\(D(\d+)·C(\d+)·T(\d+)·K(\d+)\)", index_text)
    if m is None:
        line(False, "C4-INDEX-TOTAL", "KHÔNG tìm thấy header 'Tổng **M entry** (D..·C..·T..·K..)'")
    else:
        tM, tD, tC, tT, tK = (int(m.group(i)) for i in range(1, 6))
        actual = (counts["D"], counts["C"], counts["T"], counts["K"], total_actual)
        line((tD, tC, tT, tK, tM) == actual, "C4-INDEX-TOTAL",
             f"INDEX (D{tD}·C{tC}·T{tT}·K{tK}=Σ{tM}) vs THẬT (D{counts['D']}·C{counts['C']}·T{counts['T']}·K{counts['K']}=Σ{total_actual})")

    line("Cập nhật lúc" in active_text, "C6-ACTIVE-STAMP",
         "có mốc 'Cập nhật lúc'" if "Cập nhật lúc" in active_text else "THIẾU mốc 'Cập nhật lúc'")
    refs_latest = max_entry == 0 or f"#{max_entry}" in active_text
    line(refs_latest, "C6-ACTIVE-LATEST",
         f"activeContext nhắc #{max_entry}" if refs_latest else f"KHÔNG nhắc #{max_entry} (con trỏ cũ?)")

    return ok_all, report


def test_memory_consistency():
    ok, report = check()
    assert ok, "DRIFT bộ nhớ:\n" + "\n".join(report)


if __name__ == "__main__":
    ok, report = check()
    print("=== MEMORY CONSISTENCY (chống drift) ===")
    for r in report:
        print(r)
    print("PASS: bản ghi nhất quán." if ok else "FAIL: có DRIFT — sửa bản ghi trước khi tiếp.")
    sys.exit(0 if ok else 1)
