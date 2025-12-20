# ACM 2.0 Content Architecture Specification

*Created: December 13, 2025*

---

## Overview

This document specifies the content management architecture for ACM 2.0, covering how input documents, instructions, criteria, and outputs are stored and managed.

---

## 1. GitHub Credentials in DB + GUI Connection

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     GITHUB INTEGRATION FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Settings Page (GUI)                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  GitHub Connections                                                │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │  + Add Connection                                            │  │ │
│  │  │                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │ 🔗 silky-org/policy-docs                               │  │  │ │
│  │  │  │    Branch: main                                        │  │  │ │
│  │  │  │    Status: ✅ Connected                                │  │  │ │
│  │  │  │    [Test] [Edit] [Delete]                              │  │  │ │
│  │  │  └────────────────────────────────────────────────────────┘  │  │ │
│  │  │                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │ 🔗 acme-corp/research-papers                           │  │  │ │
│  │  │  │    Branch: develop                                     │  │  │ │
│  │  │  │    Status: ✅ Connected                                │  │  │ │
│  │  │  │    [Test] [Edit] [Delete]                              │  │  │ │
│  │  │  └────────────────────────────────────────────────────────┘  │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Add Connection Modal                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Repository: [owner/repo_____________]                             │ │
│  │  Branch:     [main__________________]                              │ │
│  │  Token:      [ghp_xxxx______________] (encrypted in DB)            │ │
│  │                                                                    │ │
│  │  [Test Connection]  [Cancel]  [Save]                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Local Development - DB-Only Inputs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     INPUT SOURCE OPTIONS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Preset Configuration - Input Documents                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Source Type:  (•) Database    ( ) GitHub    ( ) Local Files      │ │
│  │                                                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │  Database Inputs                      [+ Create New]          │  │ │
│  │  │                                                              │  │ │
│  │  │  ☑ Federal Budget 2025           [View] [Edit]               │  │ │
│  │  │  ☑ Healthcare Policy Draft       [View] [Edit]               │  │ │
│  │  │  ☐ Education Spending Report     [View] [Edit]               │  │ │
│  │  │  ☐ Climate Action Plan           [View] [Edit]               │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                    │ │
│  │  ── OR (if GitHub selected) ──                                     │ │
│  │                                                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │  GitHub Connection: [silky-org/policy-docs ▼]                │  │ │
│  │  │  Input Directory:   [/inputs/_______________] [Browse]       │  │ │
│  │  │                                                              │  │ │
│  │  │  Files Found:                                                │  │ │
│  │  │  ☑ /inputs/budget-2025.md                                    │  │ │
│  │  │  ☑ /inputs/healthcare.md                                     │  │ │
│  │  │  ☐ /inputs/education.md                                      │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Instructions Editor - Dedicated "Content Library" Tab

