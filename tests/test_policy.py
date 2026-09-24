"""Unit tests: deterministic policy engine."""

from app.policy.engine import PolicyEngine, determine_approval


def test_v1_manager_under_10k():
    d = determine_approval(4500, "v1")
    assert d.approver == "MANAGER"


def test_v1_cfo_24550():
    d = determine_approval(24550, "v1")
    assert d.approver == "CFO"
    assert "10,000" in d.reason


def test_v1_boundary_10000_is_cfo():
    assert determine_approval(10000, "v1").approver == "CFO"


def test_v1_boundary_50000_is_cfo():
    assert determine_approval(50000, "v1").approver == "CFO"


def test_v1_over_50k_cfo_and_finance():
    d = determine_approval(75000, "v1")
    assert d.approver == "CFO + Finance"


def test_v2_mid_band_bu_head():
    d = determine_approval(24550, "v2")
    assert d.approver == "BU_HEAD"


def test_v2_high_is_cfo_only():
    assert determine_approval(75000, "v2").approver == "CFO"


def test_required_roles_split():
    roles = PolicyEngine().required_roles("CFO + Finance")
    assert roles == ["CFO", "FINANCE"]


def test_unknown_version_raises():
    try:
        determine_approval(100, "v9")
        assert False
    except ValueError:
        pass


def test_negative_rejected():
    try:
        determine_approval(-1, "v1")
        assert False
    except ValueError:
        pass
