import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from state import PipelineState
from workflow import workflow


def main():
    parser = argparse.ArgumentParser(
        prog="devsecops-remediate",
        description="Autonomous agentic pipeline for triaging, patching, and delivering verified security fixes."
    )
    parser.add_argument(
        "--alert", "-a",
        type=str,
        required=True,
        help="Raw security advisory, SAST alert, or CVE/CWE description."
    )
    parser.add_argument(
        "--repo", "-r",
        type=str,
        default="demo_repo",
        help="Path to the repository directory to inspect and patch (default: demo_repo)."
    )
    parser.add_argument(
        "--max-retries", "-m",
        type=int,
        default=3,
        help="Maximum self-correction reflection loops between Tester and Coder (default: 3)."
    )

    args = parser.parse_args()

    repo_path = Path(args.repo)
    if not repo_path.exists():
        print(f" Error: Repository directory '{args.repo}' does not exist.")
        sys.exit(1)

    print("=" * 60)
    print(" AUTONOMOUS DEVSECOPS REMEDIATION CLI")
    print("=" * 60)
    print(f"Target Directory : {args.repo}")
    print(f"Security Alert   : {args.alert}")
    print(f"Retry Budget     : {args.max_retries}")
    print("=" * 60)

    initial_state = PipelineState(
        raw_security_alert=args.alert,
        repo_directory=str(repo_path),
        max_iterations=args.max_retries
    )

    try:
        final_state = workflow.invoke(initial_state)
        print("\n" + "=" * 60)
        if final_state.get("human_approved"):
            print("✅ Status: Remediation successfully delivered to new branch.")
        else:
            print(" Status: Remediation completed without branch promotion.")
        print("=" * 60)
    except Exception as e:
        print(f"\n Pipeline failed with unexpected runtime exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()