# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

This is a 24-week structured learning repo to transition from Senior Full-Stack Engineer (Ruby/Rails, TypeScript, 9+ years) to **AI Engineer Freelance**, specialized in the HR/Recruitment vertical. It starts April 2026.

The thread project is a **micro-SaaS that generates structured interview reports** from audio/video recordings (upload → Whisper STT → speaker diarization → LLM structuring → shareable report). MVP target: week 18.

## Planned stack

| Layer | Choice |
|---|---|
| AI backend | Python 3.12 + FastAPI |
| Frontend | Next.js (TypeScript) + Vercel AI SDK |
| Database | PostgreSQL + pgvector |
| Primary LLM | Anthropic Claude — Sonnet 4.6 default, Haiku 4.5 for cheap/fast tasks |
| Secondary LLM | OpenAI |
| Speech-to-text | OpenAI Whisper |
| Data validation | Pydantic |
| Python package manager | uv |
| AI observability | Langfuse |
| Agent orchestration | Pydantic AI or custom (prefer custom when simple enough) |
| Deployment | Vercel (front) · Railway / Fly.io (backend) |
| CI/CD | GitHub Actions · Docker |

## Development commands (Python projects)

```bash
uv sync              # install dependencies
uv run python main.py
uv run pytest
uv run pytest tests/test_foo.py::test_bar   # single test
uv run ruff check .  # lint
uv run ruff format . # format
```

## Architecture (phases)

**Phase 1 (S1–S4) — Foundations:** standalone Python scripts, one per exercise. No shared infra yet. Each script is a self-contained demo that can be pushed to GitHub and shown on LinkedIn.

**Phase 2 (S5–S10) — Production patterns:** shared Python library starts taking shape. RAG pipeline (pgvector), agent scaffolding (Pydantic AI), evaluation harness (LLM-as-a-judge), Langfuse instrumentation.

**Phase 3 (S11–S18) — SaaS MVP:** monorepo with `backend/` (FastAPI) and `frontend/` (Next.js). Core IA pipeline lives in `backend/pipeline/` (upload → STT → diarization → LLM → structured output). Auth via Clerk or Supabase Auth. Billing via Stripe.

**Phase 4 (S19–S24) — Freelance + iteration:** SaaS stabilization and first client missions. No new architectural layer introduced.

## How to assist in this repo

- **Explain the "why"** on LLM design choices, prompting strategies, and evaluation decisions — Antoine is building mental models, not just shipping.
- **Flag missing evaluation** — measuring whether a system works is the senior signal. If code has no way to assess quality, point it out.
- **Prefer simple** — 50 readable lines beat a complex framework. Avoid new dependencies unless there's a concrete need.
- **Respect the stack** — use Pydantic for validation, `uv` for Python packages, Anthropic SDK as primary LLM client.

## Key principles (from the roadmap)

- **Evaluation > Demo** — the ability to measure system quality differentiates a senior AI Engineer.
- **Simple by default** — avoid heavy orchestration frameworks until there is a concrete, proven need.
- **The SaaS is a means, not an end** — a freelance mission paying now beats a SaaS that might pay later.

## Resources

- Anthropic docs: https://docs.anthropic.com  
- Anthropic Cookbook: https://github.com/anthropics/anthropic-cookbook
