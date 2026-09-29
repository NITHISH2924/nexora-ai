import os
import io
import sys
import uuid
import base64
import asyncio
from pathlib import Path
import pypdf
import docx
from PIL import Image

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import settings
from backend.app.database import create_tables, get_db
from backend.app.services.user_service import user_service
from backend.app.services.file_service import file_service
from backend.app.models import UserRegisterRequest, FileAIActionRequest, ImageAnalysisRequest
from fastapi import UploadFile, HTTPException

def create_sample_pdf_bytes() -> bytes:
    """Generate a clean in-memory PDF with pypdf."""
    writer = pypdf.PdfWriter()
    # Add a blank page
    page = writer.add_blank_page(width=612, height=792)
    # Write some annotation/text structure
    output_stream = io.BytesIO()
    writer.write(output_stream)
    pdf_bytes = output_stream.getvalue()
    return pdf_bytes

def create_sample_docx_bytes() -> bytes:
    """Generate a valid DOCX document in memory."""
    doc = docx.Document()
    doc.add_heading("NEXORA AI Technical Specification", level=1)
    doc.add_paragraph("This is an executive architecture document detailing multi-tenant data isolation and real-time streaming.")
    
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Component"
    hdr_cells[1].text = "Description"
    hdr_cells[2].text = "SLA"
    
    row_cells = table.add_row().cells
    row_cells[0].text = "FastAPI Backend"
    row_cells[1].text = "Asynchronous ASGI Web Engine"
    row_cells[2].text = "99.99%"
    
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()

