import asyncio
import uuid
import sys
from pathlib import Path
import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.services.chat_service import chat_service
from backend.app.services.ai_providers.manager import ai_manager
from backend.app.models import UserRegisterRequest, ChatMessageRequest
from backend.app.main import app

async def run_phase2_tests():
    print("\n" + "="*75)
    print("RUNNING PHASE 2 COMPREHENSIVE AI CHAT & WORKSPACE TEST SUITE")
    print("="*75 + "\n")

    # 1. Initialize Tables
    print("[1] Ensuring Database Tables & Indexes...")
    await create_tables()
    print("    [PASS] Tables initialized (users, audit_logs, conversations, messages).")

    # 2. Test AI Provider Manager
    print("\n[2] Testing AI Provider Layer & Fallback Engine...")
    models = ai_manager.list_models()
    assert len(models) >= 5, f"Expected at least 5 models, got {len(models)}"
    model_ids = [m["id"] for m in models]
    assert "gemini-1.5-flash" in model_ids
    assert "gpt-4o" in model_ids
    assert "nexora-core-v2" in model_ids
    print(f"    [PASS] {len(models)} models registered across providers.")

    # Test non-streaming generation
    test_msgs = [{"role": "user", "content": "Explain async await in Python"}]
    res_text, model_used = await ai_manager.generate_response(test_msgs, model="nexora-core-v2")
    assert len(res_text) > 20
    assert "def " in res_text or "async" in res_text or "Python" in res_text
    print(f"    [PASS] AI Generation succeeded using [{model_used}]: {len(res_text)} characters.")

    # Test streaming generation
    stream_chunks = []
    async for chunk in ai_manager.stream_response(test_msgs, model="nexora-core-v2"):
        stream_chunks.append(chunk)
    streamed_full = "".join(stream_chunks)
    assert len(stream_chunks) > 5
    assert len(streamed_full) > 20
    print(f"    [PASS] AI Streaming generated {len(stream_chunks)} chunks ({len(streamed_full)} chars).")

    # 3. Create Two Test Users for Multi-Tenant Isolation Testing
    print("\n[3] Setting Up Multi-Tenant Test Users...")
    u1_email = f"alice_{uuid.uuid4().hex[:6]}@example.com"
    u2_email = f"bob_{uuid.uuid4().hex[:6]}@example.com"
    
    user1, token1 = await user_service.register_user(UserRegisterRequest(email=u1_email, password="AliceSecurePass123"))
    user2, token2 = await user_service.register_user(UserRegisterRequest(email=u2_email, password="BobSecurePass123"))
    u1_id = user1["userId"]
    u2_id = user2["userId"]
    print(f"    [PASS] User 1 (Alice): {u1_id}")
    print(f"    [PASS] User 2 (Bob):   {u2_id}")

    # 4. Test Conversation Creation & Title Generation
    print("\n[4] Testing Conversation Creation...")
    conv1 = await chat_service.create_conversation(
        user_id=u1_id,
        title="New Chat",
        model="gemini-1.5-flash"
    )
    assert conv1["id"] is not None
    assert conv1["userId"] == u1_id
    assert conv1["title"] == "New Chat"
    conv1_id = conv1["id"]
    print(f"    [PASS] Conversation created with ID: {conv1_id}")

    # 5. Test Adding Messages & Auto-Title Generation
    print("\n[5] Testing User & Assistant Messages...")
    # Add first user message
    user_msg1 = await chat_service.add_message(
        user_id=u1_id,
        conversation_id=conv1_id,
        role="user",
        content="How do I build a scalable microservices architecture with FastAPI and Docker?"
    )
    assert user_msg1["id"] is not None
    assert user_msg1["role"] == "user"

    # Check that title was automatically updated from prompt
    refreshed_conv = await chat_service.get_conversation(u1_id, conv1_id)
    assert refreshed_conv["title"] != "New Chat"
    assert "FastAPI" in refreshed_conv["title"] or "microservices" in refreshed_conv["title"] or "How" in refreshed_conv["title"]
    print(f"    [PASS] Auto-generated title: '{refreshed_conv['title']}'")

    # Add assistant response
    asst_msg1 = await chat_service.add_message(
        user_id=u1_id,
        conversation_id=conv1_id,
        role="assistant",
        content="Here is a high-level overview of microservices with FastAPI:\n\n```python\n# Gateway\n```",
        model="gemini-1.5-flash"
    )
    assert asst_msg1["role"] == "assistant"

    # Add second turn
    user_msg2 = await chat_service.add_message(
        user_id=u1_id,
        conversation_id=conv1_id,
        role="user",
        content="Can you add database connection pooling?"
    )
    asst_msg2 = await chat_service.add_message(
        user_id=u1_id,
        conversation_id=conv1_id,
        role="assistant",
        content="Yes, using SQLAlchemy or aiosqlite connection pools.",
        model="gemini-1.5-flash"
    )

    conv_full = await chat_service.get_conversation(u1_id, conv1_id)
    assert len(conv_full["messages"]) == 4
    print(f"    [PASS] Conversation contains {len(conv_full['messages'])} messages across 2 turns.")

    # 6. Test Multi-Tenant Isolation (Bob cannot access Alice's conversation)
    print("\n[6] Testing Multi-Tenant Data Isolation...")
    # Bob attempts to get Alice's conversation
    try:
        await chat_service.get_conversation(u2_id, conv1_id)
        assert False, "Bob should not be able to read Alice's conversation"
    except Exception as e:
        assert hasattr(e, "status_code") and e.status_code == 404
        print("    [PASS] Cross-user conversation access rejected with 404 Not Found.")

    # Bob's conversation list should be empty
    bob_convs = await chat_service.get_user_conversations(u2_id)
    assert len(bob_convs) == 0
    print("    [PASS] Bob's conversation list is strictly isolated (0 conversations).")

    # Bob attempts to add message to Alice's conversation
    try:
        await chat_service.add_message(u2_id, conv1_id, "user", "I am hijacking this chat")
        assert False, "Bob should not be able to write to Alice's conversation"
    except Exception as e:
        assert hasattr(e, "status_code") and e.status_code == 404
        print("    [PASS] Cross-user message injection prevented.")

    # Bob attempts to delete Alice's conversation
    try:
        await chat_service.delete_conversation(u2_id, conv1_id)
        assert False, "Bob should not be able to delete Alice's conversation"
    except Exception as e:
        assert hasattr(e, "status_code") and e.status_code == 404
        print("    [PASS] Cross-user deletion prevented.")

    # 7. Test Message Editing and Cascade Truncation
    print("\n[7] Testing Message Editing & Branch Truncation...")
    # Alice edits message 1 -> messages 2, 3, 4 should be truncated
    updated_thread = await chat_service.edit_message_and_truncate(
        user_id=u1_id,
        conversation_id=conv1_id,
        message_id=user_msg1["id"],
        new_content="Explain REST vs GraphQL APIs"
    )
    assert len(updated_thread["messages"]) == 1
    assert updated_thread["messages"][0]["content"] == "Explain REST vs GraphQL APIs"
    print("    [PASS] Edited message successfully truncated trailing messages for clean regeneration.")

    # 8. Test Regeneration Preparation
    print("\n[8] Testing Regeneration Context Preparation...")
    # Add assistant message to edit point
    await chat_service.add_message(u1_id, conv1_id, "assistant", "REST is resource-oriented, GraphQL is query-oriented.")
    conv_before_regen = await chat_service.get_conversation(u1_id, conv1_id)
    assert len(conv_before_regen["messages"]) == 2

    # Call regenerate context helper
    regen_context = await chat_service.prepare_context_and_regenerate(u1_id, conv1_id)
    assert len(regen_context) == 1
    assert regen_context[0]["role"] == "user"
    print("    [PASS] Last assistant response deleted and context prepared for fresh streaming.")

    # 9. Test Conversation Renaming & Pinning
    print("\n[9] Testing Conversation Rename & Pinning...")
    renamed = await chat_service.update_conversation(
        user_id=u1_id,
        conversation_id=conv1_id,
        title="REST & GraphQL Comparison",
        is_pinned=True
    )
    assert renamed["title"] == "REST & GraphQL Comparison"
    assert renamed["isPinned"] is True
    print(f"    [PASS] Conversation renamed to '{renamed['title']}' and pinned.")

    # 10. Test Conversation Search
    print("\n[10] Testing Conversation Search...")
    search_res = await chat_service.get_user_conversations(u1_id, query="GraphQL")
    assert len(search_res) == 1
    assert search_res[0]["id"] == conv1_id
    print(f"    [PASS] Conversation found via search query 'GraphQL'.")

    # 11. Test Full HTTP API Flow with Async Client (including SSE streaming)
    print("\n[11] Testing End-to-End HTTP API & SSE Streaming Endpoint...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Auth header
        headers = {"Authorization": f"Bearer {token1}"}

        # 11.1 List Models
        res_models = await client.get("/api/chat/models", headers=headers)
        assert res_models.status_code == 200
        assert "models" in res_models.json()
        print("    [PASS] HTTP GET /api/chat/models -> 200 OK")

        # 11.2 Create Conversation via API
        res_conv = await client.post("/api/chat/conversations", headers=headers, json={"title": "HTTP Test Chat", "model": "nexora-core-v2"})
        assert res_conv.status_code == 200
        http_conv_id = res_conv.json()["id"]
        print(f"    [PASS] HTTP POST /api/chat/conversations -> 200 OK (ID: {http_conv_id})")

        # 11.3 Test Non-Streaming Message
        res_msg = await client.post(
            f"/api/chat/conversations/{http_conv_id}/messages",
            headers=headers,
            json={"content": "Hello NEXORA AI assistant", "model": "nexora-core-v2"}
        )
        assert res_msg.status_code == 200
        data_msg = res_msg.json()
        assert "userMessage" in data_msg
        assert "assistantMessage" in data_msg
        assert len(data_msg["assistantMessage"]["content"]) > 10
        print(f"    [PASS] HTTP POST /api/chat/conversations/{http_conv_id}/messages -> 200 OK")

        # 11.4 Test SSE Streaming Message
        events_received = []
        async with client.stream(
            "POST",
            f"/api/chat/conversations/{http_conv_id}/stream",
            headers=headers,
            json={"content": "Generate a Python hello world script", "model": "nexora-core-v2"}
        ) as stream_resp:
            assert stream_resp.status_code == 200
            assert "text/event-stream" in stream_resp.headers.get("content-type", "")

            async for line in stream_resp.aiter_lines():
                if line.startswith("event: "):
                    events_received.append(line[7:])
        
        assert "delta" in events_received
        assert "done" in events_received
        print(f"    [PASS] HTTP POST /api/chat/conversations/{http_conv_id}/stream -> SSE stream complete (received {len(events_received)} events).")

        # 11.5 Test SSE Stream Regeneration
        regen_events = []
        async with client.stream(
            "POST",
            f"/api/chat/conversations/{http_conv_id}/regenerate",
            headers=headers,
            json={"content": "regenerate", "model": "nexora-core-v2"}
        ) as regen_resp:
            assert regen_resp.status_code == 200
            async for line in regen_resp.aiter_lines():
                if line.startswith("event: "):
                    regen_events.append(line[7:])

        assert "delta" in regen_events
        assert "done" in regen_events
        print("    [PASS] HTTP POST /api/chat/conversations/{id}/regenerate -> SSE regeneration stream complete.")

        # 11.6 Delete Conversation via HTTP
        del_res = await client.delete(f"/api/chat/conversations/{http_conv_id}", headers=headers)
        assert del_res.status_code == 200
        print("    [PASS] HTTP DELETE /api/chat/conversations/{id} -> 200 OK")

    # 12. Test Conversation Deletion
    print("\n[12] Testing Database Conversation Deletion...")
    await chat_service.delete_conversation(u1_id, conv1_id)
    u1_convs = await chat_service.get_user_conversations(u1_id)
    assert not any(c["id"] == conv1_id for c in u1_convs)
    print("    [PASS] Conversation and all related messages deleted from SQLite.")

    print("\n" + "="*75)
    print("ALL PHASE 2 AI CHAT & WORKSPACE TESTS PASSED (100% SUCCESS)!")
    print("="*75 + "\n")

def test_phase2_chat_suite():
    asyncio.run(run_phase2_tests())

if __name__ == "__main__":
    asyncio.run(run_phase2_tests())
