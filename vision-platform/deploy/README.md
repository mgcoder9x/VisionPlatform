# Deploy — Web UI container (Linux)

> **Trạng thái:** artifact CHƯA build/verify (máy phát triển KHÔNG có docker). Bạn build trên Linux/Docker.
> Web UI đã verify chạy TRỰC TIẾP (không docker) trên máy dev: `http://127.0.0.1:8000/` phát MJPEG + box.

## Vì sao Docker + Linux
- **RTSP:** ffmpeg trên Linux xử lý digest-auth camera Dahua OK. Windows bản dev vướng `401` (K-030) dù VLC chạy được.
- **Model:** chạy inference bằng **ONNX (onnxruntime)** — sạch, không kéo torch/yolov5(GPL) vào runtime.

## Chuẩn bị (1 lần)
1. **Export weight** `.pt` (YOLOv5) → `.onnx` TRONG env syn (đúng version torch/yolov5):
   ```
   cd <syn>; python -m sources.yolov5.export --weights resources/weight/last_vehicle_n_640_04052024_dr.pt \
       --include onnx --imgsz 640 --opset 12
   ```
   → copy file `.onnx` vào `vision-platform/models/`.
2. (Kiểm layout) sau khi có `.onnx`, đối chiếu: `describe_onnx(path)` — nếu output `[1,N,5+nc]` (có objectness) →
   dùng `--yolo v5` (mặc định, gọi `yolov5_decode`). Nếu là v8 `[1,4+nc,N]` → `--yolo v8`. Web/demo app đã hỗ trợ cờ `--yolo`.

## Chạy
```
RTSP_URL="rtsp://admin:MATKHAU@192.168.120.101:554/cam/realmonitor?channel=1&subtype=0" \
  docker compose -f deploy/docker-compose.yml up --build
```
→ mở `http://<host>:8000/`.

## Bảo mật (hoãn theo yêu cầu, nhưng GHI để nhớ)
- KHÔNG hardcode mật khẩu RTSP/secret vào image/compose — dùng env/secret (đã để `${RTSP_URL}`).
- Web dev-server Flask chỉ nội bộ; production để sau nginx + auth.
- ĐỔI các secret đã lộ trong config syn (K-031).


---

## Chạy LIVE trong WSL — ĐÃ VERIFY CHẠY THẬT (2026-07-05, không cần Docker)

> Máy dev có **WSL2 Ubuntu + GPU RTX 2060**. Đã chạy thật: RTSP camera → YOLOv5 → Web UI tách-luồng, ~15fps.
> RTSP 401 trước đó CHỈ do SAI MẬT KHẨU (`L2B40AD07`→đúng `L2B40AD7`) — KHÔNG phải ffmpeg/OS (K-030/K-034).

### Dựng env WSL (1 lần, KHÔNG cần sudo)
```bash
# get-pip (Ubuntu strip ensurepip) → virtualenv → cài gói (opencv mang ffmpeg bundled)
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py --user --break-system-packages
python3 -m pip install --user --break-system-packages virtualenv
python3 -m virtualenv ~/vpvenv
~/vpvenv/bin/pip install opencv-python-headless numpy flask yolov5   # yolov5 kéo torch (CUDA cu13x)
```
Weight COCO test: `curl -fsSL -o models/yolov5n.pt https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.pt`

### Chạy Web UI LIVE (GPU, sub-stream, tách luồng)
```bash
cd <repo>/vision-platform
OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp' PYTHONPATH=src ~/vpvenv/bin/python \
  -m vision_platform.profiles.vision_web_app --host 0.0.0.0 --port 8000 \
  --rtsp 'rtsp://admin:<MATKHAU>@192.168.120.101:554/cam/realmonitor?channel=1&subtype=1' \
  --pt models/yolov5n.pt --device cuda --conf 0.35
```
- Mở browser (Windows): `http://localhost:8000/` (WSL2 tự forward localhost).
- `--device cuda` = GPU (yolov5 tự map "cuda"→"cuda:0"); `subtype=1` = sub-stream nhẹ; `--pace 0` full fps.
- Weight YOLOv5 của bạn: `--pt models/<ten>.pt --yolo v5` (đã có --yolo v5/v8).
- ⚠️ KHÔNG hardcode mật khẩu vào file — chỉ điền lúc chạy; đổi secret đã lộ (K-031).

### Kiểm nhanh (không mở browser)
```bash
curl -s http://127.0.0.1:8000/stats   # video=<n> · detect=<n> · boxes=<k>
curl -s http://127.0.0.1:8000/boxes   # JSON bbox chuẩn hoá 0–1
```
