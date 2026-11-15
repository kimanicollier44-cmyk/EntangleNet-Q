import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as en

PSI = [math.cos(0.7), math.sin(0.7)]


# statevector core
def test_bell_pair_circuit_phi_plus():
    assert en.state_fidelity(en.make_bell_pair(), en.bell_state("phi+")) > 1 - 1e-12
def test_bell_pair_psi_plus():
    assert en.state_fidelity(en.make_bell_pair("psi+"), en.bell_state("psi+")) > 1 - 1e-12
def test_bell_pair_phi_minus():
    assert en.state_fidelity(en.make_bell_pair("phi-"), en.bell_state("phi-")) > 1 - 1e-12
def test_zero_state_bounds():
    try:
        en.zero_state(7); assert False
    except ValueError:
        assert True
def test_teleport_ideal_outcome_00():
    bob, prob = en.teleport_statevector(PSI, (0, 0))
    assert abs(en.state_fidelity(bob, PSI) - 1.0) < 1e-9 and abs(prob - 0.25) < 1e-9
def test_teleport_ideal_all_outcomes():
    for outcome in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        bob, prob = en.teleport_statevector(PSI, outcome)
        assert abs(en.state_fidelity(bob, PSI) - 1.0) < 1e-9 and abs(prob - 0.25) < 1e-9
def test_swap_ideal_statevector():
    prob, fid = en.swap_statevector()
    assert abs(prob - 0.25) < 1e-9 and abs(fid - 1.0) < 1e-9

# Werner links
def test_werner_roundtrip():
    for w in (0.0, 0.3, 0.6, 1.0):
        assert abs(en.werner_w_from_fidelity(en.werner_fidelity_from_w(w)) - w) < 1e-12
def test_werner_pure_pair():
    assert abs(en.rho_fidelity(en.werner_rho(1.0), en.bell_state("phi+")) - 1.0) < 1e-12
def test_werner_maxmixed():
    assert abs(en.rho_fidelity(en.werner_rho(0.25), en.bell_state("phi+")) - 0.25) < 1e-12
def test_werner_bad_fidelity():
    try:
        en.werner_rho(0.1); assert False
    except ValueError:
        assert True
def test_link_fidelity_zero_distance(): assert en.link_fidelity(0.0) == 1.0
def test_link_fidelity_decreases():
    assert en.link_fidelity(100.0) > en.link_fidelity(400.0) > en.link_fidelity(1200.0)
def test_link_w_formula():
    assert abs(en.link_w(en.LINK_L_KM) - math.exp(-1.0)) < 1e-12
def test_link_quality_scales_w():
    assert en.link_w(500.0, 0.5) == 0.5 * en.link_w(500.0, 1.0)
def test_depolarizing_formula():
    assert en.depolarizing_fidelity(0.0) == 1.0 and en.depolarizing_fidelity(0.4) == 0.6
def test_depolarizing_matches_sim():
    for p in (0.1, 0.4, 0.7):
        assert abs(en.depolarizing_fidelity(p) - en.depolarized_pair_fidelity(p)) < 1e-9

# swapping
def test_swap_product_rule():
    expect = en.werner_fidelity_from_w(
        en.werner_w_from_fidelity(0.9) * en.werner_w_from_fidelity(0.8))
    assert abs(en.chain_fidelity([0.9, 0.8]) - expect) < 1e-12
def test_swap_sim_matches_formula():
    for F1, F2 in [(0.9, 0.8), (0.7, 0.7), (0.95, 0.6)]:
        prob, fid = en.swap_simulated(F1, F2)
        assert abs(fid - en.chain_fidelity([F1, F2])) < 1e-9 and abs(prob - 0.25) < 1e-9
def test_chain_three_links():
    expect = en.werner_fidelity_from_w(en.werner_w_from_fidelity(0.9) ** 3)
    assert abs(en.chain_fidelity([0.9, 0.9, 0.9]) - expect) < 1e-12
def test_chain_single_link():
    assert abs(en.chain_fidelity([0.85]) - 0.85) < 1e-12

# purification
def test_purify_improves_above_half(): assert en.purify_fidelity(0.8) > 0.8
def test_purify_fixed_point(): assert abs(en.purify_fidelity(0.5) - 0.5) < 1e-12
def test_purify_worsens_below_half(): assert en.purify_fidelity(0.4) < 0.4
def test_purify_perfect_stays(): assert abs(en.purify_fidelity(1.0) - 1.0) < 1e-12
def test_purify_sim_matches_formula():
    for F in (0.6, 0.8, 0.9):
        prob, fid = en.purify_simulated(F)
        assert abs(fid - en.purify_fidelity(F)) < 1e-9
        assert abs(prob - en.purify_success_prob(F)) < 1e-9
def test_purify_success_prob_bounds():
    for i in range(25, 101):
        p = en.purify_success_prob(i / 100.0)
        assert 0.0 < p <= 1.0
