"""Tiny JSONL helpers. One JSON object per line; append-friendly."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable, Iterator

_write_lock = threading.Lock()


def append_jsonl(path: str | Path, record: dict) -> None:
    """Append one record as a line. Thread-safe (workers share the file)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _write_lock:
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def write_jsonl(path: str | Path, records: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> Iterator[dict]:
    p = Path(path)
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
