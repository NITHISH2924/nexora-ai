import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.deps import get_current_user
from backend.app.models import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ChatMessageRequest,
    ChatMessageEditRequest,
    ConversationSummary,
    ConversationDetail,
    MessageItem
)
from backend.app.services.chat_service import chat_service
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("routes.chat")
router = APIRouter(prefix="/api/chat", tags=["AI Chat & Workspace"])

@router.get("/models")
async def list_ai_models(current_user: dict = Depends(get_current_user)):
    """List all supported AI models, their capabilities and availability."""
    models = ai_manager.list_models()
    return {"models": models}

@router.get("/conversations", response_model=List[ConversationSummary])
async def get_conversations(
    q: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """List conversations belonging to the authenticated user."""
    return await chat_service.get_user_conversations(
        user_id=current_user["userId"],
        query=q,
        limit=limit,
        offset=offset
    )

@router.post("/conversations", response_model=ConversationSummary)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation thread."""
    return await chat_service.create_conversation(
        user_id=current_user["userId"],
        title=req.title,
        model=req.model,
        system_prompt=req.systemPrompt
    )

@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get full conversation details and message history."""
    return await chat_service.get_conversation(
        user_id=current_user["userId"],
        conversation_id=conversation_id
    )

@router.patch("/conversations/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: str,
    req: ConversationUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Rename or update conversation metadata."""
    return await chat_service.update_conversation(
        user_id=current_user["userId"],
        conversation_id=conversation_id,
        title=req.title,
        is_pinned=req.isPinned,
        is_archived=req.isArchived,
        model=req.model
    )

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a conversation and its messages."""
    await chat_service.delete_conversation(
        user_id=current_user["userId"],
        conversation_id=conversation_id
    )
    return {"success": True, "message": "Conversation deleted successfully"}

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Non-streaming message endpoint."""
    user_id = current_user["userId"]
    
    # 1. Verify and load conversation
    conv = await chat_service.get_conversation(user_id, conversation_id)
    
    # 2. Add user message
    user_msg = await chat_service.add_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=req.content,
        model=req.model or conv["model"]
    )

    # 3. Compile full message context
    conv_updated = await chat_service.get_conversation(user_id, conversation_id)
    messages_payload = [{"role": m["role"], "content": m["content"]} for m in conv_updated["messages"]]

    # 4. Generate AI response
    model_to_use = req.model or conv["model"]
    system_prompt = req.systemPrompt or conv.get("systemPrompt")
    
    # Inject user personalization & active memories
    try:
        from backend.app.services.personalization_service import personalization_service
        personal_ctx = await personalization_service.build_personalized_context(user_id)
        if personal_ctx:
            system_prompt = f"{system_prompt}\n\n{personal_ctx}" if system_prompt else personal_ctx
    except Exception as e:
        logger.warning(f"Could not build personalized context: {e}")

    ai_text, actual_model = await ai_manager.generate_response(
        messages=messages_payload,
        model=model_to_use,
        system_prompt=system_prompt
    )

    # 5. Save assistant message
    asst_msg = await chat_service.add_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=ai_text,
        model=actual_model
    )

    return {
        "userMessage": user_msg,
        "assistantMessage": asst_msg,
        "conversation": await chat_service.get_conversation(user_id, conversation_id)
    }

@router.post("/conversations/{conversation_id}/stream")
async def stream_chat_response(
    conversation_id: str,
    req: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Real-time SSE streaming chat completion endpoint."""
    user_id = current_user["userId"]
    
    # 1. Verify conversation ownership
    conv = await chat_service.get_conversation(user_id, conversation_id)
    model_to_use = req.model or conv["model"]
    system_prompt = req.systemPrompt or conv.get("systemPrompt")

    # Inject user personalization & active memories
    try:
        from backend.app.services.personalization_service import personalization_service
        personal_ctx = await personalization_service.build_personalized_context(user_id)
        if personal_ctx:
            system_prompt = f"{system_prompt}\n\n{personal_ctx}" if system_prompt else personal_ctx
    except Exception as e:
        logger.warning(f"Could not build personalized context: {e}")

    # 2. Add user message to DB
    user_msg = await chat_service.add_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=req.content,
        model=model_to_use
    )

    # 3. Prepare full conversation history with optional file context
    conv_updated = await chat_service.get_conversation(user_id, conversation_id)
    messages_payload = [{"role": m["role"], "content": m["content"]} for m in conv_updated["messages"]]

    images_payload = []
    if req.fileIds:
        from backend.app.services.file_service import file_service
        file_attachments_text = []
        for fid in req.fileIds:
            try:
                fdata = await file_service.get_file(user_id, fid)
                if fdata["fileType"] == "image":
                    import base64
                    disk_p = await file_service.get_file_disk_path(user_id, fid)
                    with open(disk_p, "rb") as im_f:
                        im_b64 = base64.b64encode(im_f.read()).decode("utf-8")
                    images_payload.append({
                        "mime_type": fdata["mimeType"],
                        "data": im_b64,
                        "filename": fdata["originalFilename"]
                    })
                elif fdata.get("extractedText"):
                    file_attachments_text.append(f"=== ATTACHED FILE: {fdata['originalFilename']} ===\n{fdata['extractedText'][:15000]}\n=== END FILE ===")
            except Exception as e:
                logger.warning(f"Could not load attached file {fid}: {e}")

        if file_attachments_text and messages_payload:
            # Append context to latest user message
            messages_payload[-1]["content"] += "\n\n" + "\n\n".join(file_attachments_text)

    async def sse_event_generator():
        # First send user message confirmation
        yield f"event: user_message\ndata: {json.dumps(user_msg)}\n\n"

        full_content_accumulated = []
        try:
            async for chunk in ai_manager.stream_response(
                messages=messages_payload,
                model=model_to_use,
                system_prompt=system_prompt,
                images=images_payload
            ):
                full_content_accumulated.append(chunk)
                yield f"event: delta\ndata: {json.dumps({'chunk': chunk})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error in chat {conversation_id}: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        # Save assistant message in database
        full_text = "".join(full_content_accumulated)
        if full_text.strip():
            asst_msg = await chat_service.add_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=full_text,
                model=model_to_use
            )
            # Fetch latest conversation to return fresh title if auto-generated
            refreshed_conv = await chat_service.get_conversation(user_id, conversation_id)
            yield f"event: done\ndata: {json.dumps({'assistantMessage': asst_msg, 'conversationTitle': refreshed_conv['title']})}\n\n"
        else:
            yield f"event: done\ndata: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/conversations/{conversation_id}/regenerate")
