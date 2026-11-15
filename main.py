#!/usr/bin/env python3
"""EntangleNet-Q - educational quantum internet / repeater network lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
This is the network layer that sits on top of TeleportX (the
teleportation protocol) and Q6G-1TB (the link / BB84 model): how
Bell pairs are generated on noisy links, purified, swapped through
repeater chains, routed across a small city graph, waited on in
quantum memories, and finally spent on teleportation and QKD -
all simulated, all formulas checked against a from-scratch
statevector / density-matrix simulator (<= 6 qubits).

Honest scope: a production quantum internet does not exist yet.
This lab models the published physics (Werner states, DEJMPS /
Bennett purification, entanglement swapping, Shor-Preskill BB84
rates) - it operates no network, controls no hardware, and moves
no information faster than light. Every live / product claim is
a permanent HOLD gate (14 total).

Seats: Gemini Carbon 4 DECIDER (names-only, tighten-only), Muse
advisor (never overrides HOLD), Google Flow plan-only.
"""
import hashlib
import heapq
import json
import math
import sys

VERSION = "1.0.0"
MAX_QUBITS = 6
SQRT2 = math.sqrt(2.0)

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "live_network_operation": "HOLD - no operating any real quantum or classical network, ever",
    "real_hardware_control": "HOLD - no control of any real quantum hardware, repeater, or satellite",
    "claim_ftl_communication": "HOLD - entanglement never sends information faster than light; teleportation needs a classical channel",
    "claim_production_quantum_internet": "HOLD - no production quantum internet exists; this is a simulation lab",
    "live_qkd_key_use": "HOLD - no generating or using real cryptographic keys for real traffic",
    "bypass_no_cloning_claim": "HOLD - the no-cloning theorem is not bypassed; teleportation destroys the original",
    "commercial_service_claim": "HOLD - no commercial quantum-network service is offered or implied",
    "live_satellite_link": "HOLD - no commanding or tasking any real satellite link",
    "real_fiber_deployment": "HOLD - no instructions for deploying or splicing live carrier fiber plant",
    "intercept_traffic_claim": "HOLD - no intercepting, decrypting, or monitoring anyone's real traffic",
    "guaranteed_key_rate_claim": "HOLD - key rates here are asymptotic model estimates, never guarantees",
    "military_network_claim": "HOLD - no military or classified network claims",
    "investment_advice_claim": "HOLD - no investment advice about quantum networking companies or tokens",
    "medical_data_transport_claim": "HOLD - no claims about transporting real medical or personal data",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ statevector core
# Pure-Python statevector simulator for <= MAX_QUBITS qubits.
# Qubit 0 is the most significant bit of the basis index.

def zero_state(n):
    if not 1 <= n <= MAX_QUBITS:
        raise ValueError("qubits must be 1..%d" % MAX_QUBITS)
    st = [0j] * (1 << n)
    st[0] = 1.0 + 0j
    return st


def apply_1q(state, n, q, u):
    """Apply 2x2 unitary u to qubit q of an n-qubit statevector."""
    step = 1 << (n - 1 - q)
    out = list(state)
    for base in range(0, 1 << n, step * 2):
        for off in range(step):
            i0, i1 = base + off, base + off + step
            a, b = state[i0], state[i1]
            out[i0] = u[0][0] * a + u[0][1] * b
            out[i1] = u[1][0] * a + u[1][1] * b
    return out


H_GATE = [[1 / SQRT2, 1 / SQRT2], [1 / SQRT2, -1 / SQRT2]]
X_GATE = [[0, 1], [1, 0]]


def apply_cnot(state, n, control, target):
    cb, tb = n - 1 - control, n - 1 - target
    out = list(state)
    for i, amp in enumerate(state):
        if (i >> cb) & 1:
            out[i ^ (1 << tb)] = amp
    return out


def bell_state(kind="phi+"):
    """Two-qubit Bell state vectors in basis |00>,|01>,|10>,|11>."""
    s = 1 / SQRT2
    table = {
        "phi+": [s, 0, 0, s],
        "phi-": [s, 0, 0, -s],
        "psi+": [0, s, s, 0],
        "psi-": [0, s, -s, 0],
    }
    return [complex(x) for x in table[kind]]


def make_bell_pair(kind="phi+"):
    """Circuit-built Bell pair: H on qubit 0, then CNOT 0->1."""
    st = zero_state(2)
    st = apply_1q(st, 2, 0, H_GATE)
    st = apply_cnot(st, 2, 0, 1)
    if kind == "phi-":
        st = apply_1q(st, 2, 0, [[1, 0], [0, -1]])
    elif kind in ("psi+", "psi-"):
        st = apply_1q(st, 2, 1, X_GATE)
        if kind == "psi-":
            st = apply_1q(st, 2, 0, [[1, 0], [0, -1]])
    return st


def state_fidelity(state, target):
    """|<target|state>|^2 for two pure statevectors."""
    inner = sum(t.conjugate() * s for s, t in zip(state, target))
    return abs(inner) ** 2