A **dedicated Content Library tab** with a **simple text editor** (not full WYSIWYG) plus **GitHub import capability**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ACM 2.0                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┤
│  │ Dashboard │ Build Preset │ Execute │ History │ Content Library │ ⚙️ │
│  └─────────────────────────────────────────────────────────────────────┘
│                                                                         │
│  CONTENT LIBRARY                                                        │
│  ┌──────────────────────────┬──────────────────────────────────────────┐
│  │  Content Types           │  Generation Instructions                 │
│  │  ┌────────────────────┐  │  ┌────────────────────────────────────┐  │
│  │  │ 📝 Generation (3)  │◄─┤  │  Name: [Policy Analysis Prompt___]  │  │
│  │  │ 📊 Single Eval (2) │  │  │                                    │  │
│  │  │ ⚖️ Pairwise Eval(1)│  │  │  ┌────────────────────────────────┐│  │
│  │  │ 📋 Criteria (2)    │  │  │  │You are a {{ROLE}}.             ││  │
│  │  │ 🔗 Combine (1)     │  │  │  │                                ││  │
│  │  │ 🧩 Fragments (5)   │  │  │  │Your task is to analyze the     ││  │
│  │  └────────────────────┘  │  │  │following document and provide  ││  │
│  │                          │  │  │a comprehensive assessment.     ││  │
│  │  Generation Instructions │  │  │                                ││  │
│  │  ┌────────────────────┐  │  │  │{{TASK_DETAILS}}                ││  │
│  │  │ Policy Analysis ◄──┼──┤  │  │                                ││  │
│  │  │ Budget Review      │  │  │  │Document:                       ││  │
│  │  │ Research Summary   │  │  │  │{{INPUT}}                       ││  │
│  │  │ + New              │  │  │  │                                ││  │
│  │  └────────────────────┘  │  │  │{{OUTPUT_FORMAT}}               ││  │
│  │                          │  │  └────────────────────────────────┘│  │
│  │                          │  │                                    │  │
│  │                          │  │  Variables Used:                   │  │
│  │                          │  │  ┌────────────────────────────────┐│  │
│  │                          │  │  │ ROLE ──────► [Fragment ▼]      ││  │
│  │                          │  │  │              "Senior Analyst"  ││  │
│  │                          │  │  │ TASK_DETAILS► [Fragment ▼]     ││  │
│  │                          │  │  │              "Identify key..." ││  │
│  │                          │  │  │ INPUT ─────► (runtime)         ││  │
│  │                          │  │  │ OUTPUT_FORMAT► [Fragment ▼]    ││  │
│  │                          │  │  │              "Return JSON..."  ││  │
│  │                          │  │  └────────────────────────────────┘│  │
│  │                          │  │                                    │  │
│  │                          │  │  [Import from GitHub] [Duplicate]  │  │
│  │                          │  │  [Delete] [Save]                   │  │
│  │                          │  └────────────────────────────────────┘  │
│  └──────────────────────────┴──────────────────────────────────────────┘
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Import from GitHub Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Import Content from GitHub                                             │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Connection: [silky-org/policy-docs ▼]                             │ │
│  │                                                                    │ │
│  │  Browse Repository:                                                │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ 📁 /                                                         │  │ │
│  │  │   📁 prompts/                                                │  │ │
│  │  │     📄 generation-prompt.md         [Preview] [Import]       │  │ │
│  │  │     📄 eval-criteria.md             [Preview] [Import]       │  │ │
│  │  │     📄 pairwise-instructions.md     [Preview] [Import]       │  │ │
│  │  │   📁 inputs/                                                 │  │ │
│  │  │     📄 budget-2025.md                                        │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                    │ │
│  │  Import As:                                                        │ │
│  │  Type: [Generation Instructions ▼]                                 │ │
│  │  Name: [generation-prompt________________]                         │ │
│  │                                                                    │ │
│  │  [Cancel]  [Import to Library]                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Summary of Proposed Architecture

| Component | Storage | Editor | Import |
|-----------|---------|--------|--------|
| **GitHub Credentials** | DB (encrypted) | Settings page form | N/A |
| **Input Documents** | DB or GitHub (user choice) | Simple textarea + import | From GitHub |
| **Generation Instructions** | DB | Textarea with variable highlighting | From GitHub |
| **Eval Instructions** | DB | Textarea | From GitHub |
| **Eval Criteria** | DB | Textarea | From GitHub |
| **Combine Instructions** | DB | Textarea | From GitHub |
| **Template Fragments** | DB | Textarea | From GitHub |
| **Output Files** | GitHub (written after run) | N/A (generated) | N/A |

---

## 6. Text Editor Recommendation

For the content editor, recommend using **Monaco Editor** (the VS Code editor) or **CodeMirror** because:

1. **Syntax highlighting** for `{{VARIABLES}}`
2. **Line numbers** for longer content
3. **Find/replace** functionality
4. **Lightweight** - not a full WYSIWYG, just good text editing
5. **Already familiar** to developers

But we could start simpler with a plain `<textarea>` and add Monaco later if needed.

---