def test_purify_rounds_converge(): assert en.purify_rounds(0.75, 6) > 0.9
def test_purify_rounds_monotone():
    seq = [en.purify_rounds(0.7, k) for k in range(5)]
    assert all(b > a for a, b in zip(seq, seq[1:]))

# routing
def test_route_phoenix_via_vegas():
    assert en.best_fidelity_path("Los Angeles", "Phoenix") == [
        "Los Angeles", "Las Vegas", "Phoenix"]
def test_route_best_beats_hops():
    rep = en.route_report()
    assert rep["best_fidelity"] > rep["fewest_hops_fidelity"]
def test_route_endpoints():
    rep = en.route_report()
    assert rep["best_fidelity_path"][0] == "Los Angeles"
    assert rep["best_fidelity_path"][-1] == "Dallas"
    assert rep["fewest_hops"] <= rep["best_hops"]
def test_path_fidelity_consistency():
    path = en.best_fidelity_path("Los Angeles", "Denver")
    ws = [en.edge_w(path[i], path[i + 1]) for i in range(len(path) - 1)]
    assert abs(en.path_fidelity(path) - en.werner_fidelity_from_w(en.chain_w(ws))) < 1e-12

# teleportation over network
def test_teleport_formula_endpoints():
    assert en.teleport_fidelity_from_pair(1.0) == 1.0
    assert abs(en.teleport_fidelity_from_pair(0.25) - 0.5) < 1e-12
def test_teleport_sim_matches_formula():
    assert abs(en.teleport_simulated(PSI, 0.8) - en.teleport_fidelity_from_pair(0.8)) < 1e-9
def test_teleport_sim_perfect_pair():
    assert abs(en.teleport_simulated(PSI, 1.0) - 1.0) < 1e-9
def test_network_teleport_report():
    net = en.network_teleport_report()
    assert net["purified_pair_fidelity"] > net["network_pair_fidelity"]
    assert net["purified_teleport_fidelity"] > net["classical_limit"]

# QKD
def test_binary_entropy():
    assert en.binary_entropy(0.0) == 0.0 and en.binary_entropy(1.0) == 0.0
    assert abs(en.binary_entropy(0.5) - 1.0) < 1e-12
def test_qkd_perfect_link(): assert abs(en.qkd_secret_fraction(1.0) - 1.0) < 1e-12
def test_qkd_mixed_link(): assert en.qkd_secret_fraction(0.0) == 0.0
def test_qkd_qber():
    assert en.qkd_qber(1.0) == 0.0 and abs(en.qkd_qber(0.0) - 0.5) < 1e-12
def test_qkd_rate_decreases():
    assert en.qkd_key_rate(50.0) > en.qkd_key_rate(200.0) > en.qkd_key_rate(400.0)
def test_qkd_table():
    rows = en.qkd_table()
    assert len(rows) == 5 and all(r["key_rate_bits_per_s"] > 0 for r in rows)

# memory / timing
def test_memory_no_wait(): assert en.memory_decayed_w(0.8, 0.0) == 0.8
def test_memory_half_life():
    assert abs(en.memory_decayed_w(0.8, en.MEMORY_T2_S * math.log(2.0)) - 0.4) < 1e-9
def test_expected_attempts(): assert en.expected_attempts(0.02) == 50.0
def test_round_trip():
    assert abs(en.round_trip_s(200.0) - 0.002) < 1e-12
def test_chain_timing_costs_fidelity():
    rep = en.route_report()
    timing = en.chain_timing_report(rep["best_fidelity_path"])
    assert timing["waited_end_fidelity"] < timing["fresh_end_fidelity"]
    assert timing["chain_ready_s"] > 0

# classifier
def test_classifier_report():
    rep = en.link_regime_report()
    assert rep["short_clean_link"] == "good"
    assert rep["regional_noisy_link"] == "marginal"
    assert rep["long_lossy_link"] == "unusable"

# gates + seats
def test_hold_gates_count():
    assert len(en.HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in en.HOLD_GATES.values())
def test_gate_ftl(): assert en.gate("claim_ftl_communication") == "HOLD"
def test_gate_production(): assert en.gate("claim_production_quantum_internet") == "HOLD"
def test_gate_live_qkd(): assert en.gate("live_qkd_key_use") == "HOLD"
def test_gate_sandbox(): assert en.gate("run_simulation") == "PROCEED"
def test_carbon4_seat():
    d = en.carbon4_decide(); assert d["can_override_hold"] is False and d["live_calls"] == 0
def test_claude_seat(): assert en.claude_advisor()["can_override_hold"] is False
def test_flow_seat():
    f = en.google_flow_plan(); assert f["rendered"] is False and f["live"] == 0
def test_checks_all_pass():
    checks = en.run_checks(); assert all(ok for _, ok in checks) and len(checks) == 45
def test_determinism():
    import io, contextlib
    a, b = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(a): en.demo()
    with contextlib.redirect_stdout(b): en.demo()
    assert a.getvalue() == b.getvalue()
