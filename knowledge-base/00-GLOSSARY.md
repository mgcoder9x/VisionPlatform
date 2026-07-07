# 📖 GLOSSARY — Thuật ngữ (giải thích MỘT lần, dùng cho mọi bài)

> **Chỉ chứa kiến thức NHỎ** (thuật ngữ ngắn, tra 1 dòng là hiểu). Khái niệm LỚN cần học sâu
> (hexagonal, backpressure...) → folder riêng `<concept>/`, KHÔNG nhồi vào đây (xem luật ở `00-INDEX.md`).
>
> Bài dạy KHÔNG giải thích thuật ngữ inline. Thay vào đó **link tới đây**:
> `[pip](../knowledge-base/00-GLOSSARY.md#pip)` → click là thấy. Mỗi từ = 1 mục `##` (anchor được).

## 🧩 FORM CHUẨN cho mỗi từ (mọi mục PHẢI theo)
```
## <từ>
- **Là gì:** 1 câu, KHÔNG thuật ngữ.
- **Để làm gì:** khi nào dùng / gặp ở đâu.
- **Ví von:** so sánh đời thường (nếu giúp hiểu).
- **Ví dụ:** `<lệnh/đoạn thật>` (nếu có).
- **Đừng nhầm:** với cái gì (nếu hay nhầm).
- **Học sâu:** → `knowledge-base/<concept>/` (chỉ khi là khái niệm lớn, không phải từ ngắn).
```
> Từ ngắn: chỉ cần 3 dòng đầu. Mục nào không có thì bỏ. Gặp từ chưa có → nói tôi, tôi thêm theo form.

---

## pip
- **Là gì:** công cụ tải + cài thư viện Python về máy.
- **Để làm gì:** thêm thư viện cho dự án (vd cần `numpy` thì cài nó).
- **Ví von:** "App Store" cho thư viện Python.
- **Ví dụ:** `pip install numpy`
- **Đừng nhầm:** `pip` (cài thư viện) ≠ `python` (chạy code).

## venv
- **Là gì:** một "hộp" Python riêng cho từng dự án.
- **Để làm gì:** để thư viện dự án A không đụng dự án B.
- **Ví von:** mỗi dự án một cái bếp riêng, không xài chung gia vị.
- **Ví dụ:** `py -m venv .venv` → tạo hộp tên `.venv`.

## package (thư viện / library)
- **Là gì:** code viết sẵn, cài về dùng (vd `numpy`); cũng chỉ "package của mình" = thư mục code dự án.
- **Để làm gì:** khỏi viết lại cái người ta làm rồi.
- **Ví von:** mua đồ làm sẵn thay vì tự nấu từ đầu.

## pyproject.toml
- **Là gì:** file khai báo dự án tên gì, cần thư viện nào, build ra sao.
- **Để làm gì:** để `pip` cài đúng + công cụ hiểu dự án.
- **Ví von:** "lý lịch / CMND" của dự án.

## src layout
- **Là gì:** quy ước đặt code trong thư mục `src/`.
- **Để làm gì:** tránh import nhầm giữa code và test.
- **Đừng nhầm:** với "flat layout" (code ngay ở gốc) — dễ lẫn.

## pytest
- **Là gì:** công cụ chạy test tự động.
- **Để làm gì:** kiểm code chạy đúng chưa, mỗi lần sửa.
- **Ví von:** máy chấm bài.
- **Ví dụ:** `pytest` → in `2 passed`.

## import-linter
- **Là gì:** công cụ kiểm quy tắc import giữa các layer.
- **Để làm gì:** bắt lỗi "layer A lỡ import layer B sai chiều" ngay khi xảy ra.
- **Ví von:** trọng tài bắt lỗi kiến trúc.
- **Học sâu:** → (sẽ tạo) `knowledge-base/dependency-direction/`.

