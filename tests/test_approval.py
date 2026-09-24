"""Approval routing matches talk numbers."""

from app.policy.engine import PolicyEngine, determine_approval


engine = PolicyEngine()


def test_claim_a_manager():
    d = determine_approval(4500, "v1")
    assert d.approver == "MANAGER"
    assert engine.required_roles(d.approver) == ["MANAGER"]


def test_claim_b_cfo():
    d = determine_approval(24550, "v1")
    assert d.approver == "CFO"
    assert engine.required_roles(d.approver) == ["CFO"]


def test_claim_c_cfo_finance():
    d = determine_approval(75000, "v1")
    assert d.approver == "CFO + Finance"
    assert engine.required_roles(d.approver) == ["CFO", "FINANCE"]


def test_v2_changes_talk_claim_routing():
    assert determine_approval(24550, "v1").approver == "CFO"
    assert determine_approval(24550, "v2").approver == "BU_HEAD"
