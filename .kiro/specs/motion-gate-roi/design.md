# Design Document — motion-gate-roi (ROI-mask + bền-illumination)

## Overview

Đóng K-063: motion-gate v1 (`changed_ratio` full-frame) coi đổi-sáng-đều-toàn-cục là chuyển động → gate mở nhầm →
phí GPU. Thêm 2 cải tiến numpy-thuần, ĐỘC LẬP, opt-in (mặc định TẮT = v1 nguyên vẹn): (1) **ROI-mask** (chỉ đo
trong vùng quan tâm); (2) **bền-illumination** (mean-subtraction triệt đổi-sáng-đều). ADDITIVE tuyệt đối, giữ
baseline **521/1 · lint 5/0**. KHÔNG code ở PHA này (cần video thật để tune ngưỡng → code sau khi có).

**Lý do gốc (đại số, kiểm chứng được):** đổi-sáng-đều nghĩa là `curr = prev + c` (c = hằng số cộng mọi pixel).
- v1: `|curr - prev| = |c|`. Nếu `|c| > pixel_diff_threshold` → MỌI pixel "đổi" → `ratio ≈ 1` → FALSE motion (lỗi K-063).
- Mean-subtraction: `curr' = curr - mean(curr) = (prev + c) - (mean(prev) + c) = prev - mean(prev) = prev'`.
  → `d = curr' - prev' = 0` mọi pixel → `ratio = 0` → SKIP đúng. Chuyển động CỤC BỘ: chỉ vùng đổi lệch mean →
  `d ≠ 0` ở vùng đó → phát hiện. (Chứng minh này là nền của Property 2.)

## Bằng chứng code đã đọc (chống bịa)
- `domain/motion.py::changed_ratio(prev, curr, pixel_diff_threshold) -> float`: cast int16, `count_nonzero(|diff|>thr)/diff.size`, guard `prev.shape==curr.shape` (raise nếu khác), `diff.size==0 → 0.0`.
- `runtime/stages/motion_gate_stage.py::MotionGateStage(*, pixel_diff_threshold=25, min_area_ratio=0.005, max_consecutive_skip=0)`: stateful `_prev`, camera-affinity `_source_id` (fail-fast), first-frame/đổi-shape → đi tiếp + set mốc, `SkipFrameSignal` khi `ratio < min_area_ratio`, `max_consecutive_skip` ép đi tiếp. `_do_process` đọc `packet.media_ref.array`.
- Đăng ký config: `pipeline_factory` builder + `allowed_params` (K-046). CLI ở profile.

## Architecture

Thay đổi này KHÔNG thêm layer mới — nó mở rộng đúng 3 tầng có sẵn, giữ nguyên hướng phụ thuộc
hexagonal (`domain` ← `runtime` ← `profiles`). Không tầng nào đảo chiều; không import mới xuyên biên.

```
profiles/pipeline_factory (builder motion_gate) + CLI (--motion-roi / --motion-illum-robust)
        │  (đọc config → dựng)
        ▼
runtime/stages/MotionGateStage  (stateful: _prev, _mask lazy, camera-affinity)
        │  (gọi hàm thuần, truyền mask + cờ)
        ▼
domain/motion.py  changed_ratio(prev, curr, thr, *, mask, illumination_robust)
                  roi_mask(H, W, x, y, w, h) -> ndarray[bool]
        (numpy thuần — KHÔNG cv2/torch)
```

- **Luồng dữ liệu 1 frame:** `MediaPacket` → `MotionGateStage._do_process` đọc `packet.media_ref.array`
  → (frame đầu / đổi-shape) dựng `_mask` từ `roi` nếu có → gọi `changed_ratio(prev, curr, thr, mask, illum)`
  → so `min_area_ratio` → SKIP (`SkipFrameSignal`) hoặc đi tiếp (detector chạy).
- **Điểm mở tương lai (ghi, KHÔNG làm giờ):** metric nền nâng cao (MOG2/KNN) cần `cv2` → thuộc `adapters`;
  nếu cần, `MotionGateStage` sẽ nhận metric qua DI (port ở `kernel`), KHÔNG kéo cv2 vào domain. YAGNI: chưa cần.
