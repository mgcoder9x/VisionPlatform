# Bài #05b — Ring epoch switchover: đổi sang ring MỚI khi ring cũ hỏng dần · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đọc file này TRƯỚC các mẩu chi tiết. Đây là **phần nối tiếp #05**: bài #05 dựng frame bus + hardening,
> NHƯNG để lại 1 việc chưa ai làm — khi ring hỏng dần thì **chuyển sang ring mới thế nào cho an toàn**.
> Bám code thật ở `vision-platform/src/vision_platform/`: kernel `shm_control_plane_layout.py` · runtime/ipc
> `ring_control_plane.py`, `ring_pool.py`, `shm_frame_ring.py` · application `ring_supervisor.py`,
> `writer_epoch_coordinator.py`, `reader_epoch_coordinator.py`. Spec: `.kiro/specs/shm-ring-epoch-switchover/`.

---

## 1. Tổng quan — ta đang ở đâu
Bài #05: frame đi qua ranh giới process bằng **SHM ring buffer** (N slot dùng vòng), có hardening để không
"đứng bus" khi 1 process chết (slot hỏng bị đánh **QUARANTINED** = loại vĩnh viễn). Nhưng QUARANTINED tích lại
→ ring **cạn slot khỏe** dần. Bài #05 chỉ **phát tín hiệu** `shm_ring_rebuild_requested` khi số slot hỏng vượt
ngưỡng — **chưa ai xử lý tín hiệu đó**. Bài #05b làm nốt: **dựng ring mới (epoch mới) + cho writer/reader chuyển
sang an toàn + giải phóng ring cũ không rò rỉ.**

```
Ring epoch N (hỏng dần)                         Ring epoch N+1 (mới, đầy capacity)
[slot: QUARANTINED, QUARANTINED, DONE, FREE]    [slot: FREE, FREE, FREE, FREE]
        │  shm_ring_rebuild_requested                     ▲
        ▼                                                 │ publish(N+1, tên ring mới)
   RingSupervisor (application)  ──────────────────────────┘
        ▲ đọc/ghi "ring hiện tại là gì"
   [ Control-plane: 1 segment tên CỐ ĐỊNH chứa {epoch, tên-ring} ]
        ▲ poll                                   ▲ poll
   WriterEpochCoordinator                    ReaderEpochCoordinator
```

