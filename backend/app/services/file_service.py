import os
import io
import csv
import uuid
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException, status
import aiosqlite
import pypdf
import docx
from PIL import Image

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("services.file")

class FileService:
    """Service handling file upload, extraction, security isolation, and AI document/vision intelligence."""

    def __init__(self):
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal and illegal characters."""
        clean = Path(filename).name
        # Remove risky characters
        clean = "".join(c for c in clean if c.isalnum() or c in "._- ")
        return clean.strip() or "unnamed_file"

    def _get_file_type(self, ext: str, mime_type: str) -> str:
        """Categorize file into high-level type: pdf, docx, txt, csv, or image."""
        ext = ext.lower()
        if ext == ".pdf" or "pdf" in mime_type:
            return "pdf"
        elif ext in [".docx", ".doc"] or "word" in mime_type or "officedocument" in mime_type:
            return "docx"
        elif ext == ".csv" or "csv" in mime_type:
            return "csv"
        elif ext == ".txt" or "text/plain" in mime_type:
            return "txt"
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"] or mime_type.startswith("image/"):
            return "image"
        return "other"

    def validate_file(self, filename: str, content_type: Optional[str], file_size: int):
        """Validate file extension, mime type, and file size limits."""
        ext = Path(filename).suffix.lower()
        
        # 1. Extension check
        if ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'. Allowed formats: {allowed}"
            )

        # 2. File size check
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            max_mb = settings.MAX_FILE_SIZE_MB
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_mb} MB."
            )


        # 3. MIME type check (lenient fallback if browser sends generic binary stream)
        norm_mime = (content_type or "application/octet-stream").lower()
        if norm_mime != "application/octet-stream" and norm_mime not in settings.ALLOWED_MIME_TYPES:
            # If extension is valid, allow common text/image types
            if ext not in settings.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Disallowed MIME type '{content_type}' for file '{filename}'."
                )

    def extract_text_and_metadata(self, file_bytes: bytes, file_type: str) -> Tuple[str, int, Dict[str, Any]]:
        """
        Extract readable text and metadata from PDF, DOCX, TXT, CSV, or Image.
        Returns (extracted_text, page_count, metadata_dict).
        """
        extracted_text = ""
        page_count = 0
        metadata: Dict[str, Any] = {}

        try:
            if file_type == "pdf":
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
                pages_text = []
                for idx, page in enumerate(reader.pages):
                    p_txt = page.extract_text() or ""
                    if p_txt.strip():
                        pages_text.append(f"--- [Page {idx + 1}] ---\n{p_txt.strip()}")
                extracted_text = "\n\n".join(pages_text)
                metadata["totalPages"] = page_count

            elif file_type == "docx":
                doc = docx.Document(io.BytesIO(file_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                # Also extract table cells
                table_texts = []
                for table in doc.tables:
                    for row in table.rows:
                        row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                        if row_cells:
                            table_texts.append(" | ".join(row_cells))
                
                full_doc_parts = paragraphs
                if table_texts:
                    full_doc_parts.append("\n--- Tables ---\n" + "\n".join(table_texts))
                
                extracted_text = "\n\n".join(full_doc_parts)
                page_count = max(1, len(paragraphs) // 5)
                metadata["paragraphs"] = len(paragraphs)
                metadata["tables"] = len(doc.tables)

            elif file_type == "csv":
                try:
                    text_str = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text_str = file_bytes.decode("latin-1", errors="replace")

                csv_reader = csv.reader(io.StringIO(text_str))
                rows = list(csv_reader)
                row_count = len(rows)
                col_count = len(rows[0]) if rows else 0
                page_count = 1
                metadata["rows"] = row_count
                metadata["columns"] = col_count

                # Format sample into readable markdown table
                lines = [f"# CSV Data Structure ({row_count} rows, {col_count} columns)"]
                if rows:
                    headers = rows[0]
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    # Sample first 50 rows
                    for r in rows[1:51]:
                        # Pad or trim row
                        padded = r + [""] * (len(headers) - len(r))
                        lines.append("| " + " | ".join(padded[:len(headers)]) + " |")
                    if row_count > 51:
                        lines.append(f"\n*(Showing 50 of {row_count} total records)*")
                extracted_text = "\n".join(lines)

            elif file_type == "txt":
                try:
                    extracted_text = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    extracted_text = file_bytes.decode("latin-1", errors="replace")
                page_count = max(1, len(extracted_text.splitlines()) // 40)
                metadata["lines"] = len(extracted_text.splitlines())

            elif file_type == "image":
                img = Image.open(io.BytesIO(file_bytes))
                w, h = img.size
                page_count = 1
                metadata["width"] = w
                metadata["height"] = h
                metadata["dimensions"] = f"{w}x{h}"
                metadata["format"] = img.format or "IMAGE"
                metadata["mode"] = img.mode
                extracted_text = f"[Image: {img.format or 'IMAGE'}, Resolution: {w}x{h}px, Mode: {img.mode}]"

        except Exception as e:
            logger.error(f"Error extracting content from {file_type}: {e}")
            extracted_text = f"[Extraction note: Could not extract full text: {str(e)}]"

        return extracted_text.strip(), page_count, metadata

    async def save_uploaded_file(
        self,
        user_id: str,
        upload_file: UploadFile
    ) -> Dict[str, Any]:
        """Save uploaded file to disk and record in database with isolation."""
        original_name = upload_file.filename or "uploaded_file"
        file_bytes = await upload_file.read()
        file_size = len(file_bytes)

        # 1. Validation
        self.validate_file(original_name, upload_file.content_type, file_size)

        # 2. Derive file properties
        ext = Path(original_name).suffix.lower()
        file_id = str(uuid.uuid4())
        sanitized_name = self._sanitize_filename(original_name)
        mime_type = upload_file.content_type or "application/octet-stream"
        file_type = self._get_file_type(ext, mime_type)

        # 3. Secure disk storage: data/uploads/<userId>/<file_id>_<name>
        user_storage_dir = settings.UPLOAD_DIR / user_id
        user_storage_dir.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{file_id}_{sanitized_name}"
        storage_path = user_storage_dir / stored_filename

        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        # 4. Extract text and metadata
        extracted_text, page_count, metadata = self.extract_text_and_metadata(file_bytes, file_type)

        # 5. Insert into SQLite
        created_at = datetime.now(timezone.utc).isoformat()
        async with get_db() as db:
            await db.execute("""
            INSERT INTO files (
                id, userId, filename, originalFilename, fileType,
                mimeType, fileSize, storagePath, extractedText,
                summary, pageCount, createdAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                file_id,
                user_id,
                sanitized_name,
                original_name,
                file_type,
                mime_type,
                file_size,
                str(storage_path),
                extracted_text,
                None,
                page_count,
                created_at
            ))
            await db.commit()

        return await self.get_file(user_id, file_id)

    async def get_user_files(
        self,
        user_id: str,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve user files with multi-tenant isolation, optional filtering and search."""
        async with get_db() as db:
            sql = "SELECT * FROM files WHERE userId = ?"
            params: List[Any] = [user_id]

            if file_type and file_type != "all":
                sql += " AND fileType = ?"
                params.append(file_type)

            if query and query.strip():
                sql += " AND (originalFilename LIKE ? OR filename LIKE ? OR extractedText LIKE ?)"
                search_param = f"%{query.strip()}%"
                params.extend([search_param, search_param, search_param])

            sql += " ORDER BY createdAt DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            
            result = []
            for r in rows:
                item = dict(r)
                item["hasExtractedText"] = bool(item.get("extractedText") and len(item["extractedText"]) > 0)
                item["hasSummary"] = bool(item.get("summary"))
                result.append(item)
            return result

    async def get_file(self, user_id: str, file_id: str) -> Dict[str, Any]:
        """Fetch single file metadata and details with strict user isolation."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM files WHERE id = ? AND userId = ?;",
                (file_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found or access denied."
                )
            data = dict(row)
            data["hasExtractedText"] = bool(data.get("extractedText"))
            data["hasSummary"] = bool(data.get("summary"))
            data["downloadUrl"] = f"/api/files/{file_id}/download"
            return data

    async def get_file_disk_path(self, user_id: str, file_id: str) -> Path:
        """Get file Path on disk after verifying ownership."""
        file_data = await self.get_file(user_id, file_id)
        storage_path = Path(file_data["storagePath"])
        if not storage_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Physical file not found on storage."
            )
        return storage_path

    async def delete_file(self, user_id: str, file_id: str) -> bool:
        """Delete file from database and disk storage."""
        file_data = await self.get_file(user_id, file_id)
        
        # Remove from disk
        try:
            p = Path(file_data["storagePath"])
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete physical file {file_data['storagePath']}: {e}")

        # Remove from DB
        async with get_db() as db:
            await db.execute(
                "DELETE FROM files WHERE id = ? AND userId = ?;",
                (file_id, user_id)
            )
            await db.commit()
        return True

    # -------------------------------------------------------------
    # DOCUMENT AI INTELLIGENCE (PDF / DOCX / TXT / CSV)
    # -------------------------------------------------------------

    async def execute_document_ai_action(
        self,
        user_id: str,
        file_id: str,
        action: str,
        query: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute AI Document Intelligence:
        - summarize
        - qa (ask questions)
        - extract (structured information)
        - explain (content simplification)
        - notes (generate study / executive notes)
        - questions (generate practice/review questions)
        """
        file_data = await self.get_file(user_id, file_id)
        doc_text = file_data.get("extractedText") or ""
        doc_name = file_data.get("originalFilename") or file_data.get("filename")

        if not doc_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{doc_name}' contains no readable text content."
            )

        # Truncate text if huge for model context safety (keep first 40,000 chars)
        context_text = doc_text[:40000]
        if len(doc_text) > 40000:
            context_text += f"\n\n... [Note: Document content truncated for analysis. Total length: {len(doc_text)} chars] ..."

        # Construct Action Prompts
        action_instructions = {
            "summarize": (
                f"You are an expert executive document analyst. Provide a comprehensive, structured summary of the document '{doc_name}'.\n\n"
                f"Structure your response with:\n"
                f"1. **Executive Overview**: High-level essence of the document in 2-3 sentences.\n"
                f"2. **Key Takeaways & Core Themes**: Bullet points of the most critical facts and findings.\n"
                f"3. **Detailed Breakdown**: Section-by-section or topic-by-topic synthesis.\n"
                f"4. **Actionable Insights / Next Steps**: What conclusions or actions follow from this document."
            ),
            "qa": (
                f"You are a strict grounded AI research assistant. Answer the user's specific question using ONLY the provided document '{doc_name}'.\n"
                f"User Question: \"{query or 'What are the main insights in this document?'}\"\n\n"
                f"Guidelines:\n"
                f"- Rely directly on the document text.\n"
                f"- Include direct quotes, citations, and page references when available from the text.\n"
                f"- If the document does not contain the answer or sufficient information to answer the question, state clearly: \"I couldn't find that information in the uploaded document.\" Do not hallucinate or make up facts."
            ),
            "extract": (
                f"You are a precision information extraction specialist. Extract and organize all structured information, entities, and data points from the document '{doc_name}'.\n\n"
                f"Extract:\n"
                f"- **Key Entities & Stakeholders** (people, organizations, systems)\n"
                f"- **Dates, Milestones & Timelines**\n"
                f"- **Numerical Figures, Metrics, Pricing & Statistics** (formatted in a clear markdown table)\n"
                f"- **Action Items & Requirements**"
            ),
            "explain": (
                f"You are a master educator. Explain the content of the document '{doc_name}' in clear, accessible, and intuitive terms.\n\n"
                f"User Focus / Term to explain: \"{query or 'General explanation of core concepts'}\"\n\n"
                f"- Break down complex jargon, technical concepts, or legal/financial terms into plain language.\n"
                f"- Use helpful analogies and real-world examples.\n"
                f"- Provide a 'Key Terminology Glossary' at the end."
            ),
            "notes": (
                f"You are an expert note-taking specialist. Generate structured, high-yield study and executive notes from the document '{doc_name}'.\n\n"
                f"Format as:\n"
                f"- **Title & Document Scope**\n"
                f"- **Core Concepts & Definitions** (using callouts and bold terms)\n"
                f"- **Detailed Outline with Nested Highlights**\n"
                f"- **Quick Reference Summary Card**"
            ),
            "questions": (
                f"You are an expert educator. Create a comprehensive review and test question set based on the document '{doc_name}'.\n\n"
                f"Create:\n"
                f"1. **5 Multiple-Choice Questions (MCQ)** with explanations for correct answers.\n"
                f"2. **3 Short-Answer Conceptual Questions** with sample ideal answers.\n"
                f"3. **2 Deep-Dive Discussion Prompts** for critical thinking."
            )
        }

        chosen_instruction = action_instructions.get(action, action_instructions["summarize"])
        sys_prompt = system_prompt or "You are NEXORA AI Document Intelligence Engine, providing accurate, grounded, and insightful document analysis."

        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": f"{chosen_instruction}\n\n================ DOCUMENT CONTENT: {doc_name} ================\n{context_text}\n================ END DOCUMENT CONTENT ================"
            }
        ]

        ai_result, model_used = await ai_manager.generate_response(
            messages=messages,
            model=model,
            system_prompt=sys_prompt
        )

        # If action was summarize, update database record
        if action == "summarize":
            async with get_db() as db:
                await db.execute(
                    "UPDATE files SET summary = ? WHERE id = ? AND userId = ?;",
                    (ai_result, file_id, user_id)
                )
                await db.commit()

        return {
            "fileId": file_id,
            "filename": doc_name,
            "action": action,
            "result": ai_result,
            "model": model_used,
            "query": query
        }

    # -------------------------------------------------------------
    # VISION & MULTIMODAL IMAGE ANALYSIS
    # -------------------------------------------------------------

    async def execute_image_analysis(
        self,
        user_id: str,
        file_id: Optional[str] = None,
        image_base64: Optional[str] = None,
        action: str = "describe",
        query: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute Vision Intelligence on uploaded image or raw base64:
        - describe: detailed scene / visual description
        - screenshot: UI layout analysis, buttons, error messages, code
        - ocr: text extraction and transcription
        - diagram: flowchart / system architecture explanation
        - qa: custom questions about the image
        """
        img_bytes = None
        mime_type = "image/png"
        dimensions_str = "Unknown"
        img_format = "PNG"

        if file_id:
            file_data = await self.get_file(user_id, file_id)
            if file_data["fileType"] != "image":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{file_data['filename']}' is not an image."
                )
            p = Path(file_data["storagePath"])
            if not p.exists():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found on disk.")
            with open(p, "rb") as f:
                img_bytes = f.read()
            mime_type = file_data["mimeType"]
            image_base64 = base64.b64encode(img_bytes).decode("utf-8")
        elif image_base64:
            # Strip data URI header if present (e.g. data:image/png;base64,...)
            if "base64," in image_base64:
                header, raw_b64 = image_base64.split("base64,", 1)
                image_base64 = raw_b64
                if "image/" in header:
                    mime_type = header.split("image/")[1].split(";")[0]
                    mime_type = f"image/{mime_type}"
            try:
                img_bytes = base64.b64decode(image_base64)
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 image data.")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either fileId or imageBase64 must be provided.")

        # Read dimensions with PIL
        try:
            pil_img = Image.open(io.BytesIO(img_bytes))
            w, h = pil_img.size
            dimensions_str = f"{w}x{h}"
            img_format = pil_img.format or "IMAGE"
        except Exception as e:
            logger.warning(f"PIL reading error: {e}")

        # Action instructions
        vision_prompts = {
            "describe": (
                f"Analyze this image ({img_format}, {dimensions_str}) thoroughly.\n"
                f"Provide:\n"
                f"1. **Subject & Visual Overview**: The primary focus and theme.\n"
                f"2. **Detailed Breakdown**: Key elements, background, color palette, lighting, textures, and style.\n"
                f"3. **Contextual & Semantic Interpretation**: What story or meaning is conveyed.\n"
                f"4. **Key Tags / Keywords**."
            ),
            "screenshot": (
                f"Perform a detailed software UI / screenshot breakdown of this image ({dimensions_str}):\n"
                f"1. **Application & Interface Type**: Identify the platform, OS, or application shown.\n"
                f"2. **UI Component Breakdown**: Navigation bars, buttons, input fields, modals, menus.\n"
                f"3. **Errors, Warnings or Code Snippets**: Transcribe any visible error messages, logs, or code lines.\n"
                f"4. **UX / Design Analysis**: Visual hierarchy, readability, and improvement suggestions."
            ),
            "ocr": (
                f"Perform Optical Character Recognition (OCR) and text transcription on this image:\n"
                f"1. **Extracted Text (Verbatim)**: Transcribe all visible text exactly as it appears, preserving lines and hierarchy.\n"
                f"2. **Structured Table/Form Data**: If forms, tables, receipts, or signs are present, format them cleanly in markdown.\n"
                f"3. **Language & Text Quality**: Note any partially occluded or ambiguous text."
            ),
            "diagram": (
                f"Analyze and explain this architecture diagram / flowchart / chart ({dimensions_str}):\n"
                f"1. **Diagram Type & Purpose**: (e.g., Cloud Architecture, ERD, Sequence Diagram, Bar Chart).\n"
                f"2. **Core Components & Entities**: List all nodes, services, databases, or data points.\n"
                f"3. **Data Flow & Relationships**: Trace arrows, connections, and workflows step-by-step.\n"
                f"4. **Key Takeaways & Architecture Insights**."
            ),
            "qa": (
                f"Answer the user's specific question about this image ({dimensions_str}):\n"
                f"User Question: \"{query or 'What is notable in this image?'}\"\n\n"
                f"Ground your answer directly on visual evidence in the image."
            )
        }

        prompt_text = vision_prompts.get(action, vision_prompts["describe"])
        sys_prompt = "You are NEXORA AI Vision Intelligence Engine, providing comprehensive, high-precision visual reasoning, OCR, and diagram analysis."

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt_text}
        ]

        ai_result, model_used = await ai_manager.generate_response(
            messages=messages,
            model=model,
            system_prompt=sys_prompt,
            images=[{"mime_type": mime_type, "data": image_base64, "dimensions": dimensions_str, "format": img_format, "action": action, "query": query}]
        )

        return {
            "fileId": file_id,
            "action": action,
            "result": ai_result,
            "model": model_used,
            "dimensions": dimensions_str,
            "format": img_format
        }

file_service = FileService()
