import pytest

from harness.jsonlio import append_jsonl, read_jsonl, write_jsonl


@pytest.mark.unit
def test_append_and_read_roundtrip(tmp_path):
    p = tmp_path / "x.jsonl"
    append_jsonl(p, {"a": 1})
    append_jsonl(p, {"a": 2, "b": "two"})
    rows = list(read_jsonl(p))
    assert rows == [{"a": 1}, {"a": 2, "b": "two"}]


@pytest.mark.unit
def test_write_overwrites(tmp_path):
    p = tmp_path / "y.jsonl"
    write_jsonl(p, [{"x": 1}])
    write_jsonl(p, [{"x": 2}, {"x": 3}])
    assert list(read_jsonl(p)) == [{"x": 2}, {"x": 3}]


@pytest.mark.unit
def test_read_missing_file_is_empty(tmp_path):
    assert list(read_jsonl(tmp_path / "nope.jsonl")) == []
