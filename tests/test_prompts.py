import pytest

from harness import prompts


@pytest.mark.unit
def test_secrets_have_required_fields():
    secrets = prompts.load_secrets()
    assert "q3_revenue" in secrets
    s = secrets["q3_revenue"]
    for key in ("secret_value", "public_framing", "stakes"):
        assert s[key].strip()


@pytest.mark.unit
def test_directives_present():
    for strength in ("weak", "medium", "strong", "mitigation"):
        assert prompts.get_directive(strength)
    # mitigation must contain the targeted defense line
    assert "hardship" in prompts.get_directive("mitigation").lower()


@pytest.mark.unit
def test_render_target_system_fills_all_slots():
    s = prompts.get_secret("q3_revenue")
    rendered = prompts.render_target_system(s, prompts.get_directive("medium"))
    assert s["secret_value"].split()[0] in rendered
    assert "confidential" in rendered.lower()
    assert "{{" not in rendered and "}}" not in rendered  # no unfilled slots


@pytest.mark.unit
def test_load_ladder_substitutes_ask_and_counts():
    s = prompts.get_secret("q3_revenue")
    turns = prompts.load_ladder("S3", s["public_framing"])
    assert len(turns) == 3
    assert prompts.ASK_PLACEHOLDER not in "".join(turns)
    assert s["public_framing"] in "".join(turns)


@pytest.mark.unit
def test_load_ladder_max_turns_truncates():
    s = prompts.get_secret("q3_revenue")
    turns = prompts.load_ladder("S0", s["public_framing"], max_turns=2)
    assert len(turns) == 2


@pytest.mark.unit
def test_bond_seed_has_three_turns():
    assert len(prompts.load_bond_seed()) == 3
