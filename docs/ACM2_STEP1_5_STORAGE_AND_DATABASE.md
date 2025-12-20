# ACM 2.0 – Step 1.5 Storage and Database Choices

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Database Strategy:** SQLite is the primary database for single-user self-hosted deployments. PostgreSQL is optional for multi-user/team scenarios.

## 1. Purpose

Step 1.5 finalizes the **storage and database architecture** for ACM 2.0. This document specifies where data lives, how it's accessed, and the rationale for each choice. All input files, output artifacts, and logs are stored in GitHub repositories.

## 2. Design Principles

| Principle | Description |
|-----------|-------------|
| **GitHub-First** | GitHub is the single source of truth for documents, artifacts, and logs |
| **Structured Metadata** | PostgreSQL stores run/task/artifact metadata; GitHub stores file content |
| **Separation of Concerns** | Database for queries and state; GitHub for versioned file storage |
| **Auditability** | Every file change is a Git commit with author, timestamp, and message |
| **Portability** | Storage abstraction allows future backends (S3, Azure Blob) without API changes |

## 3. Storage Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACM 2.0 STORAGE ARCHITECTURE                        │
│                              (Cross-Platform)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         METADATA LAYER                                │   │
│  │               (SQLite default / PostgreSQL optional)                  │   │
│  │                                                                       │   │
│  │   runs, documents, artifacts, tasks, evaluations, api_keys            │   │
│  │   - Query by status, date, tags                                       │   │
│  │   - Track relationships (run → tasks → artifacts)                     │   │
│  │   - Store GitHub references (repo, path, sha)                         │   │
│  │   - All IDs are 26-char ULIDs                                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    │ references                              │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FILE STORAGE LAYER                            │   │
│  │                            (GitHub)                                   │   │
│  │                                                                       │   │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │   │
│  │   │   INPUTS    │   │   OUTPUTS   │   │    LOGS     │                │   │
│  │   │   (docs)    │   │ (artifacts) │   │  (traces)   │                │   │
│  │   └─────────────┘   └─────────────┘   └─────────────┘                │   │
│  │                                                                       │   │
│  │   owner/acm-docs/         owner/acm-outputs/      owner/acm-logs/    │   │
│  │   └── docs/               └── runs/               └── runs/          │   │
│  │       ├── intro.md            └── run_01.../          └── run_01.../ │   │
│  │       └── chapter1.md             ├── artifacts/          ├── acm.log│   │
│  │                                   ├── eval/               └── timeline│   │
│  │                                   └── winners/                .json  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. Database Choice

### 4.1 Primary Database: SQLite (Default)

**SQLite is the default and recommended database for ACM 2.0:**

| Feature | Benefit |
|---------|---------|
| Zero configuration | Just works out of the box |
| Single file storage | `acm2.db` — easy backup and migration |
| Cross-platform native | No external database server needed |
| ACID transactions | Run integrity guaranteed |
| JSON columns | Flexible config storage (TEXT with app-layer validation) |

**Use Cases**:
- Single-user self-hosted deployment (the primary ACM 2.0 use case)
- Local development
- CI/CD pipeline tests
- Production for individual users

### 4.2 Optional Database: PostgreSQL (Multi-User)

**PostgreSQL is available as an upgrade for team/SaaS scenarios:**

| Feature | Benefit |
|---------|---------|
| True concurrency | Multiple users, multiple runs simultaneously |
| Connection pooling | API concurrency (asyncpg + pgbouncer) |
| Native JSONB | Optimized JSON queries |
| Full-text search | Document/artifact search |

**When to Use**:
- Multiple users need concurrent access
- Team/organizational deployment
- SaaS or hosted service scenarios
- **Not required for typical self-hosted use**

### 4.3 Database Schema Summary

> **Note:** All primary keys use 26-character ULID strings (chronologically sortable).  
> For SQLite, use `TEXT` instead of `JSONB`. JSON validation happens at the application layer.