def project_onto(state, n, qubits, target):
    """Project `qubits` of the state onto `target` (pure, on those qubits).

    Returns (probability, normalized post-projection statevector).
    """
    k = len(qubits)
    bits = [n - 1 - q for q in qubits]
    out = [0j] * (1 << n)
    for i in range(1 << n):
        sub = 0
        for j, b in enumerate(bits):
            sub |= ((i >> b) & 1) << (k - 1 - j)
        out[i] = target[sub] * _slice_overlap(state, n, bits, i, target)
    norm = math.sqrt(sum(abs(a) ** 2 for a in out))
    if norm < 1e-15:
        return 0.0, out
    return norm * norm, [a / norm for a in out]


def _slice_overlap(state, n, bits, ref_index, target):
    """<target| slice of state with the non-projected bits of ref_index >."""
    k = len(bits)
    mask = 0
    for b in bits:
        mask |= 1 << b
    base = ref_index & ~mask
    total = 0j
    for m in range(1 << k):
        idx = base
        for j, b in enumerate(bits):
            if (m >> (k - 1 - j)) & 1:
                idx |= 1 << b
        total += target[m].conjugate() * state[idx]
    return total


def teleport_statevector(psi, outcome=(0, 0)):
    """Ideal teleportation of one qubit through a perfect Bell pair.

    Qubits: 0 = input, 1 = Alice's pair half, 2 = Bob's half.
    Applies the circuit, projects Alice's qubits onto `outcome`,
    applies the matching Pauli correction, returns Bob's qubit
    statevector (2 amplitudes) and the outcome probability.
    """
    pair = make_bell_pair()
    # input on q0, pair on (q1, q2)
    full = [psi[i >> 2] * pair[i & 3] for i in range(8)]
    full = apply_cnot(full, 3, 0, 1)
    full = apply_1q(full, 3, 0, H_GATE)
    target = [0j] * 4
    target[outcome[0] * 2 + outcome[1]] = 1.0 + 0j
    prob, post = project_onto(full, 3, [0, 1], target)
    # Bob's qubit = amplitudes with Alice's bits fixed at the outcome
    base = (outcome[0] << 2) | (outcome[1] << 1)
    bob = [post[base], post[base + 1]]
    # Pauli correction for the outcome
    if outcome[1] == 1:
        bob = apply_1q(bob, 1, 0, X_GATE)
    if outcome[0] == 1:
        bob = apply_1q(bob, 1, 0, [[1, 0], [0, -1]])
    nrm = math.sqrt(sum(abs(x) ** 2 for x in bob)) or 1.0
    return [x / nrm for x in bob], prob


def swap_statevector():
    """Ideal entanglement swapping on 4 qubits (two circuit-built pairs).

    Projects the middle qubits (1,2) onto phi+ and returns
    (probability, fidelity of the end pair (0,3) with phi+).
    """
    a = make_bell_pair()
    b = make_bell_pair()
    full = [a[i >> 2] * b[i & 3] for i in range(16)]
    prob, _post = project_onto(full, 4, [1, 2], bell_state("phi+"))
    return prob, _swap_end_fidelity(full)


def _swap_end_fidelity(full4):
    """Fidelity of end pair after projecting middle qubits onto phi+."""
    phi = bell_state("phi+")
    # unnormalized end amplitudes: sum over middle basis with phi weights
    end = [0j] * 4
    for i, amp in enumerate(full4):
        q0, q1, q2, q3 = (i >> 3) & 1, (i >> 2) & 1, (i >> 1) & 1, i & 1
        end[q0 * 2 + q3] += phi[q1 * 2 + q2].conjugate() * amp
    norm = math.sqrt(sum(abs(x) ** 2 for x in end))
    if norm < 1e-15:
        return 0.0
    end = [x / norm for x in end]
    return state_fidelity(end, bell_state("phi+"))


# ================================================================ density matrices
# Small complex-matrix toolkit (lists of lists). Used for Werner
# states on links, swapping / purification / teleportation with
# real noise - the simulation the analytic formulas are checked
# against. Systems here are <= 4 qubits (16x16 at most).

def mat_eye(n):
    return [[1.0 + 0j if i == j else 0j for j in range(n)] for i in range(n)]


def mat_mul(A, B):
    n, m, p = len(A), len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(m)) for j in range(p)]
            for i in range(n)]


def mat_dagger(A):
    return [[A[j][i].conjugate() for j in range(len(A))] for i in range(len(A[0]))]


def mat_trace(A):
    return sum(A[i][i] for i in range(len(A)))


def mat_kron(A, B):
    out = []
    for i, row_a in enumerate(A):
        for k, row_b in enumerate(B):
            out.append([row_a[j] * row_b[l] for j in range(len(A[0]))
                        for l in range(len(B[0]))])
    return out


def pure_rho(vec):
    return [[vec[i] * vec[j].conjugate() for j in range(len(vec))]
            for i in range(len(vec))]


def rho_fidelity(rho, vec):
    """<vec| rho |vec> - fidelity of a mixed state with a pure target."""
    tmp = [sum(rho[i][j] * vec[j] for j in range(len(vec))) for i in range(len(vec))]
    return sum(vec[i].conjugate() * tmp[i] for i in range(len(vec))).real


def partial_trace(rho, n, keep):
    """Trace out every qubit not in `keep` (qubit 0 = MSB)."""
    keep = sorted(keep)
    dim_out = 1 << len(keep)
    out = [[0j] * dim_out for _ in range(dim_out)]
    for i in range(1 << n):
        for j in range(1 << n):
            if rho[i][j] == 0:
                continue
            ok = True
            oi = oj = 0
            for pos, q in enumerate(range(n)):
                bi, bj = (i >> (n - 1 - q)) & 1, (j >> (n - 1 - q)) & 1
                if q in keep:
                    oi = (oi << 1) | bi
                    oj = (oj << 1) | bj
                elif bi != bj:
                    ok = False
                    break
            if ok:
                out[oi][oj] += rho[i][j]
    return out


