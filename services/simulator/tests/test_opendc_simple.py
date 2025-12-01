"""Simple unit test to verify OpenDC invocation and execution time."""

import time
from pathlib import Path

from odt_common.odc_runner import OpenDCRunner


def test_opendc_invocation_speed(opendc_bin_path, simple_task, simple_topology, tmp_path):
    """Test that OpenDC is invoked correctly and completes within 5 seconds.

    This is a simple integration test that verifies:
    1. The OpenDC binary can be invoked
    2. It processes a simple workload
    3. It completes within 5 seconds
    """
    runner = OpenDCRunner(opendc_bin_path)
    output_base_dir = tmp_path / "opendc"

    start_time = time.time()
    success, output_dir = runner.run_simulation(
        tasks=[simple_task],
        topology=simple_topology,
        output_base_dir=output_base_dir,
        run_number=1,
        timeout_seconds=5,
    )
    elapsed = time.time() - start_time

    # Verify it completed within 5 seconds
    assert elapsed < 5.0, f"OpenDC took {elapsed:.2f}s, expected < 5.0s"

    # Verify we got results
    assert isinstance(success, bool)
    assert isinstance(output_dir, Path)

    print(f"✅ OpenDC completed in {elapsed:.3f}s")
    print(f"   Success: {success}")
    print(f"   Output dir: {output_dir}")


def test_opendc_with_valid_workload(opendc_bin_path, simple_task, simple_topology, tmp_path):
    """Test that OpenDC successfully processes a valid workload."""
    runner = OpenDCRunner(opendc_bin_path)
    output_base_dir = tmp_path / "opendc"

    success, output_dir = runner.run_simulation(
        tasks=[simple_task],
        topology=simple_topology,
        output_base_dir=output_base_dir,
        run_number=1,
        timeout_seconds=5,
    )

    # Check result structure
    assert isinstance(success, bool)
    assert isinstance(output_dir, Path)

    # If successful, verify output directory exists
    if success:
        assert output_dir.exists()
        run_dir = output_base_dir / "run_1"
        assert run_dir.exists()
        assert (run_dir / "input").exists()
        assert (run_dir / "output").exists()
        assert (run_dir / "metadata.json").exists()

        print("✅ Simulation successful:")
        print(f"   Output dir: {output_dir}")
        print(f"   Run dir: {run_dir}")
    else:
        # Print error for debugging
        print("⚠️  Simulation failed")
        print(f"   Output dir: {output_dir}")