```sql
-- Core entities
CREATE TABLE project (
    project_id      TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,               -- URL-safe identifier
    github_config   TEXT NOT NULL,               -- JSON: {docs_repo, outputs_repo, logs_repo}
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(tenant_id, slug)
);
CREATE INDEX idx_project_tenant ON project(tenant_id);

CREATE TABLE run (
    run_id          TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    project_id      TEXT REFERENCES project(project_id),
    status          TEXT NOT NULL DEFAULT 'pending',
    config          TEXT NOT NULL,               -- JSON: frozen config snapshot
    github_branch   TEXT,                        -- e.g., "acm/runs/run_01..."
    started_at      TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_run_tenant ON run(tenant_id);
CREATE INDEX idx_run_project ON run(project_id);
CREATE INDEX idx_run_status ON run(status);
CREATE INDEX idx_run_created ON run(created_at DESC);

CREATE TABLE document (
    document_id     TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    project_id      TEXT REFERENCES project(project_id),
    github_repo     TEXT NOT NULL,               -- "owner/repo"
    github_path     TEXT NOT NULL,               -- "docs/intro.md"
    github_ref      TEXT NOT NULL,               -- "main" or commit SHA
    content_hash    TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    skip_reason     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_document_tenant ON document(tenant_id);
CREATE INDEX idx_document_project ON document(project_id);
CREATE INDEX idx_document_hash ON document(content_hash);

-- Junction table: Many-to-many between runs and documents
CREATE TABLE run_document (
    run_id          TEXT NOT NULL REFERENCES run(run_id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
    added_at        TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, document_id)
);
CREATE INDEX idx_run_document_run ON run_document(run_id);
CREATE INDEX idx_run_document_doc ON run_document(document_id);

CREATE TABLE artifact (
    artifact_id     TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    document_id     TEXT REFERENCES document(document_id),
    kind            TEXT NOT NULL,
    generator       TEXT NOT NULL,               -- 'fpf', 'gptr'
    model_id        TEXT,                        -- 'gpt-4o', 'claude-3-5-sonnet'
    github_repo     TEXT NOT NULL,
    github_path     TEXT NOT NULL,
    github_sha      TEXT,                        -- Commit SHA after write
    content_hash    TEXT,
    token_count     INTEGER,
    cost_usd        REAL,
    generation_ms   INTEGER,
    metadata        TEXT NOT NULL,               -- JSON
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_artifact_tenant ON artifact(tenant_id);
CREATE INDEX idx_artifact_run ON artifact(run_id);
CREATE INDEX idx_artifact_document ON artifact(document_id);
CREATE INDEX idx_artifact_generator ON artifact(generator);

CREATE TABLE task (
    task_id         TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    config          TEXT NOT NULL,               -- JSON
    error_message   TEXT,
    retry_count     INTEGER DEFAULT 0,
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_task_tenant ON task(tenant_id);
CREATE INDEX idx_task_run ON task(run_id);
CREATE INDEX idx_task_status ON task(status);

CREATE TABLE log_entry (
    log_id          TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    task_id         TEXT REFERENCES task(task_id),
    level           TEXT NOT NULL,               -- DEBUG, INFO, WARN, ERROR
    message         TEXT NOT NULL,
    metadata        TEXT,                        -- JSON
    github_synced   INTEGER DEFAULT 0,           -- SQLite boolean (0/1)
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_log_tenant ON log_entry(tenant_id);
CREATE INDEX idx_log_run ON log_entry(run_id);
CREATE INDEX idx_log_created ON log_entry(created_at DESC);

-- Evaluation tables (same schema as ACM 1.0 for compatibility)
CREATE TABLE single_doc_results (
    result_id       TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    artifact_id     TEXT REFERENCES artifact(artifact_id),
    dimension       TEXT NOT NULL,
    score           REAL,
    iteration       INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_single_doc_tenant ON single_doc_results(tenant_id);
CREATE INDEX idx_single_doc_run ON single_doc_results(run_id);

CREATE TABLE pairwise_results (
    result_id       TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    artifact_a      TEXT REFERENCES artifact(artifact_id),
    artifact_b      TEXT REFERENCES artifact(artifact_id),
    winner          TEXT CHECK(winner IN ('A', 'B', 'tie')),
    iteration       INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_pairwise_tenant ON pairwise_results(tenant_id);
CREATE INDEX idx_pairwise_run ON pairwise_results(run_id);

CREATE TABLE elo_ratings (
    rating_id       TEXT PRIMARY KEY,            -- ULID (26 chars)
    tenant_id       TEXT NOT NULL DEFAULT 'default',
    run_id          TEXT REFERENCES run(run_id) ON DELETE CASCADE,
    artifact_id     TEXT REFERENCES artifact(artifact_id),
    elo_rating      REAL DEFAULT 1500.0,
    games_played    INTEGER DEFAULT 0,
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_elo_tenant ON elo_ratings(tenant_id);
CREATE INDEX idx_elo_run ON elo_ratings(run_id);
```

