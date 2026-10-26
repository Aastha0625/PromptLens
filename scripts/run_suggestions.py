import argparse
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import PromptFlag, Suggestion, OptimizerUsage
from app.suggestion_service import get_or_create_suggestion

def main():
    parser = argparse.ArgumentParser(description="PromptLens Prompt Suggestion Generator")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of flags to generate suggestions for",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate suggestions even if already ok or not_verified_safe",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PromptLens Suggestion Engine - Batch Execution")
    print("=" * 60)
    print(f"Limit: {args.limit if args.limit else 'No limit'}")
    print(f"Force Regenerate: {args.regenerate}")
    print("-" * 60)

    db = SessionLocal()
    try:
        # Query flags needing suggestions:
        # If not regenerating, exclude flags that already have an 'ok' or 'not_verified_safe' suggestion (Change 1)
        query = db.query(PromptFlag)

        if not args.regenerate:
            usable_suggestion_flag_ids = db.query(Suggestion.flag_id).filter(
                Suggestion.status.in_(["ok", "not_verified_safe"])
            )
            query = query.filter(~PromptFlag.id.in_(usable_suggestion_flag_ids))

        query = query.order_by(PromptFlag.id.asc())
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)

        flags = query.all()
        print(f"Found {len(flags)} candidate flags to process.")

        processed_count = 0
        rule_based_ok = 0
        llm_verified_ok = 0
        disabled_count = 0
        failed_count = 0

        for flag in flags:
            sug = get_or_create_suggestion(db, flag_id=flag.id, regenerate=args.regenerate)
            if sug:
                processed_count += 1
                if sug.method == "rule_based" and sug.status == "ok":
                    rule_based_ok += 1
                elif sug.method == "llm_rewrite" and sug.status == "ok":
                    llm_verified_ok += 1
                elif sug.status == "disabled":
                    disabled_count += 1
                elif sug.status == "failed":
                    failed_count += 1

        print("-" * 60)
        print("Execution Complete!")
        print(f"Total Processed          : {processed_count}")
        print(f"Rule-Based Rewrites (OK) : {rule_based_ok}")
        print(f"LLM Rewrites (Verified)  : {llm_verified_ok}")
        print(f"Disabled (LLM Off)       : {disabled_count}")
        print(f"Failed Calls             : {failed_count}")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    main()