Thuật ngữ (gloss 1 dòng — đào sâu ở mẩu):
- **epoch (thế hệ ring):** số đếm tăng dần cho mỗi lần đổi ring (N → N+1). Ref cầm epoch cũ → biết là "đồ cũ".
- **switchover (chuyển ring):** hành động đổi từ ring epoch N sang N+1 khi ring cũ hỏng dần.
- **control-plane (mặt phẳng điều khiển):** 1 vùng SHM **tên cố định** ai cũng tìm được, chứa "ring hiện tại là cái nào (epoch + tên)". Tách khỏi "data-plane" (chỗ chứa frame thật).
- **supervisor (bộ điều phối):** thành phần DUY NHẤT quyết định switchover (ở tầng application), nhận tín hiệu rebuild → dựng ring mới → công bố (publish).
- **coordinator (bộ điều hướng writer/reader):** lớp bọc quanh writer/reader, tự phát hiện epoch đổi rồi chuyển ring.
- **stale-ref (con trỏ cũ):** ref stamp epoch N, sau switchover đọc ra `None` (không đọc nhầm ring cũ). (Nền có sẵn #05.)
- **ref-count / OS handle ref-count:** hệ điều hành tự đếm số "tay cầm" (handle) mở vào 1 vùng SHM; vùng chỉ bị xoá khi tay cầm CUỐI đóng.
- **pool (bể ring):** tập K ring dựng sẵn từ đầu, dùng xoay vòng — xem nhịp 3/4 (đây là mấu chốt).
- **mp.Lock:** khoá của thư viện `multiprocessing` Python; **chỉ truyền được cho process con lúc sinh (spawn)**, KHÔNG mở lại theo tên. (Đây là gốc rễ vấn đề — nhịp 2.)

File thật của #05b:
| Thành phần | Tầng | File |
|---|---|---|
| Layout control-plane segment (magic/version/epoch/ring_name) | kernel | `kernel/shm_control_plane_layout.py` |
| `RingControlPlane` (publish/read_current, fail-fast) | runtime/ipc | `runtime/ipc/ring_control_plane.py` |
| `RingPool` + `make_pool_opener` (K ring, cấp lock qua spawn) | runtime/ipc | `runtime/ipc/ring_pool.py` |
| `ShmRingBuffer.reset_for_reuse` (tái dùng ring) | runtime/ipc | `runtime/ipc/shm_frame_ring.py` |
| `RingSupervisor` (nhận rebuild → switchover) | application | `application/ring_supervisor.py` |
| `WriterEpochCoordinator` / `ReaderEpochCoordinator` | application | `application/writer_epoch_coordinator.py`, `reader_epoch_coordinator.py` |

## 2. Vấn đề & TẠI SAO nó là vấn đề (Forces)
Cần: khi ring epoch N hỏng dần, dựng ring N+1 và cho **writer + reader (ở các process KHÁC nhau)** chuyển sang.
Làm ngây thơ (naive) vấp ngay:
- **Làm sao 2 bên biết "ring hiện tại là cái nào"?** Tên ring #05 sinh bằng `new_ring_name()` = `uuid4().hex`
  (NGẪU NHIÊN — đọc `shm_frame_ring.py`), **không suy diễn được** từ epoch. → cần 1 nơi cố định ghi "tên ring hiện tại".
- **Nỗi đau GỐC (K-012):** ring mới sinh **lúc đang chạy**, nhưng mỗi slot cần 1 `mp.Lock` để đồng bộ. `mp.Lock`
  **chỉ truyền cho process con lúc spawn** (đã kiểm: `ShmRingBuffer(create=False)` bắt buộc nhận `slot_locks`;
  test `test_attach_without_locks_raises`). Process worker **đang chạy KHÔNG thể nhận khoá mới** cho ring mới →
  khoá/recovery trên ring mới **không hoạt động cross-process**. Đây là bức tường thật.
- **Rò rỉ (leak):** đổi ring nhiều lần mà không dọn → cạn RAM/`/dev/shm`.
- **Đọc nhầm ring cũ:** sau switchover, ref cũ phải hoá vô hiệu, nếu không → đọc frame rác.

**Lực giằng nhau:** *đổi ring linh hoạt lúc chạy* ↔ *khoá cross-process chỉ cấp được lúc spawn*.
(Đoán thử: nếu KHÔNG cấp được khoá mới lúc chạy, ta có thể **tránh** phải cấp khoá mới không?)

## 3. Khám phá nhiều hướng (≥2 cách — chi tiết ở `.kiro/specs/shm-ring-epoch-switchover/K-012-lock-provisioning-analysis.md`)
- **H1 — Khoá có TÊN (named OS primitive):** thay `mp.Lock` bằng khoá mở-được-theo-tên (Windows named mutex /
  POSIX `posix_ipc`). Được: ring mới lúc chạy vẫn khoá được. Mất: **thêm phụ thuộc + code theo nền tảng** +
  vòng đời khoá-có-tên (rò rỉ) + sửa MỌI chỗ khoá → rủi ro hồi quy cao.
- **H2 — Bể ring cấp sẵn (ring pool), tái dùng vòng:** dựng TRƯỚC K ring lúc khởi động, truyền **toàn bộ** khoá
  cho mọi worker **1 lần lúc spawn**; switchover = **tái dùng** 1 ring trong bể (reset + tăng epoch), KHÔNG cấp
  ring/khoá mới lúc chạy. Được: **không đụng cơ chế khoá** (dùng lại đồ đã kiểm) + hợp real-time (không cấp phát
  giữa luồng) + RAM đoán trước. Mất: giữ K× RAM; ring cũ phải "rút cạn" (drain) trước khi vòng lại tái dùng.
- **H3 — Bỏ khoá (lock-free):** chỉ dùng ghi atomic + kỷ luật. Nhẹ nhất nhưng phải **chứng minh atomicity đa
  process** (dính việc ARM chưa test) → rủi ro rất cao, mâu thuẫn quyết định #05 (đã chọn khoá).

## 4. Chốt giải pháp + TẠI SAO thắng → **H2 (ring pool)**
Chọn **H2** vì với sản phẩm 24/7 real-time: **né** vấn đề cấp-khoá-lúc-chạy thay vì đối đầu — giữ nguyên cơ chế
khoá + recovery **đã kiểm** của #05 (rủi ro thấp nhất), không cấp phát giữa luồng (không "khựng" hình), RAM
**đoán trước** = K ring. H1 để dành nếu sau cần vô số ring động (chưa cần); H3 là hướng dài hạn (gắn ARM).
Cái GIÁ đã chấp nhận (nói thật): H2 **đổi mô hình dọn dẹp** — ring không bị xoá khi đổi mà **giữ trong bể tới
khi tắt hệ** (teardown lúc shutdown). Đổi lại, "không rò rỉ" thành tính chất dễ chứng minh: **số ô nhớ KHÔNG
tăng theo số lần switchover** (luôn = K ring — đã test 20 lần switchover, tập segment không đổi).

Vì sao switchover an toàn (không đọc nhầm ring cũ): `epoch` được **đọc trực tiếp (live) từ control-plane** (đã
kiểm: `ring_epoch` là property đọc thẳng vùng SHM). Supervisor **publish epoch mới TRƯỚC** khi có frame epoch
mới nào tồn tại → writer/reader poll thấy kịp; ref epoch cũ → `None` (stale). Bằng chứng cuối: **T-B** — spawn
process writer THẬT, chuyển ring giữa chừng, process cha đọc được frame epoch mới cross-process (chạy 5/5 lần).

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự nhỏ nhất → xem `00-muc-luc.md`. (Mẩu chi tiết quote nguyên văn code + cite path.)

## 6. Nên làm / Nên tránh (cho bài #05b)
- **NÊN:** tách control-plane (tên cố định) khỏi data-plane (ring uuid); ghi **tên trước, epoch cuối** (authority
  atomic); publish epoch mới TRƯỚC khi writer ghi ring mới; check-on-write/read (kiểm epoch mỗi lần ghi/đọc);
  cấp **toàn bộ** khoá pool cho worker lúc spawn; `reset_for_reuse` tăng epoch **đơn điệu**.
- **TRÁNH:** tạo `mp.Lock` mới cho ring sinh lúc chạy (không truyền được cho worker đang chạy — K-012); đổi ring
  bằng cách tạo tên uuid mới rồi mong worker "đoán" ra (không suy diễn được); dọn ring giữa luồng theo kiểu đếm
  thủ công (đã bỏ — xem "quyết định B" ở journal); tin số frame-drop mà chưa đo dưới tải thật (Q2 = bound cấu trúc ≤ n_slots).
- **Giới hạn đã ghi rõ (CHƯA verify — không claim):** POSIX/Linux teardown `resource_tracker` (K-003, chỉ test
  Windows) · Q2 số-đo dưới tải thật (K-014) · ARM atomicity (K-001).

## Tự kiểm (đạt mới qua bài)
- Vì sao KHÔNG thể cấp `mp.Lock` mới cho ring sinh lúc chạy? (nêu đúng ràng buộc `create=False` cần `slot_locks`.)
- H2 "né" vấn đề đó bằng cách nào? Cái giá phải trả là gì (so H1)?
- Sau switchover, vì sao reader KHÔNG đọc nhầm ring cũ? "publish epoch trước" giúp gì về thứ tự?
- "Không rò rỉ" dưới H2 được chứng minh bằng tính chất nào (không cần soi /dev/shm)?

## Nguồn
- Code thật (đã đọc nguyên văn + test chạy thật, full **242 passed/1 skipped** · lint **5 kept/0 broken** · T-B 5/5):
  `kernel/shm_control_plane_layout.py`, `runtime/ipc/ring_control_plane.py`, `runtime/ipc/ring_pool.py`,
  `runtime/ipc/shm_frame_ring.py` (reset_for_reuse), `application/ring_supervisor.py`,
  `application/writer_epoch_coordinator.py`, `application/reader_epoch_coordinator.py`.
- Spec + phân tích: `.kiro/specs/shm-ring-epoch-switchover/` (design/requirements/tasks + `K-012-lock-provisioning-analysis.md` + `observability-taxonomy.md`).
- Truy vết quyết định: `ai-decision-journal/` (D-001..D-018, đặc biệt D-011..D-015 cho H2/K-012). · Độ chắc: cao (code + test chạy thật trên Windows); POSIX/ARM/Q2-tải = 🔴 chưa verify.