- **Bất biến ranh giới:** `domain` chỉ numpy; import-linter contract 6-layer giữ 5 kept/0 broken.

## Data Models

Không thêm DTO ở `kernel`. Các "mô hình dữ liệu" ở đây là kiểu tham số/giá trị nội bộ, thuần numpy/tuple:

| Tên | Kiểu | Ràng buộc | Dùng ở |
|---|---|---|---|
| `roi` | `tuple[float, float, float, float] \| None` (x, y, w, h) | mỗi giá trị ∈ [0,1]; `w>0`, `h>0`; `x+w<=1`, `y+h<=1`; None = toàn frame | config/CLI → `MotionGateStage.__init__` |
| `mask` | `np.ndarray[bool]` shape (H, W) hoặc None | True = pixel trong ROI; dựng LAZY khi biết shape frame | `MotionGateStage._mask` → `changed_ratio(mask=...)` |
| `illumination_robust` | `bool` | default `False` = hiệu thô v1 | config/CLI → stage → `changed_ratio` |
| `motion_ratio` (kết quả) | `float` ∈ [0,1] | tỉ lệ pixel đổi trong vùng xét (mask nếu có, else toàn frame) | so `min_area_ratio` |

- `changed_ratio` mở rộng giữ CHỮ KÝ CŨ tương thích: 3 tham số vị trí `(prev, curr, pixel_diff_threshold)`
  không đổi; `mask`/`illumination_robust` là **keyword-only optional** (default None/False) → gọi kiểu cũ ra kết quả y hệt v1.
- `roi_mask` là hàm THUẦN (không state): (H, W, x, y, w, h) → ndarray bool; raise `ValueError` nếu ROI không hợp lệ (xem Error Handling).

## Components and Interfaces

### 1. domain/motion.py — mở rộng `changed_ratio` (ADDITIVE, giữ chữ ký cũ)
```
def changed_ratio(prev, curr, pixel_diff_threshold, *, mask=None, illumination_robust=False) -> float:
    # (giữ guard shape + int16 như cũ)
    if prev.shape != curr.shape: raise ValueError(...)   # guard v1 giữ nguyên
    a = prev.astype(int16); b = curr.astype(int16)
    # THỨ TỰ QUAN TRỌNG (fix Lỗ-review-1): THU VỀ VÙNG ROI TRƯỚC, RỒI mới mean-subtraction —
    # để mean là mean TRONG vùng xét (nhất quán "triệt uniform-shift trong ROI"; tránh đổi-sáng
    # ngoài ROI kéo mean toàn-frame → trừ sai → tạo motion GIẢ trong ROI).
    if mask is not None:
        a = a[mask]; b = b[mask]        # mask bool (H,W) áp lên (H,W) hoặc (H,W,C) → giữ kênh C; flatten pixel ROI
    if illumination_robust:
        a = a - a.mean(); b = b - b.mean()   # mean-subtraction TRÊN VÙNG ĐANG XÉT (triệt uniform shift — Property 2)
    if a.size == 0: return 0.0          # ROI rỗng / mảng rỗng → 0 (guard)
    diff = np.abs(b - a)                # sau mean-sub: dtype float; so với threshold (int) OK
    return count_nonzero(diff > pixel_diff_threshold) / diff.size
```
- `mask`/`illumination_robust` optional → default None/False → nhánh mask/illum bị bỏ → **kết quả y hệt v1** (Property 5 backward-compat).
- `mask` là bool ndarray shape **(H, W)**; numpy boolean-index `a[mask]` áp lên (H,W) hoặc (H,W,C) đều cho mảng phẳng các pixel ROI (giữ trục kênh C). Thuần numpy.
- **dtype:** cast `int16` (chống underflow uint8 như v1); sau `mean-subtraction` mảng thành float64 (mean trả float) — `diff` float, so `> pixel_diff_threshold` (int) hợp lệ, threshold vẫn là "độ lệch pixel". KHÔNG illum → giữ int16 như v1 (kết quả bit-khớp v1).
- **Mẫu số** = số phần tử của vùng xét: có mask → `a[mask].size` (pixel ROI × C); không mask → `diff.size` (toàn frame) — đúng R1.1.

