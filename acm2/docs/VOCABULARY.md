# ACM 2.0 Vocabulary

This document defines the **official terminology** for ACM 2.0. All code, documentation, and UI must use these terms consistently.

---

## Reserved Terms

### Phase

**Definition**: A distinct stage in the ACM pipeline that processes documents.

**The only valid phases are**:
1. **Generation Phase** – FPF/GPT-R produce artifacts from documents
2. **Pre-Combine Eval Phase** – Evaluator scores/compares artifacts (pre-combine)
3. **Combine Phase** – Winner selection and artifact combination
4. **Post-Combine Eval Phase** – Final evaluation after combination

**DO NOT use "phase" for**:
- Development milestones (use "step" or "milestone" instead)
- Planning stages (use "step" instead)
- API versioning
- Any other context

---

### Run

**Definition**: A complete ACM operation that processes a set of documents through phases. A Run is a first-class entity with an ID, configuration, status, and associated documents/artifacts.

**A Run**:
- Has a unique `run_id` (ULID format)
- Contains one or more Documents
- Produces Artifacts through phases
- Has a status lifecycle: `pending` → `running` → `completed` | `failed` | `cancelled`
- Is the unit of work for the ACM API

**Example**: "Create a new run with these 5 documents" → `POST /runs`

**DO NOT use "run" as a verb for executing code**. Use "execute" instead.
- ❌ "Run the generator"
- ✅ "Execute the generator"
- ❌ "The last run of generate"
- ✅ "The last execution of generate"

---

### Generate / Generation

**Definition**: The process of producing artifacts from documents using FPF or GPT-R.

**Usage**:
- We **execute** generate (verb for the action)
- Generation **produces** artifacts
- Reports are **generated**

**Example**:
- "Execute generation for this document"
- "The generation produced 3 artifacts"
- "Generate the HTML report"

---

### Evaluate / Evaluation

**Definition**: The process of scoring or comparing artifacts.

**Usage**:
- Eval **evaluates** artifacts (it does NOT "generate" evaluations)
- Eval **produces** scores, comparisons, rankings (output is implied)
- Eval results are stored, not "generated"

**DO NOT say**:
- ❌ "Generate evaluations"
- ❌ "The evaluator generates scores"

**DO say**:
- ✅ "Evaluate the artifacts"
- ✅ "The evaluator scores the artifacts"
- ✅ "Evaluation produced the following rankings"

---

## Entity Terms

| Term | Definition |
|------|------------|
| **Document** | An input file (markdown) to be processed. Identified by `document_id`. |
| **Artifact** | An output file produced by generation. Identified by `artifact_id`. |
| **Task** | A unit of work within a run (e.g., one FPF call for one document). |
| **Project** | A collection of related runs sharing configuration (e.g., GitHub repos). |

---

## Action Verbs

| Action | Correct Usage | Avoid |
|--------|---------------|-------|
| Start a run | "Create a run" | "Run a run" |
| Process documents | "Execute generation" | "Run generation" |
| Score artifacts | "Evaluate artifacts" | "Generate evaluations" |
| Produce reports | "Generate reports" | - |
| Cancel work | "Cancel the run" | - |

---

## Development Terms

When writing planning documents or code comments:

| Use | Instead Of |
|-----|------------|
| Step 1, Step 2 | Phase 1, Phase 2 |
| Milestone | Phase |
| Development step | Development phase |
| Execute | Run (as verb) |

---

## Examples

### Correct

> "Step 2.7 implements the Run and Document lifecycle APIs."

> "The Generation Phase executes FPF for each document in the run."

> "After evaluation completes, the Combine Phase selects winners."

> "Execute the generator to produce artifacts."

### Incorrect

> ~~"Phase 2.7 implements..."~~ (Phase is reserved for pipeline stages)

> ~~"Run the evaluator"~~ (Use "execute")

> ~~"Generate the evaluation results"~~ (Eval evaluates, doesn't generate)



a Report Type is generally a fpf report type or a gpt-r report type.

a CR is a combined report

DR is deep research

fpf is filepromptforge

acm is api_cost_multiplier 