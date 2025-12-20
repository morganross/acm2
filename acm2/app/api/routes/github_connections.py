"""
GitHub Connection API Routes.

Endpoints for managing GitHub repository connections.
"""
import base64
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db
from app.infra.db.repositories import GitHubConnectionRepository, ContentRepository
from app.infra.db.models.content import ContentType as DBContentType
from ..schemas.github_connection import (
    GitHubConnectionCreate,
    GitHubConnectionUpdate,
    GitHubConnectionSummary,
    GitHubConnectionDetail,
    GitHubConnectionList,
    GitHubConnectionTestResult,
    GitHubBrowseResponse,
    GitHubFileInfo,
    GitHubFileContent,
    GitHubImportRequest,
)
from ..schemas.content import ContentDetail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github-connections", tags=["github"])


# ============================================================================
# Token Encryption Helpers
# ============================================================================
# NOTE: In production, use proper encryption (e.g., Fernet with a secret key)
# For now, we use simple base64 encoding as a placeholder

def _encrypt_token(token: str) -> str:
    """Encrypt a token for storage. TODO: Use proper encryption."""
    return base64.b64encode(f"enc:{token}".encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token. TODO: Use proper decryption."""
    try:
        decoded = base64.b64decode(encrypted).decode()
        if decoded.startswith("enc:"):
            return decoded[4:]
        return decoded
    except Exception:
        return encrypted  # Fallback for unencrypted tokens


# ============================================================================
# GitHub API Helpers
# ============================================================================

async def _get_github_client(token: str):
    """Get a GitHub client. Lazy import to avoid dependency issues."""
    try:
        from github import Github
        return Github(token)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyGithub not installed. Run: pip install PyGithub"
        )


async def _test_github_connection(token: str, repo: str, branch: str) -> tuple[bool, str]:
    """Test a GitHub connection. Returns (is_valid, message)."""
    try:
        from github import Github
        from github.GithubException import GithubException, BadCredentialsException
        
        g = Github(token)
        
        # Test authentication
        user = g.get_user()
        _ = user.login  # Force API call
        
        # Test repository access
        repository = g.get_repo(repo)
        _ = repository.full_name  # Force API call
        
        # Test branch access
        _ = repository.get_branch(branch)
        
        return True, f"Successfully connected to {repo} ({branch})"
        
    except BadCredentialsException:
        return False, "Invalid GitHub token"
    except GithubException as e:
        if e.status == 404:
            return False, f"Repository '{repo}' not found or no access"
        return False, f"GitHub API error: {e.data.get('message', str(e))}"
    except ImportError:
        return False, "PyGithub not installed"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def _connection_to_summary(conn) -> GitHubConnectionSummary:
    """Convert DB connection to summary response."""
    return GitHubConnectionSummary(
        id=conn.id,
        name=conn.name,
        repo=conn.repo,
        branch=conn.branch,
        is_valid=conn.is_valid,
        last_tested_at=conn.last_tested_at,
        created_at=conn.created_at,
    )


def _connection_to_detail(conn) -> GitHubConnectionDetail:
    """Convert DB connection to detail response."""
    return GitHubConnectionDetail(
        id=conn.id,
        name=conn.name,
        repo=conn.repo,
        branch=conn.branch,
        is_valid=conn.is_valid,
        last_tested_at=conn.last_tested_at,
        last_error=conn.last_error,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# ============================================================================
# CRUD Operations
# ============================================================================

@router.get("", response_model=GitHubConnectionList)
async def list_connections(
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionList:
    """List all GitHub connections."""
    repo = GitHubConnectionRepository(db)
    connections = await repo.get_active()
    
    return GitHubConnectionList(
        items=[_connection_to_summary(c) for c in connections],
        total=len(connections),
    )


@router.post("", response_model=GitHubConnectionDetail, status_code=201)
async def create_connection(
    data: GitHubConnectionCreate,
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionDetail:
    """Create a new GitHub connection."""
    repo = GitHubConnectionRepository(db)
    
    # Check if connection to this repo already exists
    existing = await repo.get_by_repo(data.repo)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Connection to '{data.repo}' already exists"
        )
    
    # Test the connection before saving
    is_valid, message = await _test_github_connection(data.token, data.repo, data.branch)
    
    connection = await repo.create(
        name=data.name,
        repo=data.repo,
        branch=data.branch,
        token_encrypted=_encrypt_token(data.token),
        is_valid=is_valid,
        last_tested_at=datetime.utcnow(),
        last_error=None if is_valid else message,
    )
    
    logger.info(f"Created GitHub connection: {connection.id} ({connection.repo})")
    
    if not is_valid:
        logger.warning(f"GitHub connection {connection.id} created but invalid: {message}")
    
    return _connection_to_detail(connection)


@router.get("/{connection_id}", response_model=GitHubConnectionDetail)
async def get_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionDetail:
    """Get a GitHub connection by ID."""
    repo = GitHubConnectionRepository(db)
    connection = await repo.get_by_id(connection_id)
    
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return _connection_to_detail(connection)


@router.put("/{connection_id}", response_model=GitHubConnectionDetail)
async def update_connection(
    connection_id: str,
    data: GitHubConnectionUpdate,
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionDetail:
    """Update a GitHub connection."""
    repo = GitHubConnectionRepository(db)
    connection = await repo.get_by_id(connection_id)
    
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Update fields
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.branch is not None:
        update_data["branch"] = data.branch
    
    if update_data:
        connection = await repo.update(connection_id, **update_data)
    
    # Update token separately if provided
    if data.token:
        connection = await repo.update_token(connection_id, _encrypt_token(data.token))
        # Re-test connection with new token
        is_valid, message = await _test_github_connection(
            data.token, connection.repo, connection.branch
        )
        await repo.update_test_status(connection_id, is_valid, None if is_valid else message)
        connection = await repo.get_by_id(connection_id)
    
    logger.info(f"Updated GitHub connection: {connection_id}")
    return _connection_to_detail(connection)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a GitHub connection (soft delete)."""
    repo = GitHubConnectionRepository(db)
    
    success = await repo.soft_delete(connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    logger.info(f"Deleted GitHub connection: {connection_id}")


# ============================================================================
# Test Connection
# ============================================================================

@router.post("/{connection_id}/test", response_model=GitHubConnectionTestResult)
async def test_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionTestResult:
    """Test a GitHub connection and update its status."""
    repo = GitHubConnectionRepository(db)
    connection = await repo.get_by_id(connection_id)
    
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Decrypt token and test
    token = _decrypt_token(connection.token_encrypted)
    is_valid, message = await _test_github_connection(token, connection.repo, connection.branch)
    
    # Update status
    await repo.update_test_status(connection_id, is_valid, None if is_valid else message)
    
    logger.info(f"Tested GitHub connection {connection_id}: valid={is_valid}")
    
    return GitHubConnectionTestResult(
        id=connection_id,
        is_valid=is_valid,
        message=message,
        tested_at=datetime.utcnow(),
    )


# ============================================================================
# Browse Repository
# ============================================================================

@router.get("/{connection_id}/browse", response_model=GitHubBrowseResponse)
async def browse_repository(
    connection_id: str,
    path: str = Query("/", description="Path in repository to browse"),
    db: AsyncSession = Depends(get_db),
) -> GitHubBrowseResponse:
    """Browse files and directories in a GitHub repository."""
    repo = GitHubConnectionRepository(db)
    connection = await repo.get_by_id(connection_id)
    
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        from github import Github
        from github.GithubException import GithubException
        
        token = _decrypt_token(connection.token_encrypted)
        g = Github(token)
        repository = g.get_repo(connection.repo)
        
        # Clean path
        clean_path = path.strip("/") if path != "/" else ""
        
        # Get contents
        if clean_path:
            contents = repository.get_contents(clean_path, ref=connection.branch)
        else:
            contents = repository.get_contents("", ref=connection.branch)
        
        # Handle both single file and directory listing
        if not isinstance(contents, list):
            contents = [contents]
        
        files = []
        for item in contents:
            files.append(GitHubFileInfo(
                name=item.name,
                path=item.path,
                type="dir" if item.type == "dir" else "file",
                size=item.size if item.type != "dir" else None,
                download_url=item.download_url if item.type != "dir" else None,
            ))
        
        # Sort: directories first, then files
        files.sort(key=lambda f: (0 if f.type == "dir" else 1, f.name.lower()))
        
        return GitHubBrowseResponse(
            connection_id=connection_id,
            repo=connection.repo,
            branch=connection.branch,
            path=path,
            contents=files,
        )
        
    except ImportError:
        raise HTTPException(status_code=500, detail="PyGithub not installed")
    except GithubException as e:
        raise HTTPException(status_code=400, detail=f"GitHub error: {e.data.get('message', str(e))}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error browsing repository: {str(e)}")


# ============================================================================
# Get File Content
# ============================================================================

@router.get("/{connection_id}/file", response_model=GitHubFileContent)
async def get_file_content(
    connection_id: str,
    path: str = Query(..., description="Path to file in repository"),
    db: AsyncSession = Depends(get_db),
) -> GitHubFileContent:
    """Get the content of a file from GitHub."""
    repo = GitHubConnectionRepository(db)
    connection = await repo.get_by_id(connection_id)
    
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        from github import Github
        from github.GithubException import GithubException
        
        token = _decrypt_token(connection.token_encrypted)
        g = Github(token)
        repository = g.get_repo(connection.repo)
        
        # Get file content
        file_content = repository.get_contents(path.strip("/"), ref=connection.branch)
        
        if file_content.type == "dir":
            raise HTTPException(status_code=400, detail="Path is a directory, not a file")
        
        # Decode content
        content = base64.b64decode(file_content.content).decode("utf-8")
        
        return GitHubFileContent(
            connection_id=connection_id,
            path=path,
            name=file_content.name,
            content=content,
            size=file_content.size,
            encoding="utf-8",
        )
        
    except ImportError:
        raise HTTPException(status_code=500, detail="PyGithub not installed")
    except GithubException as e:
        raise HTTPException(status_code=400, detail=f"GitHub error: {e.data.get('message', str(e))}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a text file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


# ============================================================================
# Import File as Content
# ============================================================================

@router.post("/{connection_id}/import", response_model=ContentDetail, status_code=201)
async def import_file_as_content(
    connection_id: str,
    data: GitHubImportRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentDetail:
    """Import a file from GitHub as content in the database."""
    gh_repo = GitHubConnectionRepository(db)
    content_repo = ContentRepository(db)
    
    connection = await gh_repo.get_by_id(connection_id)
    if not connection or connection.is_deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        from github import Github
        from github.GithubException import GithubException
        
        token = _decrypt_token(connection.token_encrypted)
        g = Github(token)
        repository = g.get_repo(connection.repo)
        
        # Get file content
        file_content = repository.get_contents(data.path.strip("/"), ref=connection.branch)
        
        if file_content.type == "dir":
            raise HTTPException(status_code=400, detail="Cannot import a directory")
        
        # Decode content
        content_body = base64.b64decode(file_content.content).decode("utf-8")
        
        # Validate content type
        try:
            content_type = DBContentType(data.content_type)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid content_type. Valid values: {[t.value for t in DBContentType]}"
            )
        
        # Create content
        name = data.name or file_content.name
        
        content = await content_repo.create(
            name=name,
            content_type=content_type.value,
            body=content_body,
            variables={},
            description=data.description or f"Imported from {connection.repo}/{data.path}",
            tags=data.tags,
        )
        
        logger.info(f"Imported {data.path} from {connection.repo} as content {content.id}")
        
        return ContentDetail(
            id=content.id,
            name=content.name,
            content_type=data.content_type,
            body=content.body,
            variables=content.variables or {},
            description=content.description,
            tags=content.tags or [],
            created_at=content.created_at,
            updated_at=content.updated_at,
        )
        
    except ImportError:
        raise HTTPException(status_code=500, detail="PyGithub not installed")
    except GithubException as e:
        raise HTTPException(status_code=400, detail=f"GitHub error: {e.data.get('message', str(e))}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a text file")
    except Exception as e:
        logger.exception(f"Error importing file from GitHub")
        raise HTTPException(status_code=500, detail=f"Error importing file: {str(e)}")