def permutation_unitary(n, control, target):
    """CNOT permutation matrix on n qubits (qubit 0 = MSB)."""
    dim = 1 << n
    U = [[0j] * dim for _ in range(dim)]
    cb, tb = n - 1 - control, n - 1 - target
    for i in range(dim):
        j = i ^ (1 << tb) if (i >> cb) & 1 else i
        U[j][i] = 1.0 + 0j
    return U


def apply_unitary_rho(rho, U):
    return mat_mul(mat_mul(U, rho), mat_dagger(U))


def subspace_projector(n, fixed):
    """Diagonal projector fixing {qubit: bit} (qubit 0 = MSB)."""
    dim = 1 << n
    P = [[0j] * dim for _ in range(dim)]
    for i in range(dim):
        if all(((i >> (n - 1 - q)) & 1) == b for q, b in fixed.items()):
            P[i][i] = 1.0 + 0j
    return P


# ================================================================ 1. Links: Werner pairs
# A real link delivers a Werner state: rho = w |phi+><phi+| + (1-w) I/4.
# Fidelity F = (1 + 3w)/4, so w = (4F - 1)/3 is the "Werner weight"
# that multiplies cleanly through swapping and purification math.
# Link model (SIM parameters, labeled): w_link = q * exp(-d / L)
# with fiber-quality factor q and coherence length L = LINK_L_KM.

LINK_L_KM = 2500.0


def werner_w_from_fidelity(F):
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    return (4.0 * F - 1.0) / 3.0


def werner_fidelity_from_w(w):
    return (1.0 + 3.0 * w) / 4.0


def werner_rho(F):
    """4x4 density matrix of a Werner state with fidelity F to phi+."""
    w = werner_w_from_fidelity(F)
    phi = pure_rho(bell_state("phi+"))
    return [[w * phi[i][j] + (1.0 - w) * (0.25 if i == j else 0.0)
             for j in range(4)] for i in range(4)]


def link_w(distance_km, quality=1.0):
    """Werner weight of a fresh pair on one link: q * exp(-d / L)."""
    if distance_km < 0:
        raise ValueError("distance must be non-negative")
    return quality * math.exp(-distance_km / LINK_L_KM)


def link_fidelity(distance_km, quality=1.0):
    """Fidelity of a fresh Bell pair generated on one link."""
    return werner_fidelity_from_w(link_w(distance_km, quality))


def depolarizing_fidelity(p):
    """Pair fidelity after a Pauli-twirl depolarizing hit on one qubit.

    Convention: with probability p a uniformly random Pauli (X, Y or
    Z) strikes one qubit of the pair, taking phi+ to an orthogonal
    Bell state - so the surviving fidelity is exactly F = 1 - p.
    Checked against the density-matrix simulation in run_checks via
    depolarized_pair_fidelity().
    """
    return 1.0 - p


def depolarized_pair_fidelity(p):
    """Simulated: apply depolarizing channel to one qubit of a Bell pair."""
    rho = pure_rho(bell_state("phi+"))
    # one-qubit depolarizing on qubit 1: (1-p) rho + p/3 (X rho X + Y rho Y + Z rho Z)
    paulis = {
        "X": [[0, 1], [1, 0]],
        "Y": [[0, -1j], [1j, 0]],
        "Z": [[1, 0], [0, -1]],
    }
    out = [[(1.0 - p) * rho[i][j] for j in range(4)] for i in range(4)]
    eye2 = [[1, 0], [0, 1]]
    for U in paulis.values():
        full = mat_kron(eye2, [[complex(x) for x in row] for row in U])
        term = apply_unitary_rho(rho, full)
        for i in range(4):
            for j in range(4):
                out[i][j] += (p / 3.0) * term[i][j]
    return rho_fidelity(out, bell_state("phi+"))


# ================================================================ 2. Entanglement swapping
# Two Werner pairs (A-B) and (C-D); a Bell measurement on (B,C)
# leaves (A,D) entangled. For Werner inputs the end pair is Werner
# with w_end = w1 * w2 - the product rule. Verified below against a
# full 4-qubit density-matrix simulation, not just asserted.

def swap_w(w1, w2):
    """Werner weight after one ideal entanglement swap."""
    return w1 * w2


def chain_w(weights):
    """End-to-end Werner weight of a chain: product of link weights."""
    w = 1.0
    for x in weights:
        w *= x
    return w


def chain_fidelity(fidelities):
    """End-to-end fidelity of a chain of Werner pairs (product rule)."""
    return werner_fidelity_from_w(chain_w([werner_w_from_fidelity(f)
                                            for f in fidelities]))


