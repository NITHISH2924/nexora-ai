import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncGenerator
import aiosqlite
from fastapi import HTTPException, status

from backend.app.database import get_db
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("chat_service")

def generate_title_from_prompt(prompt: str) -> str:
    """Generates a clean 3-7 word conversation title from user's first prompt."""
    clean = prompt.strip().replace("\n", " ")
    words = clean.split()
    if len(words) <= 6:
        title = " ".join(words)
    else:
        title = " ".join(words[:6]) + "..."
    # Capitalize first letter and cap length
    if title:
        title = title[0].toUpperCase() if hasattr(title[0], 'toUpperCase') else title[0].upper() + title[1:]
    return title[:60] if title else "New Chat"

class ChatService:
    @classmethod
    async def create_conversation(
        cls,
        user_id: str,
        title: Optional[str] = None,
        model: Optional[str] = "gemini-1.5-flash",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conv_title = title.strip() if (title and title.strip()) else "New Chat"
        used_model = model or "gemini-1.5-flash"

        async with get_db() as db:
            await db.execute("""
            INSERT INTO conversations (id, userId, title, model, systemPrompt, createdAt, updatedAt, isPinned, isArchived)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (conv_id, user_id, conv_title, used_model, system_prompt, now, now))
            await db.commit()

        return {
            "id": conv_id,
            "userId": user_id,
            "title": conv_title,
            "model": used_model,
            "systemPrompt": system_prompt,
            "createdAt": now,
            "updatedAt": now,
            "isPinned": False,
            "isArchived": False,
            "messageCount": 0,
            "lastMessage": None
        }

    @classmethod
    async def get_user_conversations(
        cls,
        user_id: str,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        async with get_db() as db:
            if query and query.strip():
                search_term = f"%{query.strip()}%"
                cursor = await db.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM messages m WHERE m.conversationId = c.id) as messageCount,
                       (SELECT m.content FROM messages m WHERE m.conversationId = c.id ORDER BY m.createdAt DESC LIMIT 1) as lastMessage
                FROM conversations c
                WHERE c.userId = ? AND c.isArchived = 0 AND (
                    c.title LIKE ? OR 
                    EXISTS (SELECT 1 FROM messages m WHERE m.conversationId = c.id AND m.content LIKE ?)
                )
                ORDER BY c.isPinned DESC, c.updatedAt DESC
                LIMIT ? OFFSET ?
                """, (user_id, search_term, search_term, limit, offset))
            else:
                cursor = await db.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM messages m WHERE m.conversationId = c.id) as messageCount,
                       (SELECT m.content FROM messages m WHERE m.conversationId = c.id ORDER BY m.createdAt DESC LIMIT 1) as lastMessage
                FROM conversations c
                WHERE c.userId = ? AND c.isArchived = 0
                ORDER BY c.isPinned DESC, c.updatedAt DESC
                LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
            
            rows = await cursor.fetchall()
            conversations = []
            for r in rows:
                conversations.append({
                    "id": r["id"],
                    "userId": r["userId"],
                    "title": r["title"],
                    "model": r["model"],
                    "systemPrompt": r["systemPrompt"],
                    "createdAt": r["createdAt"],
                    "updatedAt": r["updatedAt"],
                    "isPinned": bool(r["isPinned"]),
                    "isArchived": bool(r["isArchived"]),
                    "messageCount": r["messageCount"],
                    "lastMessage": r["lastMessage"]
                })
            return conversations

    @classmethod
    async def get_conversation(cls, user_id: str, conversation_id: str) -> Dict[str, Any]:
        async with get_db() as db:
            # 1. Fetch conversation with strict user verification
            cursor = await db.execute("""
            SELECT * FROM conversations WHERE id = ? AND userId = ?
            """, (conversation_id, user_id))
            conv = await cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied"
                )

            # 2. Fetch all messages ordered by timestamp
            cursor_msg = await db.execute("""
            SELECT * FROM messages WHERE conversationId = ? ORDER BY createdAt ASC
            """, (conversation_id,))
            msg_rows = await cursor_msg.fetchall()

            messages = []
            for m in msg_rows:
                messages.append({
                    "id": m["id"],
                    "conversationId": m["conversationId"],
                    "userId": m["userId"],
                    "role": m["role"],
                    "content": m["content"],
                    "model": m["model"],
                    "tokens": m["tokens"],
                    "createdAt": m["createdAt"]
                })

            return {
                "id": conv["id"],
                "userId": conv["userId"],
                "title": conv["title"],
                "model": conv["model"],
                "systemPrompt": conv["systemPrompt"],
                "createdAt": conv["createdAt"],
                "updatedAt": conv["updatedAt"],
                "isPinned": bool(conv["isPinned"]),
                "isArchived": bool(conv["isArchived"]),
                "messages": messages
            }

    @classmethod
    async def update_conversation(
        cls,
        user_id: str,
        conversation_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE id = ? AND userId = ?",
                (conversation_id, user_id)
            )
            conv = await cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied"
                )

            new_title = title.strip() if title is not None else conv["title"]
            new_pinned = int(is_pinned) if is_pinned is not None else conv["isPinned"]
            new_archived = int(is_archived) if is_archived is not None else conv["isArchived"]
            new_model = model if model is not None else conv["model"]
            now = datetime.now(timezone.utc).isoformat()

            await db.execute("""
            UPDATE conversations 
            SET title = ?, isPinned = ?, isArchived = ?, model = ?, updatedAt = ?
            WHERE id = ? AND userId = ?
            """, (new_title, new_pinned, new_archived, new_model, now, conversation_id, user_id))
            await db.commit()

        return await cls.get_conversation(user_id, conversation_id)

    @classmethod
    async def delete_conversation(cls, user_id: str, conversation_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM conversations WHERE id = ? AND userId = ?",
                (conversation_id, user_id)
            )
            conv = await cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied"
                )

            await db.execute("DELETE FROM conversations WHERE id = ? AND userId = ?", (conversation_id, user_id))
            await db.commit()
            return True

    @classmethod
    async def add_message(
        cls,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens: int = 0
    ) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        async with get_db() as db:
            # Verify user owns conversation
            cursor = await db.execute(
                "SELECT id, title FROM conversations WHERE id = ? AND userId = ?",
                (conversation_id, user_id)
            )
            conv = await cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied"
                )

            # Insert message
            await db.execute("""
            INSERT INTO messages (id, conversationId, userId, role, content, model, tokens, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, conversation_id, user_id, role, content, model, tokens, now))

            # Auto-update title if first user message and title is "New Chat"
            if role == "user" and conv["title"] == "New Chat":
                new_title = generate_title_from_prompt(content)
                await db.execute(
                    "UPDATE conversations SET title = ?, updatedAt = ? WHERE id = ?",
                    (new_title, now, conversation_id)
                )
            else:
                await db.execute(
                    "UPDATE conversations SET updatedAt = ? WHERE id = ?",
                    (now, conversation_id)
                )

            await db.commit()

        return {
            "id": msg_id,
            "conversationId": conversation_id,
            "userId": user_id,
            "role": role,
            "content": content,
            "model": model,
            "tokens": tokens,
            "createdAt": now
        }

    @classmethod
    async def edit_message_and_truncate(
        cls,
        user_id: str,
        conversation_id: str,
        message_id: str,
        new_content: str
    ) -> Dict[str, Any]:
        """Edits a user message and deletes all subsequent messages to allow fresh regeneration."""
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            # 1. Fetch message and verify ownership
            cursor = await db.execute(
                "SELECT * FROM messages WHERE id = ? AND conversationId = ? AND userId = ?",
                (message_id, conversation_id, user_id)
            )
            msg = await cursor.fetchone()
            if not msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found or access denied"
                )

            msg_created_at = msg["createdAt"]

            # 2. Delete all messages created AFTER this message in the conversation
            await db.execute(
                "DELETE FROM messages WHERE conversationId = ? AND createdAt > ?",
                (conversation_id, msg_created_at)
            )

            # 3. Update the target message content
            await db.execute(
                "UPDATE messages SET content = ? WHERE id = ?",
                (new_content, message_id)
            )

            await db.execute(
                "UPDATE conversations SET updatedAt = ? WHERE id = ?",
                (now, conversation_id)
            )
            await db.commit()

        return await cls.get_conversation(user_id, conversation_id)

    @classmethod
    async def prepare_context_and_regenerate(
        cls,
        user_id: str,
        conversation_id: str
    ) -> List[Dict[str, str]]:
        """Removes the trailing assistant message if present and returns message history for regeneration."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE id = ? AND userId = ?",
                (conversation_id, user_id)
            )
            conv = await cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied"
                )

            # Check if last message is assistant
            cursor_last = await db.execute(
                "SELECT * FROM messages WHERE conversationId = ? ORDER BY createdAt DESC LIMIT 1",
                (conversation_id,)
            )
            last_msg = await cursor_last.fetchone()
            if last_msg and last_msg["role"] == "assistant":
                await db.execute("DELETE FROM messages WHERE id = ?", (last_msg["id"],))
                await db.commit()

            # Return remaining history
            cursor_all = await db.execute(
                "SELECT role, content FROM messages WHERE conversationId = ? ORDER BY createdAt ASC",
                (conversation_id,)
            )
            rows = await cursor_all.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

chat_service = ChatService()
