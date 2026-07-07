"""Task 4 (sub-spec config-declarative): property-based tests cho parse (Property 1 + 4).

_Requirements: 1.1, 1.2, 3.2_
Property 1: round-trip parse (dict hợp lệ → AppConfig phản ánh đúng số/thứ tự/params).
Property 4: immutability (AppConfig.pipelines là tuple; params read-only).
"""
from __future__ import annotations

from hypothesis import given, strategies as st

from vision_platform.application.config_loader import parse_app_config


_params = st.dictionaries(
    st.text(alphabet="abcdefghijklmnop_", min_size=1, max_size=5),
    st.one_of(st.integers(-1000, 1000), st.text(max_size=6), st.booleans()),
    max_size=3,
)
_stage = st.fixed_dictionaries({"type": st.sampled_from(["detect", "count", "custom"])})


@st.composite
def _valid_config(draw):
    ids = draw(st.lists(st.text(alphabet="abcdef0123456789", min_size=1, max_size=5),
                        unique=True, max_size=4))
    pipelines = []
    for pid in ids:
        p = {
            "id": pid,
            "source": {"type": draw(st.sampled_from(["fake", "noise", "video"])),
                       "params": draw(_params)},
            "stages": draw(st.lists(_stage, max_size=4)),
        }
        if draw(st.booleans()):
            p["max_frames"] = draw(st.integers(1, 500))
        pipelines.append(p)
    return {"pipelines": pipelines}, ids


@given(_valid_config())
def test_roundtrip_reflects_structure(data):
    raw, ids = data
    app = parse_app_config(raw)
    # Property 1: số + thứ tự id giữ nguyên
    assert [p.id for p in app.pipelines] == ids
    for pcfg, praw in zip(app.pipelines, raw["pipelines"]):
        assert pcfg.source.type == praw["source"]["type"]
        assert dict(pcfg.source.params) == praw["source"]["params"]
        assert [s.type for s in pcfg.stages] == [s["type"] for s in praw["stages"]]


@given(_valid_config())
def test_parsed_is_immutable(data):
    raw, _ = data
    app = parse_app_config(raw)
    # Property 4: pipelines là tuple; params read-only
    assert isinstance(app.pipelines, tuple)
    for pcfg in app.pipelines:
        assert isinstance(pcfg.stages, tuple) and isinstance(pcfg.sinks, tuple)
        try:
            pcfg.source.params["_x"] = 1  # MappingProxyType → phải nổ
            raise AssertionError("params đáng lẽ read-only")
        except TypeError:
            pass
