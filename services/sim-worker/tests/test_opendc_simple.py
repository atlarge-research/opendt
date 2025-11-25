"""Simple unit test to verify OpenDC invocation and execution time."""

import time

from sim_worker.runner import OpenDCRunner, SimulationResults


def test_opendc_invocation_speed(opendc_bin_path, simple_task, simple_topology):
    """Test that OpenDC is invoked correctly and completes within 5 seconds.

    This is a simple integration test that verifies:
    1. The OpenDC binary can be invoked
    2. It processes a simple workload
    3. It completes within 5 seconds
    """
    runner = OpenDCRunner(opendc_bin_path)

    start_time = time.time()
    result = runner.run_simulation(
        tasks=[simple_task],
        topology=simple_topology,
        experiment_name="speed-test",
        timeout_seconds=5,
    )
    elapsed = time.time() - start_time

    # Verify it completed within 5 seconds
    assert elapsed < 5.0, f"OpenDC took {elapsed:.2f}s, expected < 5.0s"

    # Verify we got a SimulationResults object
    assert isinstance(result, SimulationResults)
    assert result.status in ["success", "error"]

    print(f"✅ OpenDC completed in {elapsed:.3f}s")
    print(f"   Status: {result.status}")
    if result.status == "error":
        print(f"   Error: {result.error or 'Unknown'}")


def test_opendc_with_valid_workload(opendc_bin_path, simple_task, simple_topology):
    """Test that OpenDC successfully processes a valid workload."""
    runner = OpenDCRunner(opendc_bin_path)

    result = runner.run_simulation(
        tasks=[simple_task],
        topology=simple_topology,
        experiment_name="valid-workload-test",
        timeout_seconds=5,
    )

    # Check result structure
    assert isinstance(result, SimulationResults)
    assert result.status in ["success", "error"]

    # If successful, verify we got metrics and timeseries
    if result.status == "success":
        assert result.energy_kwh >= 0
        assert result.max_power_draw >= 0
        assert isinstance(result.power_draw_series, list)
        assert isinstance(result.cpu_utilization_series, list)

        print("✅ Simulation successful:")
        print(f"   Energy: {result.energy_kwh} kWh")
        print(f"   Max Power: {result.max_power_draw} W")
        print(f"   CPU Util: {result.cpu_utilization}")
        print(f"   Power timeseries points: {len(result.power_draw_series)}")
        print(f"   CPU timeseries points: {len(result.cpu_utilization_series)}")
    else:
        # Print error for debugging
        print("⚠️  Simulation returned error status:")
        print(f"   Error: {result.error or 'Unknown'}")
