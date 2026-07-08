"""Task 2.3 — ZmqInferenceClient set SNDHWM/RCVHWM TRƯỚC connect (A3, R6.1–6.3).

Không cần server (ZMQ connect-before-bind OK). Kiểm getsockopt sau setup() == cấu hình; teardown sạch.
"""
import zmq
import pytest

from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient


def test_hwm_applied_after_setup():
    client = ZmqInferenceClient("tcp://127.0.0.1:5599", sndhwm=7, rcvhwm=11)
    client.setup()
    try:
        assert client._sock.getsockopt(zmq.SNDHWM) == 7
        assert client._sock.getsockopt(zmq.RCVHWM) == 11
    finally:
        client.teardown()


def test_hwm_default_is_1000():
    client = ZmqInferenceClient("tcp://127.0.0.1:5598")
    client.setup()
    try:
        assert client._sock.getsockopt(zmq.SNDHWM) == 1000
        assert client._sock.getsockopt(zmq.RCVHWM) == 1000
    finally:
        client.teardown()


def test_hwm_below_one_rejected():
    with pytest.raises(ValueError):
        ZmqInferenceClient("tcp://127.0.0.1:5597", sndhwm=0)
    with pytest.raises(ValueError):
        ZmqInferenceClient("tcp://127.0.0.1:5597", rcvhwm=0)
