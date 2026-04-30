from datetime import datetime
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from parser import MODEL, JobPosting, parse_job_posting
from evaluate import Metric, compare_expected_results, generate_report

load_dotenv()

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def format_salary(posting: JobPosting) -> str:
    if posting.salary is None:
        return "N/A"
    s = posting.salary
    if s.min and s.max:
        currency = s.currency or ""
        return f"{s.min//1000}–{s.max//1000}k {currency}".strip()
    return s.raw[:30] if s.raw else "N/A"


def main() -> int:
    client = anthropic.Anthropic()
    fixtures = sorted(FIXTURES_DIR.glob("*.txt"))
    all_results: list[JobPosting] = []
    all_metrics: list[Metric] = []
    start_time = datetime.now()
    total_cost = 0.0

    if not fixtures:
        print("No fixture files found in fixtures/")
        return 1

    col = "{:<30} {:<30} {:<10} {:<10} {:<20}"
    print(col.format("fixture", "title", "seniority", "salary", "skills"))
    print("-" * 128)

    failures = 0
    for path in fixtures:
        text = path.read_text(encoding="utf-8")
        try:
            result, cost_usd, latency = parse_job_posting(text, client)
            total_cost += cost_usd
            print(
                col.format(
                    path.stem[:30],
                    result.title[:30],
                    result.seniority or "N/A",
                    format_salary(result),
                    str(result.skills),
                )
            )
            expected_path = f"fixtures/expected/{path.stem}.json"
            metric = compare_expected_results(expected_path, result, latency)
            all_metrics.append(metric)
            all_results.append(result)

            if result.reasoning:
                r = result.reasoning
                print(f"  seniority : {r.seniority_evidence or 'N/A'}")
                print(f"  seniority guess : {r.seniority_guess or 'N/A'}")
                print(f"  salary    : {r.salary_interpretation or 'N/A'}")
                print(f"  salary guess : {r.salary_guess or 'N/A'}")
                if r.ambiguous_skills:
                    print(f"  ambiguous : {', '.join(r.ambiguous_skills)}")
                print()
        except Exception as exc:
            print(col.format(path.stem[:30], "ERROR", "N/A", "N/A", str(exc)[:20]))
            failures += 1

    print()
    print("*" * 40)
    print("\nEvaluation Report")
    print("*" * 40)
    generate_report(all_metrics, MODEL, start_time, total_cost)

    print()
    if failures:
        print(f"{failures}/{len(fixtures)} fixture(s) failed.")
        return 1

    print(f"All {len(fixtures)} fixtures parsed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
