"""
DEMO: Error Recovery with Try/Catch and Resource Override

This workflow demonstrates Flyte 2.0's ability to catch and handle user-level errors
like OOMError (out-of-memory) and dynamically adjust resources.

This showcases:
- ✨ Try/catch error handling in workflows (Python native!)
- ✨ Catching specific Flyte errors (OOMError, etc.)
- ✨ Dynamic resource override using .override()
- ✨ Graceful recovery from failures

Usage:
    python -m workflows.demo_error_recovery --local
"""

import asyncio
import flyte
import flyte.errors
from config import base_env

# ----------------------------------
# Demo Tasks
# ----------------------------------

# Start with minimal resources to trigger OOM
low_memory_env = flyte.TaskEnvironment(
    name="low_memory_env",
    image=base_env.image,
    secrets=base_env.secrets,
    resources=flyte.Resources(cpu=1, memory="250Mi"),  # Very low memory
)

# Demo mode - set to True to simulate OOM errors
DEMO_MODE = True  # TODO: Set to False for normal operation


@low_memory_env.task
async def memory_intensive_task(size_multiplier: int) -> str:
    """
    A task that attempts to allocate a large amount of memory.
    In DEMO_MODE, this will always fail with OOM to demonstrate recovery.

    Args:
        size_multiplier: Multiplier for memory allocation size

    Returns:
        Success message with allocated size
    """
    print(f"[Memory Task] Attempting to allocate memory with multiplier {size_multiplier}")

    if DEMO_MODE:
        # Simulate OOM by raising the error directly
        print(f"[DEMO MODE] Simulating OOM error for demonstration")
        raise flyte.errors.OOMError("Simulated out-of-memory error for demo")

    # In normal mode, try to actually allocate memory
    try:
        # Allocate a large list (this might actually cause OOM with low resources)
        large_list = [0] * (100000000 * size_multiplier)
        result = f"Successfully allocated {len(large_list):,} elements"
        print(f"[Memory Task] {result}")
        return result
    except MemoryError as e:
        # Convert Python MemoryError to Flyte OOMError
        print(f"[Memory Task] Caught MemoryError: {e}")
        raise flyte.errors.OOMError(f"Out of memory allocating list: {e}")


@base_env.task
async def always_succeeds() -> str:
    """
    A task that always succeeds - used to demonstrate 'finally' blocks.

    Returns:
        Success message
    """
    await asyncio.sleep(0.5)
    print("[Always Succeeds] Task completed successfully")
    return "Cleanup complete"


# ----------------------------------
# Main Workflow
# ----------------------------------

@base_env.task
async def demo_error_recovery_workflow() -> dict:
    """
    Demonstrates error recovery with try/catch and resource override.

    Shows:
    1. Initial attempt with low resources (fails with OOM)
    2. Catch OOMError and retry with more resources
    3. If still fails, catch again and give up gracefully
    4. Use finally block for cleanup

    Returns:
        Dict with execution results and recovery steps taken
    """
    print("=" * 80)
    print("🎬 DEMO: ERROR RECOVERY WITH RESOURCE OVERRIDE")
    print("=" * 80)

    results = {
        "first_attempt": None,
        "second_attempt": None,
        "recovery_steps": [],
        "cleanup": None,
        "final_status": "unknown"
    }

    # ----------------------------------
    # PHASE 1: Initial Attempt (Low Resources)
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 1: INITIAL ATTEMPT (250Mi memory)")
    print(f"{'='*80}")

    try:
        print("\n🔧 Attempting memory-intensive task with low resources...")
        result = await memory_intensive_task(2)
        results["first_attempt"] = "success"
        results["final_status"] = "success_on_first_try"
        print(f"✅ First attempt succeeded: {result}")

    except flyte.errors.OOMError as e:
        print(f"\n⚠️  First attempt failed with OOM: {e}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error code: {e.code}")

        results["first_attempt"] = f"failed_oom: {str(e)}"
        results["recovery_steps"].append("caught_oom_on_first_attempt")

        # ----------------------------------
        # PHASE 2: Retry with More Resources
        # ----------------------------------
        print(f"\n{'='*80}")
        print("PHASE 2: RETRY WITH INCREASED RESOURCES (1Gi memory)")
        print(f"{'='*80}")

        try:
            print("\n🔧 Retrying with 4x more memory (1Gi)...")
            # Use .override() to dynamically increase resources
            result = await memory_intensive_task.override(
                resources=flyte.Resources(cpu=1, memory="1Gi")
            )(5)

            results["second_attempt"] = "success"
            results["final_status"] = "success_after_resource_increase"
            results["recovery_steps"].append("increased_resources_to_1gi")
            print(f"✅ Second attempt succeeded with increased resources: {result}")

        except flyte.errors.OOMError as e:
            print(f"\n❌ Second attempt also failed with OOM: {e}")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Error code: {e.code}")

            results["second_attempt"] = f"failed_oom: {str(e)}"
            results["recovery_steps"].append("oom_persisted_even_with_1gi")
            results["final_status"] = "failed_after_all_attempts"

            # ----------------------------------
            # PHASE 3: Give Up Gracefully
            # ----------------------------------
            print(f"\n{'='*80}")
            print("PHASE 3: GRACEFUL FAILURE")
            print(f"{'='*80}")
            print("\n⚠️  Task requires more resources than available")
            print("   Giving up gracefully and proceeding with cleanup")

            # In a real workflow, you might:
            # - Log to monitoring system
            # - Send alert
            # - Use alternative approach
            # - Re-raise if critical
            # For demo, we'll just continue

    finally:
        # ----------------------------------
        # CLEANUP: Always Runs
        # ----------------------------------
        print(f"\n{'='*80}")
        print("CLEANUP: ALWAYS EXECUTED")
        print(f"{'='*80}")
        print("\n🧹 Running cleanup task (always executes, even on failure)...")

        cleanup_result = await always_succeeds()
        results["cleanup"] = cleanup_result
        print(f"✅ Cleanup complete: {cleanup_result}")

    # ----------------------------------
    # SUMMARY
    # ----------------------------------
    print(f"\n{'='*80}")
    print("EXECUTION SUMMARY")
    print(f"{'='*80}")
    print(f"Final Status: {results['final_status']}")
    print(f"First Attempt: {results['first_attempt']}")
    print(f"Second Attempt: {results['second_attempt']}")
    print(f"Recovery Steps: {results['recovery_steps']}")
    print(f"Cleanup: {results['cleanup']}")
    print(f"{'='*80}\n")

    return results


# ----------------------------------
# CLI Entry Point
# ----------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Demo: Error recovery with try/catch and resource override",
        epilog="Example: python -m workflows.demo_error_recovery --local"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run workflow locally using flyte.init()"
    )

    args = parser.parse_args()

    # Initialize Flyte
    if args.local:
        print("Running workflow LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("Running workflow REMOTELY with flyte.init_from_config()")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n=== Error Recovery Demo ===")
    print(f"DEMO_MODE: {DEMO_MODE}")
    print(f"This demo shows how to catch OOMError and retry with more resources\n")

    # Execute the workflow
    execution = flyte.run(demo_error_recovery_workflow)

    print(f"\n{'='*80}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI")
    print(f"{'='*80}\n")