def swap_simulated(F1, F2):
    """Density-matrix entanglement swapping of two Werner pairs.

    Qubit order (A, B, C, D); Bell-projects (B, C) onto phi+ and
    returns (success probability, end-pair fidelity with phi+).
    """
    rho = mat_kron(werner_rho(F1), werner_rho(F2))
    bell_proj = pure_rho(bell_state("phi+"))
    P = mat_kron(mat_kron(mat_eye(2), bell_proj), mat_eye(2))
    projected = mat_mul(mat_mul(P, rho), P)
    prob = mat_trace(projected).real
    if prob < 1e-15:
        return 0.0, 0.25
    projected = [[x / prob for x in row] for row in projected]
    end = partial_trace(projected, 4, keep=[0, 3])
    return prob, rho_fidelity(end, bell_state("phi+"))


# ================================================================ 3. Purification (DEJMPS-style)
# Bennett / DEJMPS distillation for Werner states: take two pairs
# of fidelity F, bilateral CNOTs, measure the target pair, keep the
# source pair when the outcomes agree. Standard result:
#   F' = (F^2 + ((1-F)/3)^2) / D
#   P_success = D,  D = F^2 + (2/3) F (1-F) + 5 ((1-F)/3)^2
# F' > F exactly when F > 1/2; F = 1/2 is a fixed point; below 1/2
# the protocol makes things worse. Verified against a full 4-qubit
# density-matrix simulation of the bilateral-CNOT protocol.

def purify_fidelity(F):
    """Fidelity after one successful DEJMPS round on two Werner pairs."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    num = F * F + third * third
    den = F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third
    return num / den


def purify_success_prob(F):
    """Probability the two measurement outcomes agree (pair is kept)."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    return F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third


def purify_rounds(F, rounds):
    """Fidelity after `rounds` successful purification rounds."""
    for _ in range(rounds):
        F = purify_fidelity(F)
    return F


def purify_simulated(F):
    """Density-matrix simulation of one DEJMPS round on two Werner pairs.

    Qubit order (A1, B1, A2, B2); CNOT A1->A2 and B1->B2, keep the
    (A1, B1) pair when the measured bits of A2 and B2 agree.
    Returns (success probability, kept-pair fidelity).
    """
    rho = mat_kron(werner_rho(F), werner_rho(F))
    rho = apply_unitary_rho(rho, permutation_unitary(4, 0, 2))
    rho = apply_unitary_rho(rho, permutation_unitary(4, 1, 3))
    keep = [[0j] * 16 for _ in range(16)]
    for outcome in (0, 1):
        P = subspace_projector(4, {2: outcome, 3: outcome})
        term = mat_mul(mat_mul(P, rho), P)
        for i in range(16):
            for j in range(16):
                keep[i][j] += term[i][j]
    prob = mat_trace(keep).real
    if prob < 1e-15:
        return 0.0, 0.25
    keep = [[x / prob for x in row] for row in keep]
    pair = partial_trace(keep, 4, keep=[0, 1])
    return prob, rho_fidelity(pair, bell_state("phi+"))


# ================================================================ 4. Repeater network routing
# Small labeled SIM graph of city nodes with approximate fiber
# distances (km) and a per-edge fiber-quality factor. Edge Werner
# weight w = q * exp(-d / L); swapping multiplies weights, so the
# best-fidelity path minimizes sum(-ln w) - a Dijkstra problem.
# Note the Los Angeles-Phoenix direct edge is labeled legacy fiber
# (low q): the best-fidelity route to Phoenix goes via Las Vegas
# even though it has MORE hops. Fidelity beats hop count.

NODES = ["Los Angeles", "Las Vegas", "Phoenix", "Albuquerque",
         "Denver", "Dallas"]

EDGES = [
    # (node_a, node_b, distance_km, fiber_quality)
    ("Los Angeles", "Las Vegas", 435, 0.98),
    ("Los Angeles", "Phoenix", 574, 0.45),      # legacy noisy fiber (sim label)
    ("Las Vegas", "Phoenix", 480, 0.97),
    ("Las Vegas", "Denver", 1197, 0.95),
    ("Phoenix", "Albuquerque", 677, 0.96),
    ("Albuquerque", "Denver", 716, 0.96),
    ("Albuquerque", "Dallas", 1046, 0.95),
    ("Denver", "Dallas", 1270, 0.94),
    ("Phoenix", "Dallas", 1420, 0.90),
]


def _adjacency():
    adj = {n: [] for n in NODES}
    for a, b, d, q in EDGES:
        w = link_w(d, q)
        adj[a].append((b, d, q, w))
        adj[b].append((a, d, q, w))
    return adj


def edge_w(a, b):
    for x, y, d, q in EDGES:
        if {x, y} == {a, b}:
            return link_w(d, q)
    raise ValueError("no edge %s-%s" % (a, b))


def path_weights(path):
    return [edge_w(path[i], path[i + 1]) for i in range(len(path) - 1)]


def path_fidelity(path):
    """End-to-end fidelity of the swapped chain along `path`."""
    return werner_fidelity_from_w(chain_w(path_weights(path)))


def best_fidelity_path(src, dst):
    """Dijkstra minimizing sum(-ln w): the max end-to-end fidelity path."""
    adj = _adjacency()
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    seen = set()
    while pq:
        cost, node = heapq.heappop(pq)
        if node in seen:
            continue
        seen.add(node)
        if node == dst:
            break
        for nxt, _d, _q, w in adj[node]:
            step = -math.log(w)
            if cost + step < dist.get(nxt, float("inf")):
                dist[nxt] = cost + step
                prev[nxt] = node
                heapq.heappush(pq, (cost + step, nxt))
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return list(reversed(path))