### 2. domain — validate ROI + xây ROI-mask (TÁCH 2 TẦNG — fix Lỗ-review-2 fail-fast)
Tách kiểm-tra thành 2 hàm theo cái CẦN gì: range [0,1] là THUẦN SỐ (không cần shape) → kiểm được lúc
parse config (fail-fast sớm, R4.3); "rỗng sau khi quy pixel" cần shape → kiểm lúc dựng mask (runtime, R1.3).
```
def validate_roi(x, y, w, h) -> None:            # THUẦN SỐ — gọi được ở builder/validate_config (config-time)
    if not (0<=x<=1 and 0<=y<=1 and w>0 and h>0 and x+w<=1 and y+h<=1):
        raise ValueError("ROI phải ∈[0,1], w>0,h>0, x+w<=1, y+h<=1")   # R1.3 (range) — fail-fast SỚM

def roi_mask(height, width, x, y, w, h) -> np.ndarray[bool]:   # CẦN shape → runtime frame đầu
    validate_roi(x, y, w, h)                     # kiểm range lại (phòng gọi trực tiếp)
    px0=round(x*width); py0=round(y*height); px1=round((x+w)*width); py1=round((y+h)*height)
    if px1<=px0 or py1<=py0:                      # rỗng sau quy pixel (vd ROI cực nhỏ trên frame nhỏ) — cần shape
        raise ValueError("ROI rỗng sau khi quy về pixel")     # R1.3 (rỗng-pixel)
    m = zeros((height,width), bool); m[py0:py1, px0:px1] = True; return m
```
- **Nơi gọi:** builder `motion_gate` (profiles) gọi `validate_roi` NGAY lúc parse → `ConfigError` trước khi pipeline chạy (đóng khoảng hở: trước đây validate nằm trong roi_mask chỉ chạy frame-đầu-runtime). `MotionGateStage` gọi `roi_mask` lazy frame đầu (bắt nốt lỗi rỗng-pixel cần shape).
- Chuẩn-hoá [0,1] → độc-lập-độ-phân-giải (R1.2). Thuần numpy, ở domain.

### 3. runtime/stages/MotionGateStage — thêm param optional (giữ mọi edge v1)
- `__init__(..., roi: tuple[float,float,float,float] | None = None, illumination_robust: bool = False)` — nếu `roi` set → gọi `validate_roi(*roi)` NGAY trong `__init__` (fail-fast range kể cả khi dựng stage trực tiếp, không đợi frame đầu; nhất quán với builder).
- `_mask: Optional[np.ndarray] = None` — xây LAZY ở frame đầu (khi biết shape thật): nếu `roi` set → `roi_mask(H,W,*roi)`; đổi-shape → xây lại mask (CÙNG nhánh reset `_prev` đã có: `self._prev is None or shape khác`).
- `_do_process`: gọi `changed_ratio(self._prev, curr, thr, mask=self._mask, illumination_robust=self._illum)`. Mọi logic khác (camera-affinity, first-frame → `motion_ratio=1.0`, `min_area_ratio`, `max_consecutive_skip`/`motion_forced`, artifacts) GIỮ NGUYÊN.
- Lỗi rỗng-pixel (roi_mask raise ở frame đầu) → propagate ValueError → StageResult.ERROR (fail-fast, R1.3).

### 4. profiles/pipeline_factory + CLI (deploy-by-config)
- Builder `motion_gate`: `allowed_params` (hiện `{pixel_diff_threshold, min_area_ratio, max_consecutive_skip}` — đã đọc code) THÊM `roi`, `illumination_robust`. Parse `roi` (list 4 số) → tuple + gọi `validate_roi` NGAY (range fail-fast); sai kiểu/độ dài/range → `ConfigError` (R4.3, fix Lỗ-review-2). KHÔNG sửa build_runner/validate_config/schema (đúng extension point D-042).
- CLI (giữ prefix `--motion-gate-*` nhất quán với `--motion-gate`, `--motion-gate-max-skip` đã có — fix Lỗ-review-3): `--motion-gate-roi "x,y,w,h"` (parse 4 float) + `--motion-gate-illum-robust` (flag). Mặc định None/False.

