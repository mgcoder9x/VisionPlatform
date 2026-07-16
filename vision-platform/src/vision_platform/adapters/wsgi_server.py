"""adapters/wsgi_server.py — phục vụ WSGI app bằng server PRODUCTION (waitress) hoặc dev fallback.

Leaf adapter (kiến trúc §4): chỉ phụ thuộc stdlib + `waitress` (OPTIONAL, import bên trong nhánh). App WSGI +
host/port/threads được TIÊM vào — adapter không biết Flask/route, chỉ biết "nhận WSGI callable → phục vụ".

Vì sao tách khỏi profiles: composition-root chọn chế độ (dev/waitress/auto) tại 1 chỗ; test được nhánh chọn
server bằng cách tiêm module giả, không cần chạy server thật (spec web-production-hardening Wave 1, P1).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_VALID_SERVERS = ("auto", "waitress", "dev")

_DEV_WARNING = (
    "waitress chưa cài → đang dùng werkzeug DEV-SERVER (KHÔNG dùng cho production). "
    "Cài server production: pip install 'vision-platform[web-prod]' rồi chạy với --server waitress."
)


def serve_wsgi(app: Any, host: str, port: int, *, threads: int = 8, server: str = "auto") -> None:
    """Phục vụ `app` (WSGI callable, vd Flask app). BLOCKING (thay chỗ `app.run`).

    server:
      - "waitress": BẮT BUỘC waitress; thiếu → ImportError (fail-fast, chỉ dẫn cài).
      - "auto":     waitress nếu import được, else werkzeug dev-server + cảnh báo (R1.3).
      - "dev":      ép werkzeug dev-server (đường lui local/dev).
    Không nuốt lỗi bind (cổng bận → OSError raise từ server) — R1.4.
    """
    if server not in _VALID_SERVERS:
        raise ValueError(f"--server không hợp lệ: {server!r} (chọn: {'|'.join(_VALID_SERVERS)})")

    if server == "dev":
        _serve_dev(app, host, port)
        return

    if server == "waitress":
        _serve_waitress(app, host, port, threads)   # thiếu waitress → ImportError bên trong (fail-fast)
        return

    # server == "auto": ưu tiên waitress, fallback dev + cảnh báo
    try:
        import waitress  # noqa: F401  (chỉ kiểm khả dụng)
    except ImportError:
        logger.warning(_DEV_WARNING)
        _serve_dev(app, host, port)
        return
    _serve_waitress(app, host, port, threads)


def _serve_waitress(app: Any, host: str, port: int, threads: int) -> None:
    from waitress import serve   # optional-dep: import BÊN TRONG (thiếu → ImportError chỉ dẫn cài extra web-prod)
    logger.info("phục vụ bằng waitress host=%s port=%s threads=%s (production WSGI)", host, port, threads)
    serve(app, host=host, port=port, threads=threads)


def _serve_dev(app: Any, host: str, port: int) -> None:
    # werkzeug dev-server qua Flask app.run (giữ threaded=True như hành vi cũ — tương thích ngược R4.1)
    app.run(host=host, port=port, threaded=True)
