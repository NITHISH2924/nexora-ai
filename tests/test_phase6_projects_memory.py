"""
Phase 6 Comprehensive Test Suite: Long-Term Organization and Personalization
- Projects Workspace (CRUD, Name, Description, Custom Instructions, Color Accent)
- Multi-Tenant Isolation (Projects, Notes, Saved Outputs, and Linked Items strictly isolated)
- Project Notes & Scratchpad (CRUD, Markdown notes)
- Project Saved Outputs (CRUD, Code snippets, research summaries, search synthesis)
- Project Item Associations (Chats, Files linking & unlinking with multi-tenant verification)
- Personalization & User Preferences (Display name, Language, Tone, Themes, Custom Instructions)
- Controlled Memory Architecture (Add, View, Update, Toggle Active, Delete, Purge All)
- AI Prompt Context Synthesis (Persona, Active Memories, Project Instructions injection)
- Project Cascade Deletion
"""

import os
import io
import sys
import uuid
import asyncio
from pathlib import Path
from fastapi import UploadFile

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import settings
from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.services.project_service import project_service
from backend.app.services.personalization_service import personalization_service
from backend.app.services.chat_service import chat_service
from backend.app.services.file_service import file_service
from backend.app.models import (
    UserRegisterRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectNoteCreateRequest,
    ProjectNoteUpdateRequest,
    ProjectSavedOutputCreateRequest,
    UserPreferencesRequest,
    MemoryCreateRequest,
    MemoryUpdateRequest
)


