import pytest

from core.pagination import GraphCursorState, InvalidCursorError, decode_cursor, encode_cursor


def _state(**overrides) -> GraphCursorState:
    defaults = dict(
        seeds=("openalex|10.1/x",),
        direction="both",
        max_depth=2,
        max_nodes_per_level=10,
        max_total_nodes=100,
        frontier=("openalex\x1f10.1/x\x1fsha256:abc",),
        visited=("sha256:abc",),
        depth_reached=0,
        total_nodes_emitted=1,
    )
    defaults.update(overrides)
    return GraphCursorState(**defaults)


def test_roundtrip():
    state = _state()
    cursor = encode_cursor("secret", state)
    decoded = decode_cursor("secret", cursor)
    assert decoded == state


def test_tampered_signature_rejected():
    state = _state()
    cursor = encode_cursor("secret", state)
    tampered = cursor[:-4] + ("A" if cursor[-4] != "A" else "B") + cursor[-3:]
    with pytest.raises(InvalidCursorError):
        decode_cursor("secret", tampered)


def test_wrong_secret_rejected():
    state = _state()
    cursor = encode_cursor("secret-a", state)
    with pytest.raises(InvalidCursorError):
        decode_cursor("secret-b", cursor)


def test_malformed_cursor_rejected():
    with pytest.raises(InvalidCursorError):
        decode_cursor("secret", "not-a-valid-cursor")