## 7. Content Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ACM 2.0 CONTENT FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │   GITHUB REPO   │  ◄── INPUT FILES (source documents)              │
│  │                 │                                                   │
│  │  /inputs/       │  • Federal Budget 2025.md                        │
│  │                 │  • Healthcare Policy.md                          │
│  │                 │  • Education Spending.md                         │
│  └────────┬────────┘                                                   │
│           │                                                            │
│           ▼  (read at runtime)                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     SQLite DATABASE                              │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ contents table                                            │   │   │
│  │  ├──────────────────────────────────────────────────────────┤   │   │
│  │  │ • generation_instructions    (prompt templates)          │   │   │
│  │  │ • single_eval_instructions   (how to rate outputs)       │   │   │
│  │  │ • pairwise_eval_instructions (how to compare A vs B)     │   │   │
│  │  │ • eval_criteria              (rubrics, scoring guides)   │   │   │
│  │  │ • combine_instructions       (how to merge outputs)      │   │   │
│  │  │ • template_fragments         (reusable {{VARIABLES}})    │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ presets table                                             │   │   │
│  │  ├──────────────────────────────────────────────────────────┤   │   │
│  │  │ • links to content pieces                                 │   │   │
│  │  │ • model configurations                                    │   │   │
│  │  │ • input_paths[] (GitHub file paths)                       │   │   │
│  │  │ • output_path (GitHub destination)                        │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ runs table                                                │   │   │
│  │  ├──────────────────────────────────────────────────────────┤   │   │
│  │  │ • generated outputs (stored inline)                       │   │   │
│  │  │ • evaluation scores                                       │   │   │
│  │  │ • combined "gold" output                                  │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                            │
│           ▼  (write after combine)                                     │
│  ┌─────────────────┐                                                   │
│  │   GITHUB REPO   │  ◄── OUTPUT FILES (final deliverables)           │
│  │                 │                                                   │
│  │  /outputs/      │  • Federal Budget Analysis - Gold.md             │
│  │                 │  • Healthcare Policy Analysis - Gold.md          │
│  │                 │                                                   │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Database Schema

### GitHub Connections Table

```python
class GitHubConnection(Base):
    __tablename__ = "github_connections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False)          # Display name
    repo = Column(String, nullable=False)          # "owner/repo"
    branch = Column(String, default="main")
    token_encrypted = Column(String, nullable=False)  # Encrypted PAT
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_tested_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True)
```

### Contents Table

```python
class ContentType(str, Enum):
    GENERATION_INSTRUCTIONS = "generation_instructions"
    SINGLE_EVAL_INSTRUCTIONS = "single_eval_instructions"
    PAIRWISE_EVAL_INSTRUCTIONS = "pairwise_eval_instructions"
    EVAL_CRITERIA = "eval_criteria"
    COMBINE_INSTRUCTIONS = "combine_instructions"
    TEMPLATE_FRAGMENT = "template_fragment"
    INPUT_DOCUMENT = "input_document"  # For DB-stored inputs

class Content(Base):
    __tablename__ = "contents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False)
    content_type = Column(Enum(ContentType), nullable=False)
    body = Column(Text, nullable=False)  # The actual text content
    variables = Column(JSON, default=dict)  # {"VAR_NAME": "content_id or null for runtime"}
    description = Column(String, nullable=True)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
```

### Updated Presets Table

```python
class InputSourceType(str, Enum):
    DATABASE = "database"
    GITHUB = "github"

class Preset(Base):
    __tablename__ = "presets"
    
    # ... existing fields ...
    
    # Input Source Configuration
    input_source_type = Column(Enum(InputSourceType), default=InputSourceType.DATABASE)
    
    # For DATABASE inputs
    input_content_ids = Column(JSON, default=list)  # List of content IDs
    
    # For GITHUB inputs
    github_connection_id = Column(String, ForeignKey("github_connections.id"), nullable=True)
    github_input_paths = Column(JSON, default=list)  # ["/inputs/doc1.md", "/inputs/doc2.md"]
    github_output_path = Column(String, nullable=True)  # "/outputs/"
    
    # Content References (all from DB)
    generation_instructions_id = Column(String, ForeignKey("contents.id"), nullable=True)
    single_eval_instructions_id = Column(String, ForeignKey("contents.id"), nullable=True)
    pairwise_eval_instructions_id = Column(String, ForeignKey("contents.id"), nullable=True)
    eval_criteria_id = Column(String, ForeignKey("contents.id"), nullable=True)
    combine_instructions_id = Column(String, ForeignKey("contents.id"), nullable=True)
```