## Correctness Properties

### Property 1: ROI giới hạn vùng đo
Với ROI cấu hình, `motion_ratio` chỉ tính pixel trong mask; đổi NGOÀI ROI (trong ROI tĩnh) → ratio dưới ngưỡng → SKIP.

**Validates: Requirements 1.1, 1.4**

### Property 2: Bền đổi-sáng-đều (đại số)
Khi `curr = prev + c` (c hằng số) và bật illumination_robust → `motion_ratio == 0` → SKIP (không chạy detector oan).

**Validates: Requirements 2.1, 2.3**

### Property 3: Vẫn phát hiện chuyển động cục bộ
Bật illumination_robust, có vùng đổi cục bộ (khác phần còn lại) → `motion_ratio > 0` → đi tiếp (không nuốt vật thật).

**Validates: Requirements 2.2**

### Property 4: ROI fail-fast
ROI ngoài [0,1] / w,h<=0 / rỗng-sau-pixel → ValueError (config → ConfigError) TRƯỚC khi đo — không đo sai im lặng.

**Validates: Requirements 1.3, 4.3**

### Property 5: Backward-compat tuyệt đối
Không mask + không illumination_robust → `changed_ratio` trả kết quả BẰNG v1 (cùng input) → gate hành vi y hệt.

**Validates: Requirements 2.4, 3.1, 3.4**

### Property 6: Ranh giới layer + additive
domain chỉ numpy (không cv2/torch); không sửa BaseStage/executor/DetectStage/runner; lint 5/0; baseline 521/1 giữ (+ test mới).

**Validates: Requirements 3.3, 3.4**

### Property 7: ROI × illumination — mean tính TRONG vùng xét (thứ tự đúng)
Khi ROI + illumination_robust cùng bật, mean-subtraction dùng mean TRONG ROI (mask-trước-mean-sub): đổi-sáng-đều
CHỈ xảy ra NGOÀI ROI (ROI tĩnh) → `motion_ratio ≈ 0` trong ROI (không bị đổi-sáng-ngoài kéo mean → không tạo motion giả).

**Validates: Requirements 1.1, 2.1, 2.3**

## Error Handling

Mọi lỗi cấu hình bị bắt SỚM (fail-fast), không đo sai âm thầm:

| Tình huống | Nơi phát hiện | Hành vi | Map |
|---|---|---|---|
| ROI ngoài [0,1] / `w<=0` / `h<=0` / `x+w>1` / `y+h>1` (range, THUẦN SỐ) | `validate_roi` — gọi ở builder lúc parse (config-time) **và** trong `roi_mask` | raise `ValueError` → builder bọc `ConfigError` (fail-fast SỚM) | R1.3, R4.3, P4 |
| ROI rỗng sau khi quy về pixel (`px1<=px0` / `py1<=py0`) — CẦN shape | `roi_mask` (domain, runtime frame đầu) | raise `ValueError` → StageResult.ERROR | R1.3, P4 |
| `roi` sai kiểu/độ dài ở config (không phải 4 số) | builder `motion_gate` (profiles) | raise `ConfigError` (bọc từ parse) | R4.3, P4 |
| Key params lạ ở config | `_check_params` (K-046, có sẵn) | raise `ConfigError` fail-fast | R4.1 |
| `prev.shape != curr.shape` (đổi độ phân giải giữa chừng) | `changed_ratio` (đã có ở v1) | raise → stage bắt ở nhánh đổi-shape → reset `_prev` + dựng lại `_mask` + đi tiếp | 3.2 (giữ edge v1) |

- Trình tự: ROI được validate LAZY ở frame ĐẦU (lúc dựng `_mask`) — lỗi ROI → `ValueError` propagate lên
  `StageResult.ERROR` (fail-fast, không nuốt). Với config-path, parse ROI xảy ra lúc build → `ConfigError`
  báo trước khi chạy pipeline (không để pipeline khởi động rồi mới chết).
- KHÔNG bắt rộng nuốt lỗi: chỉ chuyển `ValueError` ROI thành thông điệp rõ; các lỗi khác để nổi (đúng luật fail-fast).

