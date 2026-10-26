import argparse
import sys
import os

# Add parent directory to sys.path so 'app' modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.analysis_service import run_analysis
from app.embedder import Embedder

def main():
    parser = argparse.ArgumentParser(description="PromptLens Offline Prompt Analyzer")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of requests to analyze in this run",
    )
    parser.add_argument(
        "--reanalyze",
        action="store_true",
        help="Re-analyze already analyzed requests (idempotent)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PromptLens Prompt Analyzer - Batch Execution")
    print("=" * 60)
    print(f"Limit: {args.limit if args.limit else 'No limit (all eligible)'}")
    print(f"Re-analyze existing: {args.reanalyze}")
    print("-" * 60)

    db = SessionLocal()
    try:
        embedder = Embedder.get_instance()
        available = embedder.is_available()
        print(f"Semantic Embedder Available: {available} (model: {embedder.model_name})")
        if not available:
            print("Note: Running non-semantic heuristic checks only (exact dups, repeated content, verbose templates).")

        print("Running analysis...")
        result = run_analysis(db, limit=args.limit, reanalyze=args.reanalyze, embedder=embedder)

        print("-" * 60)
        print("Analysis Complete!")
        print(f"Requests Analyzed : {result['requests_analyzed']}")
        print(f"Requests Flagged  : {result['requests_flagged']}")
        print(f"Flags Created     : {result['flags_created']}")
        print(f"Semantic Ran      : {result['semantic_check_ran']}")
        print(f"Duration          : {result['duration_ms']:.2f} ms")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    main()
