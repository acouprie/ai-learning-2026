import json
import os
from datetime import datetime
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from parser import JobPosting


class Metric(BaseModel):
    latency_seconds: float = 0.0
    title_correct: bool = False
    seniority_correct: bool = False
    skills_recall: float = 0.0
    skills_precision: float = 0.0
    skills_missed: list[str] = []
    skills_hallucinated: list[str] = []
    failures: dict = {} # ex: {"salary": {"got": ..., "expected": ...}}
    salary_min_correct: bool = False
    salary_max_correct: bool = False
    salary_currency_correct: bool = False
    score_global: float = 0.0


class EvaluationResult(BaseModel):
    # Base information
    parser_name: str
    model: str
    timestamp: datetime = Field(default_factory=datetime.now)

    per_fixture: dict[str, Metric]

    # Aggregation
    title_accuracy: float
    seniority_accuracy: float
    skills_avg_recall: float
    skills_avg_precision: float
    skills_avg_f1: float
    salary_avg_score: float
    global_score: float

    # Meta-metrics
    total_usd_cost: float
    avg_latency_seconds: float
    total_compute_time: float

    # Failure analysis
    failure_patterns: dict[str, int] # ex: {"salary": 10, "title": 5}

def fuzzy_equal(a: str | None, b: str | None, threshold: int = 85) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return fuzz.token_set_ratio(a.lower(), b.lower()) >= threshold


def normalize_skill(s: str) -> str:
    s = s.lower().strip()
    aliases = {
        "react.js": "react", "reactjs": "react",
        "postgres": "postgresql",
        "node.js": "nodejs", "node": "nodejs",
        "ruby on rails": "rails", "rails": "rails", "ror": "rails",
        "typescript": "typescript", "ts": "typescript",
        "javascript": "javascript", "js": "javascript",
        "mysql": "mysql", "mariadb": "mysql", "sql": "sql",
        # à enrichir au fur et à mesure
    }
    return aliases.get(s, s)

def compute_global_score(m: Metric) -> float:
    weights = {
        "title": 0.15,
        "seniority": 0.15,
        "skills": 0.35,
        "salary": 0.35,
    }

    title_score = 1.0 if m.title_correct else 0.0
    seniority_score = 1.0 if m.seniority_correct else 0.0

    if m.skills_recall + m.skills_precision > 0:
        skills_f1 = 2 * m.skills_recall * m.skills_precision / (m.skills_recall + m.skills_precision)
    else:
        skills_f1 = 0.0

    salary_subfields = [m.salary_min_correct, m.salary_max_correct,
                        m.salary_currency_correct]
    salary_score = sum(salary_subfields) / len(salary_subfields)

    return (
        weights["title"] * title_score +
        weights["seniority"] * seniority_score +
        weights["skills"] * skills_f1 +
        weights["salary"] * salary_score
    )


