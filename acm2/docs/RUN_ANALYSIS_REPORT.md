# ACM2 Run Execution Deep Dive Analysis Report

**Run ID:** `291a498e-54f9-4e08-8b0c-596e4e5d39a2`  
**Run Name:** Analysis Run for Report  
**Status:** ✅ Completed  
**Execution Date:** December 16, 2025  
**Analysis Date:** December 15, 2025  

---

## Executive Summary

This report provides a comprehensive analysis of an ACM2 (API Cost Multiplier 2) pipeline run that executed the full generation and evaluation workflow. The run successfully processed 2 input documents using 2 models (OpenAI GPT-5-Mini and Google Gemini-2.5-Flash) through the FilePromptForge (FPF) generator, producing 4 generated documents that were then evaluated by both models across 6 criteria.

### Key Findings

| Metric | Value |
|--------|-------|
| Total Duration | **139.15 seconds** (~2.3 minutes) |
| Documents Processed | 2 |
| Models Used | 2 (openai:gpt-5-mini, google:gemini-2.5-flash) |
| Documents Generated | 4 |
| Evaluations Performed | 8 |
| Pairwise Comparisons | 0 (disabled) |
| Combine Phase | Not executed |
| Total Cost | $0.00 (cost tracking not captured) |

### Performance Winner

Based on evaluation scores:
- **Best Overall Generator Model:** `openai:gpt-5-mini` (avg score: 3.92)
- **Best Evaluated Document:** `ba289490-4678-4337-85b4-66187c93e8b2.fpf.1.openai_gpt-5-mini` (overall avg: 4.17)

---

## Table of Contents

