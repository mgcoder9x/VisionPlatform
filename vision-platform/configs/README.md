# configs/ — chạy pipeline bằng file khai báo (declarative)

Chạy qua: `python -m vision_platform.profiles.vision_slice_app --config configs/<file>.toml`
(source → detect → count → sink, dựng từ file, KHÔNG sửa code cho từng camera).

## Các file mẫu
| File | Cần gì | Dùng khi |
|---|---|---|
| `example_fake.toml` | Không GPU, không camera | Smoke test — chạy mọi máy (kể cả máy này) |
| `example_video_gpu.toml` | **GPU** + `.[pt]` (torch) + file video + weights `.pt` | Nghiệm thu YOLOv5 trên video |
| `example_rtsp_gpu.toml` | **GPU** + `.[pt]` + camera RTSP | Khi có camera thật |

## Chạy trên MÁY GPU (WSL, RTX2060) — cho tối nay
1. Cài kèm nhóm `pt` (kéo torch + yolov5):
   ```bash
   pip install -e ".[pt]"        # trong venv của máy GPU (vd WSL ~/vpvenv)
   ```
2. Đặt weights + video đúng path trong file config (sửa `params.weights` / `params.path`).
3. Chạy:
   ```bash
   python -m vision_platform.profiles.vision_slice_app --config configs/example_video_gpu.toml
   ```
   → in summary mỗi pipeline ra stderr + ghi event vào `events/<id>.jsonl` (nếu có sink jsonl).

## Lưu ý
- **Máy dev (không GPU)** chỉ chạy được `example_fake.toml`. Config `pt` sẽ lỗi import torch nếu chưa cài `.[pt]`
  — đó là kỳ vọng (torch chỉ ở máy GPU). Các file GPU đã được test **parse hợp lệ** trên máy dev (không dựng detector).
- **Bảo mật (K-031):** KHÔNG ghi mật khẩu/URL production thật vào file config commit. Dùng placeholder + biến môi trường/secret store ở máy chạy.
- **v1 chạy các pipeline TUẦN TỰ** trong 1 tiến trình (đồng bộ). Chạy N camera SONG SONG (đa tiến trình/GPU-budget) là bước `scale-architecture` sau.
- Loại `type` hỗ trợ (registry mặc định): source={fake,noise,video,rtsp} · detector={fake,pt} · stages={detect,count} · sinks={jsonl}. Thêm loại = đăng ký registry (không sửa lõi).
