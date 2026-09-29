import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from backend.app.database import get_db
from backend.app.models import (
    UserPreferencesRequest,
    UserPreferencesResponse,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryItemResponse,
    MemoryListResponse
)

logger = logging.getLogger("services.personalization")

class PersonalizationService:
    """
    Personalization & Controlled Memory Architecture Service:
    - Manages non-sensitive user preferences (display name, tone, language, theme, memory toggle).
    - Manages controlled, transparent user memory (view, add, delete, clear, toggle).
    - Synthesizes dynamic AI prompt context from active memories, preferences, and project rules.
    """

    # --------------------------------------------------------------------------
    # User Preferences
    # --------------------------------------------------------------------------

    async def get_preferences(self, user_id: str) -> UserPreferencesResponse:
        """Retrieve user preferences, initializing defaults if first access."""
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            cursor = await db.execute("""
            SELECT * FROM user_preferences WHERE userId = ?
            """, (user_id,))
            pref = await cursor.fetchone()

            if not pref:
                # Initialize default preferences
                await db.execute("""
                INSERT INTO user_preferences (
                    userId, displayName, preferredLanguage, theme, aiTone,
                    customInstructions, autoSpeakAudio, codeTheme, enableMemory, updatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, None, "English", "system", "balanced", None, 0, "atom-one-dark", 1, now))
                await db.commit()

                return UserPreferencesResponse(
                    userId=user_id,
                    displayName=None,
                    preferredLanguage="English",
                    theme="system",
                    aiTone="balanced",
                    customInstructions=None,
                    autoSpeakAudio=False,
                    codeTheme="atom-one-dark",
                    enableMemory=True,
                    updatedAt=now
                )

        return UserPreferencesResponse(
            userId=pref["userId"],
            displayName=pref["displayName"],
            preferredLanguage=pref["preferredLanguage"] or "English",
            theme=pref["theme"] or "system",
            aiTone=pref["aiTone"] or "balanced",
            customInstructions=pref["customInstructions"],
            autoSpeakAudio=bool(pref["autoSpeakAudio"]),
            codeTheme=pref["codeTheme"] or "atom-one-dark",
            enableMemory=bool(pref["enableMemory"]),
            updatedAt=pref["updatedAt"]
        )

    async def update_preferences(self, user_id: str, req: UserPreferencesRequest) -> UserPreferencesResponse:
        """Update user preferences."""
        existing = await self.get_preferences(user_id)
        now = datetime.now(timezone.utc).isoformat()

        display_name = req.displayName.strip() if req.displayName is not None else existing.displayName
        pref_lang = req.preferredLanguage if req.preferredLanguage is not None else existing.preferredLanguage
        theme = req.theme if req.theme is not None else existing.theme
        ai_tone = req.aiTone if req.aiTone is not None else existing.aiTone
        custom_inst = req.customInstructions.strip() if req.customInstructions is not None else existing.customInstructions
        auto_speak = int(req.autoSpeakAudio) if req.autoSpeakAudio is not None else int(existing.autoSpeakAudio)
        code_theme = req.codeTheme if req.codeTheme is not None else existing.codeTheme
        enable_mem = int(req.enableMemory) if req.enableMemory is not None else int(existing.enableMemory)

        async with get_db() as db:
            await db.execute("""
            INSERT INTO user_preferences (
                userId, displayName, preferredLanguage, theme, aiTone,
                customInstructions, autoSpeakAudio, codeTheme, enableMemory, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(userId) DO UPDATE SET
                displayName = excluded.displayName,
                preferredLanguage = excluded.preferredLanguage,
                theme = excluded.theme,
                aiTone = excluded.aiTone,
                customInstructions = excluded.customInstructions,
                autoSpeakAudio = excluded.autoSpeakAudio,
                codeTheme = excluded.codeTheme,
                enableMemory = excluded.enableMemory,
                updatedAt = excluded.updatedAt
            """, (user_id, display_name, pref_lang, theme, ai_tone, custom_inst, auto_speak, code_theme, enable_mem, now))
            await db.commit()

        return UserPreferencesResponse(
            userId=user_id,
            displayName=display_name,
            preferredLanguage=pref_lang,
            theme=theme,
            aiTone=ai_tone,
            customInstructions=custom_inst,
            autoSpeakAudio=bool(auto_speak),
            codeTheme=code_theme,
            enableMemory=bool(enable_mem),
            updatedAt=now
        )

    # --------------------------------------------------------------------------
    # Controlled Memory Architecture CRUD
    # --------------------------------------------------------------------------

    async def create_memory(self, user_id: str, req: MemoryCreateRequest) -> MemoryItemResponse:
        """Add a transparent, user-controlled memory item."""
        key = req.key.strip()
        value = req.value.strip()
        if not key or not value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Memory key and value are required.")

        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        category = req.category or "preference"

        async with get_db() as db:
            await db.execute("""
            INSERT INTO user_memories (id, userId, key, value, category, isActive, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (memory_id, user_id, key, value, category, now, now))
            await db.commit()

        return MemoryItemResponse(
            id=memory_id,
            userId=user_id,
            key=key,
            value=value,
            category=category,
            isActive=True,
            createdAt=now,
            updatedAt=now
        )

    async def list_memories(self, user_id: str) -> MemoryListResponse:
        """List all memories for authenticated user and indicate if memory is enabled."""
        prefs = await self.get_preferences(user_id)

        async with get_db() as db:
            cursor = await db.execute("""
            SELECT * FROM user_memories WHERE userId = ? ORDER BY updatedAt DESC
            """, (user_id,))
            rows = await cursor.fetchall()

        items = [
            MemoryItemResponse(
                id=r["id"],
                userId=r["userId"],
                key=r["key"],
                value=r["value"],
                category=r["category"],
                isActive=bool(r["isActive"]),
                createdAt=r["createdAt"],
                updatedAt=r["updatedAt"]
            ) for r in rows
        ]

        return MemoryListResponse(
            memories=items,
            memoryEnabled=prefs.enableMemory,
            total=len(items)
        )

    async def update_memory(self, user_id: str, memory_id: str, req: MemoryUpdateRequest) -> MemoryItemResponse:
        """Update memory key, value, category, or active status."""
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM user_memories WHERE id = ? AND userId = ?", (memory_id, user_id))
            mem = await cursor.fetchone()
            if not mem:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or unauthorized.")

            new_key = req.key.strip() if req.key is not None else mem["key"]
            new_val = req.value.strip() if req.value is not None else mem["value"]
            new_cat = req.category if req.category is not None else mem["category"]
            new_active = int(req.isActive) if req.isActive is not None else mem["isActive"]

            await db.execute("""
            UPDATE user_memories
            SET key = ?, value = ?, category = ?, isActive = ?, updatedAt = ?
            WHERE id = ? AND userId = ?
            """, (new_key, new_val, new_cat, new_active, now, memory_id, user_id))
            await db.commit()

        return MemoryItemResponse(
            id=memory_id,
            userId=user_id,
            key=new_key,
            value=new_val,
            category=new_cat,
            isActive=bool(new_active),
            createdAt=mem["createdAt"],
            updatedAt=now
        )

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a single memory item."""
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM user_memories WHERE id = ? AND userId = ?", (memory_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or unauthorized.")
            await db.commit()
        return True

    async def clear_all_memories(self, user_id: str) -> bool:
        """Delete all memories for authenticated user."""
        async with get_db() as db:
            await db.execute("DELETE FROM user_memories WHERE userId = ?", (user_id,))
            await db.commit()
        return True

    # --------------------------------------------------------------------------
    # AI System Prompt Context Synthesis
    # --------------------------------------------------------------------------

    async def build_personalized_context(self, user_id: str, project_id: Optional[str] = None) -> str:
        """
        Synthesize personalized guidelines, active memories, and project instructions
        to inject into LLM system prompts.
        """
        prefs = await self.get_preferences(user_id)
        sections = []

        # 1. User Identity & Persona
        user_info = []
        if prefs.displayName:
            user_info.append(f"User Display Name: {prefs.displayName}")
        if prefs.preferredLanguage and prefs.preferredLanguage != "English":
            user_info.append(f"Preferred Language: {prefs.preferredLanguage} (respond or adapt when appropriate)")
        if prefs.aiTone and prefs.aiTone != "balanced":
            user_info.append(f"Response Style Preference: {prefs.aiTone}")

        if user_info:
            sections.append("### User Personalization Profile\n" + "\n".join(f"- {u}" for u in user_info))

        # 2. Custom User Instructions
        if prefs.customInstructions:
            sections.append(f"### Custom User Instructions\n{prefs.customInstructions}")

        # 3. Controlled Active Memories (if enabled)
        if prefs.enableMemory:
            async with get_db() as db:
                cursor = await db.execute("""
                SELECT key, value, category FROM user_memories
                WHERE userId = ? AND isActive = 1
                ORDER BY category, key
                """, (user_id,))
                rows = await cursor.fetchall()

            if rows:
                mem_lines = [f"- **[{r['category'].upper()}] {r['key']}**: {r['value']}" for r in rows]
                sections.append("### User Memory & Retained Knowledge Context\n" + "\n".join(mem_lines))

        # 4. Project Instructions (if inside a project)
        if project_id:
            async with get_db() as db:
                p_cursor = await db.execute("""
                SELECT name, instructions, description FROM projects WHERE id = ? AND userId = ?
                """, (project_id, user_id))
                proj = await p_cursor.fetchone()
                if proj and proj["instructions"]:
                    sections.append(f"### Project Context ({proj['name']})\n{proj['instructions']}")

        return "\n\n".join(sections)

    # Method Aliases for developer convenience
    clear_memories = clear_all_memories

personalization_service = PersonalizationService()

