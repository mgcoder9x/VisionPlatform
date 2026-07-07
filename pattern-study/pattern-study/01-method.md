# 01 — Method (Phương pháp)

## Goal (Ta muốn gì)
Một cách để **nhìn bài toán là biết dùng pattern nào, và dùng được** — language-independent (không lệ thuộc ngôn ngữ).

## The trap (Cái bẫy)
POSA 5-box chỉ *describe* (mô tả) một pattern. Điền đủ 5 box = có tài liệu đẹp,
vẫn không biết lúc nào dùng. **Describing is not knowing** (mô tả không phải là biết).

## Learning a pattern = training 4 skills (luyện 4 năng lực)
1. **Recognize** (nhận diện) — nhìn tình huống → biết pattern nào hợp.
2. **Structure** (cấu trúc) — pattern đó hình dạng gì (boxes + arrows).
3. **Judge** (phán đoán) — nên dùng không, cost (cái giá) phải trả gì.
4. **Transfer** (chuyển giao) — áp được sang bài toán/ngôn ngữ khác.

POSA 5-box chỉ dạy **#2 Structure**. **#1 Recognize** và **#4 Transfer** là phần
khó nhất, phải luyện riêng — đây là chỗ tốn công thật.

## How to train: a 4-step process (quy trình 4 bước / 1 pattern)
> Đây là **process** (quy trình tuyến tính), không phải loop. Chạy lần lượt 1→4
> cho **mỗi** pattern. Lặp lại process này khi học pattern mới.

1. **Hook the pain** (khơi nỗi đau) — ưu tiên *tạo* nỗi đau hơn *nhớ* nỗi đau:
   viết (hoặc lấy) một đoạn C# chạy được nhưng tệ — nested if-else, copy-paste,
   class ôm quá nhiều việc — rồi thử thêm 1 tính năng để tự thấy nó đau ở đâu.
   (Đây là tinh thần *Refactoring to Patterns*, Kerievsky 2004: pattern lộ ra
   từ code xấu, không áp từ trên xuống.)
2. **Read** (đọc) — pattern theo POSA 5-box.
3. **Draw** (vẽ) — gập tài liệu, vẽ lại diagram (sơ đồ) từ trí nhớ.
4. **Transfer** (tái hiện) — refactor đống code xấu ở step 1 về pattern, RỒI áp
   pattern vào 1 bài toán khác domain (lĩnh vực) nữa.

Bỏ step 1 và step 4 = biết tên pattern mà không dùng được.

> Lưu ý cân bằng: *Refactoring to Patterns* (pattern lộ ra từ code xấu) hợp với
> **design pattern (GoF)**. Còn **architecture pattern** (Hexagonal, Layers)
> thường phải *upfront* (thiết kế trước) — ít khi "refactor vô tình" mà ra. Chọn
> cách theo tier, đừng máy móc.

## Measuring & retention (Đo tới đâu, chống quên)
Không đo bằng cảm giác. Dùng **5-level scale + test** trong `00-READ-FIRST.md`
(Know → Understand → Use → Master → Analyze & Evaluate). Đó là thước chính thức
duy nhất; file này không lặp lại.

**Retention** (chống quên): sau 1 ngày / 1 tuần / 1 tháng, chạy lại test của
level (cấp) đang đứng — draw diagram + nói Forces từ trí nhớ, không đọc lại tài liệu.

---
**Bạn nhận được gì từ file này:** lý do *learning a pattern = training 4 skills*
(không phải nạp thông tin), và một **4-step process** để biến pattern từ "đọc
thấy" thành "dùng được". Cách ĐO mình tới đâu nằm ở `00-READ-FIRST.md`.