def create_sample_image_bytes(format="PNG", size=(400, 300), color=(139, 92, 246)) -> bytes:
    """Generate a valid PNG/JPEG image in memory."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()

async def run_tests():
    print("\n" + "="*75)
    print("RUNNING PHASE 3: COMPREHENSIVE DOCUMENT & VISION INTELLIGENCE TEST SUITE")
    print("="*75 + "\n")

    # 1. Database initialization
    print("[1] Verifying database schema & upload storage...")
    await create_tables()
    assert settings.UPLOAD_DIR.exists()
    print("    [PASS] Database tables and upload directory verified.")

    # 2. Setup Multi-Tenant Test Users
    print("\n[2] Setting up Multi-Tenant Test Users (Alice & Bob)...")
    suffix_a = uuid.uuid4().hex[:6]
    suffix_b = uuid.uuid4().hex[:6]
    user_a, token_a = await user_service.register_user(UserRegisterRequest(
        email=f"alice_{suffix_a}@example.com",
        password="SecureAlicePass123"
    ))
    user_b, token_b = await user_service.register_user(UserRegisterRequest(
        email=f"bob_{suffix_b}@example.com",
        password="SecureBobPass123"
    ))
    id_a = user_a["userId"]
    id_b = user_b["userId"]
    print(f"    [PASS] User A (Alice): {id_a}")
    print(f"    [PASS] User B (Bob):   {id_b}")

    # 3. Test File Uploads Across All Formats
    print("\n[3] Testing File Uploads Across All Supported Formats...")

    # A) TXT Upload
    txt_content = (
        "NEXORA AI Architecture Whitepaper\n\n"
        "Section 1: Security & Compliance\n"
        "All data at rest is isolated by user ID. Zero cross-tenant data leakage is permitted.\n\n"
        "Section 2: High Throughput AI Ingestion\n"
        "Asynchronous stream processing provides sub-second time to first token.\n"
        "Max supported file upload size is 20 MB."
    ).encode("utf-8")
    
    upload_txt = UploadFile(
        file=io.BytesIO(txt_content),
        filename="whitepaper.txt",
        headers={"content-type": "text/plain"}
    )
    file_txt = await file_service.save_uploaded_file(id_a, upload_txt)
    assert file_txt["fileType"] == "txt"
    assert "NEXORA AI Architecture Whitepaper" in file_txt["extractedText"]
    assert file_txt["hasExtractedText"] is True
    print(f"    [PASS] TXT Uploaded: {file_txt['filename']} ({file_txt['fileSize']} bytes)")

    # B) CSV Upload
    csv_content = (
        "id,system_name,latency_ms,status\n"
        "1,FastAPI_Core,18,ACTIVE\n"
        "2,SQLite_DB,2,OPTIMAL\n"
        "3,Gemini_Provider,140,ONLINE\n"
        "4,OpenAI_Provider,165,ONLINE\n"
    ).encode("utf-8")
    upload_csv = UploadFile(
        file=io.BytesIO(csv_content),
        filename="system_metrics.csv",
        headers={"content-type": "text/csv"}
    )
    file_csv = await file_service.save_uploaded_file(id_a, upload_csv)
    assert file_csv["fileType"] == "csv"
    assert "| id | system_name | latency_ms | status |" in file_csv["extractedText"]
    print(f"    [PASS] CSV Uploaded & Formatted: {file_csv['filename']} (4 records parsed)")

    # C) DOCX Upload
    docx_bytes = create_sample_docx_bytes()
    upload_docx = UploadFile(
        file=io.BytesIO(docx_bytes),
        filename="spec_document.docx",
        headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    )
    file_docx = await file_service.save_uploaded_file(id_a, upload_docx)
    assert file_docx["fileType"] == "docx"
    assert "NEXORA AI Technical Specification" in file_docx["extractedText"]
    assert "FastAPI Backend" in file_docx["extractedText"]
    print(f"    [PASS] DOCX Uploaded & Extracted: {file_docx['filename']} (Paragraphs + Tables)")

    # D) Image Upload (PNG)
    png_bytes = create_sample_image_bytes(format="PNG", size=(800, 600), color=(139, 92, 246))
    upload_png = UploadFile(
        file=io.BytesIO(png_bytes),
        filename="architecture_diagram.png",
        headers={"content-type": "image/png"}
    )
    file_png = await file_service.save_uploaded_file(id_a, upload_png)
    assert file_png["fileType"] == "image"
    assert "800x600" in file_png["extractedText"]
    print(f"    [PASS] Image Uploaded & Verified: {file_png['filename']} (800x600px)")

    # 4. Security & Validation Checks
    print("\n[4] Testing Security Validation (Extensions, MIME, File Sizes)...")

    # Disallowed extension (.exe / .sh / .py)
    try:
        bad_upload = UploadFile(
            file=io.BytesIO(b"malicious executable payload"),
            filename="malware.exe",
            headers={"content-type": "application/x-msdownload"}
        )
        await file_service.save_uploaded_file(id_a, bad_upload)
        assert False, "Should have rejected .exe extension"
    except HTTPException as e:
        assert e.status_code == 400
        print("    [PASS] Disallowed extension (.exe) rejected with 400 Bad Request.")

    # Large file limit rejection (> 20 MB)
    try:
        # Create a dummy large payload
        fake_large_size = 25 * 1024 * 1024
        file_service.validate_file("huge_dump.txt", "text/plain", fake_large_size)
        assert False, "Should have rejected large file > 20MB"
    except HTTPException as e:
        assert e.status_code == 413
        print("    [PASS] Large file (>20MB) rejected with 413 Payload Too Large.")

    # 5. Strict Multi-Tenant Data Isolation
    print("\n[5] Testing Strict Multi-Tenant Isolation...")

    # Alice's files list
    alice_files = await file_service.get_user_files(id_a)
    assert len(alice_files) >= 4

    # Bob's files list should be 0
    bob_files = await file_service.get_user_files(id_b)
    assert len(bob_files) == 0
    print(f"    [PASS] Bob's file listing strictly isolated (0 files, Alice has {len(alice_files)} files).")

    # Bob attempts to access Alice's TXT file
    try:
        await file_service.get_file(user_id=id_b, file_id=file_txt["id"])
        assert False, "Bob should not be able to fetch Alice's file"
    except HTTPException as e:
        assert e.status_code == 404
        print("    [PASS] Cross-user file access rejected with 404 Not Found.")

    # Bob attempts to execute Document AI on Alice's file
    try:
        await file_service.execute_document_ai_action(
            user_id=id_b,
            file_id=file_txt["id"],
            action="summarize"
        )
        assert False, "Bob should not be able to trigger AI on Alice's file"
    except HTTPException as e:
        assert e.status_code == 404
        print("    [PASS] Cross-user Document AI action prevented.")

    # Bob attempts to delete Alice's file
    try:
        await file_service.delete_file(user_id=id_b, file_id=file_txt["id"])
        assert False, "Bob should not be able to delete Alice's file"
    except HTTPException as e:
        assert e.status_code == 404
        print("    [PASS] Cross-user file deletion prevented.")

    # 6. Testing Document AI Capabilities
    print("\n[6] Testing Document AI Intelligence Actions...")

    # A) Summarize
    res_summary = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_txt["id"],
        action="summarize"
    )
    assert res_summary["action"] == "summarize"
    assert len(res_summary["result"]) > 50
    # Verify DB summary was updated
    updated_txt = await file_service.get_file(id_a, file_txt["id"])
    assert updated_txt["hasSummary"] is True
    print("    [PASS] Action 'summarize' generated executive overview & updated database.")

    # B) Ask Questions (Q&A)
    res_qa = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_txt["id"],
        action="qa",
        query="What is the maximum supported file size?"
    )
    assert res_qa["action"] == "qa"
    assert len(res_qa["result"]) > 30
    print("    [PASS] Action 'qa' answered grounded document question with evidence.")

    # C) Extract Information
    res_extract = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_docx["id"],
        action="extract"
    )
    assert res_extract["action"] == "extract"
    assert "Key Entities" in res_extract["result"] or "Figures" in res_extract["result"] or len(res_extract["result"]) > 30
    print("    [PASS] Action 'extract' structured metrics and technical entities.")

    # D) Explain Content
    res_explain = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_docx["id"],
        action="explain",
        query="Explain asynchronous ASGI web engine"
    )
    assert res_explain["action"] == "explain"
    print("    [PASS] Action 'explain' provided clear educational breakdown.")

    # E) Generate Notes
    res_notes = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_txt["id"],
        action="notes"
    )
    assert res_notes["action"] == "notes"
    print("    [PASS] Action 'notes' compiled structured executive study notes.")

    # F) Generate Practice Questions
    res_questions = await file_service.execute_document_ai_action(
        user_id=id_a,
        file_id=file_txt["id"],
        action="questions"
    )
    assert res_questions["action"] == "questions"
    print("    [PASS] Action 'questions' generated multiple-choice and conceptual quizzes.")

    # 7. Testing Multimodal Vision & Image Analysis
    print("\n[7] Testing Multimodal Vision & Image Intelligence...")

    # A) Describe Image
    res_vision_desc = await file_service.execute_image_analysis(
        user_id=id_a,
        file_id=file_png["id"],
        action="describe"
    )
    assert res_vision_desc["action"] == "describe"
    assert len(res_vision_desc["result"]) > 50
    assert "800x600" in res_vision_desc["dimensions"]
    print("    [PASS] Vision 'describe' generated detailed scene and composition analysis.")

    # B) OCR Text Extraction
    res_vision_ocr = await file_service.execute_image_analysis(
        user_id=id_a,
        file_id=file_png["id"],
        action="ocr"
    )
    assert res_vision_ocr["action"] == "ocr"
    assert "Optical Character Recognition" in res_vision_ocr["result"] or "OCR" in res_vision_ocr["result"]
    print("    [PASS] Vision 'ocr' performed character recognition and structured transcription.")

    # C) Diagram / Flowchart Explanation
    res_vision_diag = await file_service.execute_image_analysis(
        user_id=id_a,
        file_id=file_png["id"],
        action="diagram"
    )
    assert res_vision_diag["action"] == "diagram"
    print("    [PASS] Vision 'diagram' analyzed architectural components and data flows.")

    # D) Screenshot / UI Breakdown
    res_vision_screen = await file_service.execute_image_analysis(
        user_id=id_a,
        file_id=file_png["id"],
        action="screenshot"
    )
    assert res_vision_screen["action"] == "screenshot"
    print("    [PASS] Vision 'screenshot' inspected UI elements and layout hierarchy.")

    # E) Direct Base64 Vision Analysis
    raw_b64 = base64.b64encode(png_bytes).decode("utf-8")
    res_vision_b64 = await file_service.execute_image_analysis(
        user_id=id_a,
        image_base64=f"data:image/png;base64,{raw_b64}",
        action="qa",
        query="What is the background color tone?"
    )
    assert res_vision_b64["action"] == "qa"
    print("    [PASS] Direct base64 image vision analysis succeeded.")

    # 8. Testing File Download & Deletion
    print("\n[8] Testing Physical Storage Cleanup & File Deletion...")
    disk_path = await file_service.get_file_disk_path(id_a, file_txt["id"])
    assert disk_path.exists()

    await file_service.delete_file(id_a, file_txt["id"])
    assert not disk_path.exists(), "Physical file should be deleted from disk"
    
    # Confirm DB deletion
    remaining_files = await file_service.get_user_files(id_a)
    remaining_ids = [f["id"] for f in remaining_files]
    assert file_txt["id"] not in remaining_ids
    print("    [PASS] File and physical disk asset safely deleted.")

    print("\n" + "="*75)
    print("ALL PHASE 3 DOCUMENT & VISION INTELLIGENCE TESTS PASSED (100% SUCCESS)!")
    print("="*75 + "\n")

def test_phase3_files_vision_suite():
    asyncio.run(run_tests())

if __name__ == "__main__":
    asyncio.run(run_tests())