> **Note:** Indexes are defined inline with each table above. The `CREATE INDEX` statements immediately follow each `CREATE TABLE` for clarity.

## 5. GitHub Storage Configuration

### 5.1 Repository Structure

ACM 2.0 uses **three GitHub repositories** per project (can be same repo with different paths):

| Repository | Purpose | Example |
|------------|---------|---------|
| **Docs Repo** | Input markdown files | `owner/acm-docs` |
| **Outputs Repo** | Generated artifacts, eval results, winners | `owner/acm-outputs` |
| **Logs Repo** | Run logs, timeline JSON, debug traces | `owner/acm-logs` |

### 5.2 Project Configuration

```yaml
# Stored in project.github_config JSONB column
{
  "docs": {
    "repository": "YOUR_USER/firstpub-Platform",
    "base_path": "docs/",
    "default_branch": "main"
  },
  "outputs": {
    "repository": "YOUR_USER/acm-outputs",
    "base_path": "runs/",
    "default_branch": "main",
    "branch_per_run": true,           # Create branch per run
    "auto_merge": false               # Require PR review
  },
  "logs": {
    "repository": "YOUR_USER/acm-logs",
    "base_path": "runs/",
    "default_branch": "main",
    "retention_days": 90              # Auto-cleanup old logs
  }
}
```

### 5.3 Outputs Repository Structure

```
acm-outputs/
├── runs/
│   ├── run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/
│   │   ├── artifacts/
│   │   │   ├── intro.fpf.1.gpt-4o.abc.md
│   │   │   ├── intro.fpf.2.claude-3-5-sonnet.def.md
│   │   │   ├── intro.gptr.1.gpt-4o.ghi.md
│   │   │   └── chapter1.fpf.1.gpt-4o.jkl.md
│   │   ├── eval/
│   │   │   ├── single_doc_results.csv
│   │   │   ├── pairwise_results.csv
│   │   │   ├── elo_rankings.csv
│   │   │   ├── eval_results.db          # SQLite export
│   │   │   └── report.html
│   │   ├── winners/
│   │   │   ├── intro.winner.md
│   │   │   └── chapter1.winner.md
│   │   └── run_manifest.json            # Run metadata snapshot
│   └── run_01HGWJ7K8L1M2N3P4Q5R6S7T8/
│       └── ...
└── README.md
```

### 5.4 Logs Repository Structure

```
acm-logs/
├── runs/
│   ├── run_01HGWJ8K9M2N3P4Q5R6S7T8U9V/
│   │   ├── acm_session.log              # Main ACM log
│   │   ├── acm_subproc.log              # Subprocess output log
│   │   ├── timeline_data.json           # Timeline for HTML report
│   │   ├── tasks/
│   │   │   ├── task_01...fpf.log
│   │   │   ├── task_02...gptr.log
│   │   │   └── task_03...eval.log
│   │   └── errors/
│   │       └── task_02...error.json     # Detailed error info
│   └── run_01HGWJ7K8L1M2N3P4Q5R6S7T8/
│       └── ...
└── README.md
```

### 5.5 Run Manifest File

Each run creates a `run_manifest.json` for self-contained reproducibility:

```json
{
  "run_id": "run_01HGWJ8K9M2N3P4Q5R6S7T8U9V",
  "acm_version": "2.0.0",
  "created_at": "2025-12-03T15:30:00Z",
  "completed_at": "2025-12-03T16:45:00Z",
  "status": "completed",
  "project": {
    "project_id": "firstpub-platform",
    "docs_repo": "YOUR_USER/firstpub-Platform",
    "docs_commit": "abc123def456..."
  },
  "config": {
    "generators": { ... },
    "evaluation": { ... }
  },
  "documents": [
    {
      "document_id": "doc_intro_001",
      "path": "docs/intro.md",
      "content_hash": "sha256:..."
    }
  ],
  "artifacts": [
    {
      "artifact_id": "art_01...",
      "path": "artifacts/intro.fpf.1.gpt-4o.abc.md",
      "generator": "fpf",
      "model": "gpt-4o"
    }
  ],
  "evaluation": {
    "winner_artifact_id": "art_01...",
    "elo_rating": 1623
  }
}
```

## 6. GitHub Storage Adapter

### 6.1 Interface Definition

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class GitHubFile:
    path: str
    content: bytes
    sha: str | None = None
    encoding: str = "utf-8"

@dataclass  
class GitHubCommit:
    sha: str
    message: str
    author: str
    timestamp: str
    files: list[str]

class StorageProvider(ABC):
    """Abstract interface for file storage."""
    
    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """Read file content."""
        pass
    
    @abstractmethod
    async def write_file(self, path: str, content: bytes, message: str) -> str:
        """Write file, return commit SHA."""
        pass
    
    @abstractmethod
    async def delete_file(self, path: str, message: str) -> str:
        """Delete file, return commit SHA."""
        pass
    
    @abstractmethod
    async def list_files(self, path_prefix: str) -> list[str]:
        """List files under path prefix."""
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    async def get_file_hash(self, path: str) -> str:
        """Get content hash (Git blob SHA or computed)."""
        pass