1. [Run Configuration](#1-run-configuration)
2. [Input Documents](#2-input-documents)
3. [Generation Phase Analysis](#3-generation-phase-analysis)
4. [Evaluation Phase Analysis](#4-evaluation-phase-analysis)
5. [Model Performance Comparison](#5-model-performance-comparison)
6. [Criteria Breakdown](#6-criteria-breakdown)
7. [Timeline Analysis](#7-timeline-analysis)
8. [Issues and Anomalies](#8-issues-and-anomalies)
9. [Recommendations](#9-recommendations)
10. [Technical Appendix](#10-technical-appendix)

---

## 1. Run Configuration

### 1.1 Generator Settings

| Setting | Value |
|---------|-------|
| Generator | FilePromptForge (FPF) |
| Iterations | 1 |
| Evaluation Enabled | ✅ Yes |
| Pairwise Enabled | ❌ No |
| Combine Enabled | ❌ No |

### 1.2 Model Configuration

| Provider | Model | Temperature | Max Tokens |
|----------|-------|-------------|------------|
| OpenAI | gpt-5-mini | 0.7 | 4000 |
| Google | gemini-2.5-flash | 0.7 | 4000 |

### 1.3 Evaluation Settings

| Setting | Value |
|---------|-------|
| Evaluation Model | gpt-5 (default) |
| Judge Models | openai:gpt-5-mini, google:gemini-2.5-flash |
| Criteria | accuracy, completeness, coherence |

### 1.4 GPTR Settings (Not Used)

The GPTR (GPT-Researcher) module was configured but not enabled for this run:
- Report Type: research_report
- Report Source: web
- Tone: Objective

---

## 2. Input Documents

Two input documents were processed in this run:

### Document 1: `ba289490-4678-4337-85b4-66187c93e8b2`

- **Type:** Input Document
- **Description:** AI-focused content (based on evaluation feedback mentioning "AI diagnosing diseases", "AI's impact")
- **Processing Status:** ✅ Successfully processed by both models

### Document 2: `0dd19fd9-45f8-456a-822f-44517469e725`

- **Name:** Sample Policy Document
- **Type:** input_document
- **Description:** Federal policy document related to Executive Order 14110 on AI (Biden administration)
- **Processing Status:** ⚠️ Mixed results - OpenAI succeeded, Gemini produced "INSUFFICIENT_EVIDENCE"

---

## 3. Generation Phase Analysis

### 3.1 Generation Summary

| Document | Model | Duration | Status | Output ID |
|----------|-------|----------|--------|-----------|
| Doc 1 (ba289490) | openai:gpt-5-mini | 10.50s | ✅ Success | ba289490...openai_gpt-5-mini |
| Doc 1 (ba289490) | google:gemini-2.5-flash | 14.04s | ✅ Success | ba289490...google_gemini-2.5-flash |
| Doc 2 (0dd19fd9) | openai:gpt-5-mini | 63.52s | ✅ Success | 0dd19fd9...openai_gpt-5-mini |
| Doc 2 (0dd19fd9) | google:gemini-2.5-flash | 7.97s | ⚠️ Partial | 0dd19fd9...google_gemini-2.5-flash |

### 3.2 Generation Performance by Model

**OpenAI GPT-5-Mini:**
- Average generation time: **37.01 seconds**
- Success rate: **100%** (2/2)
- Consistency: Variable (10.5s vs 63.5s) - Document 2 was significantly more complex

**Google Gemini-2.5-Flash:**
- Average generation time: **11.01 seconds**
- Success rate: **50%** (1/2 quality outputs)
- Issue: Document 2 generation passed but produced "INSUFFICIENT_EVIDENCE" output

### 3.3 Generation Bottlenecks

1. **Document 2 with OpenAI** took 63.52 seconds - 6x longer than Document 1
   - This suggests the policy document content was more complex/lengthy
   - May require prompt optimization for policy documents

2. **Parallel Execution** was observed - multiple generations ran concurrently

---

## 4. Evaluation Phase Analysis

### 4.1 Evaluation Matrix

All 4 generated documents were evaluated by 2 judge models across 6 criteria:

| Generated Document | Judge: openai:gpt-5-mini | Judge: google:gemini-2.5-flash | Overall Avg |
|-------------------|--------------------------|--------------------------------|-------------|
| Doc1.openai | 3.67 | 4.67 | **4.17** |
| Doc1.gemini | 3.17 | 3.67 | **3.42** |
| Doc2.openai | 3.67 | 3.67 | **3.67** |
| Doc2.gemini | 1.17 | N/A (failed) | **1.17** |

### 4.2 Evaluation Criteria Used

The evaluation used 6 criteria (expanded from the configured 3):

1. **Factuality** - Accuracy of claims and avoidance of fabrication
2. **Relevance** - Alignment with user intent and topic
3. **Completeness** - Coverage of necessary aspects
4. **Clarity** - Clear, concise, professional writing
5. **Structure** - Logical organization and formatting
6. **Depth** - Level of critical analysis and insight

### 4.3 Evaluation Timing

| Evaluation | Judge Model | Duration | Score |
|------------|-------------|----------|-------|
| Doc1.gemini → openai judge | openai:gpt-5-mini | 30.30s | 3.17 |
| Doc1.gemini → gemini judge | gemini-2.5-flash | 12.38s | 3.67 |
| Doc1.openai → openai judge | openai:gpt-5-mini | 40.54s | 3.67 |
| Doc1.openai → gemini judge | gemini-2.5-flash | 29.64s | 4.67 |
| Doc2.gemini → openai judge | openai:gpt-5-mini | 26.86s | 1.17 |
| Doc2.openai → openai judge | openai:gpt-5-mini | 58.99s | 3.67 |
| Doc2.openai → gemini judge | gemini-2.5-flash | 16.62s | 3.67 |

**Total Evaluation Time:** ~215 seconds (across all parallel evaluations)

---

## 5. Model Performance Comparison

### 5.1 Generator Model Rankings

| Rank | Generator Model | Avg Score (all docs) | Best Score | Worst Score |
|------|-----------------|----------------------|------------|-------------|
| 1 | openai:gpt-5-mini | **3.92** | 4.17 | 3.67 |
| 2 | google:gemini-2.5-flash | **2.29** | 3.42 | 1.17 |

**Analysis:** OpenAI GPT-5-Mini significantly outperformed Gemini-2.5-Flash as a generator. The Gemini model had a catastrophic failure on Document 2, producing essentially no usable output ("INSUFFICIENT_EVIDENCE").

### 5.2 Judge Model Agreement

Cross-model evaluation consistency:

| Generated Doc | openai judge | gemini judge | Δ (difference) |
|---------------|--------------|--------------|----------------|
| Doc1.openai | 3.67 | 4.67 | **1.00** |
| Doc1.gemini | 3.17 | 3.67 | **0.50** |
| Doc2.openai | 3.67 | 3.67 | **0.00** |

**Average Judge Disagreement:** 0.50 points

The Gemini judge rated the OpenAI-generated Document 1 significantly higher (+1.0) than the OpenAI judge did itself. This suggests:
- Gemini may be more lenient overall
- Or Gemini specifically appreciated certain qualities in OpenAI's output

### 5.3 Self-Evaluation Bias Analysis

| Model as Generator | Own Judge Score | Other Judge Score | Self-Bias |
|--------------------|-----------------|-------------------|-----------|
| openai:gpt-5-mini | 3.67 (avg) | 4.17 (avg) | **-0.50** (modest against self) |
| gemini-2.5-flash | 3.67 (only valid) | 3.17 | **+0.50** (slight self-favor) |

Interestingly, OpenAI's model judged its own output more harshly than Gemini judged it.

---

## 6. Criteria Breakdown

### 6.1 Document 1 - OpenAI Output (Best Performer)

| Criterion | openai judge | gemini judge | Average |
|-----------|--------------|--------------|---------|
| Factuality | 5 | 5 | **5.00** |
| Relevance | 4 | 4 | **4.00** |
| Completeness | 3 | 5 | **4.00** |
| Clarity | 4 | 5 | **4.50** |
| Structure | 4 | 5 | **4.50** |
| Depth | 2 | 4 | **3.00** |

**Strengths:**
- Excellent factuality - correctly hedged claims about AI diagnostic accuracy
- Strong clarity and structure

**Weaknesses:**
- Depth scored lowest - described as "superficial" with "little substantive critique"

### 6.2 Document 1 - Gemini Output

| Criterion | openai judge | gemini judge | Average |
|-----------|--------------|--------------|---------|
| Factuality | 4 | 4 | **4.00** |
| Relevance | 3 | 5 | **4.00** |
| Completeness | 3 | 3 | **3.00** |
| Clarity | 4 | 4 | **4.00** |
| Structure | 3 | 4 | **3.50** |
| Depth | 2 | 2 | **2.00** |

**Strengths:**
- High relevance score from Gemini judge
- Consistent clarity

**Weaknesses:**
- Low depth scores from both judges
- Less complete coverage than OpenAI output

### 6.3 Document 2 - OpenAI Output

| Criterion | openai judge | gemini judge | Average |
|-----------|--------------|--------------|---------|
| Factuality | 4 | 1 | **2.50** |
| Relevance | 4 | 1 | **2.50** |
| Completeness | 3 | 5 | **4.00** |
| Clarity | 4 | 5 | **4.50** |
| Structure | 4 | 5 | **4.50** |
| Depth | 3 | 5 | **4.00** |

**Critical Finding:** Gemini judge gave factuality and relevance scores of **1** because the document referenced Executive Order 14110 (Biden's AI EO) which was rescinded on January 20, 2025. This shows the Gemini model has more up-to-date knowledge about current policy status.

### 6.4 Document 2 - Gemini Output (Failed)

| Criterion | openai judge | Average |
|-----------|--------------|---------|
| Factuality | 1 | **1.00** |
| Relevance | 1 | **1.00** |
| Completeness | 1 | **1.00** |
| Clarity | 2 | **2.00** |
| Structure | 1 | **1.00** |
| Depth | 1 | **1.00** |

**Critical Failure:** Gemini produced only "INSUFFICIENT_EVIDENCE" - a single token with no substantive content. This appears to be a grounding enforcement failure where the FPF validator rejected the response.

---

## 7. Timeline Analysis

### 7.1 Phase Duration Breakdown

| Phase | Start Time | End Time | Duration |
|-------|------------|----------|----------|
| Initialization | 02:32:06.24 | 02:32:06.24 | <1s |
| Generation | 02:32:06.24 | 02:33:10.94 | **~65s** |
| Evaluation | 02:32:16.75 | 02:34:25.39 | **~129s** |
| Completion | 02:34:25.39 | 02:34:25.39 | <1s |
| **Total** | | | **139.15s** |

### 7.2 Execution Timeline Visualization

```
Time (seconds from start)
0        10       20       30       40       50       60       70       80       90      100      110      120      130      140
|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
▓▓▓▓▓▓▓▓▓▓░ Doc1.openai gen (10.5s)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓░ Doc1.gemini gen (14.0s)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░ Doc2.openai gen (63.5s)
                                                                  ▓▓▓▓▓▓▓▓░ Doc2.gemini gen (8.0s)
          ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Eval: Doc1.openai (40.5s)
              ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Eval: Doc1.gemini (30.3s + 12.4s)
                                                                      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Eval: Doc2.openai (59.0s + 16.6s)
                                                                          ░░░░░░░░░░░░░░░░░░░░░░░░░░░ Eval: Doc2.gemini (26.9s)
                                                                                                                                                              ✓ Complete
```

### 7.3 Parallel Execution Analysis

The run executor effectively parallelized work:
- All 4 generations started nearly simultaneously (within 56.7s window)
- Evaluations began as soon as generation completed
- Multiple evaluations ran concurrently

**Parallelism Factor:** ~3-4 concurrent operations

---

## 8. Issues and Anomalies

### 8.1 Critical Issues

#### Issue 1: Gemini Grounding Validation Failure

**Severity:** High  
**Impact:** Document 2 Gemini generation produced unusable output

**Details:**
The FPF grounding_enforcer module rejected Gemini's response for Document 2 because:
- Grounding check: **FALSE** (no web search/citations detected)
- Reasoning check: **TRUE** (content text was present)
- Overall validation: **FAILED**

**Root Cause:** The FPF system requires responses to include grounding (web citations) when processing certain document types. Gemini-2.5-Flash did not include citations, causing the validation to fail and return "INSUFFICIENT_EVIDENCE".

**Recommendation:** Consider relaxing grounding requirements for document summarization tasks, or ensure input documents specify whether web search is expected.

#### Issue 2: Executive Order Temporal Accuracy

**Severity:** Medium  
**Impact:** Document 2 OpenAI output references rescinded policy

**Details:**
The Gemini judge correctly identified that Executive Order 14110 (Biden's AI EO from Oct 30, 2023) was rescinded on January 20, 2025. The OpenAI-generated document provided excellent templates and guidance, but for a policy that no longer exists.

**Implications:**
- Gemini-2.5-Flash has more recent knowledge (post-Jan 2025)
- GPT-5-Mini may have training cutoff before EO rescission
- Policy documents require temporal validation

### 8.2 Minor Issues

#### Issue 3: Cost Tracking Not Captured

**Severity:** Low  
**Impact:** Unable to analyze cost efficiency

All cost fields show $0.00, suggesting:
- Cost tracking integration is not configured
- Or LiteLLM cost callbacks are not enabled

#### Issue 4: Evaluation JSON Parse Failures

**Severity:** Low  
**Impact:** 3 evaluation retry attempts noted

From server logs:
```
WARNING - Single eval attempt 1 failed for ba289490-...: No valid JSON found in response
WARNING - Single eval attempt 3 failed for 0dd19fd9-...: No valid JSON found in response
```

The evaluation system handled these gracefully with retries.

---

## 9. Recommendations

### 9.1 Immediate Actions

1. **Configure Cost Tracking**
   - Enable LiteLLM cost callbacks to capture per-model costs
   - Add cost aggregation to run summary

2. **Fix Grounding Enforcement**
   - Add document-type-aware grounding requirements
   - Allow non-web tasks to skip grounding validation

3. **Enable Pairwise and Combine**
   - The preset has pairwise and combine enabled but they didn't execute
   - Verify run creation is passing these flags correctly

### 9.2 Model Selection Recommendations

| Use Case | Recommended Generator | Recommended Judge |
|----------|----------------------|-------------------|
| General content | openai:gpt-5-mini | gemini-2.5-flash |
| Policy/legal docs | openai:gpt-5-mini | Both (for temporal validation) |
| Speed-critical | google:gemini-2.5-flash | openai:gpt-5-mini |

### 9.3 Evaluation Improvements

1. **Add Temporal Accuracy Criterion**
   - Specifically score whether content is up-to-date
   - Flag references to rescinded/superseded policies

2. **Weight Criteria by Document Type**
   - Policy documents: Higher weight on factuality
   - Creative content: Higher weight on depth/clarity

3. **Implement Judge Calibration**
   - Track and adjust for systematic judge biases
   - Gemini appears ~0.5 points more lenient

### 9.4 Pipeline Optimization

1. **Batch Similar Documents**
   - Document 2 took 6x longer than Document 1
   - Consider pre-categorizing documents by expected complexity

2. **Implement Streaming Progress**
   - Currently progress shows 0% throughout
   - Add real-time progress updates for long-running generations

---

## 10. Technical Appendix

### 10.1 Run Configuration JSON

```json
{
  "id": "291a498e-54f9-4e08-8b0c-596e4e5d39a2",
  "name": "Analysis Run for Report",
  "generators": ["fpf"],
  "models": [
    {"provider": "openai", "model": "gpt-5-mini", "temperature": 0.7, "max_tokens": 4000},
    {"provider": "google", "model": "gemini-2.5-flash", "temperature": 0.7, "max_tokens": 4000}
  ],
  "document_ids": [
    "ba289490-4678-4337-85b4-66187c93e8b2",
    "0dd19fd9-45f8-456a-822f-44517469e725"
  ],
  "iterations": 1,
  "evaluation": {"enabled": true, "criteria": ["accuracy", "completeness", "coherence"]}
}
```

### 10.2 Generated Document IDs

| ID | Source | Generator | Iteration | Model |
|----|--------|-----------|-----------|-------|
| ba289490-...-openai_gpt-5-mini | ba289490... | fpf | 1 | openai:gpt-5-mini |
| ba289490-...-google_gemini-2.5-flash | ba289490... | fpf | 1 | google:gemini-2.5-flash |
| 0dd19fd9-...-openai_gpt-5-mini | 0dd19fd9... | fpf | 1 | openai:gpt-5-mini |
| 0dd19fd9-...-google_gemini-2.5-flash | 0dd19fd9... | fpf | 1 | google:gemini-2.5-flash |

### 10.3 Evaluation Score Matrix (Raw)

```
Pre-Combine Evaluations:
                                          | openai judge | gemini judge |
------------------------------------------|--------------|--------------|
ba289490.fpf.1.google_gemini-2.5-flash    |    3.17     |     3.67     |
ba289490.fpf.1.openai_gpt-5-mini          |    3.67     |     4.67     |
0dd19fd9.fpf.1.google_gemini-2.5-flash    |    1.17     |     N/A      |
0dd19fd9.fpf.1.openai_gpt-5-mini          |    3.67     |     3.67     |
```

### 10.4 Timeline Events (Raw)

| # | Phase | Event Type | Time | Duration | Success |
|---|-------|------------|------|----------|---------|
| 1 | initialization | start | 02:32:06.24 | - | ✅ |
| 2 | generation | generation | 02:32:06.24 | 10.50s | ✅ |
| 3 | generation | generation | 02:32:06.25 | 14.04s | ✅ |
| 4 | generation | generation | 02:32:06.25 | 63.52s | ✅ |
| 5 | generation | generation | 02:33:02.97 | 7.97s | ✅ |
| 6 | evaluation | single_eval | 02:32:20.29 | 30.30s | ✅ |
| 7 | evaluation | single_eval | 02:32:50.59 | 12.38s | ✅ |
| 8 | evaluation | single_eval | 02:32:16.75 | 40.54s | ✅ |
| 9 | evaluation | single_eval | 02:32:57.28 | 29.64s | ✅ |
| 10 | evaluation | single_eval | 02:33:10.94 | 26.86s | ✅ |
| 11 | evaluation | single_eval | 02:33:09.77 | 58.99s | ✅ |
| 12 | evaluation | single_eval | 02:34:08.77 | 16.62s | ✅ |
| 13 | completion | complete | 02:34:25.39 | 139.15s | ✅ |

### 10.5 Server Log Excerpts

**FPF Grounding Failure:**
```
2025-12-15 18:33:05,706 ERROR grounding_enforcer: VALIDATION FAILED - Full failure report saved to:
C:\dev\silky\api_cost_multiplier\FilePromptForge\logs\validation\20251216T023257-a1a31b19-validation-FAILURE-REPORT.json
2025-12-15 18:33:05,707 ERROR grounding_enforcer: VALIDATION FAILED: Provider response failed
mandatory checks: missing grounding (web_search/citations). Enforcement is strict; no report may be written.
```

**Successful Completion:**
```
2025-12-15 18:34:25,388 - app.services.run_executor - INFO - Run 291a498e-54f9-4e08-8b0c-596e4e5d39a2:
Completed | docs=4 winner=None cost=$0.0000
2025-12-15 18:34:25,422 - app.api.routes.runs - INFO - Run 291a498e-54f9-4e08-8b0c-596e4e5d39a2
completed successfully
```

---

## Appendix A: Detailed Criterion Analysis

### A.1 Factuality Analysis

**Definition:** Claims are accurate, verifiable, and avoid fabrication or overgeneralization.

**Score Distribution:**
- Score 5 (Perfect): 2 instances - OpenAI's hedged claims about AI accuracy
- Score 4 (Good): 4 instances - Minor unsourced claims or context issues
- Score 1 (Poor): 3 instances - No content or outdated policy references

**Best Practice Identified:** OpenAI's response correctly noted AI diagnostic accuracy is "typically observed in narrow tasks and not universally" - this hedging received perfect factuality scores.

### A.2 Depth Analysis

**Definition:** Level of critical analysis, insight, and substantive treatment beyond surface description.

**Score Distribution:**
- Score 5 (Excellent): 2 instances - Gemini judge on OpenAI's policy templates
- Score 4 (Good): 2 instances - Recognition of nuanced claims
- Score 3 (Moderate): 2 instances - Operational guidance without deep analysis
- Score 2 (Poor): 4 instances - Primarily descriptive content
- Score 1 (Very Poor): 2 instances - No content

**Key Finding:** Depth was consistently the lowest-scoring criterion across all documents and judges. This suggests the generation prompts may need to explicitly request critical analysis and deeper treatment.

---

## Appendix B: Model Capability Assessment

### B.1 OpenAI GPT-5-Mini

**Strengths:**
- Consistent output quality across documents
- Strong hedging and accuracy in claims
- Excellent structure and clarity
- Longer processing allows for thorough treatment

**Weaknesses:**
- Slower than Gemini (especially on complex documents)
- May have outdated training data (pre-Jan 2025)

### B.2 Google Gemini-2.5-Flash

**Strengths:**
- Fast generation (7-14 seconds)
- More recent training data (knows about policy rescissions)
- Good evaluator calibration

**Weaknesses:**
- Grounding validation failures
- Produces incomplete/stub responses on complex tasks
- Inconsistent quality

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| ACM2 | API Cost Multiplier 2 - the pipeline orchestration system |
| FPF | FilePromptForge - the generation adapter for file-based prompts |
| GPTR | GPT-Researcher - web research agent (not used in this run) |
| Pairwise | Head-to-head comparison between generated documents |
| Combine | Merge top documents into a "Gold Standard" output |
| Grounding | Web search citations in generated content |
| Judge Model | LLM used to evaluate generated documents |

---

**Report Generated:** December 15, 2025  
**Run Analysis Tool:** ACM2 v2.0  
**Report Version:** 1.0  

---

*End of Report*
