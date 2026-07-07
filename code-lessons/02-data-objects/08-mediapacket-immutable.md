# #02 · Mẩu 08: `MediaPacket` bất biến + `MappingProxyType` + `__post_init__`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` · tầng **kernel** ·
đây là **gói trung tâm** chảy qua cả pipeline: 1 frame ảnh + thông tin kèm theo, **không cho sửa tại chỗ**.

## 2. Cần biết trước
- [MappingProxyType](../../knowledge-base/00-GLOSSARY.md#mappingproxytype) ·
  [immutable](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass)
- Mẩu 06 (`InMemoryArrayRef`) — `media_ref` là kiểu đó. CoW (`with_*`) → mẩu 09.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/kernel/media_packet.py
@dataclass(frozen=True)
class MediaPacket:
    """Immutable MediaPacket with CoW semantics.

    Mutation antipattern (BLOCKED):  packet.metadata["new"] = "value"   # raises
    CoW pattern (CORRECT):           new_packet = packet.with_metadata("new", "value")
    """
    packet_id: str
    source_id: str
    media_ref: InMemoryArrayRef
    capture_time_ns: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Wrap dict-like fields trong MappingProxyType với defensive copy.
        # object.__setattr__ bypass frozen=True — chỉ dùng trong __post_init__.
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if not isinstance(self.artifacts, MappingProxyType):
            object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))

    def __getstate__(self) -> dict:
        # ERRATA E-16: MappingProxyType KHÔNG pickle được (`TypeError: cannot pickle
        # 'mappingproxy' object` — verify thật). Hệ đa tiến trình gửi MediaPacket qua
        # IPC sẽ crash. → convert metadata/artifacts về dict THÔ khi pickle.
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "media_ref": self.media_ref,
            "capture_time_ns": self.capture_time_ns,
            "metadata": dict(self.metadata),
            "artifacts": dict(self.artifacts),
        }

    def __setstate__(self, state: dict) -> None:
        # pickle KHÔNG chạy __post_init__ → tự re-wrap MappingProxyType để GIỮ bất biến
        # sau unpickle. object.__setattr__ vì frozen=True. (ERRATA E-16)
        object.__setattr__(self, "packet_id", state["packet_id"])
        object.__setattr__(self, "source_id", state["source_id"])
        object.__setattr__(self, "media_ref", state["media_ref"])
        object.__setattr__(self, "capture_time_ns", state["capture_time_ns"])
        object.__setattr__(self, "metadata", MappingProxyType(dict(state["metadata"])))
        object.__setattr__(self, "artifacts", MappingProxyType(dict(state["artifacts"])))

    # ... (các thao tác CoW with_*/without_* — xem mẩu 09) ...