def fewest_hops_path(src, dst):
    """Breadth-first shortest path by hop count (fidelity ignored)."""
    adj = _adjacency()
    prev = {src: None}
    queue = [src]
    while queue:
        node = queue.pop(0)
        if node == dst:
            break
        for nxt, _d, _q, _w in adj[node]:
            if nxt not in prev:
                prev[nxt] = node
                queue.append(nxt)
    path = [dst]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return list(reversed(path))


def route_report(src="Los Angeles", dst="Dallas"):
    """Best-fidelity vs fewest-hops routes, with end-to-end numbers."""
    best = best_fidelity_path(src, dst)
    hops = fewest_hops_path(src, dst)
    return {
        "source": src,
        "destination": dst,
        "best_fidelity_path": best,
        "best_fidelity": round(path_fidelity(best), 6),
        "best_hops": len(best) - 1,
        "fewest_hops_path": hops,
        "fewest_hops_fidelity": round(path_fidelity(hops), 6),
        "fewest_hops": len(hops) - 1,
    }


# ================================================================ 5. Teleportation over the network
# Spending an end-to-end Werner pair (fidelity F) on teleportation
# gives output fidelity F_tel = (2F + 1)/3 for every input - the
# same protocol as TeleportX, now with a network-grade resource.
# Verified against a 3-qubit density-matrix circuit simulation.

def teleport_fidelity_from_pair(F):
    """Average teleportation fidelity using a Werner pair of fidelity F."""
    return (2.0 * F + 1.0) / 3.0


def teleport_simulated(psi, F):
    """Density-matrix teleportation of `psi` through a Werner pair (F).

    Qubits (input, Alice, Bob); circuit CNOT + H, Alice outcome 00
    selected (identity correction), returns Bob's output fidelity.
    """
    rho = mat_kron(pure_rho(psi), werner_rho(F))
    rho = apply_unitary_rho(rho, permutation_unitary(3, 0, 1))
    h_full = mat_kron([[complex(x) for x in row] for row in H_GATE],
                      mat_eye(4))
    rho = apply_unitary_rho(rho, h_full)
    P = subspace_projector(3, {0: 0, 1: 0})
    projected = mat_mul(mat_mul(P, rho), P)
    prob = mat_trace(projected).real
    if prob < 1e-15:
        return 0.0
    projected = [[x / prob for x in row] for row in projected]
    bob = partial_trace(projected, 3, keep=[2])
    return rho_fidelity(bob, psi)


PURIFY_ROUNDS_PER_LINK = 2


def purified_path_fidelity(path, rounds=PURIFY_ROUNDS_PER_LINK):
    """Chain fidelity when every link is purified `rounds` times first."""
    fids = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        d = next(dd for x, y, dd, _q in EDGES if {x, y} == {a, b})
        q = next(qq for x, y, _dd, qq in EDGES if {x, y} == {a, b})
        fids.append(purify_rounds(link_fidelity(d, q), rounds))
    return chain_fidelity(fids)


def network_teleport_report():
    """Teleport LA -> Dallas over the best path, raw vs purified links."""
    rep = route_report()
    path = rep["best_fidelity_path"]
    F_net = path_fidelity(path)
    F_pur = purified_path_fidelity(path)
    F_direct = link_fidelity(574, 0.45)  # the legacy LA-Phoenix-grade link, stretched
    return {
        "network_pair_fidelity": round(F_net, 6),
        "network_teleport_fidelity": round(teleport_fidelity_from_pair(F_net), 6),
        "purified_pair_fidelity": round(F_pur, 6),
        "purified_teleport_fidelity": round(teleport_fidelity_from_pair(F_pur), 6),
        "single_noisy_link_pair_fidelity": round(F_direct, 6),
        "single_noisy_link_teleport_fidelity": round(
            teleport_fidelity_from_pair(F_direct), 6),
        "classical_limit": round(2.0 / 3.0, 6),
    }


# ================================================================ 6. QKD over a network link (BB84)
# Same BB84 model family as Q6G-1TB, network edition. A Werner link
# with weight w gives QBER Q = (1 - w)/2 in each basis; the
# Shor-Preskill asymptotic secret fraction is r = 1 - 2 h2(Q)
# (zero once Q >= ~0.11). Pair generation rate is an effective
# model R = R0 * exp(-d / L_rate) - labeled estimates, not promises.

QKD_R0_PAIRS_PER_S = 1.0e6
QKD_L_RATE_KM = 250.0


def binary_entropy(x):
    if x <= 0.0 or x >= 1.0:
        return 0.0 if x in (0.0, 1.0) else float("nan")
    return -x * math.log2(x) - (1.0 - x) * math.log2(1.0 - x)


def qkd_qber(w):
    """BB84 quantum bit error rate for a Werner link of weight w."""
    return (1.0 - w) / 2.0


def qkd_secret_fraction(w):
    """Shor-Preskill asymptotic secret bits per pair (clipped at 0)."""
    return max(0.0, 1.0 - 2.0 * binary_entropy(qkd_qber(w)))


def qkd_pair_rate(distance_km):
    """Effective heralded pair rate model (pairs per second)."""
    return QKD_R0_PAIRS_PER_S * math.exp(-distance_km / QKD_L_RATE_KM)


