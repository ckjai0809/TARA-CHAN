import pytest

from harness import orchestrate_traj as O
from harness.traj_config import parse_traj_config


@pytest.mark.unit
def test_build_tasks_counts():
    cfg = parse_traj_config({
        "name": "t", "models": ["m1", "m2"], "n": 3,
        "steps": [{"kind": "probe", "op": "plain", "secret_id": "p1"}],
    })
    tasks = O.build_tasks(cfg)
    assert len(tasks) == 2 * 3  # models x n
