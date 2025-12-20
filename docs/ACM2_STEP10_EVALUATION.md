# ACM 2.0 – Step 10: Evaluation and Reporting

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Dependency:** This step builds on Step 9 (FPF Adapter) which produces artifacts to evaluate.  
> **Document Type:** Implementation specification for the code writer. Code samples are illustrative, not copy-paste ready.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Prerequisites](#3-prerequisites)
4. [Eval Database Schema](#4-eval-database-schema)
5. [Judge Configuration](#5-judge-configuration)
6. [Criteria Configuration](#6-criteria-configuration)
7. [Single-Doc Evaluation Interface](#7-single-doc-evaluation-interface)
8. [Single-Doc Execution Flow](#8-single-doc-execution-flow)
9. [Single-Doc Scoring](#9-single-doc-scoring)
10. [Pairwise Evaluation Interface](#10-pairwise-evaluation-interface)
11. [Pairwise Execution Flow](#11-pairwise-execution-flow)
12. [Elo Rating Calculation](#12-elo-rating-calculation)
13. [Top-N Selection](#13-top-n-selection)
14. [Evaluation Orchestration](#14-evaluation-orchestration)
15. [Post-Combine Evaluation](#15-post-combine-evaluation)
16. [Result Aggregation](#16-result-aggregation)
17. [HTML Report Generation](#17-html-report-generation)
18. [API Endpoints](#18-api-endpoints)
19. [Tests](#19-tests)
20. [Success Criteria](#20-success-criteria)
21. [File Structure](#21-file-structure)
22. [Next Steps](#22-next-steps)

---

## 1. Purpose

Step 10 implements the **evaluation system** that scores and ranks generated artifacts to identify the best outputs.

### Why Evaluation?

Generation produces multiple artifacts per document (different models, iterations). Evaluation answers: **which artifact is best?**

| Problem | Solution |
|---------|----------|
| Multiple generators (FPF, GPT-R) produce different outputs | Score each, pick winners |
| Same generator with different models produces variations | Compare quality objectively |
| Multiple iterations may vary in quality | Identify best iteration |
| Need to select inputs for Combine Phase | Top-N selection based on scores |

### Evaluation Types

| Type | Description | Output |
|------|-------------|--------|
| **Single-Doc** | AI judges score each artifact on criteria (1-10) | Numeric scores per criterion |
| **Pairwise** | AI judges compare two artifacts, pick winner | Win/loss record, Elo ratings |
| **Post-Combine** | Same evaluation on combined artifacts | Final quality assessment |

### How It Works (Summary)

1. **Single-doc scores**: Each artifact is scored by multiple AI judges on criteria like accuracy, completeness, clarity
2. **Pairwise comparisons**: Artifacts are compared head-to-head, producing Elo ratings
3. **Top-N selection**: Highest-rated artifacts advance to Combine Phase
4. **Post-combine**: Combined outputs are evaluated the same way

### Deliverables

1. `SingleDocEvaluator` — scores individual artifacts
2. `PairwiseEvaluator` — compares artifact pairs
3. `EloCalculator` — computes Elo ratings from comparisons
4. `EvalOrchestrator` — coordinates full evaluation pipeline
5. Evaluation database schema (compatible with ACM 1.0)
6. HTML report generation
7. API endpoints for triggering and querying evaluations

---

## 2. Scope

### 2.1 In Scope

| Item | Description |
|------|-------------|
| Single-doc evaluation | Score artifacts on configurable criteria |
| Multiple judges | Support multiple AI models as judges |
| Multiple iterations | Run evaluation N times, aggregate results |
| Pairwise comparison | Head-to-head artifact comparison |
| Elo rating system | Calculate rankings from pairwise results |
| Top-N selection | Select best artifacts for Combine Phase |
| Post-combine evaluation | Evaluate combined outputs |
| Result aggregation | Average scores across judges/iterations |
| HTML reports | Generate human-readable evaluation reports |
| Database storage | Persist all eval results |
| API endpoints | Trigger, monitor, and query evaluations |

### 2.2 Out of Scope

| Item | Reason |
|------|--------|
| Human evaluation UI | Future feature; this step is AI-judge only |
| Real-time evaluation streaming | Polling sufficient for now |
| Custom judge plugins | Standard LLM judges only |
| Cross-run comparisons | Evaluation is per-run |
| Evaluation of source documents | Only generated artifacts evaluated |

### 2.3 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring scale | **1-10 integer** | Matches ACM 1.0, intuitive |
| Default judges | **GPT-4o, Claude 3.5 Sonnet** | High quality, different perspectives |
| Elo K-factor | **32** | Standard for new systems |
| Initial Elo | **1500** | Standard starting point |
| Pairwise selection | **Round-robin for small N, sampled for large N** | Balance coverage vs cost |
| Tie-breaking | **Pairwise Elo > Single-doc score > Creation time** | Pairwise is more reliable |

---

## 3. Prerequisites

### 3.1 Required Dependencies

Already in `pyproject.toml` from previous steps:

| Package | Version | Purpose |
|---------|---------|---------|
| `httpx` | >=0.26.0 | LLM API calls |
| `structlog` | >=23.2.0 | Structured logging |
| `tenacity` | >=8.2.0 | Retry logic for API calls |
| `pydantic` | >=2.0.0 | Configuration and result validation |
| `jinja2` | >=3.1.0 | HTML report templates |

### 3.2 Completed Steps

| Step | Provides | Used By Evaluation |
|------|----------|-------------------|
| **Step 7** | `Run`, `Document` models | Eval linked to runs |
| **Step 8** | `StorageProvider` | Read artifacts, store reports |
| **Step 9** | `Artifact` records | Input to evaluation |

### 3.3 Configuration Requirements

The code writer should add these settings to `app/config.py`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `eval_judges` | list[dict] | See below | Judge configurations |
| `eval_iterations` | int | 3 | Evaluations per judge |
| `eval_timeout` | int | 120 | Seconds per evaluation call |
| `eval_max_concurrent` | int | 4 | Parallel eval calls |
| `elo_k_factor` | int | 32 | Elo update magnitude |
| `elo_initial` | int | 1500 | Starting Elo rating |
| `top_n_count` | int | 3 | Artifacts to advance |
| `top_n_threshold` | float | 0.7 | Min score to advance (0-1) |

**Default judges:**
```yaml
eval_judges:
  - provider: openai
    model: gpt-4o
    weight: 1.0
  - provider: anthropic
    model: claude-3-5-sonnet-20241022
    weight: 1.0
```

### 3.4 LLM API Requirements

Evaluation requires API access for judge models:

| Provider | Environment Variable | Required For |
|----------|---------------------|--------------|
| OpenAI | `OPENAI_API_KEY` | GPT-4o judge |
| Anthropic | `ANTHROPIC_API_KEY` | Claude judge |
| Google | `GOOGLE_API_KEY` | Gemini judge (optional) |

---

## 4. Eval Database Schema

### 4.1 Overview

Evaluation data is stored in the same SQLite database as runs/artifacts. Schema is designed for compatibility with ACM 1.0 eval database where possible.

### 4.2 Single-Doc Evaluation Results

**Table:** `eval_results`

| Column | Type | Description |
|--------|------|-------------|
| `eval_id` | TEXT PK | ULID |
| `tenant_id` | TEXT | Multi-tenant support |
| `run_id` | TEXT FK | References runs |
| `artifact_id` | TEXT FK | References artifacts (nullable) |
| `combined_output_id` | TEXT FK | References combined_outputs (nullable) |
| `judge_provider` | TEXT | e.g., `openai` |
| `judge_model` | TEXT | e.g., `gpt-4o` |
| `iteration` | INTEGER | 1-N evaluation iteration |
| `criteria_scores` | TEXT | JSON: `{"accuracy": 8, "completeness": 7, ...}` |
| `overall_score` | REAL | Weighted average (0-10) |
| `reasoning` | TEXT | Judge's explanation |
| `raw_response` | TEXT | Full LLM response (for debugging) |
| `input_tokens` | INTEGER | Tokens in prompt |
| `output_tokens` | INTEGER | Tokens in response |
| `duration_ms` | INTEGER | Evaluation time |
| `created_at` | TEXT | ISO timestamp |

**Indexes:**
- `(run_id, artifact_id)` — lookup by artifact
- `(artifact_id, judge_model, iteration)` — unique constraint
- `(run_id, overall_score DESC)` — ranking query

### 4.3 Pairwise Comparison Results

**Table:** `pairwise_comparisons`

| Column | Type | Description |
|--------|------|-------------|
| `comparison_id` | TEXT PK | ULID |
| `tenant_id` | TEXT | Multi-tenant support |
| `run_id` | TEXT FK | References runs |
| `artifact_a_id` | TEXT FK | First artifact (nullable) |
| `artifact_b_id` | TEXT FK | Second artifact (nullable) |
| `combined_output_a_id` | TEXT FK | First combined output (nullable) |
| `combined_output_b_id` | TEXT FK | Second combined output (nullable) |
| `judge_provider` | TEXT | e.g., `anthropic` |
| `judge_model` | TEXT | e.g., `claude-3-5-sonnet` |
| `iteration` | INTEGER | Comparison iteration |
| `winner` | TEXT | `a`, `b`, or `tie` |
| `confidence` | REAL | 0-1 confidence score |
| `reasoning` | TEXT | Judge's explanation |
| `raw_response` | TEXT | Full LLM response |
| `created_at` | TEXT | ISO timestamp |

**Indexes:**
- `(run_id, artifact_a_id, artifact_b_id)` — pair lookup
- `(artifact_a_id, artifact_b_id, judge_model, iteration)` — unique constraint

### 4.4 Elo Ratings

**Table:** `elo_ratings`

| Column | Type | Description |
|--------|------|-------------|
| `rating_id` | TEXT PK | ULID |
| `tenant_id` | TEXT | Multi-tenant support |
| `run_id` | TEXT FK | References runs |
| `artifact_id` | TEXT FK | References artifacts (nullable) |
| `combined_output_id` | TEXT FK | References combined_outputs (nullable) |
| `rating` | REAL | Current Elo rating |
| `games_played` | INTEGER | Number of comparisons |
| `wins` | INTEGER | Win count |
| `losses` | INTEGER | Loss count |
| `ties` | INTEGER | Tie count |
| `rating_history` | TEXT | JSON array of rating changes |
| `updated_at` | TEXT | ISO timestamp |

**Indexes:**
- `(run_id, rating DESC)` — ranking query
- `(artifact_id)` — unique constraint per run

### 4.5 ACM 1.0 Compatibility

For migration and interoperability, the schema maps to ACM 1.0:

| ACM 1.0 Field | ACM 2.0 Equivalent |
|---------------|-------------------|
| `doc_name` | `artifact.document.display_name` |
| `model` | `artifact.metadata.model` |
| `score` | `eval_results.overall_score` |
| `judge` | `eval_results.judge_model` |
| `iteration` | `eval_results.iteration` |

---

## 5. Judge Configuration

### 5.1 Judge Definition

A judge is an AI model configured to evaluate artifacts:

**JudgeConfig data class:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | str | Required | `openai`, `anthropic`, `google` |
| `model` | str | Required | Model identifier |
| `weight` | float | 1.0 | Weight in aggregation |
| `temperature` | float | 0.3 | Low for consistency |
| `max_tokens` | int | 2000 | Response limit |
| `system_prompt` | str \| None | None | Custom judge instructions |

### 5.2 Multiple Judges

Using multiple judges provides:

| Benefit | Description |
|---------|-------------|
| **Reduced bias** | Different models have different biases |
| **Increased reliability** | Outlier scores are averaged out |
| **Cross-validation** | Disagreement flags uncertain quality |

**Default configuration:**
```python
default_judges = [
    JudgeConfig(provider="openai", model="gpt-4o", weight=1.0),
    JudgeConfig(provider="anthropic", model="claude-3-5-sonnet-20241022", weight=1.0),
]
```

### 5.3 Judge Weighting

When aggregating scores from multiple judges:

```
final_score = Σ(judge_score × judge_weight) / Σ(weights)
```

**Example:**
- GPT-4o scores 8, weight 1.0
- Claude scores 7, weight 1.0
- Final: (8×1 + 7×1) / (1+1) = 7.5

**Weight use cases:**
- Higher weight for more capable models
- Lower weight for faster/cheaper models used for volume
- Zero weight to disable a judge without removing config

### 5.4 Judge Selection Per Evaluation Type

| Eval Type | Recommended Judges | Rationale |
|-----------|-------------------|-----------|
| Single-doc | 2 judges, 3 iterations each | Balance accuracy vs cost |
| Pairwise | 1 judge, 1 iteration | Binary decision is simpler |
| Post-combine | 2 judges, 2 iterations | Fewer artifacts, can afford more |

### 5.5 Judge Prompts

Prompts define how the judge evaluates the artifact.

**Storage:**
- Default prompts are stored in `acm2/evaluation/prompts/` as text files (e.g., `single_doc_judge.txt`, `pairwise_judge.txt`).
- Prompts can be overridden via `JudgeConfig.system_prompt` or `EvalConfig.custom_prompts`.

**Prompt Variables:**
- `{{ criteria }}`: List of evaluation criteria and descriptions.
- `{{ artifact_content }}`: The text to evaluate.
- `{{ artifact_a }}` / `{{ artifact_b }}`: For pairwise comparison.
- `{{ context }}`: Optional context (e.g., source document).

**Action Required:** Create default prompt files during implementation.

---

## 6. Criteria Configuration

### 6.1 Default Evaluation Criteria

Single-doc evaluation scores on multiple criteria:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| `accuracy` | 0.30 | Factual correctness, no hallucinations |
| `completeness` | 0.25 | Covers all required topics |
| `clarity` | 0.20 | Well-written, easy to understand |
| `relevance` | 0.15 | Stays on topic, no tangents |
| `formatting` | 0.10 | Proper structure, headings, lists |

### 6.2 Criteria Data Class

**EvalCriterion:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Identifier (e.g., `accuracy`) |
| `description` | str | What the criterion measures |
| `weight` | float | Weight in overall score |
| `min_score` | int | Minimum (default 1) |
| `max_score` | int | Maximum (default 10) |
| `prompt_guidance` | str | Instructions for judge |

### 6.3 Overall Score Calculation

```
overall_score = Σ(criterion_score × criterion_weight) / Σ(weights)
```

**Example:**
- accuracy: 8 × 0.30 = 2.40
- completeness: 7 × 0.25 = 1.75
- clarity: 9 × 0.20 = 1.80
- relevance: 8 × 0.15 = 1.20
- formatting: 7 × 0.10 = 0.70
- **Overall: 7.85**

### 6.4 Custom Criteria

Runs can override default criteria:

```json
{
  "eval_config": {
    "criteria": [
      {"name": "accuracy", "weight": 0.40},
      {"name": "completeness", "weight": 0.30},
      {"name": "policy_alignment", "weight": 0.30, "description": "Aligns with stated policy goals"}
    ]
  }
}
```

### 6.5 Criteria Prompt Template

Judges receive criteria in structured format:

```
Evaluate the following document on these criteria (score 1-10 each):

1. ACCURACY (30%): Factual correctness, no hallucinations
2. COMPLETENESS (25%): Covers all required topics
3. CLARITY (20%): Well-written, easy to understand
4. RELEVANCE (15%): Stays on topic, no tangents
5. FORMATTING (10%): Proper structure, headings, lists

For each criterion, provide:
- Score (1-10)
- Brief justification (1-2 sentences)

Then provide an overall assessment.
```

---

## 7. Single-Doc Evaluation Interface

### 7.1 SingleDocEvaluator Class

**File:** `app/evaluation/single_doc.py`

| Method | Description |
|--------|-------------|
| `__init__(judges, criteria, settings)` | Initialize with judge and criteria config |
| `evaluate(artifact, context)` | Evaluate single artifact, return `EvalResult` |
| `evaluate_batch(artifacts, context)` | Evaluate multiple artifacts with concurrency |
| `_build_prompt(artifact, criteria)` | Construct evaluation prompt |
| `_parse_response(response)` | Extract scores from LLM response |
| `_call_judge(judge, prompt)` | Make LLM API call |

### 7.2 Method Signatures

**evaluate():**
```
async def evaluate(
    artifact: Artifact,
    context: EvalContext,
    judge: JudgeConfig | None = None,
    iteration: int = 1,
) -> EvalResult
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artifact` | Artifact | The artifact to evaluate |
| `context` | EvalContext | Source document, instructions, run config |
| `judge` | JudgeConfig \| None | Override default judge |
| `iteration` | int | Which iteration (for multiple runs) |

### 7.3 EvalContext Data Class

Context provided to help the judge:

| Field | Type | Description |
|-------|------|-------------|
| `source_document` | str | Original document content |
| `instructions` | str \| None | Generation instructions |
| `guidelines` | str \| None | Style guidelines |
| `run_config` | dict | Run configuration |
| `document_metadata` | dict | Source document metadata |

### 7.4 EvalResult Data Class

**File:** `app/evaluation/result.py`

| Field | Type | Description |
|-------|------|-------------|
| `eval_id` | str | ULID |
| `artifact_id` | str | Evaluated artifact |
| `judge_provider` | str | Judge provider |
| `judge_model` | str | Judge model |
| `iteration` | int | Evaluation iteration |
| `criteria_scores` | dict[str, int] | Per-criterion scores |
| `overall_score` | float | Weighted average |
| `reasoning` | str | Judge's explanation |
| `confidence` | float \| None | Self-reported confidence |
| `duration_ms` | int | Evaluation time |
| `tokens_used` | TokenUsage | Input/output tokens |
| `created_at` | datetime | Timestamp |

---

## 8. Single-Doc Execution Flow

### 8.1 High-Level Flow

```
evaluate(artifact)
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 1. Load artifact content from StorageProvider   │
│ 2. Build evaluation context                     │
│ 3. For each judge:                              │
│    a. Build prompt with criteria                │
│    b. Call LLM API                              │
│    c. Parse response for scores                 │
│    d. Store EvalResult in database              │
│ 4. Aggregate scores across judges               │
│ 5. Return aggregated result                     │
└─────────────────────────────────────────────────┘
```

### 8.2 Prompt Construction

The evaluation prompt follows this structure:

```
SYSTEM:
You are an expert evaluator assessing document quality.
Score each criterion from 1 (poor) to 10 (excellent).
Be consistent and fair in your scoring.

USER:
## Source Document (for reference)
{source_document_excerpt}

## Generated Report to Evaluate
{artifact_content}

## Evaluation Criteria
{criteria_list_with_descriptions}

## Instructions
For each criterion, provide:
1. Score (1-10)
2. One sentence justification

Then provide:
- Overall score (weighted average)
- Summary assessment (2-3 sentences)

Respond in JSON format:
{
  "criteria_scores": {"accuracy": 8, "completeness": 7, ...},
  "reasoning": {"accuracy": "...", "completeness": "...", ...},
  "overall_score": 7.5,
  "summary": "..."
}
```

### 8.3 Response Parsing

Parse JSON from LLM response:

| Step | Action |
|------|--------|
| 1 | Extract JSON from response (may be in markdown code block) |
| 2 | Validate all criteria have scores |
| 3 | Validate scores are in range (1-10) |
| 4 | Calculate overall if not provided |
| 5 | Handle parse errors gracefully |

**Error handling:**
- If JSON invalid: retry with stricter prompt
- If scores missing: use default (5) and flag
- If response truncated: retry with lower max_tokens

### 8.4 Concurrency

Multiple evaluations run concurrently:

```python
# Pseudocode
semaphore = asyncio.Semaphore(max_concurrent)  # e.g., 4

async def evaluate_with_limit(artifact, judge, iteration):
    async with semaphore:
        return await evaluator.evaluate(artifact, context, judge, iteration)

# Run all evaluations concurrently
tasks = [
    evaluate_with_limit(artifact, judge, iteration)
    for artifact in artifacts
    for judge in judges
    for iteration in range(1, iterations + 1)
]
results = await asyncio.gather(*tasks)
```

---

## 9. Single-Doc Scoring

### 9.1 Per-Criterion Scoring

Each criterion receives an integer score:

| Score | Meaning |
|-------|---------|
| 1-2 | Poor — Major issues |
| 3-4 | Below average — Significant gaps |
| 5-6 | Average — Meets basic requirements |
| 7-8 | Good — Above expectations |
| 9-10 | Excellent — Outstanding quality |

### 9.2 Overall Score Calculation

```python
def calculate_overall(criteria_scores: dict, criteria_config: list) -> float:
    """Calculate weighted average of criterion scores."""
    total_weight = sum(c.weight for c in criteria_config)
    weighted_sum = sum(
        criteria_scores[c.name] * c.weight 
        for c in criteria_config
    )
    return weighted_sum / total_weight
```

### 9.3 Multi-Judge Aggregation

When multiple judges evaluate the same artifact:

```python
def aggregate_judge_scores(results: list[EvalResult]) -> AggregatedScore:
    """Aggregate scores from multiple judges."""
    # Group by criterion
    criterion_scores = defaultdict(list)
    for result in results:
        for criterion, score in result.criteria_scores.items():
            criterion_scores[criterion].append(score)
    
    # Average per criterion
    averaged = {
        criterion: statistics.mean(scores)
        for criterion, scores in criterion_scores.items()
    }
    
    # Overall from averaged criteria
    overall = calculate_overall(averaged, criteria_config)
    
    return AggregatedScore(
        criteria_scores=averaged,
        overall_score=overall,
        judge_count=len(results),
        std_dev=calculate_std_dev(results),
    )
```

### 9.4 Multi-Iteration Aggregation

When same judge runs multiple iterations:

| Aggregation | Formula |
|-------------|---------|
| Mean | `sum(scores) / count` |
| Median | `sorted(scores)[count // 2]` |
| Trimmed mean | Drop highest/lowest, then mean |

**Default:** Mean of all iterations.

### 9.5 Confidence Estimation

Estimate confidence based on score variance:

| Std Dev | Confidence | Interpretation |
|---------|------------|----------------|
| < 0.5 | High | Judges agree |
| 0.5 - 1.0 | Medium | Some disagreement |
| > 1.0 | Low | Significant disagreement |

### 9.6 AggregatedScore Data Class

| Field | Type | Description |
|-------|------|-------------|
| `artifact_id` | str | Artifact evaluated |
| `criteria_scores` | dict[str, float] | Averaged per-criterion |
| `overall_score` | float | Final score |
| `judge_count` | int | Number of judges |
| `iteration_count` | int | Iterations per judge |
| `std_dev` | float | Score standard deviation |
| `confidence` | str | `high`, `medium`, `low` |
| `min_score` | float | Lowest individual score |
| `max_score` | float | Highest individual score |

---

## 10. Pairwise Evaluation Interface

### 10.1 PairwiseEvaluator Class

**File:** `app/evaluation/pairwise.py`

| Method | Description |
|--------|-------------|
| `__init__(judge, settings)` | Initialize with judge config |
| `compare(artifact_a, artifact_b, context)` | Compare two artifacts, return winner |
| `compare_batch(pairs, context)` | Compare multiple pairs concurrently |
| `_build_prompt(artifact_a, artifact_b)` | Construct comparison prompt |
| `_parse_winner(response)` | Extract winner from response |

### 10.2 Method Signature

**compare():**
```
async def compare(
    artifact_a: Artifact,
    artifact_b: Artifact,
    context: EvalContext,
    judge: JudgeConfig | None = None,
) -> ComparisonResult
```

### 10.3 ComparisonResult Data Class

| Field | Type | Description |
|-------|------|-------------|
| `comparison_id` | str | ULID |
| `artifact_a_id` | str | First artifact |
| `artifact_b_id` | str | Second artifact |
| `winner` | str | `"a"`, `"b"`, or `"tie"` |
| `confidence` | float | 0-1 confidence in decision |
| `reasoning` | str | Judge's explanation |
| `judge_provider` | str | Judge provider |
| `judge_model` | str | Judge model |
| `duration_ms` | int | Comparison time |
| `created_at` | datetime | Timestamp |

### 10.4 Position Bias Mitigation

To avoid position bias (judges favoring first/second option), optionally run comparisons twice with swapped positions:

| Run | Order | Winner |
|-----|-------|--------|
| 1 | A vs B | A wins |
| 2 | B vs A | A wins (reported as B in this order) |
| Final | — | A wins (consistent) |

If results conflict (A wins run 1, B wins run 2), mark as `tie`.

---

## 11. Pairwise Execution Flow

### 11.1 Pair Selection Strategies

| Strategy | When Used | Description |
|----------|-----------|-------------|
| **Round-robin** | N ≤ 10 | Every artifact compared to every other |
| **Swiss-system** | 10 < N ≤ 50 | Artifacts paired by similar rating |
| **Top-K sampling** | N > 50 | Only compare top candidates |

**Round-robin pair count:** $\frac{N(N-1)}{2}$

| Artifacts | Pairs |
|-----------|-------|
| 5 | 10 |
| 10 | 45 |
| 20 | 190 |

### 11.2 Comparison Prompt

```
SYSTEM:
You are an expert evaluator comparing two documents.
Choose which document is better overall, or declare a tie if they are equal.
Consider: accuracy, completeness, clarity, and relevance.

USER:
## Document A
{artifact_a_content}

## Document B
{artifact_b_content}

## Task
Compare these two documents and determine which is better.

Respond in JSON format:
{
  "winner": "a" | "b" | "tie",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your decision"
}
```

### 11.3 Winner Determination

Parse response and validate:

| Check | Action |
|-------|--------|
| Valid JSON | Extract winner field |
| Winner is "a", "b", or "tie" | Accept |
| Invalid winner value | Retry or mark as tie |
| Confidence < 0.3 | Consider marking as tie |

### 11.4 Batch Processing

```python
# Pseudocode for batch pairwise comparison
async def compare_all_pairs(artifacts: list[Artifact], context: EvalContext):
    pairs = generate_pairs(artifacts)  # Based on strategy
    
    async def compare_with_limit(pair):
        async with semaphore:
            return await evaluator.compare(pair[0], pair[1], context)
    
    results = await asyncio.gather(*[compare_with_limit(p) for p in pairs])
    return results
```

---

## 12. Elo Rating Calculation

### 12.1 Elo Algorithm Overview

Elo rating system ranks artifacts based on head-to-head comparisons:

1. All artifacts start at initial rating (default: 1500)
2. After each comparison, ratings are updated based on outcome
3. Unexpected wins/losses cause larger rating changes
4. Over many comparisons, ratings converge to true skill

### 12.2 Expected Score Formula

The expected score for artifact A against artifact B:

$$E_A = \frac{1}{1 + 10^{(R_B - R_A) / 400}}$$

Where:
- $E_A$ = Expected probability A wins
- $R_A$ = Current rating of A
- $R_B$ = Current rating of B

### 12.3 Rating Update Formula

After a comparison:

$$R'_A = R_A + K \times (S_A - E_A)$$

Where:
- $R'_A$ = New rating for A
- $K$ = K-factor (default: 32)
- $S_A$ = Actual score (1 for win, 0.5 for tie, 0 for loss)
- $E_A$ = Expected score

### 12.4 K-Factor Configuration

| K-Factor | Effect | Use Case |
|----------|--------|----------|
| 16 | Small changes | Stable ratings, many games |
| 32 | Medium changes | Default, balances speed/stability |
| 64 | Large changes | Few games, rapid convergence |

### 12.5 Implementation

```python
class EloCalculator:
    def __init__(self, k_factor: int = 32, initial_rating: int = 1500):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.ratings: dict[str, float] = {}
    
    def get_rating(self, artifact_id: str) -> float:
        return self.ratings.get(artifact_id, self.initial_rating)
    
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def update_ratings(self, result: ComparisonResult) -> tuple[float, float]:
        rating_a = self.get_rating(result.artifact_a_id)
        rating_b = self.get_rating(result.artifact_b_id)
        
        expected_a = self.expected_score(rating_a, rating_b)
        expected_b = 1 - expected_a
        
        # Actual scores
        if result.winner == "a":
            score_a, score_b = 1.0, 0.0
        elif result.winner == "b":
            score_a, score_b = 0.0, 1.0
        else:  # tie
            score_a, score_b = 0.5, 0.5
        
        # Update ratings
        new_rating_a = rating_a + self.k_factor * (score_a - expected_a)
        new_rating_b = rating_b + self.k_factor * (score_b - expected_b)
        
        self.ratings[result.artifact_a_id] = new_rating_a
        self.ratings[result.artifact_b_id] = new_rating_b
        
        return new_rating_a, new_rating_b
```

### 12.6 Processing Order

Comparison order can affect final ratings. Options:

| Order | Description |
|-------|-------------|
| Chronological | Process in order comparisons were made |
| Random shuffle | Reduce ordering bias |
| Multiple passes | Process all comparisons multiple times |

**Recommendation:** Chronological for simplicity; ratings stabilize with enough comparisons.

---

## 13. Top-N Selection

### 13.1 Purpose

Select the best artifacts to advance to the Combine Phase. Not all artifacts need to be combined — only the top performers.

### 13.2 Selection Criteria

Artifacts are ranked using (in priority order):

| Priority | Criterion | Rationale |
|----------|-----------|-----------|
| 1 | Elo rating | Most reliable if pairwise was run |
| 2 | Single-doc overall score | Fallback if no pairwise |
| 3 | Creation timestamp | Tie-breaker (newer preferred) |

### 13.3 Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `top_n_count` | int | 3 | Number of artifacts to select |
| `top_n_threshold` | float | 0.7 | Minimum score (0-1 normalized) |
| `top_n_min` | int | 1 | Minimum to select even below threshold |
| `top_n_max` | int | 5 | Maximum even if all above threshold |

### 13.4 Selection Algorithm

```python
def select_top_n(
    artifacts: list[Artifact],
    scores: dict[str, AggregatedScore],
    elo_ratings: dict[str, float],
    config: TopNConfig,
) -> list[Artifact]:
    """Select top N artifacts for Combine Phase."""
    
    # Score each artifact (Elo if available, else single-doc)
    def get_rank_score(artifact_id: str) -> float:
        if artifact_id in elo_ratings:
            # Normalize Elo to 0-1 (assuming 1000-2000 range)
            return (elo_ratings[artifact_id] - 1000) / 1000
        elif artifact_id in scores:
            return scores[artifact_id].overall_score / 10
        else:
            return 0.0
    
    # Sort by rank score descending
    ranked = sorted(artifacts, key=lambda a: get_rank_score(a.artifact_id), reverse=True)
    
    # Apply threshold
    above_threshold = [a for a in ranked if get_rank_score(a.artifact_id) >= config.threshold]
    
    # Select count
    if len(above_threshold) >= config.count:
        return above_threshold[:config.count]
    elif len(above_threshold) >= config.min:
        return above_threshold
    else:
        # Below minimum, take best available
        return ranked[:config.min]
```

### 13.5 Tie-Breaking

When artifacts have equal scores:

| Tie-Breaker | Description |
|-------------|-------------|
| 1. More pairwise wins | Higher win count |
| 2. Lower score variance | More consistent across judges |
| 3. Newer artifact | Most recent creation time |

### 13.6 Selection Results

**TopNResult data class:**

| Field | Type | Description |
|-------|------|-------------|
| `selected` | list[Artifact] | Artifacts advancing to Combine |
| `rankings` | list[RankedArtifact] | All artifacts with ranks/scores |
| `selection_method` | str | `"elo"` or `"single_doc"` |
| `threshold_applied` | float | Threshold used |

---

## 14. Evaluation Orchestration

### 14.1 EvalOrchestrator Class

**File:** `app/evaluation/orchestrator.py`

Coordinates the full evaluation pipeline:

| Method | Description |
|--------|-------------|
| `__init__(config, judges, criteria)` | Initialize with configuration |
| `evaluate_run(run_id)` | Run full evaluation pipeline |
| `run_single_doc_phase(artifacts)` | Execute single-doc evaluations |
| `run_pairwise_phase(artifacts)` | Execute pairwise comparisons |
| `calculate_rankings(results)` | Compute final rankings |
| `select_top_n(rankings)` | Select artifacts for Combine |
| `generate_report(results)` | Create HTML report |

### 14.2 Full Pipeline Flow

```
POST /runs/{id}/evaluate
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 1. Load artifacts for run                           │
│ 2. Single-Doc Phase:                                │
│    - For each artifact × judge × iteration          │
│    - Score on criteria                              │
│    - Store eval_results                             │
│ 3. Aggregate single-doc scores                      │
│ 4. Pairwise Phase (optional):                       │
│    - Generate pairs (round-robin or sampled)        │
│    - Compare each pair                              │
│    - Store pairwise_comparisons                     │
│ 5. Calculate Elo ratings                            │
│ 6. Compute final rankings                           │
│ 7. Select Top-N for Combine                         │
│ 8. Generate HTML report                             │
│ 9. Update run status                                │
└─────────────────────────────────────────────────────┘
    │
    ▼
Response: evaluation complete
```

### 14.3 Phase Configuration

| Phase | Required | Default | Can Disable |
|-------|----------|---------|-------------|
| Single-doc | Yes | Enabled | No |
| Pairwise | No | Enabled if N > 1 | Yes |
| Top-N selection | No | Enabled | Yes |
| Report generation | No | Enabled | Yes |

### 14.4 Progress Tracking

Track progress during evaluation:

| Field | Type | Description |
|-------|------|-------------|
| `phase` | str | Current phase |
| `artifacts_total` | int | Total artifacts |
| `artifacts_evaluated` | int | Completed evaluations |
| `pairs_total` | int | Total pairs (if pairwise) |
| `pairs_compared` | int | Completed comparisons |
| `progress_percent` | int | Overall 0-100 |

### 14.5 Cancellation

Evaluation can be cancelled:

1. Set cancellation flag
2. Complete current LLM call
3. Save partial results
4. Mark evaluation as `cancelled`

Partial results are kept — evaluation can be resumed.

---

## 15. Post-Combine Evaluation

### 15.1 When It Runs

Post-Combine evaluation runs after the Combine Phase produces combined artifacts:

```
Generation Phase → Eval Phase → Combine Phase → Post-Combine Eval
                                      ↓
                              Combined artifacts
                                      ↓
                              Evaluate combined
```

### 15.2 How It Differs

| Aspect | Pre-Combine Eval | Post-Combine Eval |
|--------|------------------|-------------------|
| Input | Generator artifacts (FPF, GPT-R) | Combined artifacts |
| Purpose | Select best for combining | Assess final quality |
| Top-N | Yes, selects for Combine | Optional |
| Pairwise | Often yes | Usually no (few artifacts) |
| Report | Intermediate | Final report |

### 15.3 Configuration

Post-Combine evaluation uses same judges/criteria but can override:

```json
{
  "post_combine_eval": {
    "enabled": true,
    "judges": ["gpt-4o"],
    "iterations": 2,
    "pairwise": false,
    "criteria": [
      {"name": "coherence", "weight": 0.3, "description": "Combined content flows well"},
      {"name": "completeness", "weight": 0.3},
      {"name": "accuracy", "weight": 0.4}
    ]
  }
}
```

### 15.4 Result Storage

Post-Combine results stored in same tables with flag:

| Field | Value |
|-------|-------|
| `eval_results.artifact_id` | Combined artifact ID |
| `artifacts.generator` | `"combine"` |
| `artifacts.metadata.eval_phase` | `"post_combine"` |

### 15.5 Final Report Integration

Post-Combine results appear in final HTML report:

- Section: "Combined Artifact Evaluation"
- Comparison to pre-combine top scores
- Quality improvement/degradation assessment

---

## 16. Result Aggregation

### 16.1 Aggregation Hierarchy

Results are aggregated at multiple levels:

```
Individual eval_results (per judge, per iteration)
    ↓ Aggregate by iteration
Per-judge scores (mean of iterations)
    ↓ Aggregate by judge
Per-artifact scores (weighted mean of judges)
    ↓ Rank
Final rankings
```

### 16.2 Iteration Aggregation

For same judge evaluating same artifact multiple times:

```python
def aggregate_iterations(results: list[EvalResult]) -> JudgeScore:
    """Aggregate multiple iterations from one judge."""
    # Mean of overall scores
    overall = statistics.mean(r.overall_score for r in results)
    
    # Mean per criterion
    criteria = {}
    for criterion in results[0].criteria_scores.keys():
        criteria[criterion] = statistics.mean(
            r.criteria_scores[criterion] for r in results
        )
    
    return JudgeScore(
        overall_score=overall,
        criteria_scores=criteria,
        iteration_count=len(results),
        std_dev=statistics.stdev(r.overall_score for r in results) if len(results) > 1 else 0,
    )
```

### 16.3 Judge Aggregation

Combine scores from multiple judges:

```python
def aggregate_judges(judge_scores: list[JudgeScore], weights: list[float]) -> ArtifactScore:
    """Aggregate scores from multiple judges with weights."""
    total_weight = sum(weights)
    
    # Weighted mean of overall scores
    overall = sum(s.overall_score * w for s, w in zip(judge_scores, weights)) / total_weight
    
    # Weighted mean per criterion
    criteria = {}
    for criterion in judge_scores[0].criteria_scores.keys():
        criteria[criterion] = sum(
            s.criteria_scores[criterion] * w 
            for s, w in zip(judge_scores, weights)
        ) / total_weight
    
    return ArtifactScore(
        overall_score=overall,
        criteria_scores=criteria,
        judge_count=len(judge_scores),
    )
```

### 16.4 Final Rankings

Rank artifacts by combined metrics:

| Rank Method | Formula | Use Case |
|-------------|---------|----------|
| Elo only | Sort by Elo rating | Many pairwise comparisons |
| Score only | Sort by overall score | No pairwise |
| Combined | `0.6 × Elo_norm + 0.4 × Score_norm` | Both available |

```python
def compute_final_rankings(
    artifact_scores: dict[str, ArtifactScore],
    elo_ratings: dict[str, float],
) -> list[RankedArtifact]:
    """Compute final rankings combining scores and Elo."""
    
    rankings = []
    for artifact_id, score in artifact_scores.items():
        elo = elo_ratings.get(artifact_id, 1500)
        
        # Normalize Elo to 0-10 scale
        elo_norm = (elo - 1000) / 100  # 1500 → 5, 2000 → 10
        
        # Combined rank score
        if artifact_id in elo_ratings:
            rank_score = 0.6 * elo_norm + 0.4 * score.overall_score
        else:
            rank_score = score.overall_score
        
        rankings.append(RankedArtifact(
            artifact_id=artifact_id,
            rank_score=rank_score,
            overall_score=score.overall_score,
            elo_rating=elo,
            criteria_scores=score.criteria_scores,
        ))
    
    # Sort descending
    rankings.sort(key=lambda r: r.rank_score, reverse=True)
    
    # Assign ranks
    for i, r in enumerate(rankings):
        r.rank = i + 1
    
    return rankings
```

### 16.5 RankedArtifact Data Class

| Field | Type | Description |
|-------|------|-------------|
| `artifact_id` | str | Artifact ID |
| `rank` | int | Final rank (1 = best) |
| `rank_score` | float | Combined ranking score |
| `overall_score` | float | Single-doc overall |
| `elo_rating` | float | Elo rating |
| `criteria_scores` | dict | Per-criterion scores |
| `judge_count` | int | Judges that evaluated |
| `comparison_count` | int | Pairwise comparisons |

---

## 17. HTML Report Generation

### 17.1 Report Structure

**File:** `app/evaluation/report.py`

| Section | Content |
|---------|---------|
| Header | Run title, date, configuration summary |
| Executive Summary | Top artifact, key metrics, recommendations |
| Rankings Table | All artifacts ranked with scores |
| Criteria Breakdown | Per-criterion scores for top artifacts |
| Pairwise Results | Win/loss matrix, Elo progression |
| Judge Analysis | Per-judge score distributions |
| Appendix | Full eval results, methodology |

### 17.2 Report Generator

```python
class HtmlReportGenerator:
    def __init__(self, template_dir: Path):
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True,
        )
    
    async def generate(
        self,
        run: Run,
        rankings: list[RankedArtifact],
        eval_results: list[EvalResult],
        comparisons: list[ComparisonResult],
    ) -> str:
        """Generate HTML report."""
        template = self.env.get_template("eval_report.html")
        
        return template.render(
            run=run,
            rankings=rankings,
            summary=self._build_summary(rankings),
            criteria_chart=self._build_criteria_chart(rankings[:5]),
            elo_chart=self._build_elo_chart(rankings),
            win_matrix=self._build_win_matrix(comparisons),
            generated_at=datetime.utcnow(),
        )
```

### 17.3 Visualizations

| Chart | Type | Shows |
|-------|------|-------|
| Rankings bar chart | Horizontal bars | Overall scores by artifact |
| Criteria radar | Radar/spider | Multi-criteria comparison |
| Elo progression | Line chart | Rating changes over comparisons |
| Win/loss matrix | Heatmap | Pairwise comparison outcomes |
| Score distribution | Histogram | Score spread across artifacts |

**Implementation:** Charts rendered using inline SVG or embedded Chart.js.

### 17.4 Template Structure

```html
<!-- templates/eval_report.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Evaluation Report: {{ run.title }}</title>
    <style>/* Embedded CSS */</style>
</head>
<body>
    <header>
        <h1>{{ run.title }}</h1>
        <p>Generated: {{ generated_at }}</p>
    </header>
    
    <section id="summary">
        <h2>Executive Summary</h2>
        {{ summary | safe }}
    </section>
    
    <section id="rankings">
        <h2>Final Rankings</h2>
        <table><!-- Rankings table --></table>
    </section>
    
    <section id="criteria">
        <h2>Criteria Analysis</h2>
        {{ criteria_chart | safe }}
    </section>
    
    <section id="pairwise">
        <h2>Pairwise Comparisons</h2>
        {{ win_matrix | safe }}
        {{ elo_chart | safe }}
    </section>
</body>
</html>
```

### 17.5 Export Formats

| Format | Method | Use Case |
|--------|--------|----------|
| HTML | Primary | Web viewing, email |
| PDF | Via browser print | Formal reports |
| JSON | API response | Programmatic access |
| CSV | Rankings export | Spreadsheet analysis |

### 17.6 Report Storage

Reports stored via StorageProvider:

**Path:** `{outputs_repo}/runs/{run_id}/reports/eval_report.html`

**Metadata:** `eval_report.html.meta.json` with generation info.

---

## 18. API Endpoints

### 18.1 Trigger Evaluation

**Endpoint:** `POST /api/v1/runs/{run_id}/evaluate`

**Request Body:**
```json
{
  "mode": "full",
  "config": {
    "judges": [
      {"provider": "openai", "model": "gpt-4o"},
      {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}
    ],
    "iterations": 3,
    "pairwise": true,
    "top_n": 3
  },
  "artifacts": ["01HGWJ...", "01HGXYZ..."]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | str | `"full"` | `"single_doc"`, `"pairwise"`, `"full"` |
| `config` | object | Run config | Override eval settings |
| `artifacts` | list | All | Specific artifacts to evaluate |

**Response (202 Accepted):**
```json
{
  "eval_task_id": "01HGABC...",
  "status": "pending",
  "artifacts_count": 10,
  "estimated_duration_seconds": 300,
  "message": "Evaluation started"
}
```

### 18.2 Check Evaluation Status

**Endpoint:** `GET /api/v1/runs/{run_id}/evaluate/status`

**Response:**
```json
{
  "eval_task_id": "01HGABC...",
  "status": "running",
  "phase": "pairwise",
  "progress": {
    "single_doc_complete": true,
    "artifacts_evaluated": 10,
    "pairs_total": 45,
    "pairs_compared": 20,
    "percent": 65
  },
  "started_at": "2025-12-04T12:00:00Z",
  "estimated_completion": "2025-12-04T12:05:00Z"
}
```

### 18.3 Get Evaluation Results

**Endpoint:** `GET /api/v1/runs/{run_id}/evaluate/results`

**Query Parameters:**
- `format` — `json` (default), `summary`
- `include` — `rankings`, `scores`, `comparisons`, `all`

**Response:**
```json
{
  "run_id": "01HGWJ...",
  "status": "completed",
  "rankings": [
    {
      "rank": 1,
      "artifact_id": "01HGDEF...",
      "generator": "fpf",
      "model": "gpt-4o",
      "overall_score": 8.2,
      "elo_rating": 1620,
      "criteria_scores": {
        "accuracy": 8.5,
        "completeness": 8.0,
        "clarity": 8.3
      }
    }
  ],
  "summary": {
    "artifacts_evaluated": 10,
    "judges_used": 2,
    "iterations_per_judge": 3,
    "pairwise_comparisons": 45,
    "top_score": 8.2,
    "mean_score": 6.8,
    "score_std_dev": 1.2
  },
  "completed_at": "2025-12-04T12:05:00Z"
}
```

### 18.4 Get Reports

**Endpoint:** `GET /api/v1/runs/{run_id}/reports`

**Response:**
```json
{
  "reports": [
    {
      "report_id": "01HGRPT...",
      "type": "eval",
      "format": "html",
      "storage_path": "runs/01HGWJ.../reports/eval_report.html",
      "created_at": "2025-12-04T12:05:00Z"
    }
  ]
}
```

**Endpoint:** `GET /api/v1/runs/{run_id}/reports/{report_id}`

Returns raw report content with appropriate Content-Type.

### 18.5 Cancel Evaluation

**Endpoint:** `POST /api/v1/runs/{run_id}/evaluate/cancel`

**Response:**
```json
{
  "eval_task_id": "01HGABC...",
  "status": "cancelling",
  "message": "Cancellation requested, saving partial results"
}
```

---

## 19. Tests

### 19.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_single_doc_evaluator.py` | SingleDocEvaluator scoring logic |
| `test_pairwise_evaluator.py` | PairwiseEvaluator comparison logic |
| `test_elo_calculator.py` | Elo rating calculations |
| `test_eval_orchestrator.py` | Orchestration flow |
| `test_result_aggregator.py` | Score aggregation |
| `test_html_report_generator.py` | Report generation |

### 19.2 SingleDocEvaluator Tests

```python
# test_single_doc_evaluator.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from acm2.evaluation import SingleDocEvaluator
from acm2.evaluation.models import EvalResult, CriterionScore

class TestSingleDocEvaluator:
    """Tests for SingleDocEvaluator."""
    
    @pytest.fixture
    def mock_model_client(self):
        client = AsyncMock()
        # Mock judge response with scores
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="""
{
    "scores": {
        "accuracy": {"score": 8, "justification": "Content is factually correct"},
        "completeness": {"score": 7, "justification": "Covers main points"},
        "clarity": {"score": 9, "justification": "Well organized"},
        "relevance": {"score": 8, "justification": "Addresses the topic"},
        "formatting": {"score": 8, "justification": "Good structure"}
    },
    "overall": 8,
    "summary": "High quality document"
}
"""))]
        )
        return client
    
    @pytest.fixture
    def evaluator(self, mock_model_client):
        return SingleDocEvaluator(
            model_client=mock_model_client,
            judge_config={"model": "gpt-4o", "temperature": 0.1}
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_returns_scores(self, evaluator):
        """Verify evaluate() returns criterion scores."""
        result = await evaluator.evaluate(
            artifact_content="# Test Document\n\nContent here.",
            criteria=["accuracy", "completeness", "clarity"],
            reference_content="Original prompt content"
        )
        
        assert isinstance(result, EvalResult)
        assert result.overall_score == 8
        assert len(result.criterion_scores) == 5
        assert result.criterion_scores["accuracy"].score == 8
    
    @pytest.mark.asyncio
    async def test_evaluate_handles_parse_error(self, evaluator, mock_model_client):
        """Verify graceful handling of malformed judge response."""
        mock_model_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Not valid JSON"))]
        )
        
        with pytest.raises(EvalParseError):
            await evaluator.evaluate(
                artifact_content="Content",
                criteria=["accuracy"],
                reference_content="Reference"
            )
    
    @pytest.mark.asyncio
    async def test_evaluate_validates_score_range(self, evaluator, mock_model_client):
        """Verify scores outside 1-10 are rejected."""
        mock_model_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="""
{
    "scores": {"accuracy": {"score": 15, "justification": "Invalid"}},
    "overall": 15
}
"""))]
        )
        
        with pytest.raises(EvalValidationError):
            await evaluator.evaluate(
                artifact_content="Content",
                criteria=["accuracy"],
                reference_content="Reference"
            )
```

### 19.3 PairwiseEvaluator Tests

```python
# test_pairwise_evaluator.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from acm2.evaluation import PairwiseEvaluator
from acm2.evaluation.models import PairwiseResult

class TestPairwiseEvaluator:
    """Tests for PairwiseEvaluator."""
    
    @pytest.fixture
    def mock_model_client(self):
        client = AsyncMock()
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="""
{
    "winner": "A",
    "confidence": 0.85,
    "reasoning": "Document A is more comprehensive and better organized."
}
"""))]
        )
        return client
    
    @pytest.fixture
    def evaluator(self, mock_model_client):
        return PairwiseEvaluator(
            model_client=mock_model_client,
            judge_config={"model": "gpt-4o", "temperature": 0.1}
        )
    
    @pytest.mark.asyncio
    async def test_compare_returns_winner(self, evaluator):
        """Verify compare() returns correct winner."""
        result = await evaluator.compare(
            artifact_a="Document A content",
            artifact_b="Document B content",
            reference="Original prompt"
        )
        
        assert isinstance(result, PairwiseResult)
        assert result.winner == "A"
        assert result.confidence == 0.85
    
    @pytest.mark.asyncio
    async def test_compare_handles_tie(self, evaluator, mock_model_client):
        """Verify tie handling."""
        mock_model_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="""
{
    "winner": "TIE",
    "confidence": 0.5,
    "reasoning": "Both documents are of similar quality."
}
"""))]
        )
        
        result = await evaluator.compare(
            artifact_a="Doc A",
            artifact_b="Doc B",
            reference="Ref"
        )
        
        assert result.winner == "TIE"
    
    @pytest.mark.asyncio
    async def test_compare_randomizes_order(self, evaluator):
        """Verify position bias mitigation via randomization."""
        # Run multiple comparisons, verify both orderings occur
        results = []
        for _ in range(10):
            result = await evaluator.compare(
                artifact_a="A",
                artifact_b="B",
                reference="Ref",
                randomize_order=True
            )
            results.append(result)
        
        # Check that internal tracking shows both orderings
        orderings = [r._internal_order for r in results]
        assert "AB" in orderings or "BA" in orderings
```

### 19.4 EloCalculator Tests

```python
# test_elo_calculator.py

import pytest
from acm2.evaluation import EloCalculator

class TestEloCalculator:
    """Tests for Elo rating calculations."""
    
    @pytest.fixture
    def calculator(self):
        return EloCalculator(k_factor=32, initial_rating=1500)
    
    def test_initial_ratings(self, calculator):
        """Verify new artifacts start at initial rating."""
        rating = calculator.get_initial_rating()
        assert rating == 1500
    
    def test_expected_score_equal_ratings(self, calculator):
        """Verify expected score is 0.5 for equal ratings."""
        expected = calculator.expected_score(1500, 1500)
        assert expected == 0.5
    
    def test_expected_score_higher_wins(self, calculator):
        """Verify higher-rated player has higher expected score."""
        expected_higher = calculator.expected_score(1600, 1400)
        expected_lower = calculator.expected_score(1400, 1600)
        
        assert expected_higher > 0.5
        assert expected_lower < 0.5
        assert abs(expected_higher + expected_lower - 1.0) < 0.001
    
    def test_update_ratings_winner_gains(self, calculator):
        """Verify winner gains rating points."""
        new_winner, new_loser = calculator.update_ratings(
            winner_rating=1500,
            loser_rating=1500,
            is_tie=False
        )
        
        assert new_winner > 1500
        assert new_loser < 1500
        # Zero-sum: gains equal losses
        assert abs((new_winner - 1500) + (new_loser - 1500)) < 0.001
    
    def test_update_ratings_tie(self, calculator):
        """Verify tie with equal ratings produces no change."""
        new_a, new_b = calculator.update_ratings(
            winner_rating=1500,
            loser_rating=1500,
            is_tie=True
        )
        
        assert new_a == 1500
        assert new_b == 1500
    
    def test_upset_bonus(self, calculator):
        """Verify underdog upset yields larger rating change."""
        # Underdog (1400) beats favorite (1600)
        new_underdog, new_favorite = calculator.update_ratings(
            winner_rating=1400,  # Winner was lower rated
            loser_rating=1600,
            is_tie=False
        )
        
        underdog_gain = new_underdog - 1400
        
        # Normal win (equal ratings)
        normal_winner, _ = calculator.update_ratings(1500, 1500, False)
        normal_gain = normal_winner - 1500
        
        assert underdog_gain > normal_gain
```

### 19.5 EvalOrchestrator Tests

```python
# test_eval_orchestrator.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from acm2.evaluation import EvalOrchestrator
from acm2.database import Database

class TestEvalOrchestrator:
    """Tests for EvalOrchestrator."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Database)
    
    @pytest.fixture
    def mock_single_evaluator(self):
        evaluator = AsyncMock()
        evaluator.evaluate.return_value = MagicMock(
            overall_score=8.0,
            criterion_scores={"accuracy": MagicMock(score=8)}
        )
        return evaluator
    
    @pytest.fixture
    def mock_pairwise_evaluator(self):
        evaluator = AsyncMock()
        evaluator.compare.return_value = MagicMock(
            winner="A",
            confidence=0.8
        )
        return evaluator
    
    @pytest.fixture
    def orchestrator(self, mock_db, mock_single_evaluator, mock_pairwise_evaluator):
        return EvalOrchestrator(
            db=mock_db,
            single_evaluator=mock_single_evaluator,
            pairwise_evaluator=mock_pairwise_evaluator,
            config={
                "num_iterations": 3,
                "pairwise_strategy": "round_robin"
            }
        )
    
    @pytest.mark.asyncio
    async def test_run_single_doc_evaluation(self, orchestrator, mock_db):
        """Verify single-doc evaluation runs for all artifacts."""
        mock_db.get_artifacts_for_run.return_value = [
            {"id": 1, "content": "Doc 1"},
            {"id": 2, "content": "Doc 2"}
        ]
        
        await orchestrator.run_single_doc_evaluation(run_id=1)
        
        # Should evaluate each artifact
        assert orchestrator._single_evaluator.evaluate.call_count == 2 * 3  # 2 artifacts × 3 iterations
    
    @pytest.mark.asyncio
    async def test_run_pairwise_evaluation(self, orchestrator, mock_db):
        """Verify pairwise evaluation generates all pairs."""
        mock_db.get_artifacts_for_run.return_value = [
            {"id": 1, "content": "Doc 1", "elo_rating": 1500},
            {"id": 2, "content": "Doc 2", "elo_rating": 1500},
            {"id": 3, "content": "Doc 3", "elo_rating": 1500}
        ]
        
        await orchestrator.run_pairwise_evaluation(run_id=1)
        
        # Round-robin: 3 artifacts = 3 pairs (1v2, 1v3, 2v3)
        assert orchestrator._pairwise_evaluator.compare.call_count == 3
    
    @pytest.mark.asyncio
    async def test_select_top_n(self, orchestrator, mock_db):
        """Verify top-N selection by Elo rating."""
        mock_db.get_artifacts_with_elo.return_value = [
            {"id": 1, "elo_rating": 1600},
            {"id": 2, "elo_rating": 1550},
            {"id": 3, "elo_rating": 1450}
        ]
        
        top = await orchestrator.select_top_n(run_id=1, n=2)
        
        assert len(top) == 2
        assert top[0]["id"] == 1  # Highest Elo
        assert top[1]["id"] == 2
```

### 19.6 Integration Tests

```python
# test_evaluation_integration.py

import pytest
import tempfile
import os
from pathlib import Path
from acm2.evaluation import EvalOrchestrator, SingleDocEvaluator, PairwiseEvaluator
from acm2.database import Database
from acm2.storage import FileSystemStorage

class TestEvaluationIntegration:
    """Integration tests for full evaluation pipeline."""
    
    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def db(self, temp_workspace):
        db_path = temp_workspace / "test.db"
        db = Database(db_path)
        db.initialize()
        return db
    
    @pytest.fixture
    def storage(self, temp_workspace):
        return FileSystemStorage(temp_workspace / "storage")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_evaluation_pipeline(self, db, storage, temp_workspace):
        """Test complete evaluation from artifacts to rankings."""
        # Setup: Create run with artifacts
        run_id = db.create_run({
            "name": "Test Run",
            "config": {"generators": ["fpf"]}
        })
        
        # Create test artifacts
        for i in range(3):
            content = f"# Document {i}\n\nTest content for document {i}."
            artifact_path = storage.save_artifact(
                run_id=run_id,
                generator="fpf",
                doc_name="test_doc",
                content=content,
                iteration=i
            )
            db.create_artifact({
                "run_id": run_id,
                "generator": "fpf",
                "doc_name": "test_doc",
                "iteration": i,
                "path": str(artifact_path)
            })
        
        # Use mock evaluators for integration test
        # (Real LLM calls would be in E2E tests)
        orchestrator = EvalOrchestrator(
            db=db,
            single_evaluator=MockSingleEvaluator(),
            pairwise_evaluator=MockPairwiseEvaluator(),
            config={"num_iterations": 1, "pairwise_strategy": "round_robin"}
        )
        
        # Run evaluation
        await orchestrator.run_evaluation(run_id)
        
        # Verify results stored
        results = db.get_eval_results(run_id)
        assert len(results) == 3  # One per artifact
        
        # Verify Elo ratings computed
        artifacts = db.get_artifacts_with_elo(run_id)
        assert all(a["elo_rating"] is not None for a in artifacts)
        
        # Verify rankings deterministic
        top_2 = await orchestrator.select_top_n(run_id, n=2)
        assert len(top_2) == 2
```

### 19.7 Mock Evaluator for Testing

```python
# acm2/evaluation/mock.py

class MockSingleEvaluator:
    """Mock evaluator for testing without LLM calls."""
    
    def __init__(self, scores: dict = None):
        self._scores = scores or {
            "accuracy": 8,
            "completeness": 7,
            "clarity": 8,
            "relevance": 7,
            "formatting": 8
        }
        self._call_count = 0
    
    async def evaluate(self, artifact_content: str, criteria: list, reference_content: str):
        self._call_count += 1
        
        # Vary scores slightly based on content length (for testing)
        length_bonus = min(len(artifact_content) / 1000, 1.0)
        
        return EvalResult(
            overall_score=sum(self._scores.values()) / len(self._scores) + length_bonus,
            criterion_scores={
                k: CriterionScore(score=v, justification=f"Mock score for {k}")
                for k, v in self._scores.items()
            },
            summary="Mock evaluation"
        )


class MockPairwiseEvaluator:
    """Mock pairwise evaluator for testing."""
    
    def __init__(self, winner_strategy: str = "longer"):
        self._strategy = winner_strategy
        self._call_count = 0
    
    async def compare(self, artifact_a: str, artifact_b: str, reference: str, **kwargs):
        self._call_count += 1
        
        if self._strategy == "longer":
            winner = "A" if len(artifact_a) >= len(artifact_b) else "B"
        elif self._strategy == "random":
            import random
            winner = random.choice(["A", "B"])
        else:
            winner = "A"
        
        return PairwiseResult(
            winner=winner,
            confidence=0.75,
            reasoning="Mock comparison"
        )
```

---

## 20. Success Criteria

### 20.1 Functional Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| F-10.1 | Single-doc evaluation scores artifacts on 5 criteria | Unit test, manual test |
| F-10.2 | Scores are in range 1-10 with 0.5 increments | Validation in code |
| F-10.3 | Multiple judges can be configured | Config test |
| F-10.4 | Multiple iterations aggregate to mean score | Unit test |
| F-10.5 | Pairwise comparison returns winner (A, B, or TIE) | Unit test |
| F-10.6 | Elo ratings computed with K=32, initial=1500 | Unit test |
| F-10.7 | Top-N selection returns highest-rated artifacts | Unit test |
| F-10.8 | Post-combine evaluation uses same pipeline | Integration test |
| F-10.9 | Results persisted to database | Integration test |
| F-10.10 | HTML reports generated | Integration test |

### 20.2 Quality Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| Q-10.1 | All public methods have docstrings | Code review |
| Q-10.2 | Type hints on all function signatures | mypy check |
| Q-10.3 | Error handling for LLM failures with retry | Unit test |
| Q-10.4 | Logging at INFO level for pipeline progress | Log inspection |
| Q-10.5 | Unit test coverage ≥ 80% | pytest-cov |

### 20.3 Performance Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| P-10.1 | Single-doc evaluation < 30s per artifact | Manual timing |
| P-10.2 | Pairwise comparison < 30s per pair | Manual timing |
| P-10.3 | Full evaluation of 10 artifacts < 10 minutes | Integration test |
| P-10.4 | Report generation < 5s | Manual timing |

### 20.4 Acceptance Checklist

- [ ] `SingleDocEvaluator.evaluate()` returns scores for all criteria
- [ ] `PairwiseEvaluator.compare()` returns winner with reasoning
- [ ] `EloCalculator` correctly updates ratings after each comparison
- [ ] `EvalOrchestrator` coordinates full pipeline
- [ ] Database schema stores all eval results
- [ ] HTML report displays scores, rankings, comparisons
- [ ] API endpoints trigger and query evaluations
- [ ] Error handling recovers from LLM failures
- [ ] All unit tests pass
- [ ] Integration test demonstrates full pipeline

---

## 21. File Structure

```
acm2/
├── evaluation/
│   ├── __init__.py              # Public exports
│   ├── models.py                # EvalResult, PairwiseResult, CriterionScore
│   ├── single_doc.py            # SingleDocEvaluator class
│   ├── pairwise.py              # PairwiseEvaluator class
│   ├── elo.py                   # EloCalculator class
│   ├── orchestrator.py          # EvalOrchestrator class
│   ├── aggregator.py            # ResultAggregator class
│   ├── mock.py                  # MockSingleEvaluator, MockPairwiseEvaluator
│   ├── prompts/
│   │   ├── single_doc.txt       # Prompt template for single-doc eval
│   │   └── pairwise.txt         # Prompt template for pairwise comparison
│   └── reports/
│       ├── __init__.py
│       ├── generator.py         # HtmlReportGenerator class
│       └── templates/
│           ├── base.html        # Base Jinja2 template
│           ├── eval_report.html # Full evaluation report
│           └── partials/
│               ├── scores_table.html
│               ├── rankings.html
│               └── comparisons.html
├── api/
│   └── routes/
│       └── evaluation.py        # API endpoints (added to existing router)
├── database/
│   └── migrations/
│       └── 010_eval_tables.sql  # Eval schema migration
└── tests/
    └── evaluation/
        ├── __init__.py
        ├── test_single_doc_evaluator.py
        ├── test_pairwise_evaluator.py
        ├── test_elo_calculator.py
        ├── test_eval_orchestrator.py
        ├── test_result_aggregator.py
        ├── test_html_report_generator.py
        └── test_evaluation_integration.py
```

### Module Dependencies

```
orchestrator.py
    ├── single_doc.py
    │   └── models.py
    ├── pairwise.py
    │   └── models.py
    ├── elo.py
    ├── aggregator.py
    │   └── models.py
    └── reports/generator.py
        └── templates/
```

---

## 22. Next Steps

After Step 10 (Evaluation and Reporting) is complete:

### Immediate Dependencies

| Step | Name | Dependency on Step 10 |
|------|------|----------------------|
| **Step 11** | Web GUI | Displays eval results, rankings, reports |
| **Step 16** | GPT-R Adapter | Produces artifacts to evaluate |
| **Step 17** | Combine | Uses Top-N selection to get inputs |

### Recommended Order

1. **Step 11 (Web GUI)** — Build UI to display evaluation results. Users need visibility into scores and rankings.

2. **Step 16 (GPT-R Adapter)** — Add second generator. Evaluation system is ready to score GPT-R outputs.

3. **Step 17 (Combine Phase)** — Merge top-rated artifacts. Relies on Top-N selection from evaluation.

### Integration Points

| From Step 10 | Used By | Purpose |
|--------------|---------|---------|
| `EvalOrchestrator.select_top_n()` | Step 17 (Combine) | Select inputs for merging |
| `HtmlReportGenerator.generate()` | Step 11 (Web GUI) | Display reports in browser |
| Eval API endpoints | Step 11 (Web GUI) | Trigger evals, fetch results |
| `eval_results` table | Step 11 (Web GUI) | Show scores in dashboard |
| `elo_ratings` table | Step 11 (Web GUI) | Show rankings in dashboard |

### Future Enhancements (Post-MVP)

| Enhancement | Description |
|-------------|-------------|
| Parallel evaluation | Run multiple judge calls concurrently |
| Custom criteria | User-defined evaluation criteria |
| Multi-model judges | Use different models for different criteria |
| Confidence intervals | Statistical confidence on aggregated scores |
| A/B comparison UI | Interactive pairwise comparison interface |
| Export to CSV | Download eval results as spreadsheet |

---

**End of Step 10: Evaluation and Reporting**