async def regenerate_response(
    conversation_id: str,
    req: Optional[ChatMessageRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """Regenerate last assistant response using streaming SSE."""
    user_id = current_user["userId"]
    conv = await chat_service.get_conversation(user_id, conversation_id)
    
    model_to_use = (req.model if req and req.model else None) or conv["model"]
    system_prompt = (req.systemPrompt if req and req.systemPrompt else None) or conv.get("systemPrompt")

    # Inject user personalization & active memories
    try:
        from backend.app.services.personalization_service import personalization_service
        personal_ctx = await personalization_service.build_personalized_context(user_id)
        if personal_ctx:
            system_prompt = f"{system_prompt}\n\n{personal_ctx}" if system_prompt else personal_ctx
    except Exception as e:
        logger.warning(f"Could not build personalized context: {e}")

    # Clean previous assistant response and retrieve messages
    messages_payload = await chat_service.prepare_context_and_regenerate(user_id, conversation_id)

    async def sse_event_generator():
        full_content_accumulated = []
        try:
            async for chunk in ai_manager.stream_response(
                messages=messages_payload,
                model=model_to_use,
                system_prompt=system_prompt
            ):
                full_content_accumulated.append(chunk)
                yield f"event: delta\ndata: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Regenerate streaming error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        full_text = "".join(full_content_accumulated)
        if full_text.strip():
            asst_msg = await chat_service.add_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=full_text,
                model=model_to_use
            )
            yield f"event: done\ndata: {json.dumps({'assistantMessage': asst_msg})}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.put("/conversations/{conversation_id}/messages/{message_id}")
async def edit_message(
    conversation_id: str,
    message_id: str,
    req: ChatMessageEditRequest,
    current_user: dict = Depends(get_current_user)
):
    """Edit a user message, truncating subsequent messages and returning updated thread."""
    user_id = current_user["userId"]
    updated_conv = await chat_service.edit_message_and_truncate(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        new_content=req.content
    )
    return {"success": True, "conversation": updated_conv}
