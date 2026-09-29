import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from backend.app.database import get_db
from backend.app.models import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectNoteCreateRequest,
    ProjectNoteUpdateRequest,
    ProjectNoteResponse,
    ProjectSavedOutputCreateRequest,
    ProjectSavedOutputResponse,
    ProjectSummary,
    ProjectDetail
)

logger = logging.getLogger("services.projects")

class ProjectService:
    """
    Project Workspace Service:
    - Long-term organization workspace: Projects, Notes, Saved Outputs, and linked Chats & Files.
    - Strict multi-tenant isolation: all project records belong to a specific user.
    """

    async def create_project(self, user_id: str, req: ProjectCreateRequest) -> ProjectSummary:
        """Create a new project workspace for authenticated user."""
        name = req.name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name cannot be empty."
            )

        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        color = req.color or "#8B5CF6"

        async with get_db() as db:
            await db.execute("""
            INSERT INTO projects (id, userId, name, description, instructions, color, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                user_id,
                name,
                req.description.strip() if req.description else None,
                req.instructions.strip() if req.instructions else None,
                color,
                now,
                now
            ))
            await db.commit()

        return ProjectSummary(
            id=project_id,
            userId=user_id,
            name=name,
            description=req.description,
            instructions=req.instructions,
            color=color,
            chatCount=0,
            fileCount=0,
            noteCount=0,
            outputCount=0,
            createdAt=now,
            updatedAt=now
        )

    async def list_projects(self, user_id: str, limit: int = 50, offset: int = 0) -> List[ProjectSummary]:
        """List all projects belonging to the authenticated user with item counts."""
        async with get_db() as db:
            cursor = await db.execute("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM project_items pi WHERE pi.projectId = p.id AND pi.itemType = 'chat') as chatCount,
                   (SELECT COUNT(*) FROM project_items pi WHERE pi.projectId = p.id AND pi.itemType = 'file') as fileCount,
                   (SELECT COUNT(*) FROM project_notes pn WHERE pn.projectId = p.id) as noteCount,
                   (SELECT COUNT(*) FROM project_saved_outputs po WHERE po.projectId = p.id) as outputCount
            FROM projects p
            WHERE p.userId = ?
            ORDER BY p.updatedAt DESC
            LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            rows = await cursor.fetchall()

        results = []
        for r in rows:
            results.append(ProjectSummary(
                id=r["id"],
                userId=r["userId"],
                name=r["name"],
                description=r["description"],
                instructions=r["instructions"],
                color=r["color"] or "#8B5CF6",
                chatCount=r["chatCount"],
                fileCount=r["fileCount"],
                noteCount=r["noteCount"],
                outputCount=r["outputCount"],
                createdAt=r["createdAt"],
                updatedAt=r["updatedAt"]
            ))
        return results

    async def get_project(self, user_id: str, project_id: str) -> ProjectDetail:
        """Get full project details with notes, saved outputs, and linked items."""
        async with get_db() as db:
            cursor = await db.execute("""
            SELECT * FROM projects WHERE id = ? AND userId = ?
            """, (project_id, user_id))
            proj = await cursor.fetchone()

            if not proj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or unauthorized."
                )

            # 1. Fetch Notes
            notes_cursor = await db.execute("""
            SELECT * FROM project_notes WHERE projectId = ? AND userId = ? ORDER BY updatedAt DESC
            """, (project_id, user_id))
            note_rows = await notes_cursor.fetchall()

            notes = [
                ProjectNoteResponse(
                    id=n["id"],
                    projectId=n["projectId"],
                    userId=n["userId"],
                    title=n["title"],
                    content=n["content"],
                    createdAt=n["createdAt"],
                    updatedAt=n["updatedAt"]
                ) for n in note_rows
            ]

            # 2. Fetch Saved Outputs
            outputs_cursor = await db.execute("""
            SELECT * FROM project_saved_outputs WHERE projectId = ? AND userId = ? ORDER BY createdAt DESC
            """, (project_id, user_id))
            output_rows = await outputs_cursor.fetchall()

            saved_outputs = []
            for o in output_rows:
                meta = None
                if o["metadata"]:
                    try:
                        meta = json.loads(o["metadata"])
                    except Exception:
                        meta = None
                saved_outputs.append(ProjectSavedOutputResponse(
                    id=o["id"],
                    projectId=o["projectId"],
                    userId=o["userId"],
                    title=o["title"],
                    outputType=o["outputType"],
                    content=o["content"],
                    metadata=meta,
                    createdAt=o["createdAt"]
                ))

            # 3. Fetch Linked Chats
            chats_cursor = await db.execute("""
            SELECT c.id, c.title, c.model, c.createdAt, c.updatedAt
            FROM conversations c
            JOIN project_items pi ON pi.itemId = c.id
            WHERE pi.projectId = ? AND pi.userId = ? AND pi.itemType = 'chat'
            ORDER BY c.updatedAt DESC
            """, (project_id, user_id))
            chat_rows = await chats_cursor.fetchall()
            chats = [dict(r) for r in chat_rows]

            # 4. Fetch Linked Files
            files_cursor = await db.execute("""
            SELECT f.id, f.filename, f.originalFilename, f.fileType, f.fileSize, f.createdAt
            FROM files f
            JOIN project_items pi ON pi.itemId = f.id
            WHERE pi.projectId = ? AND pi.userId = ? AND pi.itemType = 'file'
            ORDER BY f.createdAt DESC
            """, (project_id, user_id))
            file_rows = await files_cursor.fetchall()
            files = [dict(r) for r in file_rows]

        return ProjectDetail(
            id=proj["id"],
            userId=proj["userId"],
            name=proj["name"],
            description=proj["description"],
            instructions=proj["instructions"],
            color=proj["color"] or "#8B5CF6",
            createdAt=proj["createdAt"],
            updatedAt=proj["updatedAt"],
            chats=chats,
            files=files,
            notes=notes,
            savedOutputs=saved_outputs
        )

    async def update_project(self, user_id: str, project_id: str, req: ProjectUpdateRequest) -> ProjectSummary:
        """Update project name, description, instructions, or color."""
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            proj = await cursor.fetchone()
            if not proj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or unauthorized."
                )

            new_name = req.name.strip() if req.name is not None else proj["name"]
            if not new_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project name cannot be empty."
                )

            new_desc = req.description if req.description is not None else proj["description"]
            new_inst = req.instructions if req.instructions is not None else proj["instructions"]
            new_color = req.color if req.color is not None else proj["color"]
            now = datetime.now(timezone.utc).isoformat()

            await db.execute("""
            UPDATE projects
            SET name = ?, description = ?, instructions = ?, color = ?, updatedAt = ?
            WHERE id = ? AND userId = ?
            """, (new_name, new_desc, new_inst, new_color, now, project_id, user_id))
            await db.commit()

        return await self.get_project_summary(user_id, project_id)

    async def get_project_summary(self, user_id: str, project_id: str) -> ProjectSummary:
        """Get summary metadata for a project."""
        async with get_db() as db:
            cursor = await db.execute("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM project_items pi WHERE pi.projectId = p.id AND pi.itemType = 'chat') as chatCount,
                   (SELECT COUNT(*) FROM project_items pi WHERE pi.projectId = p.id AND pi.itemType = 'file') as fileCount,
                   (SELECT COUNT(*) FROM project_notes pn WHERE pn.projectId = p.id) as noteCount,
                   (SELECT COUNT(*) FROM project_saved_outputs po WHERE po.projectId = p.id) as outputCount
            FROM projects p
            WHERE p.id = ? AND p.userId = ?
            """, (project_id, user_id))
            r = await cursor.fetchone()

        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or unauthorized."
            )

        return ProjectSummary(
            id=r["id"],
            userId=r["userId"],
            name=r["name"],
            description=r["description"],
            instructions=r["instructions"],
            color=r["color"] or "#8B5CF6",
            chatCount=r["chatCount"],
            fileCount=r["fileCount"],
            noteCount=r["noteCount"],
            outputCount=r["outputCount"],
            createdAt=r["createdAt"],
            updatedAt=r["updatedAt"]
        )

    async def delete_project(self, user_id: str, project_id: str) -> bool:
        """Delete project and cascade delete all its notes, saved outputs, and item links."""
        async with get_db() as db:
            cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            proj = await cursor.fetchone()
            if not proj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or unauthorized."
                )

            await db.execute("DELETE FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            await db.commit()
        return True

    # --------------------------------------------------------------------------
    # Project Notes CRUD
    # --------------------------------------------------------------------------

    async def add_note(self, user_id: str, project_id: str, req: ProjectNoteCreateRequest) -> ProjectNoteResponse:
        """Create a new note inside a project."""
        title = req.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note title cannot be empty.")

        note_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        async with get_db() as db:
            # Verify project ownership
            p_cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            if not await p_cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")

            await db.execute("""
            INSERT INTO project_notes (id, projectId, userId, title, content, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (note_id, project_id, user_id, title, req.content, now, now))

            # Update project updatedAt
            await db.execute("UPDATE projects SET updatedAt = ? WHERE id = ?", (now, project_id))
            await db.commit()

        return ProjectNoteResponse(
            id=note_id,
            projectId=project_id,
            userId=user_id,
            title=title,
            content=req.content,
            createdAt=now,
            updatedAt=now
        )

    async def list_notes(self, user_id: str, project_id: str) -> List[ProjectNoteResponse]:
        """List all notes in a project."""
        async with get_db() as db:
            p_cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            if not await p_cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")

            cursor = await db.execute("""
            SELECT * FROM project_notes WHERE projectId = ? AND userId = ? ORDER BY updatedAt DESC
            """, (project_id, user_id))
            rows = await cursor.fetchall()

        return [
            ProjectNoteResponse(
                id=r["id"],
                projectId=r["projectId"],
                userId=r["userId"],
                title=r["title"],
                content=r["content"],
                createdAt=r["createdAt"],
                updatedAt=r["updatedAt"]
            ) for r in rows
        ]

    async def update_note(self, user_id: str, project_id: str, note_id: str, req: ProjectNoteUpdateRequest) -> ProjectNoteResponse:
        """Update note title and/or content."""
        now = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            cursor = await db.execute("""
            SELECT * FROM project_notes WHERE id = ? AND projectId = ? AND userId = ?
            """, (note_id, project_id, user_id))
            note = await cursor.fetchone()
            if not note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or unauthorized.")

            new_title = req.title.strip() if req.title is not None else note["title"]
            new_content = req.content if req.content is not None else note["content"]

            await db.execute("""
            UPDATE project_notes SET title = ?, content = ?, updatedAt = ? WHERE id = ? AND userId = ?
            """, (new_title, new_content, now, note_id, user_id))
            await db.execute("UPDATE projects SET updatedAt = ? WHERE id = ?", (now, project_id))
            await db.commit()

        return ProjectNoteResponse(
            id=note_id,
            projectId=project_id,
            userId=user_id,
            title=new_title,
            content=new_content,
            createdAt=note["createdAt"],
            updatedAt=now
        )

    async def delete_note(self, user_id: str, project_id: str, note_id: str) -> bool:
        """Delete a note from a project."""
        async with get_db() as db:
            cursor = await db.execute("""
            DELETE FROM project_notes WHERE id = ? AND projectId = ? AND userId = ?
            """, (note_id, project_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or unauthorized.")
            await db.commit()
        return True

    # --------------------------------------------------------------------------
    # Project Saved Outputs CRUD
    # --------------------------------------------------------------------------

    async def save_output(self, user_id: str, project_id: str, req: ProjectSavedOutputCreateRequest) -> ProjectSavedOutputResponse:
        """Save an AI output (code, summary, text, diagram, search synthesis) to a project."""
        title = req.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Output title cannot be empty.")

        output_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(req.metadata) if req.metadata else None

        async with get_db() as db:
            p_cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            if not await p_cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")

            await db.execute("""
            INSERT INTO project_saved_outputs (id, projectId, userId, title, outputType, content, metadata, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (output_id, project_id, user_id, title, req.outputType, req.content, meta_str, now))
            await db.execute("UPDATE projects SET updatedAt = ? WHERE id = ?", (now, project_id))
            await db.commit()

        return ProjectSavedOutputResponse(
            id=output_id,
            projectId=project_id,
            userId=user_id,
            title=title,
            outputType=req.outputType,
            content=req.content,
            metadata=req.metadata,
            createdAt=now
        )

    async def list_saved_outputs(self, user_id: str, project_id: str) -> List[ProjectSavedOutputResponse]:
        """List all saved outputs in a project."""
        async with get_db() as db:
            p_cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            if not await p_cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")

            cursor = await db.execute("""
            SELECT * FROM project_saved_outputs WHERE projectId = ? AND userId = ? ORDER BY createdAt DESC
            """, (project_id, user_id))
            rows = await cursor.fetchall()

        results = []
        for r in rows:
            meta = None
            if r["metadata"]:
                try:
                    meta = json.loads(r["metadata"])
                except Exception:
                    meta = None
            results.append(ProjectSavedOutputResponse(
                id=r["id"],
                projectId=r["projectId"],
                userId=r["userId"],
                title=r["title"],
                outputType=r["outputType"],
                content=r["content"],
                metadata=meta,
                createdAt=r["createdAt"]
            ))
        return results

    async def delete_saved_output(self, user_id: str, project_id: str, output_id: str) -> bool:
        """Delete a saved output from a project."""
        async with get_db() as db:
            cursor = await db.execute("""
            DELETE FROM project_saved_outputs WHERE id = ? AND projectId = ? AND userId = ?
            """, (output_id, project_id, user_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output not found or unauthorized.")
            await db.commit()
        return True

    # --------------------------------------------------------------------------
    # Project Item Associations (Link/Unlink Chats and Files)
    # --------------------------------------------------------------------------

    async def associate_item(self, user_id: str, project_id: str, item_type: str, item_id: str) -> Dict[str, Any]:
        """Link an existing chat or file to a project workspace."""
        if item_type not in ('chat', 'file'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item type. Must be 'chat' or 'file'.")

        now = datetime.now(timezone.utc).isoformat()
        link_id = str(uuid.uuid4())

        async with get_db() as db:
            # 1. Verify Project ownership
            p_cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND userId = ?", (project_id, user_id))
            if not await p_cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")

            # 2. Verify Item ownership
            if item_type == 'chat':
                c_cursor = await db.execute("SELECT id FROM conversations WHERE id = ? AND userId = ?", (item_id, user_id))
                if not await c_cursor.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized.")
            elif item_type == 'file':
                f_cursor = await db.execute("SELECT id FROM files WHERE id = ? AND userId = ?", (item_id, user_id))
                if not await f_cursor.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or unauthorized.")

            # 3. Insert or ignore duplicate
            await db.execute("""
            INSERT OR IGNORE INTO project_items (id, projectId, userId, itemType, itemId, createdAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (link_id, project_id, user_id, item_type, item_id, now))
            await db.execute("UPDATE projects SET updatedAt = ? WHERE id = ?", (now, project_id))
            await db.commit()

        return {"success": True, "projectId": project_id, "itemType": item_type, "itemId": item_id}

    async def remove_associated_item(self, user_id: str, project_id: str, item_type: str, item_id: str) -> bool:
        """Unlink a chat or file from a project."""
        async with get_db() as db:
            cursor = await db.execute("""
            DELETE FROM project_items WHERE projectId = ? AND userId = ? AND itemType = ? AND itemId = ?
            """, (project_id, user_id, item_type, item_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked item not found.")
            await db.commit()
        return True

    # Method Aliases for developer convenience
    create_note = add_note
    create_saved_output = save_output
    link_item = associate_item
    unlink_item = remove_associated_item

project_service = ProjectService()