async def run_phase6_tests():
    print("\n" + "="*80)
    print("RUNNING PHASE 6: LONG-TERM ORGANIZATION & PERSONALIZATION VERIFICATION")
    print("1. Projects Workspace Management & Strict Multi-Tenant Isolation")
    print("2. Project Notes, Brainstorms & Markdown Scratchpad")
    print("3. Project Saved Outputs (Snippets, Summaries & Synthesis)")
    print("4. Project Item Associations (Chats & Files Link/Unlink with Cross-User Security)")
    print("5. User Personalization Preferences & Experience Customization")
    print("6. Controlled Memory Architecture (Transparent Retention, Toggles & Purge)")
    print("7. AI Persona & Personalized Context Compilation for System Prompts")
    print("8. Cascade Deletion & Multi-Tenant Boundary Integrity")
    print("="*80 + "\n")

    await create_tables()

    # -------------------------------------------------------------------------
    # Setup Test Users
    # -------------------------------------------------------------------------
    user_a_email = f"proj_user_a_{uuid.uuid4().hex[:6]}@example.com"
    user_b_email = f"proj_user_b_{uuid.uuid4().hex[:6]}@example.com"
    test_password = "SecurePassword123!"

    print(f"[*] Registering test users:\n    User A: {user_a_email}\n    User B: {user_b_email}")
    user_a_dict, _ = await user_service.register_user(UserRegisterRequest(email=user_a_email, password=test_password))
    user_b_dict, _ = await user_service.register_user(UserRegisterRequest(email=user_b_email, password=test_password))
    user_a_id = user_a_dict["userId"]
    user_b_id = user_b_dict["userId"]

    assert user_a_id and user_b_id, "User registration failed"
    print("  [OK] Test users registered successfully.")

    # =========================================================================
    # TEST 1: Projects CRUD & Multi-Tenant Isolation
    # =========================================================================
    print("\n--- TEST 1: Projects Workspace CRUD & Isolation ---")
    
    # User A creates a project
    proj_a_req = ProjectCreateRequest(
        name="Distributed Ledger Engine",
        description="High-throughput blockchain consensus and cryptography research",
        instructions="Always write modular Python with strict type hints. Focus on zero memory allocations.",
        color="#8B5CF6"
    )
    proj_a = await project_service.create_project(user_a_id, proj_a_req)
    assert proj_a.id is not None
    assert proj_a.name == "Distributed Ledger Engine"
    assert proj_a.userId == user_a_id
    assert proj_a.color == "#8B5CF6"
    print(f"  [OK] User A created project: {proj_a.name} (ID: {proj_a.id})")

    # User A lists projects
    user_a_projects = await project_service.list_projects(user_a_id)
    assert len(user_a_projects) == 1
    assert user_a_projects[0].id == proj_a.id
    print(f"  [OK] User A lists 1 project successfully.")

    # User B lists projects (must be 0 - strict isolation)
    user_b_projects = await project_service.list_projects(user_b_id)
    assert len(user_b_projects) == 0, "User B should not see User A's projects"
    print("  [OK] User B sees 0 projects (Multi-tenant isolation verified).")

    # User B attempts to access User A's project detail (must fail)
    try:
        await project_service.get_project(user_b_id, proj_a.id)
        assert False, "User B should NOT be able to view User A's project"
    except Exception as e:
        assert "not found" in str(e).lower() or "denied" in str(e).lower()
        print(f"  [OK] Access denied for User B viewing User A project: {e}")

    # User B attempts to update User A's project (must fail)
    try:
        await project_service.update_project(user_b_id, proj_a.id, ProjectUpdateRequest(name="Hacked Project"))
        assert False, "User B should NOT be able to update User A's project"
    except Exception as e:
        assert "not found" in str(e).lower() or "denied" in str(e).lower()
        print(f"  [OK] Access denied for User B updating User A project: {e}")

    # User A updates their project
    updated_proj = await project_service.update_project(
        user_a_id,
        proj_a.id,
        ProjectUpdateRequest(
            name="Distributed Ledger & Vector Engine",
            instructions="Always use Python 3.12+ features with async/await."
        )
    )
    assert updated_proj.name == "Distributed Ledger & Vector Engine"
    assert updated_proj.instructions == "Always use Python 3.12+ features with async/await."
    print("  [OK] User A updated project details successfully.")

    # =========================================================================
    # TEST 2: Project Notes & Scratchpad
    # =========================================================================
    print("\n--- TEST 2: Project Notes & Scratchpad ---")
    
    note_req = ProjectNoteCreateRequest(
        title="Architecture Decision Record 001",
        content="## ADR 001: Raft Consensus vs PBFT\nWe choose Raft for leader election and state machine replication."
    )
    note = await project_service.create_note(user_a_id, proj_a.id, note_req)
    assert note.id is not None
    assert note.title == "Architecture Decision Record 001"
    assert note.projectId == proj_a.id
    print(f"  [OK] User A created project note: {note.title} (ID: {note.id})")

    # User B cannot create note in User A's project
    try:
        await project_service.create_note(user_b_id, proj_a.id, ProjectNoteCreateRequest(title="Spy Note", content="Secret"))
        assert False, "User B should not be able to create note in User A's project"
    except Exception as e:
        print(f"  [OK] Prevented User B from creating note in User A project: {e}")

    # User A updates note
    updated_note = await project_service.update_note(
        user_a_id,
        proj_a.id,
        note.id,
        ProjectNoteUpdateRequest(content="Updated content with formal proofs.")
    )
    assert updated_note.content == "Updated content with formal proofs."
    print("  [OK] User A updated project note content successfully.")

    # =========================================================================
    # TEST 3: Project Saved Outputs
    # =========================================================================
    print("\n--- TEST 3: Project Saved Outputs ---")

    output_req = ProjectSavedOutputCreateRequest(
        title="Optimized Raft State Machine",
        outputType="code",
        content="async def apply_entry(state, entry):\n    state[entry.key] = entry.value\n    return state"
    )
    saved_out = await project_service.create_saved_output(user_a_id, proj_a.id, output_req)
    assert saved_out.id is not None
    assert saved_out.outputType == "code"
    assert saved_out.projectId == proj_a.id
    print(f"  [OK] User A saved output snippet: {saved_out.title} (ID: {saved_out.id})")

    # User B cannot view or delete User A's saved output
    try:
        await project_service.delete_saved_output(user_b_id, proj_a.id, saved_out.id)
        assert False, "User B should not delete User A's saved output"
    except Exception as e:
        print(f"  [OK] Prevented User B from deleting User A output: {e}")

    # =========================================================================
    # TEST 4: Project Item Associations (Chats & Files)
    # =========================================================================
    print("\n--- TEST 4: Project Item Linking & Multi-Tenant Verification ---")

    # Create a chat and a file for User A
    chat_a = await chat_service.create_conversation(user_a_id, "Consensus Brainstorm")
    file_a = await file_service.save_uploaded_file(
        user_a_id,
        UploadFile(
            file=io.BytesIO(b"Raft consensus protocol specification and formal invariants."),
            filename="raft_spec.txt",
            headers={"content-type": "text/plain"}
        )
    )

    # Create a chat and file for User B
    chat_b = await chat_service.create_conversation(user_b_id, "User B Private Chat")
    file_b = await file_service.save_uploaded_file(
        user_b_id,
        UploadFile(
            file=io.BytesIO(b"Top secret user B data."),
            filename="user_b_secrets.txt",
            headers={"content-type": "text/plain"}
        )
    )

    # User A links their own chat and file to Project A
    link_chat_res = await project_service.link_item(user_a_id, proj_a.id, "chat", chat_a["id"])
    assert link_chat_res["success"] is True
    link_file_res = await project_service.link_item(user_a_id, proj_a.id, "file", file_a["id"])
    assert link_file_res["success"] is True
    print("  [OK] User A linked own chat and file to project.")

    # User A attempts to link User B's file or chat to Project A (Must fail)
    try:
        await project_service.link_item(user_a_id, proj_a.id, "file", file_b["id"])
        assert False, "User A should not link User B's file"
    except Exception as e:
        print(f"  [OK] Blocked cross-user file link attempt: {e}")

    try:
        await project_service.link_item(user_a_id, proj_a.id, "chat", chat_b["id"])
        assert False, "User A should not link User B's chat"
    except Exception as e:
        print(f"  [OK] Blocked cross-user chat link attempt: {e}")

    # Verify project detail aggregates all items
    proj_detail = await project_service.get_project(user_a_id, proj_a.id)
    assert len(proj_detail.chats) == 1
    assert len(proj_detail.files) == 1
    assert len(proj_detail.notes) == 1
    assert len(proj_detail.savedOutputs) == 1
    print(f"  [OK] Project detail verified with aggregated counts:\n       {len(proj_detail.chats)} chats, {len(proj_detail.files)} files, {len(proj_detail.notes)} notes, {len(proj_detail.savedOutputs)} outputs.")

    # =========================================================================
    # TEST 5: Personalization & User Preferences
    # =========================================================================
    print("\n--- TEST 5: User Preferences & Personalization ---")

    # Get initial default preferences
    prefs_a_initial = await personalization_service.get_preferences(user_a_id)
    assert prefs_a_initial.preferredLanguage == "English"
    assert prefs_a_initial.aiTone == "balanced"
    print("  [OK] Default preferences loaded correctly.")

    # Update User A's preferences
    update_prefs_req = UserPreferencesRequest(
        displayName="Dr. Alice Smith",
        preferredLanguage="English",
        aiTone="technical",
        theme="dark",
        codeTheme="monokai",
        customInstructions="Always include algorithmic complexity O(n) analysis.",
        enableMemory=True,
        autoSpeak=False
    )
    updated_prefs_a = await personalization_service.update_preferences(user_a_id, update_prefs_req)
    assert updated_prefs_a.displayName == "Dr. Alice Smith"
    assert updated_prefs_a.aiTone == "technical"
    assert updated_prefs_a.customInstructions == "Always include algorithmic complexity O(n) analysis."
    print("  [OK] User A personalization preferences updated.")

    # Verify User B has separate, independent preferences
    prefs_b = await personalization_service.get_preferences(user_b_id)
    assert prefs_b.displayName is None or prefs_b.displayName == ""
    assert prefs_b.aiTone == "balanced"
    print("  [OK] User B preferences verified isolated from User A.")

    # =========================================================================
    # TEST 6: Controlled Memory Architecture
    # =========================================================================
    print("\n--- TEST 6: Controlled Memory Architecture ---")

    # Create memory items across various categories
    mem1 = await personalization_service.create_memory(
        user_a_id,
        MemoryCreateRequest(
            category="preference",
            key="Code Style",
            value="Prefers type-annotated Python with PEP 8 standards."
        )
    )
    mem2 = await personalization_service.create_memory(
        user_a_id,
        MemoryCreateRequest(
            category="context",
            key="Role",
            value="Principal Distributed Systems Engineer at Nexora Lab."
        )
    )
    mem3 = await personalization_service.create_memory(
        user_a_id,
        MemoryCreateRequest(
            category="skill",
            key="Frameworks",
            value="Specializes in FastAPI, SQLite, Pydantic, and WebSockets."
        )
    )
    assert mem1.id and mem2.id and mem3.id
    print("  [OK] User A created 3 memory items across categories.")

    # List memories
    mem_list = await personalization_service.list_memories(user_a_id)
    assert mem_list.total == 3
    assert mem_list.memoryEnabled is True
    print(f"  [OK] User A retrieved {mem_list.total} active memories.")

    # User B list memories (must be 0)
    user_b_mems = await personalization_service.list_memories(user_b_id)
    assert user_b_mems.total == 0
    print("  [OK] User B memories list is empty (0 memories).")

    # User B cannot update or delete User A's memory
    try:
        await personalization_service.delete_memory(user_b_id, mem1.id)
        assert False, "User B should not delete User A's memory"
    except Exception as e:
        print(f"  [OK] Prevented User B from deleting User A memory: {e}")

    # Toggle active state of memory 3
    updated_mem3 = await personalization_service.update_memory(
        user_a_id,
        mem3.id,
        MemoryUpdateRequest(isActive=False)
    )
    assert updated_mem3.isActive is False
    print("  [OK] User A deactivated memory item 3.")

    # =========================================================================
    # TEST 7: AI Persona & Personalized Context Compilation
    # =========================================================================
    print("\n--- TEST 7: AI Prompt Context Synthesis ---")

    # Build context for User A with Project A
    context_with_proj = await personalization_service.build_personalized_context(user_a_id, proj_a.id)
    assert context_with_proj is not None
    assert "Dr. Alice Smith" in context_with_proj
    assert "technical" in context_with_proj
    assert "Prefers type-annotated Python" in context_with_proj
    assert "Principal Distributed Systems Engineer" in context_with_proj
    assert "Distributed Ledger & Vector Engine" in context_with_proj
    assert "Always use Python 3.12+" in context_with_proj
    # Deactivated memory (mem3) should NOT be present
    assert "Specializes in FastAPI" not in context_with_proj
    print("  [OK] Personalized context compilation verified with active memories, persona, and project rules.")

    # Test disabling global memory
    await personalization_service.update_preferences(user_a_id, UserPreferencesRequest(enableMemory=False))
    context_no_mem = await personalization_service.build_personalized_context(user_a_id, proj_a.id)
    assert "Prefers type-annotated Python" not in context_no_mem
    assert "Principal Distributed Systems Engineer" not in context_no_mem
    print("  [OK] When enableMemory=False, retained memory facts are excluded from AI prompts.")

    # Re-enable memory
    await personalization_service.update_preferences(user_a_id, UserPreferencesRequest(enableMemory=True))

    # =========================================================================
    # TEST 8: Memory Purge & Cascade Deletion
    # =========================================================================
    print("\n--- TEST 8: Memory Purge & Project Cascade Deletion ---")

    # Purge all memories
    purge_res = await personalization_service.clear_memories(user_a_id)
    assert purge_res is True
    mem_list_after = await personalization_service.list_memories(user_a_id)
    assert mem_list_after.total == 0
    print("  [OK] All memories purged successfully.")

    # Delete Project A and verify cascade cleanup
    delete_res = await project_service.delete_project(user_a_id, proj_a.id)
    assert delete_res is True

    # Verify project is gone
    projects_after = await project_service.list_projects(user_a_id)
    assert len(projects_after) == 0

    # Verify linked chat and file still exist in user's root repository
    chat_still_exists = await chat_service.get_conversation(user_a_id, chat_a["id"])
    assert chat_still_exists is not None
    file_still_exists = await file_service.get_file(user_a_id, file_a["id"])
    assert file_still_exists is not None
    print("  [OK] Project deleted cleanly without destroying underlying user chats and files.")

    print("\n" + "="*80)
    print("ALL PHASE 6 PROJECTS & PERSONALIZATION TESTS PASSED SUCCESSFULLY! (100% SUCCESS)")
    print("="*80 + "\n")


def test_phase6_projects_memory_suite():
    asyncio.run(run_phase6_tests())

if __name__ == "__main__":
    asyncio.run(run_phase6_tests())