## bulkhead
- **Là gì:** "vách ngăn" — tách hệ thống thành khoang riêng.
- **Để làm gì:** lỗi/hỏng 1 khoang không lan ra cả hệ (vd tách project riêng).
- **Ví von:** khoang kín trên tàu thủy — thủng 1 khoang, tàu không chìm.
- **Học sâu:** → (sẽ tạo) `knowledge-base/bulkhead/` (khái niệm lớn, Module 02).

## dataclass
- **Là gì:** cách khai báo nhanh một "lớp chứa dữ liệu" trong Python — chỉ liệt kê các trường, Python tự sinh hàm khởi tạo.
- **Để làm gì:** gói vài giá trị liên quan lại (vd x, y, w, h) mà không phải viết tay code lặp.
- **Ví dụ:** `@dataclass\nclass Point:\n    x: float\n    y: float`
- **Đừng nhầm:** `@dataclass(frozen=True)` = không cho sửa sau khi tạo (bất biến); không có `frozen` = sửa được.

## frozen (frozen=True)
- **Là gì:** tùy chọn của `dataclass` khoá đối tượng lại — gán lại trường sau khi tạo sẽ báo lỗi.
- **Để làm gì:** làm đối tượng **bất biến** (immutable) → an toàn khi chia sẻ nhiều nơi.
- **Ví von:** đổ bê tông: đổ xong là cứng, muốn khác thì đúc khuôn mới.

## immutable (bất biến)
- **Là gì:** một giá trị/đối tượng KHÔNG đổi sau khi tạo; muốn "đổi" thì tạo bản mới.
- **Để làm gì:** tránh bug "ai đó sửa lén", an toàn khi nhiều bước/nhiều tiến trình dùng chung.
- **Ví von:** số 5 là bất biến — `5 + 1` cho ra số 6 mới, chứ không biến số 5 thành 6.
- **Học sâu:** → (sẽ tạo) `knowledge-base/immutability-cow/` (kèm Copy-on-Write).

## DTO (Data Transfer Object)
- **Là gì:** một gói dữ liệu thuần để **truyền giữa các phần** của hệ, không chứa logic nghiệp vụ.
- **Để làm gì:** bên A đưa dữ liệu cho bên B theo một "hình dạng" rõ ràng (vd `ReadResult`, `MediaPacket`).
- **Ví von:** cái phong bì có ô điền sẵn — chỉ đựng thông tin, không "làm" gì.

## MappingProxyType
- **Là gì:** lớp bọc một dict thành **chỉ-đọc** — đọc được, ghi vào sẽ báo lỗi.
- **Để làm gì:** cho người ngoài xem metadata nhưng KHÔNG cho sửa tại chỗ (giữ bất biến).
- **Ví von:** tủ kính bảo tàng — nhìn được, không thò tay đổi hiện vật.

## Enum (enumeration)
- **Là gì:** một kiểu liệt kê **tập giá trị cố định, có tên** (vd 4 không gian tọa độ, 6 trạng thái đọc).
- **Để làm gì:** thay vì dùng chuỗi/số trần dễ gõ sai, ta dùng tên rõ ràng + chỉ nhận đúng các giá trị đã định.
- **Ví von:** nút chọn radio — chỉ được chọn 1 trong các lựa chọn có sẵn, không tự điền bậy.
- **Ví dụ:** `class Color(Enum):\n    RED = "red"\n    GREEN = "green"`
- **Đừng nhầm:** `CoordinateSpace.NORMALIZED` (một thành viên enum) ≠ chuỗi `"normalized"` (giá trị bên trong nó).

## TypeVar
- **Là gì:** một "biến kiểu" — chỗ giữ chỗ cho MỘT kiểu chưa biết trước (vd `T`), sẽ được điền sau.
- **Để làm gì:** viết code/lớp dùng được với nhiều kiểu mà vẫn giữ thông tin kiểu (vd hộp chứa "T", T là int hay ndarray tuỳ lúc dùng).
- **Ví dụ:** `T = TypeVar("T")`
- **Đừng nhầm:** `TypeVar` (khai báo biến kiểu) khác `Generic[T]` (dùng biến kiểu đó cho 1 lớp).

