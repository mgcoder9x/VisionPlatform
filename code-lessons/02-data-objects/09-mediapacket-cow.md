# #02 · Mẩu 09: CoW — `with_metadata` / `with_artifact` / `without_artifact` + `replace`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (trong `MediaPacket`) ·
tầng **kernel** · đây là cách **"đổi" một packet bất biến** mà không vi phạm tính bất biến.

## 2. Cần biết trước
- [immutable](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến) ·
  [MappingProxyType](../../knowledge-base/00-GLOSSARY.md#mappingproxytype) ·
  [zero-copy](../../knowledge-base/00-GLOSSARY.md#zero-copy)
- Mẩu 08 (`MediaPacket` bất biến) — đọc trước. Học sâu: (sẽ tạo) `knowledge-base/immutability-cow/`.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)

> **🖼 Sơ đồ CoW (nguồn Draw.io):** [mediapacket-cow.drawio](diagrams/mediapacket-cow.drawio) — `with_metadata` tạo packet MỚI, copy dict nhỏ, dùng chung ảnh.
> Xem nhúng: Draw.io → **Export as → SVG** → lưu `diagrams/mediapacket-cow.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

```python
# vision-platform/src/vision_platform/kernel/media_packet.py  (trong class MediaPacket)
    # ---- CoW operations ----
    def with_artifact(self, key: str, value: Any) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts[key] = value
        return replace(self, artifacts=MappingProxyType(new_artifacts))

    def with_metadata(self, key: str, value: Any) -> "MediaPacket":
        new_metadata = dict(self.metadata)
        new_metadata[key] = value
        return replace(self, metadata=MappingProxyType(new_metadata))

    def without_artifact(self, key: str) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts.pop(key, None)
        return replace(self, artifacts=MappingProxyType(new_artifacts))
```

## 4. Giải thích từng phần nhỏ nhất
- `# ---- CoW operations ----` → comment đánh dấu nhóm thao tác **Copy-on-Write** ("đổi thì tạo bản mới").
- `def with_artifact(self, key, value) -> "MediaPacket":` → trả về **một `MediaPacket` MỚI** có thêm 1 artifact (không sửa packet cũ). `-> "MediaPacket"` là gợi ý kiểu trả về.
  - `new_artifacts = dict(self.artifacts)` → tạo **bản sao** dict artifacts hiện tại (vì bản gốc là chỉ-đọc, phải copy ra dict ghi được).
  - `new_artifacts[key] = value` → thêm/ghi vào bản sao.
  - `return replace(self, artifacts=MappingProxyType(new_artifacts))` → `replace` (của dataclasses) tạo bản sao packet, chỉ **thay trường `artifacts`** bằng bản mới (đã bọc lại chỉ-đọc). Các trường khác (gồm `media_ref` = ảnh) **dùng lại y nguyên, KHÔNG copy ảnh**.
- `with_metadata(...)` → y hệt nhưng cho `metadata`.
- `without_artifact(key)`:
  - `new_artifacts.pop(key, None)` → bỏ `key` khỏi bản sao (`None` = không lỗi nếu key không có).
  - rồi `replace` ra packet mới.

## 5. Là gì (1–2 câu)
Đây là 3 thao tác **CoW**: muốn thêm/bớt metadata/artifact thì **tạo packet mới** (sao trường nhỏ),
chứ không sửa packet cũ. Packet cũ vẫn nguyên vẹn.

## 6. Tại sao tồn tại / vấn đề nó giải
`MediaPacket` bất biến (mẩu 08) nên KHÔNG sửa tại chỗ được — nhưng pipeline vẫn cần "gắn thêm kết quả"
(vd thêm detections sau bước AI). CoW giải mâu thuẫn "bất biến nhưng cần đổi": **chỉ copy phần nhỏ
(metadata/artifacts dict) và DÙNG CHUNG phần lớn (ảnh `media_ref`)**. Vừa an toàn (bản cũ bất biến,
nhiều bước giữ tham chiếu không sợ đổi) vừa nhanh (không copy ảnh 6,2 triệu số).

## 7. Dùng ở đâu trong project (cụ thể)
- Các stage trong pipeline (#04) "gắn kết quả" vào packet bằng `with_artifact` → trả packet mới cho stage sau.
- Test thật `tests/test_step_02_domain.py` (đã CHẠY pass):
  - `test_packet_with_artifact_returns_new_packet`: `p2 = p1.with_artifact("detections",[1,2,3])` → `p1 is not p2`, `"detections" not in p1.artifacts`, `p2.artifacts["detections"]==[1,2,3]`.
  - `test_packet_with_metadata_chain`: `p1.with_metadata("a",1).with_metadata("b",2)` → `p1.metadata=={}`, `p2` có a=1,b=2 (nối chuỗi được).
  - `test_packet_without_artifact`: `p2=p1.without_artifact("x")` → `"x" in p1.artifacts` (cũ còn), `"x" not in p2.artifacts`.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Cho sửa tại chỗ (`packet.artifacts["k"]=v`): mất bất biến → bước sau lỡ sửa, bước trước "bị đổi sau lưng".
- Copy CẢ packet kèm ảnh mỗi lần đổi metadata: đúng nhưng **chậm/ngốn RAM** (copy 6,2 triệu số chỉ để thêm 1 nhãn nhỏ). CoW chỉ copy dict nhỏ, giữ chung ảnh.

## 9. Ví von đời thường
CoW như **photo có chỉnh sửa**: cần thêm 1 dòng ghi chú thì **photo tờ bìa hồ sơ rồi ghi lên bản photo**,
giữ nguyên hồ sơ gốc; **tập ảnh dày bên trong KHÔNG photo lại** (dùng chung) → nhanh, rẻ, bản gốc còn nguyên.

## 10. Liên kết bức tranh lớn
Đây là mảnh KHÉP LẠI câu chuyện #02: **bất biến (mẩu 08) + chia sẻ ảnh zero-copy (mẩu 06) + CoW (mẩu này)**
= "an toàn mà vẫn nhanh". Pattern này (Copy-on-Write) lặp lại ở nhiều hệ; sẽ học sâu ở `knowledge-base/immutability-cow/`.

## 11. Cạm bẫy / lỗi thường gặp
- Quên rằng `with_*` trả packet MỚI: viết `p.with_metadata("a",1)` mà không gán lại → kết quả bị bỏ, `p` không đổi (đúng bản chất bất biến, nhưng dễ nhầm). Phải `p = p.with_metadata(...)`.
- Tưởng CoW copy cả ảnh → KHÔNG; ảnh (`media_ref`) dùng chung qua `replace`. (Đó là lý do nó nhanh.)
- Sửa tại chỗ `p.artifacts["k"]=v` → raise (mẩu 08); luôn dùng `with_*`.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: CoW copy cái gì, KHÔNG copy cái gì? Vì sao vừa an toàn vừa nhanh?
- Tình huống: stage AI cần gắn `detections` vào packet — viết dòng nào? Packet cũ có đổi không?
- Giải thích lại bằng LỜI MÌNH: "Copy-on-Write nghĩa là ... ; ở đây copy ... giữ chung ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại CoW copy gì/giữ gì | 1 tuần → tự viết 1 thao tác `with_x` cho 1 dataclass frozen | 1 tháng → giải thích "bất biến mà vẫn nhanh" bằng lời mình.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (đã ĐỌC LẠI nguyên văn 3 thao tác CoW). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_02_domain.py -k packet` → **6 passed** (gồm 3 test CoW trích ở §7). · Độ chắc: **cao**.
- CoW "không copy ảnh, copy dict nhỏ": suy từ code (`replace` giữ `media_ref`, chỉ thay `artifacts`/`metadata`); [chưa đo benchmark RAM/tốc độ tại mẩu này] — đúng theo cấu trúc code. · Độ chắc: cao về cơ chế.
