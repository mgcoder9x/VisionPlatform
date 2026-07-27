"""secret_scan.py — CỔNG CHẶN SECRET vào git history (chỉ-đọc, có self-test guard-the-guard).

VÌ SAO (🔴 K-031 + sự cố #457): repo hiện SẠCH secret (đã quét: 0 kết quả cho private-key/AKIA/sk-/ghp_/xox),
nhưng cái giữ nó sạch tới giờ là **KỶ LUẬT**. Kỷ luật hỏng đúng một lần là secret nằm trong git history VĨNH VIỄN
(rewrite history = việc đau). Ở #457 chính AI đã vô tình làm `cmd set` in TOÀN BỘ biến môi trường (gồm 3 biến chứa
API key) ra log phiên ⇒ bằng chứng "dựa kỷ luật là không đủ". Nên: cưỡng chế BẰNG MÁY, cùng triết lý `drift_check`.

THIẾT KẾ — ĐỘ CHÍNH XÁC TRƯỚC ĐỘ PHỦ (bài học K-127: checker báo-động-giả sẽ bị TẮT, rồi lần sau có việc thật
cũng bị bỏ qua). Repo CỐ Ý chứa placeholder (`rtsp://USER:PASS@HOST`, `admin:***`, `<MATKHAU>`, `s3cret` trong test)
⇒ nếu chặn nhóm đó thì tự bắn vào chân. Vì vậy 2 tầng:

  [BLOCK] (exit 1) — mẫu độ-tin-cậy-CAO, FP ≈ 0: private key block · AWS `AKIA…` · OpenAI `sk-…` ·
      GitHub `ghp_/gho_/ghu_/ghs_/github_pat_` · Slack `xox[baprs]-` + webhook · Google `AIza…`
      + **FILE bị cấm tracked**: `.env`/`.env.*`, `*.pem`, `*.key`, `id_rsa*`.
  [WARN] (exit 0, chỉ báo) — URL có credential (`rtsp://u:p@`, `http(s)://u:p@`): repo dùng placeholder hợp lệ.

PHẠM VI: chỉ **file git-tracked** (`git ls-files`) — đúng thứ thực sự đi vào history; file scratch/gitignored không
liên quan. Bỏ qua file nhị phân + file quá lớn. `self_test()` trồng secret GIẢ → checker phải BẮT (chống regex-rot).

§3.1 — script CỐ ĐỊNH, CHỈ-ĐỌC. Chạy: `py tests/secret_scan.py`  (hoặc `scripts\vp.cmd secrets`).
Exit 0 = không có BLOCK · 1 = có BLOCK (secret thật) · 2 = lỗi môi trường (không chạy được git).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024          # bỏ qua file lớn (model/ảnh) — secret không nằm ở đó
SELF_PATH = "tests/secret_scan.py"   # file NÀY chứa mẫu regex → không tự quét chính mình (tránh FP hiển nhiên)

# --- BLOCK: mẫu định danh nhà cung cấp (prefix cố định) → gần như không thể là placeholder ngẫu nhiên ---
BLOCK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("openai-api-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
]

# --- BLOCK: tên file KHÔNG được tracked (dù nội dung có gì) ---
FORBIDDEN_FILE = re.compile(
    r"(?:^|/)(?:\.env(?:\.[^/]+)?|id_rsa(?:\.[^/]+)?|id_dsa|id_ecdsa|id_ed25519)$|\.(?:pem|key|p12|pfx|jks)$")

# --- WARN: URL có credential — repo CỐ Ý có placeholder, nên chỉ BÁO, không chặn ---
WARN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("url-with-credentials", re.compile(r"\b(?:rtsp|rtsps|https?|ftp)://[^\s'\"/@]+:[^\s'\"/@]+@")),
]


def tracked_files() -> list[str]:
    """File git-tracked (đúng thứ vào history). Lỗi git → raise (caller trả exit 2, KHÔNG im lặng PASS)."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _read_text(rel: str) -> Optional[str]:
    p = ROOT / rel
    try:
        if not p.is_file() or p.stat().st_size > MAX_BYTES:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:        # heuristic nhị phân
        return None
    return data.decode("utf-8", errors="replace")


