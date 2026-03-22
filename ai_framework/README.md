# AI Automation Framework

Playwright + DeepEval framework for testing LLM-powered systems.
Handles non-deterministic AI responses with semantic assertions, hallucination
detection, security red-teaming, and performance monitoring.

## Quick Start

```bash
cd ai_framework

# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure environment
cp .env.example .env
# Edit .env — set AI_API_KEY and AI_BASE_URL

# 3. Run all AI/API tests (no browser required)
pytest -m "ai or api"

# 4. Run security red-team tests
pytest -m security

# 5. Run performance tests
pytest -m performance

# 6. Run UI tests (requires a running app with a chat interface)
pytest -m ui

# 7. Run everything
pytest
```

## Test Suites

| Marker | Command | What it tests |
|--------|---------|---------------|
| `api` | `pytest -m api` | Chat API, conversation flows, tool-call schemas |
| `security` | `pytest -m security` | OWASP LLM Top-10, injection, toxicity, bias |
| `performance` | `pytest -m performance` | Latency P95/P99, tokens/sec, token efficiency |
| `ai` | `pytest -m ai` | Hallucination, faithfulness, LLM-as-judge |
| `ui` | `pytest -m ui` | Playwright browser chat interface tests |

## Reports

After each run, reports are written to `reports/`:

| File | Contents |
|------|---------|
| `test_report.html` | pytest-html full test results |
| `ai_quality_metrics.json` | Time-series quality scores (hallucination, relevancy) |
| `hallucination_curves.json` | Per-test hallucination-vs-token-count curves |
| `security_report.json` | Red-team results by OWASP category |
| `performance_report.json` | Latency percentiles and token efficiency |

## Architecture

```
core/           — Types, config, logger, response capture
evaluators/     — Hallucination, token tracker, semantic assertions,
                  schema validator, conversation runner, agent workflow
security/       — Injection checker, safety checker, red team runner
performance/    — Latency tracker, token efficiency, baselines
ui/             — Playwright page objects (BasePage, AIChatPage)
api/            — AIClient (OpenAI-compatible), RestClient
reporting/      — JSON report writers
tests/          — pytest test files
fixtures/       — JSON test data (payloads, schemas, scripts, baselines)
```

## Key Concepts

### Hallucination Inflection Point
`HallucinationAnalyzer` tracks scores turn-by-turn and finds the exact token count
where model reliability degrades — giving you a safe token budget per conversation.

### Token Utilization Warnings
`TokenTracker` fires warnings at 70% context use and critical alerts at 85%,
before the model starts truncating or hallucinating from context overflow.

### OWASP LLM Top-10 Coverage
`RedTeamRunner` tests LLM01 (Prompt Injection), LLM02 (Insecure Output),
LLM06 (Sensitive Disclosure), and LLM08 (Excessive Agency) automatically.

### Semantic Assertions (not exact-match)
All response checks use `satisfies_intent()` (keyword/topic) or DeepEval metrics
— never brittle `assert response == "..."` comparisons.