class GitHubStorageProvider(StorageProvider):
    """GitHub-backed storage implementation."""
    
    def __init__(
        self,
        repository: str,           # "owner/repo"
        base_path: str,            # "runs/"
        branch: str = "main",
        token: str | None = None,  # GitHub PAT or installation token
    ):
        self.repository = repository
        self.base_path = base_path.rstrip("/") + "/"
        self.branch = branch
        self.token = token
        self._client: httpx.AsyncClient | None = None
    
    async def read_file(self, path: str) -> bytes:
        """
        Read file from GitHub via Contents API.
        
        GET /repos/{owner}/{repo}/contents/{path}?ref={branch}
        """
        full_path = self.base_path + path
        url = f"https://api.github.com/repos/{self.repository}/contents/{full_path}"
        
        async with self._get_client() as client:
            response = await client.get(
                url,
                params={"ref": self.branch},
                headers=self._headers()
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("encoding") == "base64":
                import base64
                return base64.b64decode(data["content"])
            else:
                return data["content"].encode("utf-8")
    
    async def write_file(self, path: str, content: bytes, message: str) -> str:
        """
        Write file to GitHub via Contents API.
        
        PUT /repos/{owner}/{repo}/contents/{path}
        
        If file exists, include SHA for update. Otherwise create new.
        """
        full_path = self.base_path + path
        url = f"https://api.github.com/repos/{self.repository}/contents/{full_path}"
        
        import base64
        encoded_content = base64.b64encode(content).decode("ascii")
        
        # Check if file exists to get SHA for update
        existing_sha = None
        try:
            async with self._get_client() as client:
                check_response = await client.get(
                    url,
                    params={"ref": self.branch},
                    headers=self._headers()
                )
                if check_response.status_code == 200:
                    existing_sha = check_response.json().get("sha")
        except Exception:
            pass  # File doesn't exist, create new
        
        payload = {
            "message": message,
            "content": encoded_content,
            "branch": self.branch
        }
        if existing_sha:
            payload["sha"] = existing_sha
        
        async with self._get_client() as client:
            response = await client.put(
                url,
                json=payload,
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()["commit"]["sha"]
    
    async def write_files_batch(
        self,
        files: list[GitHubFile],
        message: str
    ) -> GitHubCommit:
        """
        Write multiple files in a single commit using Git Data API.
        
        More efficient than multiple single-file writes.
        Uses: Trees API + Commits API
        """
        # 1. Get current commit SHA
        # 2. Create blobs for each file
        # 3. Create tree with new blobs
        # 4. Create commit pointing to tree
        # 5. Update branch ref
        
        # ... implementation details ...
        pass
    
    async def create_branch(self, branch_name: str, from_branch: str = "main") -> str:
        """
        Create a new branch for run isolation.
        
        POST /repos/{owner}/{repo}/git/refs
        """
        # Get SHA of source branch
        # Create new ref pointing to same SHA
        pass
    
    async def create_pull_request(
        self,
        title: str,
        head_branch: str,
        base_branch: str = "main",
        body: str = ""
    ) -> int:
        """
        Create PR for review before merging artifacts.
        
        POST /repos/{owner}/{repo}/pulls
        """
        pass
```

### 6.2 Batch Write Optimization

For runs generating many artifacts, use Git Data API for atomic multi-file commits:

```python
async def commit_run_artifacts(
    self,
    run_id: str,
    artifacts: list[tuple[str, bytes]],  # (path, content) pairs
    message: str
) -> GitHubCommit:
    """
    Commit all artifacts for a run in a single Git commit.
    
    Steps:
    1. Create blob for each file
    2. Build tree with all blobs
    3. Create commit with tree
    4. Update branch reference
    
    This is ~10x faster than individual file commits for large runs.
    """
    
    # 1. Get base tree SHA from current branch head
    base_tree_sha = await self._get_branch_tree_sha(self.branch)
    
    # 2. Create blobs in parallel
    blob_tasks = [
        self._create_blob(content)
        for path, content in artifacts
    ]
    blob_shas = await asyncio.gather(*blob_tasks)
    
    # 3. Build tree entries
    tree_entries = [
        {
            "path": self.base_path + path,
            "mode": "100644",  # Regular file
            "type": "blob",
            "sha": blob_sha
        }
        for (path, _), blob_sha in zip(artifacts, blob_shas)
    ]
    
    # 4. Create tree
    new_tree_sha = await self._create_tree(base_tree_sha, tree_entries)
    
    # 5. Create commit
    parent_sha = await self._get_branch_head_sha(self.branch)
    commit_sha = await self._create_commit(
        message=message,
        tree_sha=new_tree_sha,
        parent_shas=[parent_sha]
    )
    
    # 6. Update branch ref
    await self._update_ref(self.branch, commit_sha)
    
    return GitHubCommit(
        sha=commit_sha,
        message=message,
        author="ACM 2.0",
        timestamp=datetime.utcnow().isoformat(),
        files=[path for path, _ in artifacts]
    )
```

### 6.3 Rate Limiting & Caching

```python
class GitHubStorageProvider(StorageProvider):
    
    def __init__(self, ...):
        ...
        self._rate_limiter = AsyncRateLimiter(
            requests_per_second=10,      # GitHub API limit
            burst_size=30
        )
        self._cache = TTLCache(
            maxsize=1000,
            ttl=300                       # 5 minute cache
        )
    
    async def read_file(self, path: str) -> bytes:
        cache_key = f"read:{self.repository}:{self.branch}:{path}"
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Rate limit API calls
        async with self._rate_limiter:
            content = await self._fetch_file(path)
        
        self._cache[cache_key] = content
        return content
    
    async def invalidate_cache(self, path_prefix: str = ""):
        """Invalidate cache entries matching prefix."""
        keys_to_remove = [
            k for k in self._cache.keys()
            if path_prefix in k
        ]
        for key in keys_to_remove:
            del self._cache[key]
```

## 7. Log Storage Strategy

### 7.1 Real-Time vs Batch Logging

| Log Type | Storage Strategy | Sync Frequency |
|----------|------------------|----------------|
| **Task logs** | Buffer in memory, write on task complete | Per task |
| **Run session log** | Buffer, flush every 30s or 1000 lines | Periodic |
| **Timeline JSON** | Generate at run end | Once |
| **Error traces** | Write immediately | Immediate |

### 7.2 Log Writer Implementation

```python
class GitHubLogWriter:
    """Buffered log writer with periodic GitHub sync."""
    
    def __init__(
        self,
        storage: GitHubStorageProvider,
        run_id: str,
        buffer_size: int = 1000,
        flush_interval: float = 30.0
    ):
        self.storage = storage
        self.run_id = run_id
        self.buffer: list[str] = []
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
    
    async def log(self, level: str, message: str, **metadata):
        """Add log entry to buffer."""
        timestamp = datetime.utcnow().isoformat()
        entry = json.dumps({
            "timestamp": timestamp,
            "level": level,
            "message": message,
            **metadata
        })
        
        async with self._lock:
            self.buffer.append(entry)
            
            if len(self.buffer) >= self.buffer_size:
                await self._flush()
    
    async def _flush(self):
        """Write buffered logs to GitHub."""
        if not self.buffer:
            return
        
        async with self._lock:
            content = "\n".join(self.buffer) + "\n"
            self.buffer.clear()
        
        path = f"{self.run_id}/acm_session.log"
        
        # Append to existing log file
        try:
            existing = await self.storage.read_file(path)
            content = existing.decode("utf-8") + content
        except Exception:
            pass  # File doesn't exist yet
        
        await self.storage.write_file(
            path=path,
            content=content.encode("utf-8"),
            message=f"[ACM] Log update for {self.run_id}"
        )
    
    async def start_periodic_flush(self):
        """Start background task for periodic flushing."""
        async def _periodic():
            while True:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
        
        self._flush_task = asyncio.create_task(_periodic())
    
    async def close(self):
        """Final flush and cleanup."""
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush()
```

## 8. Skip Logic Integration

### 8.1 GitHub-Based Skip Check

```python
async def should_skip_document(
    document: Document,
    storage: GitHubStorageProvider,
    run_config: RunConfig
) -> tuple[bool, str | None]:
    """
    Check if document should be skipped based on existing GitHub artifacts.
    
    Returns: (should_skip, reason)
    """
    base_name = document.base_name  # e.g., "intro"
    
    # Check 1: Existing artifacts in outputs repo
    artifacts_path = f"runs/*/artifacts/{base_name}.*"
    existing_artifacts = await storage.list_files_glob(artifacts_path)
    if existing_artifacts:
        return True, f"Found existing artifact: {existing_artifacts[0]}"
    
    # Check 2: Existing winner
    winners_path = f"runs/*/winners/{base_name}.*"
    existing_winners = await storage.list_files_glob(winners_path)
    if existing_winners:
        return True, f"Found existing winner: {existing_winners[0]}"
    
    # Check 3: Same content hash in recent runs
    if run_config.skip_unchanged:
        recent_runs = await get_recent_runs(limit=10)
        for run in recent_runs:
            if run.has_document_with_hash(document.content_hash):
                return True, f"Content unchanged since run {run.run_id}"
    
    return False, None
```

### 8.2 Content Hash Tracking

```python
async def compute_document_hash(
    storage: GitHubStorageProvider,
    path: str
) -> str:
    """
    Compute content hash for skip logic.
    Uses Git blob SHA for efficiency (already computed by GitHub).
    """
    # GitHub API returns sha in contents response
    url = f"https://api.github.com/repos/{storage.repository}/contents/{path}"
    response = await storage._client.get(url, params={"ref": storage.branch})
    
    if response.status_code == 200:
        # Git blob SHA is content-addressable hash
        return f"git:{response.json()['sha']}"
    
    # Fallback: compute SHA-256
    content = await storage.read_file(path)
    import hashlib
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
```

## 9. Database Connection Management

### 9.1 SQLite Configuration (Default)

```python
# app/infra/db/config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class DatabaseSettings(BaseSettings):
    """
    Database configuration from environment.
    
    SQLite is the default. Set use_postgres=True for multi-user deployments.
    """
    
    # SQLite (default)
    sqlite_path: str = "./acm2.db"
    
    # PostgreSQL (optional, for multi-user)
    use_postgres: bool = False
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "acm2"
    postgres_password: str = ""
    postgres_database: str = "acm2"
    
    # Connection pool (PostgreSQL only)
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minutes
    
    @property
    def database_url(self) -> str:
        if self.use_postgres:
            return (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
            )
        # SQLite is default
        return f"sqlite+aiosqlite:///{self.sqlite_path}"
    
    @property
    def is_sqlite(self) -> bool:
        return not self.use_postgres
    
    class Config:
        env_prefix = "ACM2_DB_"
```

### 9.2 Session Factory

```python
# app/infra/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        
        # SQLite doesn't use connection pooling
        engine_kwargs = {"echo": False}  # Set True for SQL logging
        
        if not settings.is_sqlite:
            # PostgreSQL connection pooling
            engine_kwargs.update({
                "pool_size": settings.pool_size,
                "max_overflow": settings.max_overflow,
                "pool_timeout": settings.pool_timeout,
                "pool_recycle": settings.pool_recycle,
            })
        
        self.engine = create_async_engine(settings.database_url, **engine_kwargs)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a transactional scope around operations."""
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> bool:
        """Verify database connectivity."""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
```

## 10. Migration Strategy

### 10.1 Alembic Setup

```
acm2/
├── alembic/
│   ├── versions/
│   │   ├── 20251203_1200_initial_schema.py
│   │   └── 20251203_1300_add_github_columns.py
│   ├── env.py
│   └── script.py.mako
└── alembic.ini
```

### 10.2 Migration Commands

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current
```

## 11. Environment Variables

```bash
# Database (SQLite is default - no config needed for basic use)
ACM2_DB_SQLITE_PATH=./acm2.db              # SQLite database file path

# PostgreSQL (optional - set USE_POSTGRES=true for multi-user)
ACM2_DB_USE_POSTGRES=false                  # Set to true for PostgreSQL
ACM2_DB_POSTGRES_HOST=localhost
ACM2_DB_POSTGRES_PORT=5432
ACM2_DB_POSTGRES_USER=acm2
ACM2_DB_POSTGRES_PASSWORD=secret
ACM2_DB_POSTGRES_DATABASE=acm2

# GitHub
ACM2_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
ACM2_GITHUB_APP_ID=123456
ACM2_GITHUB_APP_PRIVATE_KEY_PATH=C:\path\to\key.pem    # Windows path

# Storage defaults
ACM2_DEFAULT_DOCS_REPO=YOUR_USER/acm-docs
ACM2_DEFAULT_OUTPUTS_REPO=YOUR_USER/acm-outputs
ACM2_DEFAULT_LOGS_REPO=YOUR_USER/acm-logs
```

## 12. Security Considerations

| Concern | Mitigation |
|---------|------------|
| GitHub token exposure | Store in environment variables, never in code or DB |
| Database credentials | For SQLite: file permissions. For PostgreSQL: use secrets manager |
| Log data sensitivity | Redact API keys, tokens from logs before GitHub sync |
| Repository access | Use fine-grained GitHub tokens with minimal scope |
| Artifact tampering | Content hash verification on read |
| Windows file security | Set appropriate NTFS permissions on `acm2.db` |

## 13. Performance Targets

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| SQLite query (indexed) | < 5ms | Single file, local disk |
| PostgreSQL query (indexed) | < 10ms | Connection pooling for multi-user |
| DB query (complex) | < 100ms | Add indexes as needed |
| GitHub read (cached) | < 5ms | TTL cache for hot paths |
| GitHub read (uncached) | < 500ms | Rate limited |
| GitHub write (single file) | < 2s | Including commit |
| GitHub write (batch, 10 files) | < 5s | Using Git Data API |
| Log flush | < 3s | Async, non-blocking |

## 14. Resolved Questions

> These questions from the initial draft have been resolved.

| Question | Resolution |
|----------|------------|
| SQLite vs PostgreSQL? | **SQLite is default**. PostgreSQL optional for multi-user. |
| Docker? | **No**. Python + database, no containerization. |
| Platform support? | Windows, Linux, macOS. |
| ID format? | **ULID** (26-char chronologically sortable strings). |

## 15. Open Questions

1. Should each run create its own GitHub branch, or commit directly to main?
2. What's the retention policy for old run artifacts in GitHub?
3. Do we need GitHub Actions integration for post-run workflows?
4. Should logs be stored as individual files or appended to a single file?
5. How do we handle GitHub API rate limits during high-volume runs?
6. Should we support GitHub Enterprise Server in addition to github.com?
