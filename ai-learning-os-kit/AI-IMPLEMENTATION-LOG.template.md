# 🧾 AI Implementation Log (Hộp đen chống Drift)

> AI hay *drift*. File này là nhật ký **append-only**: mỗi lần triển khai bất cứ gì, AI thêm
> 1 entry vào cuối. Append-only — không sửa/xóa entry cũ; đảo quyết định thì ghi entry mới trỏ ngược.

## 📌 Quy tắc cho AI (dán vào AGENTS.md)
```
LOG (chống drift) — MẶC ĐỊNH LUÔN BẬT:
- LUÔN append 1 entry sau mọi lần triển khai (đổi code / tạo file / quyết định). Không cần được nhắc.
- Chỉ bỏ khi người dùng nói rõ "đừng ghi log lần này".
- Đầu phiên: đọc 5 entry cuối + memory-bank + LEARNING-MAP. Mâu thuẫn → DỪNG, hỏi.
- Mục nào trống thì ghi "Không có" — đừng bỏ trống.
```

## 🧩 TEMPLATE 1 ENTRY (copy mỗi lần)
```markdown
### Entry #<số> — <ngày> — <task> — <tool>

**Bối cảnh:** <1 câu>

**1. Quyết định AI tự ra (spec không nói):**
- <quyết định> — vì <lý do>

**2. Chỗ phải đổi so với yêu cầu ban đầu:**
- <đổi gì> → <từ gì sang gì> — vì <lý do>

**3. Trade-off đã cân nhắc:**
- <A vs B> → chọn <X> vì <lý do + cái mất>

**4. Điều bạn nên biết:**
- <giả định chưa kiểm chứng / phần CHƯA verify / rủi ro / nợ kỹ thuật cố ý>

**Đã verify:** <...> · **Chưa verify:** <...>
```

## 📖 NHẬT KÝ (mới nhất ở dưới cùng)
<!-- entry đầu tiên của dự án mới bắt đầu từ đây -->
