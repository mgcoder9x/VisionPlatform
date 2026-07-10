"""Test helper `wait_until` (spec test-stability-hardening, P8) — an-toàn-ngoại-lệ, xác định, KHÔNG spawn."""
from tests._wait_helpers import wait_until, log_text, log_line_count


def test_wait_until_true_immediately():
    assert wait_until(lambda: True, deadline_s=0.5) is True


def test_wait_until_false_at_deadline():
    assert wait_until(lambda: False, deadline_s=0.1, poll_s=0.01) is False


def test_wait_until_becomes_true():
    state = {"n": 0}
    def pred():
        state["n"] += 1
        return state["n"] >= 3
    assert wait_until(pred, deadline_s=1.0, poll_s=0.005) is True


def test_wait_until_predicate_raising_is_not_yet(tmp_path):
    """P8: predicate ném (vd đọc file CHƯA tạo) → coi 'chưa thoả', KHÔNG crash; True NGAY khi điều kiện tới."""
    log = tmp_path / "late.log"
    calls = {"n": 0}
    def pred():
        calls["n"] += 1
        if calls["n"] < 3:
            return "x" in open(log).read()   # FileNotFoundError 2 lần đầu (file chưa tạo)
        log.write_text("x\n")                 # tạo file → lần sau thoả
        return "x" in open(log).read()
    assert wait_until(pred, deadline_s=1.0, poll_s=0.005) is True


def test_wait_until_always_raising_returns_false():
    def pred():
        raise RuntimeError("luôn lỗi")
    assert wait_until(pred, deadline_s=0.1, poll_s=0.01) is False


def test_log_text_missing_file_returns_empty(tmp_path):
    assert log_text(tmp_path / "nope.log") == ""
    assert log_line_count(tmp_path / "nope.log") == 0


def test_log_helpers_read_content(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("alive_1\nalive_2\n\n")
    assert "alive_1" in log_text(p)
    assert log_line_count(p) == 2   # bỏ dòng rỗng