---

## 9. Variable Resolution System

### Variable Syntax

Use Mustache-style `{{VARIABLE_NAME}}` syntax.

### Variable Types

1. **Static Variables**: Resolved at prompt build time from other content pieces
   - `{{ROLE}}` → "Senior Policy Analyst"
   - `{{OUTPUT_FORMAT}}` → "Return a JSON object with..."

2. **Runtime Variables**: Resolved at execution time
   - `{{INPUT}}` → The actual document content being processed
   - `{{OUTPUT_A}}` → First output (for pairwise eval)
   - `{{OUTPUT_B}}` → Second output (for pairwise eval)
   - `{{OUTPUTS}}` → All outputs (for combine)

### Resolution Algorithm

```python
def resolve_variables(content: Content, runtime_vars: dict) -> str:
    """Resolve all variables in content body."""
    result = content.body
    
    # 1. Resolve static variables (from DB content pieces)
    for var_name, content_id in content.variables.items():
        if content_id:  # Static variable with linked content
            linked_content = get_content(content_id)
            # Recursively resolve nested variables
            resolved = resolve_variables(linked_content, runtime_vars)
            result = result.replace(f"{{{{{var_name}}}}}", resolved)
    
    # 2. Resolve runtime variables
    for var_name, value in runtime_vars.items():
        result = result.replace(f"{{{{{var_name}}}}}", value)
    
    return result
```

---

## 10. Implementation Phases

### Phase 1: Database Schema
- Create `github_connections` table
- Create `contents` table
- Update `presets` table with new fields
- Create Alembic migrations

### Phase 2: Backend API
- GitHub connection CRUD endpoints (`/api/v1/github-connections`)
- Content CRUD endpoints (`/api/v1/contents`)
- GitHub file browser endpoint (`/api/v1/github/{connection_id}/browse`)
- GitHub file import endpoint (`/api/v1/github/{connection_id}/import`)
- Variable resolution service

### Phase 3: Frontend - Content Library
- New "Content Library" tab/page
- Content type sidebar navigation
- Content editor with variable highlighting
- Import from GitHub modal
- Variable linking UI

### Phase 4: Frontend - Build Preset Updates
- Input source type selector (Database/GitHub)
- Database input picker (with create/edit)
- GitHub file browser and selector
- Content piece selectors (generation, eval, combine instructions)

### Phase 5: Execution Flow Updates
- Read inputs from DB or GitHub based on preset config
- Resolve variables in all instruction content
- Write outputs to GitHub if configured

---

## 11. API Endpoints

### GitHub Connections

```
GET    /api/v1/github-connections           # List all connections
POST   /api/v1/github-connections           # Create connection
GET    /api/v1/github-connections/{id}      # Get connection details
PUT    /api/v1/github-connections/{id}      # Update connection
DELETE /api/v1/github-connections/{id}      # Delete connection
POST   /api/v1/github-connections/{id}/test # Test connection
GET    /api/v1/github-connections/{id}/browse?path=/  # Browse repo files
POST   /api/v1/github-connections/{id}/import  # Import file as content
```

### Contents

```
GET    /api/v1/contents                     # List all contents
GET    /api/v1/contents?type=generation_instructions  # Filter by type
POST   /api/v1/contents                     # Create content
GET    /api/v1/contents/{id}                # Get content with body
PUT    /api/v1/contents/{id}                # Update content
DELETE /api/v1/contents/{id}                # Soft delete content
POST   /api/v1/contents/{id}/resolve        # Preview resolved content
```

---

*End of Specification*
