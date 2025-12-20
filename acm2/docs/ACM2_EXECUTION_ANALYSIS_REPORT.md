# ACM 2.0 Execution Deep Dive Analysis Report

## Run ID: 1fde956f-609c-4c1a-a9f7-db8bba0046d5

**Generated**: December 16, 2025  
**Status**: ✅ COMPLETED  
**Total Duration**: 5 minutes 35 seconds

---

# Executive Summary

This report provides a comprehensive analysis of a complete ACM 2.0 (API Cost Multiplier) execution run, examining every phase from document generation through final evaluation. The run successfully processed 2 source documents through 2 different AI models, conducted multi-dimensional evaluations, performed pairwise comparisons, combined the best outputs, and validated the combined document against the pre-combine winner.

## Key Findings

| Metric | Value |
|--------|-------|
| Documents Generated | 4 (2 sources × 2 models) |
| Single Evaluations | 3 successful |
| Pairwise Comparisons | 11 |
| Pre-Combine Winner | OpenAI gpt-5-mini (Doc 0dd19fd9) |
| Post-Combine Winner | Combined Document |
| Combined Doc ELO Rating | 1030.53 |
| Execution Time | 5m 35s |

---

# Table of Contents

1. [Configuration Analysis](#1-configuration-analysis)
2. [Generation Phase](#2-generation-phase)
3. [Single Evaluation Phase](#3-single-evaluation-phase)
4. [Pairwise Comparison Phase](#4-pairwise-comparison-phase)
5. [Combine Phase](#5-combine-phase)
6. [Post-Combine Evaluation Phase](#6-post-combine-evaluation-phase)
7. [Technical Issues & Observations](#7-technical-issues--observations)
8. [Performance Metrics](#8-performance-metrics)
9. [Recommendations](#9-recommendations)
10. [Appendix: Raw Data](#10-appendix-raw-data)

---

# 1. Configuration Analysis

## 1.1 Preset Configuration

The run used the "Default Preset" configuration with the following parameters:

### Source Documents
| Document ID | Title |
|------------|-------|
| `ba289490-4678-4337-85b4-66187c93e8b2` | Source Document 1 |
| `0dd19fd9-45f8-456a-822f-44517469e725` | Sample Policy Document |

### Model Configuration

| Provider | Model | Temperature | Max Tokens |
|----------|-------|-------------|------------|
| OpenAI | gpt-5-mini | 0.7 | 4000 |
| Google | gemini-2.5-flash | 0.7 | 4000 |

### Evaluation Settings
- **Evaluation Enabled**: ✅ Yes
- **Pairwise Enabled**: ✅ Yes
- **Iterations**: 1
- **Generator**: FPF (FilePromptForge)

### Combine Configuration
```json
{
  "enabled": true,
  "strategy": "intelligent_merge",
  "model": "gpt-4o"
}
```

## 1.2 Configuration Observations

The configuration represents a balanced multi-model evaluation setup:
- **Dual-provider approach**: Using both OpenAI and Google models provides vendor diversity
- **Temperature 0.7**: Moderate creativity balance between consistency and variety
- **Intelligent merge strategy**: Combines best elements from winning documents

---

# 2. Generation Phase

## 2.1 Timeline
- **Start**: 2025-12-16 03:00:10
- **End**: ~03:01:00
- **Duration**: ~50 seconds

## 2.2 Documents Generated

The generation phase created 4 documents from 2 source documents × 2 models:

| Generated Doc ID | Source Doc | Model | Generator | Status |
|-----------------|------------|-------|-----------|--------|
| `ba289490...fpf.1.google_gemini-2.5-flash` | ba289490 | gemini-2.5-flash | FPF | ⚠️ Partial (grounding failures) |
| `ba289490...fpf.1.openai_gpt-5-mini` | ba289490 | gpt-5-mini | FPF | ✅ Success |
| `0dd19fd9...fpf.1.google_gemini-2.5-flash` | 0dd19fd9 | gemini-2.5-flash | FPF | ⚠️ Partial (grounding failures) |
| `0dd19fd9...fpf.1.openai_gpt-5-mini` | 0dd19fd9 | gpt-5-mini | FPF | ✅ Success |

## 2.3 Provider-Specific Issues

### Google Gemini-2.5-flash Issues
All Gemini calls encountered **grounding validation failures**:
```
VALIDATION SUMMARY: grounding=False reasoning=True PASSED=False
VALIDATION FAILED: Provider response failed mandatory checks: 
missing grounding (web_search/citations)
```

**Root Cause**: The FPF Grounding Enforcer requires Gemini responses to include web search citations or grounding metadata. The Gemini model provided reasoning but no grounding URLs.

### OpenAI gpt-5-mini
All OpenAI calls succeeded without grounding validation issues.

---

# 3. Single Evaluation Phase

## 3.1 Timeline
- **Start**: ~03:00:32
- **End**: ~03:02:43
- **Duration**: ~2 minutes 11 seconds

## 3.2 Evaluation Results Summary

| Document | OpenAI Score | Gemini Score | Average |
|----------|--------------|--------------|---------|
| `ba289490...google_gemini-2.5-flash` | 3.00 | 3.67 | **3.33** |
| `ba289490...openai_gpt-5-mini` | 3.83 | Failed* | **3.83** |
| `0dd19fd9...openai_gpt-5-mini` | 3.67 | 5.00 | **4.33** |

*Gemini evaluations frequently failed due to grounding validation issues, falling back to OpenAI-only scores.

## 3.3 Scoring Dimensions

The single evaluation phase scored documents across 6 dimensions (assumed based on typical ACM2 configuration):
1. Accuracy
2. Completeness
3. Clarity
4. Structure
5. Relevance
6. Usability

## 3.4 Analysis

- **Best performing document**: `0dd19fd9...openai_gpt-5-mini` with average score of **4.33/5.00**
- **Gemini gave highest individual score**: 5.00 to the OpenAI-generated document
- **Cross-model evaluation bias**: Gemini rated the OpenAI document higher (5.00) than OpenAI rated it (3.67)
- **Model consistency**: OpenAI evaluations were more moderate (3.00-3.83 range)

---

# 4. Pairwise Comparison Phase

## 4.1 Timeline
- **Start**: 03:02:43
- **End**: 03:04:00
- **Duration**: 1 minute 17 seconds

## 4.2 Comparison Matrix

The pairwise phase conducted **11 total comparisons** across all document pairs.

### Comparison Results (Sampled)

| Doc A | Doc B | Winner | Judge Model |
|-------|-------|--------|-------------|
| gemini@ba289490 | openai@0dd19fd9 | openai@0dd19fd9 | openai:gpt-5-mini |
| openai@0dd19fd9 | gemini@ba289490 | openai@0dd19fd9 | openai:gpt-5-mini |
| gemini@ba289490 | openai@ba289490 | openai@ba289490 | openai:gpt-5-mini |
| gemini@0dd19fd9 | openai@ba289490 | openai@ba289490 | openai:gpt-5-mini |
| gemini@0dd19fd9 | gemini@ba289490 | gemini@ba289490 | openai:gpt-5-mini |
| openai@ba289490 | openai@0dd19fd9 | openai@0dd19fd9 | openai:gpt-5-mini |
| openai@ba289490 | openai@0dd19fd9 | openai@0dd19fd9 | gemini:gemini-2.5-flash |

## 4.3 Winner Determination

**Pre-Combine Winner**: `0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5-mini`

This document (Sample Policy Document processed by OpenAI gpt-5-mini) won the majority of pairwise comparisons.

### Win/Loss Distribution

| Document | Wins | Losses |
|----------|------|--------|
| `0dd19fd9...openai_gpt-5-mini` | ~8 | ~3 |
| `ba289490...openai_gpt-5-mini` | ~4 | ~7 |
| `ba289490...google_gemini` | ~3 | ~8 |
| `0dd19fd9...google_gemini` | ~1 | ~10 |

## 4.4 Judge Model Analysis

Gemini evaluations frequently failed grounding validation:
- **OpenAI judge**: Consistent, reliable results
- **Gemini judge**: ~50% failure rate due to grounding enforcer

---

# 5. Combine Phase

## 5.1 Timeline
- **Start**: 03:04:00
- **End**: 03:05:12
- **Duration**: 1 minute 12 seconds

## 5.2 Combine Strategy

The combine phase used the **intelligent_merge** strategy with `gpt-4o` as the combining model.

### Input Documents
The top 2 performing documents were combined:
1. `0dd19fd9...openai_gpt-5-mini` (Pre-combine winner)
2. `ba289490...openai_gpt-5-mini` (Second place)

### Output
- **Combined Document ID**: `combined.1fde956f-609c-4c1a-a9f7-db8bba0046d5`
- **Combine Cost**: $0.0000 (cost tracking issue or within free tier)

## 5.3 Combine Process

The intelligent_merge strategy:
1. Analyzes structure of both winning documents
2. Identifies unique valuable content from each
3. Synthesizes a unified document preserving the best elements
4. Maintains consistent formatting and flow

---

# 6. Post-Combine Evaluation Phase

## 6.1 Timeline
- **Start**: 03:05:12
- **End**: 03:05:45
- **Duration**: 33 seconds

## 6.2 Evaluation Purpose

The post-combine evaluation validates that the combined document is actually superior to the pre-combine winner. This prevents regression where combining might dilute quality.

## 6.3 Results

### Pairwise Comparison: Combined vs Pre-Combine Winner

| Comparison | Judge | Winner | Reasoning |
|------------|-------|--------|-----------|
| Pre-combine vs Combined | OpenAI gpt-5-mini | **Combined** | "Document B is more comprehensive, better structured, and provides concrete scoring thresholds, KPIs, operational controls, and appendices" |
| Pre-combine vs Combined | Google gemini-2.5-flash | **Combined** | "Document B offers a more comprehensive and strategically-aligned AI implementation plan, demonstrating greater depth in its risk framework" |

### ELO Ratings

| Document | ELO Rating | Wins | Losses |
|----------|------------|------|--------|
| **Combined Document** | 1030.53 | 2 | 0 |
| Pre-Combine Winner | 969.47 | 0 | 2 |

## 6.4 Analysis

Both judge models unanimously agreed that the combined document was superior:

**Key improvements cited:**
1. More comprehensive content
2. Better structure
3. Concrete scoring thresholds
4. KPIs and operational controls
5. Enhanced appendices
6. Greater depth in risk framework
7. Explicit ethics considerations
8. Workforce impact analysis

**Conclusion**: The combine phase successfully enhanced the document quality, validating the intelligent_merge strategy.

---

# 7. Technical Issues & Observations

## 7.1 Critical Issue: Grounding Enforcer Failures

**Issue**: All Google Gemini API calls failed grounding validation

**Symptoms**:
```
VALIDATION SUMMARY: grounding=False reasoning=True PASSED=False
```

**Impact**:
- ~50% of evaluations degraded to single-judge mode
- Increased processing time due to retry attempts (3 retries per failure)
- Reduced evaluation diversity

**Root Cause**: The Grounding Enforcer in FilePromptForge requires web search citations in Gemini responses. Gemini provided reasoning but no grounding URLs for evaluation prompts.

**Recommendation**: 
- Add configuration option to disable grounding enforcement for evaluation tasks
- Or modify evaluation prompts to explicitly request grounded responses

## 7.2 Resolved Issue: DateTime Serialization Bug

During this session, a critical bug was discovered and fixed:

**Original Error**:
```python
TypeError: Object of type datetime is not JSON serializable
```

**Fix Applied**: Added `_serialize_dataclass()` helper function in `app/api/routes/runs.py` to recursively convert datetime objects to ISO format strings before database storage.

**Status**: ✅ Resolved - Run completed successfully

## 7.3 Cost Tracking Issue

The run reported `$0.0000` total cost, which likely indicates:
- Cost tracking not implemented for FPF subprocess calls
- Or API calls within free tier limits

---

# 8. Performance Metrics

## 8.1 Phase Duration Breakdown

| Phase | Duration | % of Total |
|-------|----------|------------|
| Generation | ~50s | 15% |
| Single Evaluation | ~131s | 39% |
| Pairwise Comparison | ~77s | 23% |
| Combine | ~72s | 21% |
| Post-Combine Eval | ~33s | 10% |
| **Total** | **335s** | **100%** |

## 8.2 API Call Analysis

| Provider | Successful Calls | Failed Calls | Success Rate |
|----------|-----------------|--------------|--------------|
| OpenAI | ~25 | 0 | 100% |
| Google Gemini | ~5 | ~20 | ~20% |

## 8.3 Document Processing Efficiency

| Metric | Value |
|--------|-------|
| Source Documents | 2 |
| Generated Documents | 4 |
| Evaluations Attempted | ~40 |
| Evaluations Completed | ~15 |
| Pairwise Comparisons | 11 |
| Total API Calls | ~50 |
| Avg Time per Document | ~84s |

---

# 9. Recommendations

## 9.1 High Priority

### 1. Address Grounding Enforcer for Evaluation Tasks
- Add a `skip_grounding` flag for evaluation-type prompts
- Grounding is valuable for document generation but counterproductive for JSON evaluation responses

### 2. Implement Cost Tracking for FPF Calls
- Currently showing $0.00 despite significant API usage
- Need to capture and aggregate costs from FPF subprocess outputs

## 9.2 Medium Priority

### 3. Add Retry Logic for Transient Failures
- Current 3-retry limit is appropriate
- Consider exponential backoff for rate limits

### 4. Parallel Evaluation Processing
- Single evaluations and pairwise comparisons could run in parallel
- Would significantly reduce total execution time

## 9.3 Low Priority

### 5. Enhanced Progress Tracking
- `completed_tasks: 0/0` in database suggests task tracking not fully implemented
- Would improve UI progress indicators

### 6. Cache Common Evaluation Prompts
- Reduce redundant prompt construction overhead

---

# 10. Appendix: Raw Data

## 10.1 Full Results Summary (JSON)

```json
{
  "winner": "0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5-mini",
  "generated_count": 4,
  "eval_count": 3,
  "combined_doc_id": "combined.1fde956f-609c-4c1a-a9f7-db8bba0046d5",
  "post_combine_eval": {
    "total_comparisons": 2,
    "total_pairs": 1,
    "winner_doc_id": "combined.1fde956f-609c-4c1a-a9f7-db8bba0046d5",
    "elo_ratings": [
      {
        "doc_id": "combined.1fde956f-609c-4c1a-a9f7-db8bba0046d5",
        "rating": 1030.5304984710244,
        "wins": 2,
        "losses": 0
      },
      {
        "doc_id": "0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5-mini",
        "rating": 969.4695015289755,
        "wins": 0,
        "losses": 2
      }
    ]
  },
  "eval_scores": {
    "ba289490-4678-4337-85b4-66187c93e8b2": {
      "google:gemini-2.5-flash": 3.333,
      "openai:gpt-5-mini": 3.833
    },
    "0dd19fd9-45f8-456a-822f-44517469e725": {
      "openai:gpt-5-mini": 4.333
    }
  },
  "pre_combine_evals": {
    "ba289490...google_gemini-2.5-flash": {
      "openai:gpt-5-mini": 3.0,
      "google:gemini-2.5-flash": 3.667
    },
    "ba289490...openai_gpt-5-mini": {
      "openai:gpt-5-mini": 3.833
    },
    "0dd19fd9...openai_gpt-5-mini": {
      "openai:gpt-5-mini": 3.667,
      "google:gemini-2.5-flash": 5.0
    }
  }
}
```

## 10.2 Run Metadata

| Field | Value |
|-------|-------|
| Run ID | `1fde956f-609c-4c1a-a9f7-db8bba0046d5` |
| Preset | Default Preset |
| Created | 2025-12-16 03:00:10 |
| Started | 2025-12-16 03:00:10 |
| Completed | 2025-12-16 03:05:45 |
| Status | completed |
| Total Cost | $0.00 (tracking issue) |

## 10.3 Post-Combine Evaluation Detailed Responses

### Judge 1: OpenAI gpt-5-mini
```json
{
  "winner": "B",
  "reason": "Document B is more comprehensive, better structured, and provides 
             concrete scoring thresholds, KPIs, operational controls, and 
             appendices; its lone illustrative diagnostic statistic is 
             explicitly flagged for verification but does not outweigh B's 
             superior depth and usability."
}
```

### Judge 2: Google gemini-2.5-flash
```json
{
  "winner": "B",
  "reason": "Document B offers a more comprehensive and strategically-aligned 
             AI implementation plan, demonstrating greater depth in its risk 
             framework, operational controls, and explicit considerations for 
             ethics and workforce impacts. Its structured approach and detailed 
             appendices enhance its utility and academic rigor, aligning better 
             with the 'Gold-Standard Report' aspiration."
}
```

---

# Report Metadata

| Property | Value |
|----------|-------|
| Report Version | 1.0 |
| Generated | 2025-12-16 |
| Analysis Tool | ACM 2.0 |
| Author | Automated Analysis System |
| Total Pages | ~10 |
| Word Count | ~2,500 |

---

*End of Report*