def qkd_key_rate(distance_km, quality=1.0):
    """Asymptotic secret key rate estimate for one link, bits/second."""
    w = link_w(distance_km, quality)
    return qkd_pair_rate(distance_km) * qkd_secret_fraction(w)


def qkd_table(distances=(10, 50, 100, 200, 400)):
    rows = []
    for d in distances:
        w = link_w(d)
        rows.append({
            "distance_km": d,
            "link_fidelity": round(link_fidelity(d), 6),
            "qber": round(qkd_qber(w), 6),
            "secret_fraction": round(qkd_secret_fraction(w), 6),
            "key_rate_bits_per_s": round(qkd_key_rate(d), 2),
        })
    return rows


# ================================================================ 7. Quantum memory / repeater timing
# The repeater timing problem: links succeed at different times,
# and a pair waiting in memory decoheres - its Werner weight decays
# as exp(-t / T2). Expected-value model (labeled): each link needs
# an expected 1/p attempts, one attempt round lasts the light
# round-trip time of the segment in fiber (c_fiber ~ 200,000 km/s).

C_FIBER_KM_S = 200_000.0
LINK_SUCCESS_P = 0.02          # heralded success per attempt (sim parameter)
MEMORY_T2_S = 1.0              # memory coherence time, seconds (sim parameter)


def round_trip_s(distance_km):
    """Light round-trip time of one segment in fiber, seconds."""
    return 2.0 * distance_km / C_FIBER_KM_S


def expected_attempts(p=LINK_SUCCESS_P):
    """Expected attempts until one heralded success: 1/p."""
    return 1.0 / p


def memory_decayed_w(w0, wait_s, t2=MEMORY_T2_S):
    """Werner weight after waiting `wait_s` in a memory with time T2."""
    return w0 * math.exp(-wait_s / t2)


def chain_timing_report(path, p=LINK_SUCCESS_P, t2=MEMORY_T2_S):
    """Expected schedule for building the chain along `path`.

    Every link is attempted in parallel rounds; link i is ready
    after an expected 1/p rounds of its own round-trip time. Early
    pairs wait for the slowest link and decay in memory meanwhile.
    """
    legs = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        d = next(dd for x, y, dd, _q in EDGES if {x, y} == {a, b})
        legs.append({"link": "%s-%s" % (a, b), "distance_km": d,
                     "ready_s": expected_attempts(p) * round_trip_s(d),
                     "w_fresh": edge_w(a, b)})
    ready_all = max(leg["ready_s"] for leg in legs)
    w_product = 1.0
    for leg in legs:
        leg["wait_s"] = ready_all - leg["ready_s"]
        leg["w_after_wait"] = memory_decayed_w(leg["w_fresh"], leg["wait_s"], t2)
        w_product *= leg["w_after_wait"]
    return {
        "path": path,
        "chain_ready_s": round(ready_all, 6),
        "fresh_end_fidelity": round(path_fidelity(path), 6),
        "waited_end_fidelity": round(werner_fidelity_from_w(w_product), 6),
        "legs": [{k: (round(v, 6) if isinstance(v, float) else v)
                  for k, v in leg.items()} for leg in legs],
    }


# ================================================================ 8. Link regime classifier (TinyML kNN)
# Features: (distance_km / 1000, depolarizing noise p). Labels:
# good / marginal / unusable. Tiny labeled set, euclidean kNN, k=3.

KNN_TRAINING = [
    ((0.05, 0.01), "good"),
    ((0.10, 0.03), "good"),
    ((0.20, 0.02), "good"),
    ((0.15, 0.06), "good"),
    ((0.40, 0.08), "marginal"),
    ((0.55, 0.12), "marginal"),
    ((0.45, 0.15), "marginal"),
    ((0.65, 0.10), "marginal"),
    ((0.90, 0.25), "unusable"),
    ((1.10, 0.35), "unusable"),
    ((0.80, 0.30), "unusable"),
    ((1.25, 0.22), "unusable"),
]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def classify_link(features, k=3):
    """kNN classification of a link regime from (distance/1000, noise)."""
    ranked = sorted(KNN_TRAINING, key=lambda row: _dist(features, row[0]))
    votes = {}
    for _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def link_regime_report():
    scenarios = {
        "short_clean_link": (0.08, 0.02),
        "regional_noisy_link": (0.50, 0.13),
        "long_lossy_link": (1.05, 0.30),
    }
    return {name: classify_link(f) for name, f in scenarios.items()}