## Testing Strategy
- **ROI (numpy dựng tay):** frame nền tĩnh; đổi 1 ô TRONG ROI → ratio>ngưỡng (đi tiếp); đổi 1 ô NGOÀI ROI (ROI tĩnh) → ratio~0 (SKIP); kiểm mẫu số = số pixel ROI (×C nếu có kênh).
- **Illumination (đại số + numpy):** `curr = prev + 40` (uniform) + illum-robust → ratio==0; đối chứng KHÔNG illum-robust → ratio~1 (chứng minh K-063 + cải tiến sửa). Vật cục bộ + illum-robust → ratio>0.
- **ROI × illumination cùng bật (test THỨ TỰ — fix Lỗ-review-1):** đổi-sáng-đều CHỈ NGOÀI ROI + ROI tĩnh + illum-robust → ratio~0 trong ROI (vì mean tính TRONG ROI, đổi-sáng ngoài không kéo mean ROI). Chứng minh mask-trước-mean-sub đúng, mean-toàn-frame-trước sẽ SAI test này.
- **Backward-compat:** loạt `(prev,curr,thr)` gọi `changed_ratio` cũ vs mới-không-tham-số → BẰNG NHAU, cùng dtype path int16 (property-based Hypothesis, xác định).
- **Validate 2 tầng (fix Lỗ-review-2):** `validate_roi` range sai → ValueError/ConfigError lúc BUILD (không cần frame); `roi_mask` rỗng-pixel → ValueError lúc frame đầu (cần shape). Test cả 2 điểm.
- **Stage/config/CLI:** first-frame/đổi-shape/camera-affinity giữ (tái dùng test v1); ROI range sai → ConfigError SỚM; bật qua config (`roi`/`illumination_robust`) + CLI (`--motion-gate-roi`/`--motion-gate-illum-robust`) → dựng đúng chuỗi.
- **Baseline:** full `pytest -q` ≥ 521 passed (+ test mới) / 1 skipped; lint `importlinter.api` 5 kept/0 broken.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** giảm-false-motion (tiết kiệm GPU) ⟂ không-nuốt-vật-thật (an toàn giám sát) ⟂ đơn-giản-numpy (domain thuần, no cv2) ⟂ backward-compat. Mean-subtraction cân được: triệt uniform (giảm false) mà giữ local (không nuốt thật).
- **What varies?** cách đo "đổi thật vs nhiễu sáng" — trừu tượng đúng chỗ là THAM SỐ metric (raw vs mean-sub), không phải class-hierarchy. Giữ 1 hàm + cờ (YAGNI).
- **Which way deps point?** domain (motion math) ← runtime (stage) ← profiles (config/CLI). Không đảo. cv2-based (MOG2) sẽ ở adapters — nếu cần metric cv2, MotionGate nhận metric qua DI (port) — GHI để sau, KHÔNG làm giờ (chưa cần).
- **Cái GIÁ:** mean-subtraction thêm 2 phép `.mean()` + trừ broadcast/frame (rẻ, O(pixels), vẫn CPU-nhẹ so với inference). ROI-mask thêm 1 boolean-index (rẻ).
- **Khi nào KHÔNG dùng:** (a) đổi-sáng KHÔNG-đều (bóng mây loang, đèn quét) → mean-subtraction KHÔNG triệt hết → cần background-model (MOG2, cv2, adapters — Non-Goal). (b) camera rung/pan → cả frame dịch hình học → cả 2 cải tiến KHÔNG xử lý (cần stabilization). (c) ROI quá nhỏ → mẫu số nhỏ → 1 vật nhỏ cũng ratio cao (tune min_area_ratio theo ROI). GHI RÕ trong Non-Goal + R2.5 (không over-claim).
- **Recognize (dấu hiệu cần):** gate chạy detector liên tục lúc trời-tối-dần/bật-đèn dù cảnh vắng = triệu chứng K-063 → bật illumination_robust; nhiều trigger từ vùng-trời/cây = bật ROI.

## Non-Goals (nhắc lại)
MOG2/KNN background-model (cv2→adapters, sub-spec sau) · optical-flow · ROI đa-giác · ổn-định-camera (stabilization) ·
xử-lý-đổi-sáng-không-đều hoàn hảo.
