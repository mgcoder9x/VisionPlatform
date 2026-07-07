"""Linter luật: RULES_VERSION ở AGENTS.md phải khớp mọi file mirror.
Chạy: py tests/test_rules_sync.py   (exit 0 = khớp, 1 = lệch)
Dùng được với pytest qua test_rules_version_in_sync().
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [
    "AGENTS.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".kiro/steering/00-core-rules.md",
]
PAT = re.compile(r"RULES_VERSION:\s*(\d+)")


def versions():
    out = {}
    for f in FILES:
        p = ROOT / f
        if not p.exists():
            out[f] = None
            continue
        m = PAT.search(p.read_text(encoding="utf-8"))
        out[f] = m.group(1) if m else None
    return out


def check():
    v = versions()
    vals = set(v.values())
    ok = len(vals) == 1 and None not in vals
    return ok, v


def test_rules_version_in_sync():
    ok, v = check()
    assert ok, f"RULES_VERSION lech giua cac file: {v}"


if __name__ == "__main__":
    ok, v = check()
    for f, ver in v.items():
        print(f"{ver if ver else 'MISSING':>8}  {f}")
    if ok:
        print("PASS: RULES_VERSION khop.")
        sys.exit(0)
    print("FAIL: RULES_VERSION lech - dong bo lai mirror.")
    sys.exit(1)
