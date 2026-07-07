# Vision Platform — web UI container (Linux). CHẠY TRÊN LINUX/DOCKER của bạn.
# Vì sao Linux: ffmpeg Linux xử lý RTSP digest (Dahua) OK — Windows bản này vướng 401 (K-030).
# Detector: dùng ONNX (onnxruntime, sạch) — export .pt(YOLOv5)→.onnx ở env syn trước rồi mount vào /app/models.
#
# ⚠️ CHƯA build/verify tại máy phát triển (không có docker ở đó). Cần bạn build trên Linux.
FROM python:3.11-slim

# ffmpeg: RTSP; libgl1/libglib2: opencv-python-headless cần.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Cài package + runtime web/inference (headless: KHÔNG cần GUI trong container).
RUN pip install --no-cache-dir . onnxruntime flask opencv-python-headless

EXPOSE 8000

# Mặc định synthetic (đổi command trong compose để dùng --rtsp + --onnx).
CMD ["python", "-m", "vision_platform.profiles.vision_web_app", "--host", "0.0.0.0", "--port", "8000"]
