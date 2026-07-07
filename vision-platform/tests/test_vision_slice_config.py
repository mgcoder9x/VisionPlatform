"""Task (a) integration: vision_slice_app chạy qua --config (đường declarative), NO-GPU.

_Requirements (config-declarative): 3.1, 3.2_ — end-to-end config→factory→runner trong profile thật.
"""
from __future__ import annotations

from vision_platform.profiles.vision_slice_app import main


def _write_cfg(tmp_path, body: str):
    p = tmp_path / "app.toml"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_config_path_runs_single_pipeline(tmp_path):
    cfg = _write_cfg(tmp_path, (
        '[[pipelines]]\n'
        'id = "cam-01"\n'
        'max_frames = 5\n'
        '[pipelines.source]\n'
        'type = "fake"\n'
        'params = { max_frames = 5 }\n'
        '[pipelines.detector]\n'
        'type = "fake"\n'
        'params = { model_size = 640 }\n'
        '[[pipelines.stages]]\n'
        'type = "detect"\n'
        '[[pipelines.stages]]\n'
        'type = "count"\n'
    ))
    assert main(["--config", cfg]) == 0


def test_config_path_runs_multiple_pipelines(tmp_path):
    cfg = _write_cfg(tmp_path, (
        '[[pipelines]]\n'
        'id = "a"\n'
        'max_frames = 3\n'
        '[pipelines.source]\n'
        'type = "noise"\n'
        'params = { max_frames = 3 }\n'
        '[[pipelines.stages]]\n'
        'type = "count"\n'
        '\n'
        '[[pipelines]]\n'
        'id = "b"\n'
        'max_frames = 2\n'
        '[pipelines.source]\n'
        'type = "fake"\n'
        'params = { max_frames = 2 }\n'
        '[[pipelines.stages]]\n'
        'type = "count"\n'
    ))
    assert main(["--config", cfg]) == 0


def test_argparse_path_unchanged(tmp_path):
    # KHÔNG có --config → đường cũ vẫn chạy (không phá base)
    assert main(["--source", "fake", "--detector", "fake", "--frames", "3"]) == 0


# --- K-045: bulkhead per-pipeline (1 pipeline lỗi KHÔNG kéo sập các pipeline khác) ---

_THREE_PIPELINES = (
    '[[pipelines]]\n'
    'id = "a-build-fails"\n'
    '[pipelines.source]\n'
    'type = "fake"\n'
    '[[pipelines.stages]]\n'
    'type = "count"\n'
    '\n'
    '[[pipelines]]\n'
    'id = "b-run-fails"\n'
    '[pipelines.source]\n'
    'type = "fake"\n'
    '[[pipelines.stages]]\n'
    'type = "count"\n'
    '\n'
    '[[pipelines]]\n'
    'id = "c-ok"\n'
    '[pipelines.source]\n'
    'type = "fake"\n'
    '[[pipelines.stages]]\n'
    'type = "count"\n'
)


def test_bulkhead_one_pipeline_failure_does_not_kill_others(tmp_path):
    """K-045: pipeline 'a' lỗi lúc BUILD + 'b' lỗi lúc RUN → 'c' VẪN chạy; return code non-zero."""
    from vision_platform.profiles.vision_slice_app import _run_from_config
    from vision_platform.runtime.pipeline_runner import RunStats

    cfg = _write_cfg(tmp_path, _THREE_PIPELINES)
    ran: list[str] = []

    class _FailRunRunner:
        def run(self, *, max_frames=None):
            raise RuntimeError("run boom")

    class _OkRunner:
        def run(self, *, max_frames=None):
            ran.append("c-ok")
            return RunStats(frames_read=1, processed=1)

    def fake_build(pcfg):
        if pcfg.id == "a-build-fails":
            raise RuntimeError("build boom")
        if pcfg.id == "b-run-fails":
            return _FailRunRunner()
        return _OkRunner()

    rc = _run_from_config(cfg, build=fake_build)
    assert ran == ["c-ok"]   # c chạy dù a (build) + b (run) đã ném lỗi trước đó
    assert rc == 1           # có lỗi một phần → KHÔNG được báo thành công (0)


def test_bulkhead_all_ok_returns_zero(tmp_path):
    """Mọi pipeline ok → return 0 (giữ tương thích hành vi thành công)."""
    from vision_platform.profiles.vision_slice_app import _run_from_config
    from vision_platform.runtime.pipeline_runner import RunStats

    cfg = _write_cfg(tmp_path, _THREE_PIPELINES)

    class _OkRunner:
        def run(self, *, max_frames=None):
            return RunStats()

    rc = _run_from_config(cfg, build=lambda pcfg: _OkRunner())
    assert rc == 0