def compare_expected_results(path: str, result: JobPosting, latency: float) -> Metric:
    def log_local(metric_name, expected, got):
        if metric_name is None:
            return
        local_failures.setdefault(metric_name, []).append(
            {"got": got, "expected": expected}
        )

    def fuzzy_hits(sources: list[str], targets: list[str]) -> int:
        return sum(any(fuzzy_equal(s, t) for t in targets) for s in sources)

    def find_matches_and_misses(sources, targets):
        matched = []
        unmatched = []
        for s in sources:
            if any(fuzzy_equal(s, t) for t in targets):
                matched.append(s)
            else:
                unmatched.append(s)
        return matched, unmatched

    local_failures: dict = {}
    expected_file = "fixtures/expected/" + os.path.basename(path)

    with open(expected_file, "r") as file:
        expect = json.load(file)

    expected_skills = set([normalize_skill(s) for s in expect["skills"]])
    result_skills = set([normalize_skill(s) for s in result.skills])

    recall_hits = fuzzy_hits(expected_skills, result_skills)
    precision_hits = fuzzy_hits(result_skills, expected_skills)

    title_correct = fuzzy_equal(expect["title"], result.title)
    seniority_correct = fuzzy_equal(expect["seniority"], result.seniority)
    got_min = str(result.salary.min) if result.salary and result.salary.min else ""
    got_max = str(result.salary.max) if result.salary and result.salary.max else ""
    got_currency = (result.salary.currency or "") if result.salary else ""
    salary_min_correct = str(expect.get("salary_min", "")) == got_min
    salary_max_correct = str(expect.get("salary_max", "")) == got_max
    salary_currency_correct = str(expect.get("salary_currency", "")) == got_currency

    if not title_correct:
        log_local("title", expect["title"], result.title)
    if not seniority_correct:
        log_local("seniority", expect["seniority"], result.seniority)
    if not salary_min_correct:
        log_local("salary_min", expect["salary_min"], str(result.salary.min) if result.salary else None)
    if not salary_max_correct:
        log_local("salary_max", expect["salary_max"], str(result.salary.max) if result.salary else None)
    if not salary_currency_correct:
        log_local("salary_currency", expect["salary_currency"], str(result.salary.currency) if result.salary else None)

    metric = Metric(
        title_correct=title_correct,
        seniority_correct=seniority_correct,
        skills_recall=recall_hits / len(expected_skills) if expected_skills else 1.0,
        skills_precision=precision_hits / len(result_skills) if result_skills else 1.0,
        skills_missed=find_matches_and_misses(expected_skills, result_skills)[1],
        skills_hallucinated=find_matches_and_misses(result_skills, expected_skills)[1],
        salary_min_correct=salary_min_correct,
        salary_max_correct=salary_max_correct,
        salary_currency_correct=salary_currency_correct,
        failures=local_failures,
        latency_seconds=latency
    )
    metric.score_global = compute_global_score(metric)
    return metric


def generate_report(evaluation_results: list[Metric], model: str, start_time: datetime, total_cost: float) -> dict:
    evaluation_report = EvaluationResult(
        parser_name="job_posting_parser",
        model=model,
        per_fixture={f"fixture_{i}": m for i, m in enumerate(evaluation_results)},
        title_accuracy=sum(m.title_correct for m in evaluation_results) / len(evaluation_results),
        seniority_accuracy=sum(m.seniority_correct for m in evaluation_results) / len(evaluation_results),
        skills_avg_recall=sum(m.skills_recall for m in evaluation_results) / len(evaluation_results),
        skills_avg_precision=sum(m.skills_precision for m in evaluation_results) / len(evaluation_results),
        skills_avg_f1=sum(2 * m.skills_recall * m.skills_precision / (m.skills_recall + m.skills_precision) if (m.skills_recall + m.skills_precision) > 0 else 0.0 for m in evaluation_results) / len(evaluation_results),
        salary_avg_score=sum((m.salary_min_correct + m.salary_max_correct + m.salary_currency_correct) / 3 for m in evaluation_results) / len(evaluation_results),
        global_score=sum(m.score_global for m in evaluation_results) / len(evaluation_results),
        total_usd_cost=total_cost,
        avg_latency_seconds=sum(m.latency_seconds for m in evaluation_results) / len(evaluation_results),
        total_compute_time=(datetime.now() - start_time).total_seconds(),
        failure_patterns={k: sum(k in m.failures for m in evaluation_results) for k in set(k for m in evaluation_results for k in m.failures)},
    )
    print_report(evaluation_report)
    save_report(evaluation_report)
    return evaluation_report


def print_report(report: EvaluationResult):
    print(f"Model: {report.model}")
    print(f"Title Accuracy: {report.title_accuracy:.2%}")
    print(f"Seniority Accuracy: {report.seniority_accuracy:.2%}")
    print(f"Skills Avg Recall: {report.skills_avg_recall:.2%}")
    print(f"Skills Avg Precision: {report.skills_avg_precision:.2%}")
    print(f"Skills Avg F1: {report.skills_avg_f1:.2%}")
    print(f"Salary Avg Score: {report.salary_avg_score:.2%}")
    print(f"Global Score: {report.global_score:.2%}")
    print(f"Total USD Cost: ${report.total_usd_cost:.2f}")
    print(f"Average Latency (s): {report.avg_latency_seconds:.2f}")
    print(f"Total Compute Time (s): {report.total_compute_time:.2f}")
    print("Failure Patterns:")
    for pattern, count in report.failure_patterns.items():
        print(f"  {pattern}: {count} failures")


def save_report(report: EvaluationResult, output_dir: str = "eval_reports"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/{report.parser_name}_{timestamp}.json"
    with open(filename, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Report saved to {filename}")