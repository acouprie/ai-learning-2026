from datetime import datetime
import json
import re

import anthropic
from pydantic import BaseModel, field_validator


MODEL = "claude-haiku-4-5-20251001"
OUTPUT_COST_PER_1M_TOKENS = 5.00
INPUT_COST_PER_1M_TOKENS = 1.00
SYSTEM_PROMPT = """You are extracting structured information from job descriptions.

<output_schema>
{
  "title": "string",
  "seniority": "Junior | Mid | Senior | Lead | Principal | null",
  "skills": ["string"],
  "salary": { "raw": "string", "min": "int|null", "max": "int|null", "currency": "string|null" }
}
</output_schema>

<rules>
- Return only the JSON, without markdown or explanation.
- Unknown field → null (or [] for skills).
- Salary in annual amounts if possible. If daily rate, keep the text in "raw" and set min/max to null.
- Normalize skill names: "React.js" → "React", "Postgres" → "PostgreSQL".
</rules>
"""


class Salary(BaseModel):
    raw: str | None = None
    min: int | None = None
    max: int | None = None
    currency: str | None = None

    @field_validator("raw", mode="before")
    @classmethod
    def coerce_raw_to_str(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)

    @field_validator("min", "max", mode="before")
    @classmethod
    def coerce_to_int(cls, v: object) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"salary amount must be numeric, got {v!r}") from e


class Reasoning(BaseModel):
    seniority_evidence: str | None = None
    seniority_guess: str | None = None
    salary_interpretation: str | None = None
    salary_guess: str | None = None
    ambiguous_skills: list[str] = []


class JobPosting(BaseModel):
    reasoning: Reasoning | None = None
    title: str
    seniority: str | None = None
    skills: list[str] = []
    salary: Salary | None = None


def _extract_json(text: str) -> str:
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_job_posting(text: str, client: anthropic.Anthropic) -> tuple[JobPosting, float, float]:
    start = datetime.now()
    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<job_posting>\n{text}\n</job_posting>",
            }
        ],
    )
    latency = (datetime.now() - start).total_seconds()

    input_cost  = message.usage.input_tokens  * INPUT_COST_PER_1M_TOKENS / 1_000_000
    output_cost = message.usage.output_tokens * OUTPUT_COST_PER_1M_TOKENS / 1_000_000
    cost_usd = input_cost + output_cost

    raw_json = _extract_json(message.content[0].text)
    data = json.loads(raw_json)
    return JobPosting.model_validate(data), cost_usd, latency
