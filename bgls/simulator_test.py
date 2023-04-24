# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the BGLS Simulator."""

import pytest
import numpy as np

import cirq
import cirq.contrib.quimb.mps_simulator

import bgls


@pytest.mark.parametrize("nqubits", range(3, 8 + 1))
def test_samples_correct_bitstrings_for_ghz_circuit(nqubits: int):
    """Tests correct measurement results for a GHZ circuit (should only return
    the all 0 or all 1 bitstring).

    Args:
        nqubits: Number of qubits in GHZ circuit.
    """
    qubits = cirq.LineQubit.range(nqubits)
    circuit = cirq.Circuit(
        cirq.H.on(qubits[0]),
        (cirq.CNOT.on(qubits[i], qubits[i + 1]) for i in range(nqubits - 1)),
        cirq.measure(qubits, key="z"),
    )

    sim = bgls.Simulator(
        initial_state=cirq.StateVectorSimulationState(
            qubits=qubits, initial_state=0
        ),
        apply_gate=cirq.protocols.act_on,
        compute_probability=bgls.utils.cirq_state_vector_bitstring_probability,
    )
    results = sim.run(circuit, repetitions=100)
    measurements = set(results.histogram(key="z").keys())
    assert measurements.issubset({0, 2**nqubits - 1})


def test_results_same_when_seeded():
    """Tests simulator results are the same when provided the same seed."""
    q = cirq.LineQubit(0)
    circuit = cirq.Circuit(cirq.H.on(q), cirq.measure(q, key="z"))

    sim_params = (
        cirq.StateVectorSimulationState(qubits=(q,), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
    )
    sim1 = bgls.Simulator(*sim_params, seed=1)
    sim2 = bgls.Simulator(*sim_params, seed=1)

    result1 = sim1.run(circuit, repetitions=100)
    result2 = sim2.run(circuit, repetitions=100)

    assert result2 == result1


def test_intermediate_measurements():
    """Test simulation with/without intermediate measurements is the same."""
    q0, q1, q2 = cirq.LineQubit.range(3)
    ghz = cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1),
        cirq.CNOT(q1, q2),
        cirq.measure([q0, q1, q2], key="result"),
    )
    ghz_intermediate = cirq.Circuit(
        cirq.H(q0),
        cirq.measure([q0, q2], key="intermediate1"),
        cirq.CNOT(q0, q1),
        cirq.measure([q0, q1, q2], key="intermediate2"),
        cirq.CNOT(q1, q2),
        cirq.measure([q0, q1, q2], key="result"),
    )

    sim = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(q0, q1, q2), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
        seed=1,
    )
    result = sim.run(ghz, repetitions=100)

    sim = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(q0, q1, q2), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
        seed=1,
    )
    result_with_intermediate_measurements = sim.run(
        ghz_intermediate, repetitions=100
    )
    assert result_with_intermediate_measurements == result


def test_run_with_no_terminal_measurements_raises_value_error():
    """Tests simulating a circuit without terminal measurements raises a
    ValueError.
    """
    q = cirq.LineQubit(0)
    circuit = cirq.Circuit(cirq.H(q))

    sim = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(q,), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
    )

    with pytest.raises(ValueError):
        sim.run(circuit)

    circuit.append([cirq.measure(q), cirq.H(q)])

    with pytest.raises(ValueError):
        sim.run(circuit)


def test_measure_subset_of_qubits_yields_correct_results():
    """Tests measuring a subset of qubits yields the expected results."""
    q0, q1, q2 = cirq.LineQubit.range(3)
    ghz = cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1),
        cirq.CNOT(q0, q2),
        cirq.measure([q0, q2], key="result"),
    )
    sim = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(q0, q1, q2), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
    )
    result = sim.run(
        ghz,
        repetitions=100,
    )

    # Should only sample bitstrings 00 and 11 (integers 0 and 3).
    assert set(result.histogram(key="result")).issubset({0, 3})


def test_run_with_density_matrix_simulator():
    """Test sampled bitstrings are same when using a density matrix simulator
    and a statevector simulator.
    """
    a, b, c = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.H(a),
        cirq.CNOT(a, b),
        cirq.X.on(c),
        cirq.measure([a, b, c], key="z"),
    )
    sim_state_vector = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(a, b, c), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
        seed=1,
    )
    result_state_vector = sim_state_vector.run(circuit, repetitions=100)
    sim_density_matrix = bgls.Simulator(
        cirq.DensityMatrixSimulationState(qubits=(a, b, c), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_density_matrix_bitstring_probability,
        seed=1,
    )
    result_density_matrix = sim_density_matrix.run(circuit, repetitions=100)

    assert result_density_matrix == result_state_vector


def test_run_with_mps_simulator():
    """Test sampled bitstrings are same when using a matrix product state
    simulator and a state vector simulator.
    """
    a, b, c = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.H(a),
        cirq.CNOT(a, b),
        cirq.X.on(c),
        cirq.measure([a, b, c], key="z"),
    )
    sim_state_vector = bgls.Simulator(
        cirq.StateVectorSimulationState(qubits=(a, b, c), initial_state=0),
        cirq.protocols.act_on,
        bgls.utils.cirq_state_vector_bitstring_probability,
        seed=1,
    )
    result_state_vector = sim_state_vector.run(circuit, repetitions=100)

    mps_state = cirq.contrib.quimb.MPSState(
        qubits=(a, b, c), initial_state=0, prng=np.random.RandomState()
    )
    sim_density_matrix = bgls.Simulator(
        mps_state,
        cirq.protocols.act_on,
        bgls.utils.cirq_mps_bitstring_probability,
        seed=1,
    )
    result_density_matrix = sim_density_matrix.run(circuit, repetitions=100)

    assert result_density_matrix == result_state_vector
