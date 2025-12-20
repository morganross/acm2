"""
Content API Routes.

Endpoints for managing content (instructions, criteria, fragments, input documents).
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db
from app.infra.db.repositories import ContentRepository
from app.infra.db.models.content import ContentType as DBContentType
from ..schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentSummary,
    ContentDetail,
    ContentList,
    ContentType,
    ContentResolveRequest,
    ContentResolved,
    ContentTypeCounts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contents", tags=["contents"])


def _content_to_summary(content) -> ContentSummary:
    """Convert DB content to summary response."""
    return ContentSummary(
        id=content.id,
        name=content.name,
        content_type=ContentType(content.content_type),
        description=content.description,
        tags=content.tags or [],
        body_preview=content.body[:200] if content.body else "",
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


def _content_to_detail(content) -> ContentDetail:
    """Convert DB content to detail response."""
    return ContentDetail(
        id=content.id,
        name=content.name,
        content_type=ContentType(content.content_type),
        body=content.body,
        variables=content.variables or {},
        description=content.description,
        tags=content.tags or [],
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


# ============================================================================
# List / Search
# ============================================================================

@router.get("", response_model=ContentList)
async def list_contents(
    content_type: Optional[ContentType] = Query(None, description="Filter by content type"),
    search: Optional[str] = Query(None, description="Search by name"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ContentList:
    """
    List contents with optional filtering.
    
    - Filter by content_type to get only specific types
    - Search by name for partial matches
    - Filter by tag
    """
    repo = ContentRepository(db)
    offset = (page - 1) * page_size
    
    if search:
        db_type = DBContentType(content_type.value) if content_type else None
        items = await repo.search_by_name(search, content_type=db_type, limit=page_size)
        total = len(items)  # Approximate for search
    elif tag:
        db_type = DBContentType(content_type.value) if content_type else None
        items = await repo.search_by_tag(tag, content_type=db_type, limit=page_size)
        total = len(items)
    elif content_type:
        db_type = DBContentType(content_type.value)
        items = await repo.get_by_type(db_type, limit=page_size, offset=offset)
        total = await repo.count_by_type(db_type)
    else:
        items = await repo.get_active(limit=page_size, offset=offset)
        # For total count, we'd need another query - approximate for now
        all_items = await repo.get_active(limit=1000, offset=0)
        total = len(all_items)
    
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    return ContentList(
        items=[_content_to_summary(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/counts", response_model=ContentTypeCounts)
async def get_content_counts(
    db: AsyncSession = Depends(get_db),
) -> ContentTypeCounts:
    """Get count of contents by type."""
    repo = ContentRepository(db)
    
    counts = ContentTypeCounts()
    counts.generation_instructions = await repo.count_by_type(DBContentType.GENERATION_INSTRUCTIONS)
    counts.input_document = await repo.count_by_type(DBContentType.INPUT_DOCUMENT)
    counts.single_eval_instructions = await repo.count_by_type(DBContentType.SINGLE_EVAL_INSTRUCTIONS)
    counts.pairwise_eval_instructions = await repo.count_by_type(DBContentType.PAIRWISE_EVAL_INSTRUCTIONS)
    counts.eval_criteria = await repo.count_by_type(DBContentType.EVAL_CRITERIA)
    counts.combine_instructions = await repo.count_by_type(DBContentType.COMBINE_INSTRUCTIONS)
    counts.template_fragment = await repo.count_by_type(DBContentType.TEMPLATE_FRAGMENT)
    counts.total = (
        counts.generation_instructions + 
        counts.input_document +
        counts.single_eval_instructions +
        counts.pairwise_eval_instructions +
        counts.eval_criteria +
        counts.combine_instructions +
        counts.template_fragment
    )
    
    return counts


# ============================================================================
# CRUD Operations
# ============================================================================

@router.post("", response_model=ContentDetail, status_code=201)
async def create_content(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
) -> ContentDetail:
    """Create new content."""
    repo = ContentRepository(db)
    
    # Check if name already exists for this type
    existing = await repo.get_by_name(data.name)
    if existing and existing.content_type == data.content_type.value:
        raise HTTPException(
            status_code=400,
            detail=f"Content with name '{data.name}' already exists for type {data.content_type.value}"
        )
    
    content = await repo.create(
        name=data.name,
        content_type=data.content_type.value,
        body=data.body,
        variables=data.variables,
        description=data.description,
        tags=data.tags,
    )
    
    logger.info(f"Created content: {content.id} ({content.name})")
    return _content_to_detail(content)


@router.get("/{content_id}", response_model=ContentDetail)
async def get_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
) -> ContentDetail:
    """Get content by ID."""
    repo = ContentRepository(db)
    content = await repo.get_by_id(content_id)
    
    if not content or content.is_deleted:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return _content_to_detail(content)


@router.put("/{content_id}", response_model=ContentDetail)
async def update_content(
    content_id: str,
    data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContentDetail:
    """Update content."""
    repo = ContentRepository(db)
    content = await repo.get_by_id(content_id)
    
    if not content or content.is_deleted:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Build update dict
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.body is not None:
        update_data["body"] = data.body
    if data.variables is not None:
        update_data["variables"] = data.variables
    if data.description is not None:
        update_data["description"] = data.description
    if data.tags is not None:
        update_data["tags"] = data.tags
    
    if update_data:
        content = await repo.update(content_id, **update_data)
    
    logger.info(f"Updated content: {content_id}")
    return _content_to_detail(content)


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete content (soft delete)."""
    repo = ContentRepository(db)
    
    success = await repo.soft_delete(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    
    logger.info(f"Deleted content: {content_id}")


# ============================================================================
# Variable Resolution
# ============================================================================

@router.post("/{content_id}/resolve", response_model=ContentResolved)
async def resolve_content(
    content_id: str,
    data: ContentResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentResolved:
    """
    Resolve/preview content with variables substituted.
    
    Static variables (linked to other content) are resolved recursively.
    Runtime variables are substituted from the request body.
    """
    repo = ContentRepository(db)
    content = await repo.get_by_id(content_id)
    
    if not content or content.is_deleted:
        raise HTTPException(status_code=404, detail="Content not found")
    
    resolved_body, unresolved = await _resolve_variables(
        content, 
        data.runtime_variables, 
        repo,
        visited=set()
    )
    
    return ContentResolved(
        id=content.id,
        name=content.name,
        content_type=ContentType(content.content_type),
        resolved_body=resolved_body,
        unresolved_variables=unresolved,
    )


async def _resolve_variables(
    content,
    runtime_vars: dict[str, str],
    repo: ContentRepository,
    visited: set[str],
) -> tuple[str, list[str]]:
    """
    Recursively resolve variables in content.
    
    Returns (resolved_body, list_of_unresolved_variables)
    """
    # Prevent infinite recursion
    if content.id in visited:
        return content.body, []
    visited.add(content.id)
    
    result = content.body
    unresolved = []
    
    # Find all {{VARIABLE}} patterns
    pattern = r"\{\{(\w+)\}\}"
    matches = re.findall(pattern, result)
    
    for var_name in matches:
        placeholder = f"{{{{{var_name}}}}}"
        
        # Check runtime variables first
        if var_name in runtime_vars:
            result = result.replace(placeholder, runtime_vars[var_name])
            continue
        
        # Check static variables (linked content)
        static_vars = content.variables or {}
        if var_name in static_vars and static_vars[var_name]:
            linked_id = static_vars[var_name]
            linked_content = await repo.get_by_id(linked_id)
            
            if linked_content and not linked_content.is_deleted:
                # Recursively resolve the linked content
                resolved_linked, linked_unresolved = await _resolve_variables(
                    linked_content, runtime_vars, repo, visited
                )
                result = result.replace(placeholder, resolved_linked)
                unresolved.extend(linked_unresolved)
            else:
                unresolved.append(var_name)
        else:
            # Variable not found
            unresolved.append(var_name)
    
    return result, unresolved


# ============================================================================
# Duplicate
# ============================================================================

@router.post("/{content_id}/duplicate", response_model=ContentDetail, status_code=201)
async def duplicate_content(
    content_id: str,
    name: Optional[str] = Query(None, description="Name for the duplicate"),
    db: AsyncSession = Depends(get_db),
) -> ContentDetail:
    """Create a copy of existing content."""
    repo = ContentRepository(db)
    content = await repo.get_by_id(content_id)
    
    if not content or content.is_deleted:
        raise HTTPException(status_code=404, detail="Content not found")
    
    new_name = name or f"{content.name} (Copy)"
    
    duplicate = await repo.create(
        name=new_name,
        content_type=content.content_type,
        body=content.body,
        variables=content.variables.copy() if content.variables else {},
        description=content.description,
        tags=content.tags.copy() if content.tags else [],
    )
    
    logger.info(f"Duplicated content {content_id} -> {duplicate.id}")
    return _content_to_detail(duplicate)
