"""
System prompts management routes for ChatTwelve API.
"""

from fastapi import APIRouter, HTTPException, status

from src.core.logging import logger
from src.database.prompt_repo import prompt_repo
from src.api.schemas.requests import CreatePromptRequest, UpdatePromptRequest
from src.api.schemas.responses import (
    PromptResponse, PromptListResponse, PromptDeleteResponse
)


router = APIRouter(prefix="/api/prompts", tags=["Prompts"])


def _prompt_to_response(prompt) -> PromptResponse:
    """Convert SystemPrompt to PromptResponse."""
    return PromptResponse(
        id=prompt.id,
        name=prompt.name,
        prompt=prompt.prompt,
        description=prompt.description,
        is_active=prompt.is_active,
        created_at=prompt.created_at.isoformat() + "Z",
        updated_at=prompt.updated_at.isoformat() + "Z"
    )


@router.get("/active", response_model=PromptResponse)
async def get_active_prompt():
    """
    Get the currently active system prompt.

    Returns the system prompt that is currently being used by the AI.
    """
    try:
        prompt = await prompt_repo.get_active_prompt()

        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active prompt found"
            )

        return _prompt_to_response(prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active prompt"
        )


@router.get("", response_model=PromptListResponse)
async def list_prompts():
    """
    Get all system prompts.

    Returns a list of all system prompts in the database.
    """
    try:
        prompts = await prompt_repo.list_all()

        return PromptListResponse(
            prompts=[_prompt_to_response(p) for p in prompts],
            count=len(prompts)
        )

    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list prompts"
        )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str):
    """
    Get a specific system prompt by ID.

    Args:
        prompt_id: ID of the prompt to retrieve
    """
    try:
        prompt = await prompt_repo.get_by_id(prompt_id)

        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}"
            )

        return _prompt_to_response(prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get prompt"
        )


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(request: CreatePromptRequest):
    """
    Create a new system prompt.

    Args:
        request: Prompt creation request with name, prompt text, and optional description

    Returns:
        The created system prompt
    """
    try:
        # Check if name already exists
        existing = await prompt_repo.get_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prompt with name '{request.name}' already exists"
            )

        prompt = await prompt_repo.create(
            name=request.name,
            prompt=request.prompt,
            description=request.description,
            is_active=request.is_active
        )

        return _prompt_to_response(prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prompt"
        )


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(prompt_id: str, request: UpdatePromptRequest):
    """
    Update an existing system prompt.

    Args:
        prompt_id: ID of the prompt to update
        request: Update request with optional fields to update

    Returns:
        The updated system prompt
    """
    try:
        # Check if name already exists (if changing name)
        if request.name is not None:
            existing = await prompt_repo.get_by_name(request.name)
            if existing and existing.id != prompt_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Prompt with name '{request.name}' already exists"
                )

        success = await prompt_repo.update(
            prompt_id=prompt_id,
            name=request.name,
            prompt=request.prompt,
            description=request.description,
            is_active=request.is_active
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}"
            )

        # Get the updated prompt to return
        prompt = await prompt_repo.get_by_id(prompt_id)
        return _prompt_to_response(prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update prompt"
        )


@router.delete("/{prompt_id}", response_model=PromptDeleteResponse)
async def delete_prompt(prompt_id: str):
    """
    Delete a system prompt.

    Args:
        prompt_id: ID of the prompt to delete

    Returns:
        Deletion confirmation
    """
    try:
        # Check if this is the active prompt
        active = await prompt_repo.get_active_prompt()
        if active and active.id == prompt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the active prompt. Set another prompt as active first."
            )

        success = await prompt_repo.delete(prompt_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}"
            )

        return PromptDeleteResponse(
            message="Prompt deleted successfully",
            prompt_id=prompt_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete prompt"
        )


@router.post("/{prompt_id}/activate", response_model=PromptResponse)
async def activate_prompt(prompt_id: str):
    """
    Set a prompt as the active one.

    Args:
        prompt_id: ID of the prompt to activate

    Returns:
        The activated prompt
    """
    try:
        success = await prompt_repo.set_active(prompt_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found: {prompt_id}"
            )

        prompt = await prompt_repo.get_by_id(prompt_id)
        return _prompt_to_response(prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate prompt"
        )
