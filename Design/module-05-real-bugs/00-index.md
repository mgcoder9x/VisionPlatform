# Module 05 — Real Bugs (case studies từ R1-R5 review)

## Mục đích

Vision Platform đã pass 5 vòng review chuyên gia với 51+ bug được phát hiện và fix. Module này không liệt kê khô khan — mỗi bug là 1 **case study** giúp bạn:

1. **Pattern recognition**: nhận diện bug tương tự trong code của mình.
2. **Hiểu fix**: tại sao cách fix lại đúng (và 2-3 cách fix khác sẽ sai như thế nào).
3. **Prevention**: pattern code/test phòng ngừa từ đầu.

## Cách đọc module này

KHÔNG đọc tuần tự. **Đọc khi gặp bug tương tự trong code mình**, hoặc đọc khi review code đồng nghiệp.

Mục đích là **xây pattern recognition** — gặp 12 bug tương tự = nhận ra ngay khi gặp bug mới giống pattern.

## File template

Mỗi bug 1 file, format:

- **Setup** (3 phút): code 50 dòng minimal reproducer.
- **Bug story** (5 phút): symptoms ở production + cách phát hiện.
- **Why it happened** (10 phút): root cause + mental model sai.
- **Fix** (10 phút): code fix + 2-3 cách fix khác và lý do KHÔNG dùng.
- **Prevent** (5 phút): test pattern + lint rule + review checklist item.
- **Liên kết production** + R-id.

## Bugs covered (4 case studies đại diện)

Module này deep-dive **4 bug critical** đại diện cho 4 pattern khác biệt:

| # | ID | File | Severity | Pattern |
|---|------|------|----------|---------|
| 1 | R5-CRITICAL-02 | [`02-traceback-retention-r5.md`](02-traceback-retention-r5.md) | CRITICAL | Memory leak via Exception traceback |
| 2 | R5-CRITICAL-01 | [`01-mutex-poisoning-r5.md`](01-mutex-poisoning-r5.md) | CRITICAL | OS-level mutex poisoning |
| 3 | CR-RT-03 | [`03-block-policy-rtsp-r1.md`](03-block-policy-rtsp-r1.md) | HIGH | TCP Zero Window cascade |
| 4 | CR-DC-01 | [`04-frozen-dataclass-with-mutable-dict.md`](04-frozen-dataclass-with-mutable-dict.md) | MED | Shallow immutability trap |

→ 4 bug = 4 pattern. Hiểu sâu 4 cases này → bạn có cognitive frame để đọc các bug khác trong Vision Platform R1-R5 review tables nhanh hơn.

## Tự đọc thêm

Sau khi học 4 case studies trên, **đọc thêm** các bug khác đã fix trong Vision Platform — pattern + format giống nhau:

- **Round 1 (R1)**: bảng fix trong `Vision_platform_architecture_design/00-README.md` mục R1.
- **Round 5 (R5)**: bảng fix trong `Vision_platform_architecture_design/00-README.md` mục R5 + sub-folder `13-immutability-and-error-handling/`.

Pattern bug đáng lưu ý (đã fix trong design, có thể tự dive khi cần):

- CR-PL-02: `StageStatus.RETRY` chỉ drop frame, không re-process.
- CR-INF-02: `asyncio.gather` không có `return_exceptions=True` → 1 task error tắt cả batch.
- CR-SEC-01: HMAC không sign timestamp → replay attack.
- CR-PRV-01: DLQ wrap PrivacyFilter → PII leak khi sink fail.
- HI-IPC-04: dedup cache unbounded → OOM dài hạn.
- HI-OBS-01: PrintLogger blocking stdout → tail latency spike.
- D.4: AdaptiveSourceWrapper vẫn decode dù muốn drop → CPU lãng phí.
- C.7: DLQ rotate file lock race condition.

→ Pattern + format giống nhau. Hiểu 4 cases trong Module 05 → đọc các bug khác sẽ nhanh.

---

## Output

Sau Module 05: bạn có **bug pattern repertoire** — gặp code tương tự ở dự án thật, nhận ra ngay.

**Không phải mục tiêu**: thuộc lòng 12 bug ID. Là pattern recognition.

---

➡️ Bắt đầu với bug critical nhất: [`01-mutex-poisoning-r5.md`](01-mutex-poisoning-r5.md)