```

## 4. Giải thích từng phần nhỏ nhất
- `@dataclass(frozen=True) class MediaPacket:` → gói bất biến (không gán lại trường sau khi tạo).
- Docstring nêu thẳng quy tắc: sửa tại chỗ `packet.metadata["new"]=...` → **raise**; muốn đổi thì `with_metadata(...)` (CoW, mẩu 09).
- 6 trường:
  - `packet_id: str` → mã định danh gói; `source_id: str` → nguồn nào (camera nào).
  - `media_ref: InMemoryArrayRef` → **ảnh** (bọc read-only, mẩu 06).
  - `capture_time_ns: int` → thời điểm chụp (nano-giây).
  - `metadata: Mapping[str, Any] = field(default_factory=dict)` → thông tin mô tả; `field(default_factory=dict)` = mặc định là dict RỖNG MỚI mỗi lần (không dùng chung 1 dict).
  - `artifacts: Mapping[str, Any] = ...` → kết quả xử lý kèm theo (vd detections), cũng mặc định rỗng.
- `__post_init__`:
  - `if not isinstance(self.metadata, MappingProxyType):` → nếu chưa phải dạng chỉ-đọc thì...
  - `object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))` → bọc nó: `dict(self.metadata)` tạo **bản sao** (defensive copy), rồi `MappingProxyType(...)` làm nó **chỉ-đọc**. `object.__setattr__` để vượt khoá `frozen`.
  - Làm y hệt cho `artifacts`.
- `__getstate__`/`__setstate__` (ERRATA E-16 — cho hệ đa tiến trình):
  - **Vấn đề:** `MappingProxyType` **KHÔNG pickle được** (`TypeError: cannot pickle 'mappingproxy' object` — chạy thật). Hệ đa tiến trình gửi `MediaPacket` qua IPC sẽ crash.
  - `__getstate__` → khi pickle, trả dict với `metadata`/`artifacts` convert về **dict thô** (pickle được).
  - `__setstate__` → khi unpickle, **re-wrap** lại `MappingProxyType` → giữ bất biến sau khi qua ranh giới process. (pickle không chạy `__post_init__` nên phải tự làm.)

## 5. Là gì (1–2 câu)
`MediaPacket` là gói bất biến mang 1 frame + metadata/artifacts. `__post_init__` bọc 2 trường dict thành
**chỉ-đọc** (`MappingProxyType`) trên một **bản sao riêng**, nên không ai sửa được nội dung qua packet.

## 6. Tại sao tồn tại / vấn đề nó giải
`frozen=True` chỉ chặn **gán lại trường** (`packet.metadata = ...`), KHÔNG chặn **sửa nội dung dict bên trong**
(`packet.metadata["k"]=...`). Đó là lỗ hổng "frozen với dict mutable" (đã nói ở mẩu 01 §11). Hai lớp khoá:
1. `MappingProxyType` → chặn ghi vào dict qua packet.
2. `dict(self.metadata)` (defensive copy) → cắt liên kết với dict GỐC của caller; caller sửa dict cũ của họ cũng không ảnh hưởng packet.
→ Gói thật sự bất biến, an toàn khi nhiều bước/nhiều tiến trình dùng chung.

## 7. Dùng ở đâu trong project (cụ thể)
- Là "đơn vị dữ liệu" chảy qua pipeline (#04) và bus đa tiến trình (#05).
- Test thật `tests/test_step_02_domain.py` (đã CHẠY pass):
  - `test_packet_metadata_blocked`: `p.metadata["new"]="x"` → raise `(TypeError, AttributeError)`.
  - `test_packet_artifacts_blocked`: tương tự cho `artifacts`.
  - `test_packet_caller_dict_mutation_does_not_leak`: sửa dict GỐC sau khi tạo packet → `p.metadata["k"]` vẫn `"original"`, `"new" not in p.metadata` (defensive copy hiệu lực).
  - `test_packet_pickle_roundtrip_preserves_immutability` (E-16): pickle→unpickle `MediaPacket` → giá trị giữ nguyên + metadata/artifacts vẫn chặn ghi + array vẫn read-only.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Không `MappingProxyType`: `packet.metadata["k"]=...` sửa được → mất bất biến, bug "ai sửa metadata".
- Không defensive copy (`dict(...)`): packet dùng CHUNG dict với caller → caller sửa dict cũ là packet đổi theo (`test_packet_caller_dict_mutation_does_not_leak` sẽ fail). Cả 2 lớp đều cần.

## 9. Ví von đời thường
`MediaPacket` như **hồ sơ niêm phong**: ảnh + giấy tờ kèm. `dict(...)` = **photo giấy tờ** bỏ vào hồ sơ
(không giữ bản gốc của người nộp); `MappingProxyType` = **ép nhựa** tờ photo lại (đọc được, không viết lên được).

## 10. Liên kết bức tranh lớn
Đây là "gói bất biến" trung tâm của câu chuyện #02. Bất biến + chứa `media_ref` read-only (mẩu 06) +
giữ qua pickle (mẩu 07) → an toàn end-to-end. Muốn "đổi" gói thì dùng CoW (mẩu 09) — copy metadata nhỏ, KHÔNG copy ảnh.

## 11. Cạm bẫy / lỗi thường gặp
- Tưởng `frozen=True` là đủ → KHÔNG, dict bên trong vẫn sửa được nếu không bọc `MappingProxyType`. Đây là lý do tồn tại `__post_init__` này.
- Quên defensive copy (`dict(...)`) → rò rỉ qua dict caller (xem test caller_dict_mutation).
- `object.__setattr__` chỉ dùng hợp lệ trong `__post_init__`/`__setstate__`; dùng bừa nơi khác là phá ý nghĩa `frozen`.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `frozen=True` KHÔNG chặn được gì với dict? Hai lớp khoá của `__post_init__` là gì, mỗi lớp chặn điều gì?
- Tình huống: caller tạo packet từ dict của họ rồi sửa dict đó — packet có đổi không? Vì sao?
- Giải thích lại bằng LỜI MÌNH: "MappingProxyType để ... ; defensive copy để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 2 lớp khoá | 1 tuần → tự bọc 1 dict thành read-only + copy | 1 tháng → giải thích "frozen không đủ với dict".

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/kernel/media_packet.py` (đã ĐỌC LẠI nguyên văn `MediaPacket` + `__post_init__`). · Độ chắc: **cao**.
- Hành vi: đã CHẠY THẬT `pytest tests/test_step_02_domain.py -k packet` → **6 passed** (gồm 3 test trích ở §7; 3 test CoW còn lại để mẩu 09). · Độ chắc: **cao**.
