"""
User Management Endpoints

Handles user creation and API key generation for WordPress integration.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional

from acm2.app.db.master import MasterDB
from acm2.app.auth.api_keys import generate_api_key
from acm2.app.db.user_db import UserDB

router = APIRouter(tags=["Users"])


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""
    username: str
    email: EmailStr
    wordpress_user_id: Optional[int] = None


class CreateUserResponse(BaseModel):
    """Response model for user creation."""
    user_id: int
    username: str
    email: str
    api_key: str
    message: str


@router.post("/users", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: CreateUserRequest):
    """
    Create a new ACM2 user and generate an API key.
    
    This endpoint is called by WordPress when a new user is created.
    It creates the user in the master database, generates an API key,
    and initializes their user database.
    """
    master_db = MasterDB()
    
    try:
        # Check if user already exists
        if request.wordpress_user_id:
            existing_user = await master_db.get_user_by_wordpress_id(request.wordpress_user_id)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with WordPress ID {request.wordpress_user_id} already exists"
                )
        
        # Check if email already exists
        existing_email = await master_db.get_user_by_email(request.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {request.email} already exists"
            )
        
        # Create user in master database
        user_id = await master_db.create_user(
            username=request.username,
            email=request.email,
            wordpress_user_id=request.wordpress_user_id
        )
        
        # Generate API key
        plaintext_key, key_hash, key_prefix = generate_api_key()
        
        # Save API key to master database
        await master_db.create_api_key(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=f"WordPress API Key for {request.username}"
        )
        
        # Initialize user's personal database
        user_db = UserDB(user_id)
        await user_db.init_db()
        
        return CreateUserResponse(
            user_id=user_id,
            username=request.username,
            email=request.email,
            api_key=plaintext_key,
            message="User created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/users/me")
async def get_current_user_info():
    """
    Get information about the current authenticated user.
    
    Requires authentication via X-ACM2-API-Key header.
    """
    # TODO: Implement this endpoint with authentication
    # For now, return placeholder
    return {
        "message": "This endpoint requires authentication implementation"
    }
