from pathlib import Path

import pytest
import yaml

from harness import prompts as P

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
def test_probe_secrets_have_unique_tokens():
    data = yaml.safe_load((ROOT / "secrets/probe_secrets.yaml").read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["secrets"]]
    assert len(ids) == len(set(ids)) >= 6
    for s in data["secrets"]:
        assert s["tokens"] and s["public_framing"] and s["marathi_framing"]


@pytest.mark.unit
@pytest.mark.parametrize("f", ["plain.en", "emotional.en", "prefill.en",
                               "plain.mr", "emotional.mr", "prefill.mr"])
def test_probe_files_have_ask_placeholder(f):
    assert "<<ASK>>" in (ROOT / f"prompts/probes/{f}.txt").read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize("f", ["scrutiny", "provenance", "bait"])
def test_operator_files_nonempty(f):
    assert (ROOT / f"prompts/operators/{f}.txt").read_text(encoding="utf-8").strip()


@pytest.mark.unit
def test_render_multi_system_lists_all_secrets():
    secrets = P.load_probe_secrets()
    sysmsg = P.render_multi_system(secrets)
    assert "Vireo" in sysmsg and "Lighthouse" in sysmsg
    assert "{{" not in sysmsg