def scan(files: Optional[Iterable[str]] = None,
         read_text=None) -> tuple[list[str], list[str]]:
    """Quét → `(blocks, warns)` mỗi phần tử là 1 dòng báo cáo `path:line  [tag]  <trích đoạn>`.

    `files`/`read_text` TIÊM để self-test chạy thuần-in-memory (khuôn giống `drift_check`: checker phải test được
    chính nó mà không phụ thuộc trạng thái repo).
    """
    if files is None:
        files = tracked_files()
    if read_text is None:
        read_text = _read_text
    blocks: list[str] = []
    warns: list[str] = []
    for rel in files:
        if FORBIDDEN_FILE.search(rel.replace("\\", "/")):
            blocks.append(f"{rel}  [forbidden-file]  file loại này KHÔNG được tracked")
            continue
        if rel.replace("\\", "/") == SELF_PATH:
            continue                  # file chứa chính các regex
        text = read_text(rel)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for tag, pat in BLOCK_PATTERNS:
                m = pat.search(line)
                if m:
                    blocks.append(f"{rel}:{lineno}  [{tag}]  {m.group(0)[:12]}…(đã cắt)")
            for tag, pat in WARN_PATTERNS:
                m = pat.search(line)
                if m:
                    warns.append(f"{rel}:{lineno}  [{tag}]  {line.strip()[:90]}")
    return blocks, warns


# --------------------------------------------------------------------------------------
# SELF-TEST (guard-the-guard): trồng secret GIẢ → checker PHẢI bắt; bản sạch PHẢI không bắt.
# Chống regex-rot: nếu ai sửa regex làm mất khả năng phát hiện, self-test đỏ ngay.
# --------------------------------------------------------------------------------------
def self_test() -> tuple[bool, list[str]]:
    rep: list[str] = []
    ok_all = True

    def rec(ok: bool, name: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        rep.append(f"[{'PASS' if ok else 'FAIL'}] self:{name}")

    clean = {"a.py": "print('hello')\n", "b.md": "rtsp url placeholder: rtsp://USER:PASS@HOST:554/stream\n"}
    b, w = scan(files=list(clean), read_text=clean.get)
    rec(not b, "clean-no-block")
    rec(len(w) == 1, "clean-warns-url-credential")   # placeholder → WARN, KHÔNG block

    cases = {
        "catch-private-key": "-----BEGIN RSA PRIVATE KEY-----\n",
        "catch-aws-akia": "aws_key = 'AKIAIOSFODNN7EXAMPLE'\n",
        "catch-openai": "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123\n",
        "catch-github-pat": "token: ghp_abcdefghijklmnopqrstuvwxyz0123\n",
        "catch-slack": "hook = 'xoxb-1234567890-abcdefghij'\n",
        "catch-google": "key=AIza" + "B" * 35 + "\n",
    }
    for name, content in cases.items():
        files = {"planted.txt": content}
        b, _ = scan(files=list(files), read_text=files.get)
        rec(bool(b), name)

    for name, path in {"catch-dotenv": ".env", "catch-env-suffix": "deploy/.env.production",
                       "catch-pem": "certs/server.pem", "catch-id-rsa": "keys/id_rsa"}.items():
        b, _ = scan(files=[path], read_text=lambda _p: None)
        rec(bool(b), name)

    b, _ = scan(files=["docs/notes.md"], read_text=lambda _p: "file .env duoc nhac trong van ban\n")
    rec(not b, "no-false-positive-on-prose-mentioning-dotenv")
    return ok_all, rep


def main() -> int:
    print("=== SECRET SCAN (file git-tracked · BLOCK = secret thật · WARN = URL có credential) ===")
    try:
        files = tracked_files()
    except Exception as e:  # noqa: BLE001 — không chạy được git thì KHÔNG được im lặng PASS
        print(f"[LOI MOI TRUONG] khong chay duoc `git ls-files`: {type(e).__name__}: {e}")
        return 2
    blocks, warns = scan(files=files)

    print(f"[i] da quet {len(files)} file tracked")
    if warns:
        print(f"\n--- WARN ({len(warns)}) — URL co credential (repo CO Y dung placeholder; kiem mat de chac) ---")
        for w in warns[:40]:
            print("  " + w)
        if len(warns) > 40:
            print(f"  … va {len(warns) - 40} dong nua")
    if blocks:
        print(f"\n--- BLOCK ({len(blocks)}) — SECRET THAT / FILE BI CAM ---")
        for b in blocks:
            print("  " + b)

    ok_self, rep = self_test()
    print("\n=== SELF-TEST (guard-the-guard: checker phai BAT duoc secret trong) ===")
    for line in rep:
        print(line)

    if blocks:
        print("\nSECRET-SCAN: FAIL — co secret/file bi cam trong file tracked. XOA + ROTATE truoc khi commit.")
        return 1
    if not ok_self:
        print("\nSECRET-SCAN: FAIL — SELF-TEST do (regex-rot: checker mat kha nang phat hien).")
        return 1
    print("\nSECRET-SCAN: PASS — khong co secret thật trong file tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