## Generic[T]
- **Là gì:** đánh dấu một lớp là "tổng quát theo kiểu T" → dùng được như `ReadResult[ndarray]`, `ReadResult[int]`.
- **Để làm gì:** một lớp khuôn dùng cho nhiều kiểu dữ liệu, vẫn ghi rõ "đang chứa kiểu gì".
- **Ví von:** cái hộp ghi nhãn `[___]`, lúc dùng mới dán nhãn cụ thể `[táo]` hay `[sách]`.
- **Đừng nhầm:** đây là **gợi ý kiểu** (cho công cụ kiểm static); Python KHÔNG ép kiểu lúc chạy.

## Optional
- **Là gì:** `Optional[X]` = "giá trị có thể là kiểu X, hoặc là `None`".
- **Để làm gì:** nói rõ một trường có thể vắng (vd `data` chỉ có khi đọc được frame).
- **Ví dụ:** `data: Optional[int] = None`
- **Đừng nhầm:** `Optional[X]` chỉ là gợi ý kiểu (= `X | None`); không tự kiểm tra lúc chạy.

## ndarray (numpy array)
- **Là gì:** mảng số nhiều chiều của thư viện `numpy` — cách Python lưu ảnh/ma trận hiệu quả.
- **Để làm gì:** chứa frame ảnh (vd mảng cao×rộng×3 kênh màu) + tính toán nhanh trên nó.
- **Ví von:** một bảng ô vuông khổng lồ chứa toàn số, máy đọc/tính cực nhanh.
- **Ví dụ:** `np.zeros((1080, 1920, 3))` → ảnh đen 1080×1920, 3 kênh.

## zero-copy
- **Là gì:** chia sẻ dữ liệu mà **không sao chép** — nhiều nơi cùng trỏ vào một vùng nhớ.
- **Để làm gì:** tránh copy dữ liệu lớn (ảnh) → nhanh + tiết kiệm RAM.
- **Ví von:** cho mượn đọc chung 1 cuốn sách, thay vì photo cho mỗi người một bản.
- **Đừng nhầm:** zero-copy nhanh nhưng nếu ai đó ghi bậy lên vùng chung thì mọi nơi bị ảnh hưởng → cần khoá read-only.

## pickle
- **Là gì:** công cụ chuẩn của Python để **đóng gói một đối tượng thành chuỗi byte** và bung lại — gọi là "serialize / deserialize".
- **Để làm gì:** lưu xuống file, hoặc **gửi đối tượng giữa các tiến trình** (process) — rất quan trọng khi dự án chạy đa tiến trình.
- **Ví von:** xếp đồ vào vali (dumps) để chuyển đi, rồi mở vali sắp lại như cũ (loads).
- **Đừng nhầm:** khi bung (`loads`), Python KHÔNG gọi lại `__init__`/`__post_init__` — nên trạng thái cần khôi phục phải xử lý ở `__setstate__`.
- **Học sâu:** → (sẽ tạo) `knowledge-base/pickle/`.

## port (cổng — Hexagonal)
- **Là gì:** một "hợp đồng" (interface) mô tả VIỆC cần làm, chưa nói làm BẰNG GÌ (vd "nguồn frame": có setup/read/teardown).
- **Để làm gì:** lõi chỉ phụ thuộc port (ổn định); bản cài cụ thể (adapter) cắm vào — đổi nguồn không đụng lõi.
- **Ví von:** ổ cắm điện chuẩn — thiết bị nào đúng chuẩn phích là cắm được.
- **Học sâu:** → (sẽ tạo) `knowledge-base/hexagonal-architecture/`.