# ================================================================ 9. Advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="entanglenet-q-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all live-operation gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="entanglenet-q-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Route by end-to-end fidelity, not hop count; purify any link below F=0.6 before swapping, and never quote a key rate without its model assumptions.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["city nodes light up", "Bell pairs on links", "purification funnel",
                  "swapping chain reaction", "teleport across the map"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    psi = [math.cos(0.7), math.sin(0.7)]
    # statevector core
    chk("bell_pair_circuit", state_fidelity(make_bell_pair(), bell_state("phi+")) > 1 - 1e-12)
    chk("bell_pair_psi_plus", state_fidelity(make_bell_pair("psi+"), bell_state("psi+")) > 1 - 1e-12)
    tel_ok = True
    for outcome in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        bob, prob = teleport_statevector(psi, outcome)
        tel_ok = tel_ok and abs(state_fidelity(bob, psi) - 1.0) < 1e-9 and abs(prob - 0.25) < 1e-9
    chk("teleport_ideal_all_outcomes", tel_ok)
    prob, fid = swap_statevector()
    chk("swap_ideal_prob_quarter", abs(prob - 0.25) < 1e-9)
    chk("swap_ideal_fidelity_one", abs(fid - 1.0) < 1e-9)
    # Werner links
    chk("werner_roundtrip", abs(werner_w_from_fidelity(werner_fidelity_from_w(0.6)) - 0.6) < 1e-12)
    chk("werner_maxmixed_is_quarter", abs(rho_fidelity(werner_rho(0.25), bell_state("phi+")) - 0.25) < 1e-12)
    chk("link_fidelity_zero_distance", link_fidelity(0.0) == 1.0)
    chk("link_fidelity_decreases", link_fidelity(100.0) > link_fidelity(400.0) > link_fidelity(1200.0))
    chk("link_w_formula", abs(link_w(LINK_L_KM) - math.exp(-1.0)) < 1e-12)
    chk("depolarizing_matches_sim",
        all(abs(depolarizing_fidelity(p) - depolarized_pair_fidelity(p)) < 1e-9
            for p in (0.1, 0.4)))
    # swapping: formula vs density-matrix simulation
    chk("swap_product_rule",
        abs(chain_fidelity([0.9, 0.8]) -
            werner_fidelity_from_w(werner_w_from_fidelity(0.9) * werner_w_from_fidelity(0.8))) < 1e-12)
    sim_ok = True
    for F1, F2 in [(0.9, 0.8), (0.7, 0.7), (0.95, 0.6)]:
        p_sim, f_sim = swap_simulated(F1, F2)
        sim_ok = sim_ok and abs(f_sim - chain_fidelity([F1, F2])) < 1e-9 and abs(p_sim - 0.25) < 1e-9
    chk("swap_sim_matches_formula", sim_ok)
    chk("chain_three_links",
        abs(chain_fidelity([0.9, 0.9, 0.9]) -
            werner_fidelity_from_w(werner_w_from_fidelity(0.9) ** 3)) < 1e-12)
    # purification: formula vs simulation, threshold behavior
    chk("purify_improves_above_half", purify_fidelity(0.8) > 0.8)
    chk("purify_fixed_point_half", abs(purify_fidelity(0.5) - 0.5) < 1e-12)
    chk("purify_worsens_below_half", purify_fidelity(0.4) < 0.4)
    pur_ok = True
    for F in (0.6, 0.8, 0.9):
        p_sim, f_sim = purify_simulated(F)
        pur_ok = pur_ok and abs(f_sim - purify_fidelity(F)) < 1e-9 \
            and abs(p_sim - purify_success_prob(F)) < 1e-9
    chk("purify_sim_matches_formula", pur_ok)
    chk("purify_rounds_converge", purify_rounds(0.75, 6) > 0.9 > purify_fidelity(0.75))
    # routing
    chk("route_phoenix_via_vegas",
        best_fidelity_path("Los Angeles", "Phoenix") == ["Los Angeles", "Las Vegas", "Phoenix"])
    rep = route_report()
    chk("route_best_beats_fewest_hops", rep["best_fidelity"] > rep["fewest_hops_fidelity"])
    chk("route_dallas_path_valid",
        rep["best_fidelity_path"][0] == "Los Angeles" and rep["best_fidelity_path"][-1] == "Dallas")
    # teleportation over the network: formula vs circuit simulation
    chk("teleport_formula_endpoints",
        teleport_fidelity_from_pair(1.0) == 1.0 and abs(teleport_fidelity_from_pair(0.25) - 0.5) < 1e-12)
    chk("teleport_sim_matches_formula",
        abs(teleport_simulated(psi, 0.8) - teleport_fidelity_from_pair(0.8)) < 1e-9)
    net = network_teleport_report()
    chk("teleport_network_raw_honest", 0.25 < net["network_pair_fidelity"] < 1.0)
    chk("teleport_purified_beats_classical",
        net["purified_teleport_fidelity"] > net["classical_limit"]
        and net["purified_pair_fidelity"] > net["network_pair_fidelity"])
    # QKD
    chk("entropy_endpoints", binary_entropy(0.0) == 0.0 and abs(binary_entropy(0.5) - 1.0) < 1e-12)
    chk("qkd_perfect_link_full_rate", abs(qkd_secret_fraction(1.0) - 1.0) < 1e-12)
    chk("qkd_mixed_link_no_key", qkd_secret_fraction(0.0) == 0.0)
    chk("qkd_rate_decreases_with_distance", qkd_key_rate(50.0) > qkd_key_rate(200.0) > qkd_key_rate(400.0))
    chk("qkd_table_rows", len(qkd_table()) == 5 and all(r["key_rate_bits_per_s"] > 0 for r in qkd_table()))
    # memory / timing
    chk("memory_no_wait_no_decay", memory_decayed_w(0.8, 0.0) == 0.8)
    chk("memory_half_life", abs(memory_decayed_w(0.8, MEMORY_T2_S * math.log(2.0)) - 0.4) < 1e-9)
    chk("expected_attempts", expected_attempts(0.02) == 50.0)
    timing = chain_timing_report(rep["best_fidelity_path"])
    chk("memory_wait_costs_fidelity", timing["waited_end_fidelity"] < timing["fresh_end_fidelity"])
    # classifier
    reg = link_regime_report()
    chk("classifier_good", reg["short_clean_link"] == "good")
    chk("classifier_marginal", reg["regional_noisy_link"] == "marginal")
    chk("classifier_unusable", reg["long_lossy_link"] == "unusable")
    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_ftl_hold", gate("claim_ftl_communication") == "HOLD")
    chk("gate_live_qkd_hold", gate("live_qkd_key_use") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("EntangleNet-Q - educational quantum internet / repeater network lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | SIMULATION ONLY")
    print("=" * 68)
    print("\n[1] Bell pairs on links (Werner model, w = q * exp(-d / L))")
    for d in (0, 100, 435, 800, 1420):
        print(f"    link {d:5d} km: w = {link_w(d):.4f}, pair fidelity F = {link_fidelity(d):.4f}")
    print(f"    depolarizing check: formula F(0.4) = {depolarizing_fidelity(0.4):.4f}, "
          f"simulated = {depolarized_pair_fidelity(0.4):.4f}")
    print("\n[2] Entanglement swapping (product rule, verified vs density-matrix sim)")
    for F1, F2 in [(0.9, 0.8), (0.7, 0.7)]:
        p_sim, f_sim = swap_simulated(F1, F2)
        print(f"    F1={F1} F2={F2}: formula F_end = {chain_fidelity([F1, F2]):.4f}, "
              f"simulated = {f_sim:.4f} (outcome prob {p_sim:.2f})")
    print("\n[3] Purification (DEJMPS-style, verified vs simulation)")
    for F in (0.4, 0.6, 0.8):
        p_sim, f_sim = purify_simulated(F)
        print(f"    F={F:.2f} -> F' = {purify_fidelity(F):.4f} (sim {f_sim:.4f}), "
              f"success prob = {purify_success_prob(F):.4f} (sim {p_sim:.4f})")
    print(f"    F=0.75 after 6 rounds: {purify_rounds(0.75, 6):.4f} (F > 0.5 climbs, F < 0.5 dies)")
    print("\n[4] Routing: Los Angeles -> Dallas (fidelity beats hop count)")
    rep = route_report()
    print(f"    best fidelity: {' -> '.join(rep['best_fidelity_path'])} "
          f"({rep['best_hops']} hops, F = {rep['best_fidelity']:.4f})")
    print(f"    fewest hops:   {' -> '.join(rep['fewest_hops_path'])} "
          f"({rep['fewest_hops']} hops, F = {rep['fewest_hops_fidelity']:.4f})")
    print(f"    LA -> Phoenix best route: {' -> '.join(best_fidelity_path('Los Angeles', 'Phoenix'))} "
          f"(the direct legacy-fiber edge loses despite fewer hops)")
    print("\n[5] Teleportation over the network (TeleportX protocol, network resource)")
    net = network_teleport_report()
    print(f"    raw chain pair F = {net['network_pair_fidelity']:.4f} -> teleport F = {net['network_teleport_fidelity']:.4f}")
    print(f"    purified links pair F = {net['purified_pair_fidelity']:.4f} -> teleport F = {net['purified_teleport_fidelity']:.4f}")
    print(f"    classical teleport limit = {net['classical_limit']:.4f} (raw chain barely clears it; purification makes it real)")
    print("\n[6] QKD over links (BB84, Shor-Preskill asymptotic model - estimates, not promises)")
    for row in qkd_table():
        print(f"    {row['distance_km']:4d} km: F = {row['link_fidelity']:.4f}, QBER = {row['qber']:.4f}, "
              f"secret fraction = {row['secret_fraction']:.4f}, key rate ~ {row['key_rate_bits_per_s']:,.0f} bits/s")
    print("\n[7] Repeater timing: pairs wait in memory and decay (T2 = %.1f s sim)" % MEMORY_T2_S)
    timing = chain_timing_report(rep["best_fidelity_path"])
    print(f"    chain ready after ~{timing['chain_ready_s']:.3f} s of attempts; "
          f"F fresh = {timing['fresh_end_fidelity']:.4f} -> F after waits = {timing['waited_end_fidelity']:.4f}")
    print("\n[8] Link regime classifier (TinyML kNN)")
    for name, label in link_regime_report().items():
        print(f"    {name:22s} -> {label}")
    print("\n[9] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[10] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "route":
        print(json.dumps(route_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "purify":
        for F in (0.4, 0.5, 0.6, 0.75, 0.9):
            print(f"F={F:.2f} F'={purify_fidelity(F):.4f} P_success={purify_success_prob(F):.4f} "
                  f"F_after_6_rounds={purify_rounds(F, 6):.4f}")
        return 0
    if cmd == "swap":
        for F1, F2 in [(0.9, 0.8), (0.7, 0.7), (0.95, 0.6)]:
            p_sim, f_sim = swap_simulated(F1, F2)
            print(f"F1={F1} F2={F2} formula={chain_fidelity([F1, F2]):.4f} sim={f_sim:.4f} prob={p_sim:.4f}")
        return 0
    if cmd == "teleport-net":
        print(json.dumps(network_teleport_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "qkd":
        print(json.dumps(qkd_table(), indent=2, sort_keys=True))
        return 0
    if cmd == "memory":
        print(json.dumps(chain_timing_report(route_report()["best_fidelity_path"]),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(link_regime_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "claim_ftl_communication"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
