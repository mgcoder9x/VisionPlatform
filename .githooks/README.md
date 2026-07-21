# .githooks/ — Git hooks phiên bản hoá (chống drift, dùng chung mọi máy)

> **Vì sao thư mục này (không dùng `.git/hooks/`):** `.git/hooks/` KHÔNG được version-control →
> mỗi máy phải tự tạo lại → chính nó là nguồn drift + không audit được. `.githooks/` được **tracked
> trong repo** → 1 nguồn sự thật, mọi máy/clone dùng chung, review được trong PR.

## Kích hoạt (1 lần / mỗi clone)

```
scripts\vp.cmd install-hooks        # Windows — đặt core.hooksPath = .githooks
# hoặc thủ công (mọi OS):
git config core.hooksPath .githooks
```

Gỡ: `git config --unset core.hooksPath`.

Trên Linux/macOS (máy Docker) cần cấp quyền chạy 1 lần: `chmod +x .githooks/pre-commit`
(trên Git-for-Windows không cần — hook chạy qua shebang).

## Hook hiện có

| Hook | Làm gì | Vì sao |
|---|---|---|
| `pre-commit` | Chạy `tests/drift_check.py`; **chặn commit** nếu FAIL | Bắt drift SỚM NHẤT (lúc commit) thay vì sau push (CI). Chỉ chạy drift-check (nhanh) — pytest/lint để `vp verify` + CI, tránh bị bypass vì chậm. |

## Phòng thủ nhiều lớp (defense-in-depth) chống drift

1. **Hook `agentStop`** (`.kiro/hooks/auto-drift-check.kiro.hook`) — AI tự chạy `vp check` cuối mỗi lượt.
2. **`pre-commit`** (file này) — chặn drift vào commit ở LOCAL, mỗi lần commit.
3. **CI** (`.github/workflows/verify.yml`) — gate server-side mỗi push/PR (gọi thẳng `tests/drift_check.py`).

Bỏ qua có chủ đích 1 commit: `git commit --no-verify` (chỉ khi thật sự cần, KHÔNG khuyến khích).