## adapter (bộ chuyển — Hexagonal)
- **Là gì:** bản cài CỤ THỂ của một port, nối với thế giới ngoài (camera, file, nguồn giả).
- **Để làm gì:** hiện thực hợp đồng port bằng công nghệ cụ thể (OpenCV, RTSP, numpy...).
- **Ví von:** cái phích cụ thể cắm vào ổ chuẩn (port).

## Protocol (typing.Protocol)
- **Là gì:** cách khai báo "hợp đồng" trong Python theo **structural typing** — lớp nào CÓ ĐỦ method đúng dạng là "khớp", KHÔNG cần kế thừa.
- **Để làm gì:** định nghĩa port (vd IFrameSource) mà adapter không phải `class A(IFrameSource)`.
- **Ví von:** "ai biết bơi thì xuống nước" — không cần thẻ hội viên, cứ bơi được là đạt.
- **Đừng nhầm:** khác kế thừa (inheritance) — Protocol dựa trên "có đúng hình dạng", không dựa "thuộc dòng họ nào".

## fixture (pytest)
- **Là gì:** hàm chuẩn bị dữ liệu/đối tượng cho test trong pytest, test "xin" bằng cách nhận tham số cùng tên.
- **Để làm gì:** dựng sẵn thứ cần test (vd 1 adapter đã setup) + dọn dẹp sau test.
- **Ví dụ:** `@pytest.fixture(params=[...])` → chạy test lặp cho mỗi param.

## pipeline (dây chuyền xử lý)
- **Là gì:** chuỗi các bước (stage) nối tiếp: đầu ra bước này là đầu vào bước kia.
- **Để làm gì:** xử lý frame qua nhiều công đoạn (chỉnh sáng → lọc → suy luận → gửi) một cách có trật tự.
- **Ví von:** dây chuyền nhà máy: mỗi trạm làm 1 việc rồi chuyền sang trạm sau.

## stage (bước xử lý)
- **Là gì:** một bước trong pipeline — nhận 1 packet, trả 1 packet (hoặc skip/lỗi).
- **Để làm gì:** đóng gói 1 việc nhỏ (vd tính độ sáng) thành đơn vị ráp được.
- **Ví von:** một trạm trên dây chuyền.

## ABC (Abstract Base Class)
- **Là gì:** "lớp cha trừu tượng" — định nghĩa khung chung + bắt buộc lớp con cài một số method (`@abstractmethod`).
- **Để làm gì:** chia sẻ code chung (scaffold) + ép lớp con phải cài phần riêng.
- **Đừng nhầm:** ABC dựa **kế thừa** (nominal); `Protocol` dựa **hình dạng** (structural). Hai cách khác nhau.

## Template Method (mẫu thiết kế)
- **Là gì:** lớp cha viết sẵn "khung quy trình" (gọi các bước), chừa 1 bước cho lớp con điền (`_do_process`).
- **Để làm gì:** phần chung (bắt lỗi, đo thời gian...) viết 1 lần ở cha; lớp con chỉ lo phần riêng.
- **Ví von:** mẫu đơn in sẵn, chỉ chừa vài ô trống để điền.

## context manager (with statement)
- **Là gì:** đối tượng dùng được với `with ...:` — tự chạy "vào" (`__enter__`) + "ra" (`__exit__`) kể cả khi có lỗi giữa chừng.
- **Để làm gì:** đảm bảo dọn dẹp (đóng file, teardown) LUÔN chạy, không quên.
- **Ví von:** cửa tự đóng — vào thì mở, ra (kể cả chạy vội) thì tự đóng lại.

## result object (đối tượng kết quả)
- **Là gì:** trả về một ĐỐI TƯỢNG mang trạng thái rõ ràng (SUCCESS/SKIPPED/ERROR...) thay vì trả `None`/giá trị trần.
- **Để làm gì:** phân biệt các kết cục khác nhau (vd "bỏ cố ý" vs "lỗi") để xử lý đúng.
- **Đừng nhầm:** khác trả `None` (mơ hồ) hay ném exception (mất phân biệt).
