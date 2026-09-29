import os
import re
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any, Optional, Dict, List
import aiosqlite

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from backend.app.config import settings

logger = logging.getLogger("database")

# Canonical camelCase mapping for case-insensitive column lookups in PostgreSQL
CAMEL_KEY_MAP = {
    "userid": "userId",
    "passwordhash": "passwordHash",
    "accountcreatedat": "accountCreatedAt",
    "lastloginat": "lastLoginAt",
    "logincount": "loginCount",
    "accountstatus": "accountStatus",
    "emailverified": "emailVerified",
    "emailverificationtoken": "emailVerificationToken",
    "emailverificationtokenexpires": "emailVerificationTokenExpires",
    "passwordresettoken": "passwordResetToken",
    "passwordresettokenexpires": "passwordResetTokenExpires",
    "conversationid": "conversationId",
    "systemprompt": "systemPrompt",
    "createdat": "createdAt",
    "updatedat": "updatedAt",
    "ispinned": "isPinned",
    "isarchived": "isArchived",
    "originalfilename": "originalFilename",
    "filetype": "fileType",
    "mimetype": "mimeType",
    "filesize": "fileSize",
    "storagepath": "storagePath",
    "extractedtext": "extractedText",
    "pagecount": "pageCount",
    "negativeprompt": "negativePrompt",
    "aspectratio": "aspectRatio",
    "imagepath": "imagePath",
    "imageurl": "imageUrl",
    "projectid": "projectId",
    "outputtype": "outputType",
    "itemtype": "itemType",
    "itemid": "itemId",
    "displayname": "displayName",
    "preferredlanguage": "preferredLanguage",
    "aitone": "aiTone",
    "custominstructions": "customInstructions",
    "autospeakaudio": "autoSpeakAudio",
    "codetheme": "codeTheme",
    "enablememory": "enableMemory",
    "isactive": "isActive",
    "ipaddress": "ipAddress",
    "useragent": "userAgent",
}

class CaseInsensitiveRow(dict):
    """
    Dictionary subclass providing case-insensitive key access and automatic
    normalization to canonical camelCase keys expected by NEXORA AI services.
    """
    def __init__(self, data=None, **kwargs):
        self._key_map = {}
        super().__init__()
        if data:
            if isinstance(data, dict):
                for k, v in data.items():
                    norm_k = CAMEL_KEY_MAP.get(str(k).lower(), k)
                    self[norm_k] = v
            else:
                for k, v in data:
                    norm_k = CAMEL_KEY_MAP.get(str(k).lower(), k)
                    self[norm_k] = v
        for k, v in kwargs.items():
            norm_k = CAMEL_KEY_MAP.get(str(k).lower(), k)
            self[norm_k] = v

    def __setitem__(self, key, value):
        norm_k = CAMEL_KEY_MAP.get(str(key).lower(), key) if hasattr(self, '_key_map') else key
        super().__setitem__(norm_k, value)
        if hasattr(self, '_key_map'):
            self._key_map[str(key).lower()] = norm_k
            self._key_map[str(norm_k).lower()] = norm_k

    def __getitem__(self, key):
        if super().__contains__(key):
            return super().__getitem__(key)
        lower_k = str(key).lower()
        if hasattr(self, '_key_map') and lower_k in self._key_map:
            return super().__getitem__(self._key_map[lower_k])
        for actual_k in self.keys():
            if str(actual_k).lower() == lower_k:
                return super().__getitem__(actual_k)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        return str(key).lower() in (str(k).lower() for k in self.keys())

def is_postgres() -> bool:
    """Check if DATABASE_URL is configured for PostgreSQL."""
    url = (getattr(settings, "DATABASE_URL", "") or "").strip()
    return url.startswith("postgres://") or url.startswith("postgresql://")

def get_normalized_pg_url() -> str:
    """Normalize postgres:// to postgresql:// for standard drivers."""
    url = (getattr(settings, "DATABASE_URL", "") or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url

def init_db_sync():
    """Ensure database directory and upload storage paths exist."""
    try:
        settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

class PgCursorWrapper:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def description(self):
        return getattr(self._cursor, "description", None)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)

    async def fetchone(self) -> Optional[CaseInsensitiveRow]:
        row = await self._cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return CaseInsensitiveRow(row)
        try:
            return CaseInsensitiveRow(dict(row))
        except Exception:
            cols = [desc[0] for desc in self._cursor.description]
            return CaseInsensitiveRow(dict(zip(cols, row)))

    async def fetchall(self) -> List[CaseInsensitiveRow]:
        rows = await self._cursor.fetchall()
        if not rows:
            return []
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(CaseInsensitiveRow(r))
            else:
                try:
                    result.append(CaseInsensitiveRow(dict(r)))
                except Exception:
                    cols = [desc[0] for desc in self._cursor.description]
                    result.append(CaseInsensitiveRow(dict(zip(cols, r))))
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class DummyCursor:
    async def fetchone(self): return None
    async def fetchall(self): return []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    @property
    def description(self): return None
    @property
    def rowcount(self): return 0
    @property
    def lastrowid(self): return None

class PgExecuteContextManager:
    """
    Dual-purpose executor supporting BOTH:
      1. `cursor = await db.execute(sql, params)`
      2. `async with db.execute(sql, params) as cursor:`
    """
    def __init__(self, conn, sql: str, params: Any = None):
        self._conn = conn
        self._sql = sql
        self._params = params
        self._cursor_wrapper = None

    async def _execute(self) -> PgCursorWrapper:
        if self._cursor_wrapper is None:
            clean_sql = self._conn._convert_sql(self._sql)
            if clean_sql.strip().upper().startswith("PRAGMA"):
                self._cursor_wrapper = DummyCursor()
                return self._cursor_wrapper

            cur = self._conn._conn.cursor()
            if self._params is not None:
                if isinstance(self._params, (list, tuple)):
                    await cur.execute(clean_sql, self._params)
                elif isinstance(self._params, dict):
                    await cur.execute(clean_sql, self._params)
                else:
                    await cur.execute(clean_sql, (self._params,))
            else:
                await cur.execute(clean_sql)
            self._cursor_wrapper = PgCursorWrapper(cur)
        return self._cursor_wrapper

    def __await__(self):
        return self._execute().__await__()

    async def __aenter__(self) -> PgCursorWrapper:
        return await self._execute()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class PgConnectionWrapper:
    """Unified wrapper around PostgreSQL connection to match aiosqlite interface."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def _convert_sql(self, sql: str) -> str:
        """Convert SQLite-style '?' placeholders and PRAGMAs to PostgreSQL syntax."""
        # Convert ? to %s for psycopg
        converted = re.sub(r'\?', '%s', sql)
        # Remove SQLite specific collation
        converted = re.sub(r'COLLATE\s+NOCASE', '', converted, flags=re.IGNORECASE)
        # Convert AUTOINCREMENT to SERIAL syntax in create statements if present
        converted = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', converted, flags=re.IGNORECASE)
        return converted

    def execute(self, sql: str, params: Any = None) -> PgExecuteContextManager:
        return PgExecuteContextManager(self, sql, params)

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()

    async def close(self):
        await self._conn.close()

@asynccontextmanager
async def get_db() -> AsyncGenerator[Any, None]:
    """
    Unified async database connection manager.
    Automatically connects to PostgreSQL if DATABASE_URL is provided,
    otherwise falls back cleanly to local aiosqlite.
    """
    init_db_sync()

    if is_postgres():
        if psycopg is None:
            raise RuntimeError("PostgreSQL driver 'psycopg' is not installed. Please install 'psycopg[binary]'.")
        conn_str = get_normalized_pg_url()
        raw_conn = await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row)
        wrapped = PgConnectionWrapper(raw_conn)
        try:
            yield wrapped
        finally:
            await wrapped.close()
    else:
        db = await aiosqlite.connect(settings.DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        try:
            yield db
        finally:
            await db.close()

async def create_tables():
    """Create database tables, indexes, and constraints if they do not exist."""
    init_db_sync()
    async with get_db() as db:
        if is_postgres():
            # PostgreSQL Schema
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                userId TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                passwordHash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'USER' CHECK(role IN ('USER', 'OWNER', 'CEO', 'ADMIN')),
                accountCreatedAt TEXT NOT NULL,
                lastLoginAt TEXT,
                loginCount INTEGER NOT NULL DEFAULT 0,
                accountStatus TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(accountStatus IN ('ACTIVE', 'PENDING_VERIFICATION', 'SUSPENDED')),
                emailVerified INTEGER NOT NULL DEFAULT 0,
                emailVerificationToken TEXT,
                emailVerificationTokenExpires TEXT,
                passwordResetToken TEXT,
                passwordResetTokenExpires TEXT
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                userId TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ipAddress TEXT,
                userAgent TEXT,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_userId ON audit_logs(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'gemini-1.5-flash',
                systemPrompt TEXT,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                isPinned INTEGER NOT NULL DEFAULT 0,
                isArchived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_userId ON conversations(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_updatedAt ON conversations(updatedAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversationId TEXT NOT NULL,
                userId TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                model TEXT,
                tokens INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (conversationId) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_convId ON messages(conversationId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_userId ON messages(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_createdAt ON messages(createdAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                filename TEXT NOT NULL,
                originalFilename TEXT NOT NULL,
                fileType TEXT NOT NULL,
                mimeType TEXT NOT NULL,
                fileSize INTEGER NOT NULL,
                storagePath TEXT NOT NULL,
                extractedText TEXT,
                summary TEXT,
                pageCount INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_userId ON files(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_createdAt ON files(createdAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS generated_images (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                prompt TEXT NOT NULL,
                negativePrompt TEXT,
                model TEXT NOT NULL DEFAULT 'dall-e-3',
                aspectRatio TEXT NOT NULL DEFAULT '1:1',
                style TEXT NOT NULL DEFAULT 'photorealistic',
                imagePath TEXT NOT NULL,
                imageUrl TEXT NOT NULL,
                fileSize INTEGER NOT NULL DEFAULT 0,
                width INTEGER NOT NULL DEFAULT 1024,
                height INTEGER NOT NULL DEFAULT 1024,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_gen_images_userId ON generated_images(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                instructions TEXT,
                color TEXT NOT NULL DEFAULT '#8B5CF6',
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_userId ON projects(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_updatedAt ON projects(updatedAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_notes (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_notes_projId ON project_notes(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_notes_userId ON project_notes(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_saved_outputs (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                outputType TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                metadata TEXT,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_outputs_projId ON project_saved_outputs(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_outputs_userId ON project_saved_outputs(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_items (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                itemType TEXT NOT NULL CHECK(itemType IN ('chat', 'file')),
                itemId TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE,
                UNIQUE (projectId, itemType, itemId)
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_items_projId ON project_items(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_items_userId ON project_items(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                userId TEXT PRIMARY KEY,
                displayName TEXT,
                preferredLanguage TEXT NOT NULL DEFAULT 'English',
                theme TEXT NOT NULL DEFAULT 'system',
                aiTone TEXT NOT NULL DEFAULT 'balanced',
                customInstructions TEXT,
                autoSpeakAudio INTEGER NOT NULL DEFAULT 0,
                codeTheme TEXT NOT NULL DEFAULT 'atom-one-dark',
                enableMemory INTEGER NOT NULL DEFAULT 1,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'preference',
                isActive INTEGER NOT NULL DEFAULT 1,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_memories_userId ON user_memories(userId);")
            await db.commit()

        else:
            # SQLite Schema
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                userId TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                passwordHash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'USER' CHECK(role IN ('USER', 'OWNER', 'CEO', 'ADMIN')),
                accountCreatedAt TEXT NOT NULL,
                lastLoginAt TEXT,
                loginCount INTEGER NOT NULL DEFAULT 0,
                accountStatus TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(accountStatus IN ('ACTIVE', 'PENDING_VERIFICATION', 'SUSPENDED')),
                emailVerified INTEGER NOT NULL DEFAULT 0,
                emailVerificationToken TEXT,
                emailVerificationTokenExpires TEXT,
                passwordResetToken TEXT,
                passwordResetTokenExpires TEXT
            );
            """)

            # Migration for role CHECK constraint if older schema exists
            cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            row = await cursor.fetchone()
            if row and "CHECK(role IN ('USER', 'OWNER'))" in (row["sql"] or ""):
                await db.execute("PRAGMA foreign_keys=OFF;")
                await db.execute("""
                CREATE TABLE users_new (
                    userId TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    passwordHash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'USER' CHECK(role IN ('USER', 'OWNER', 'CEO', 'ADMIN')),
                    accountCreatedAt TEXT NOT NULL,
                    lastLoginAt TEXT,
                    loginCount INTEGER NOT NULL DEFAULT 0,
                    accountStatus TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(accountStatus IN ('ACTIVE', 'PENDING_VERIFICATION', 'SUSPENDED')),
                    emailVerified INTEGER NOT NULL DEFAULT 0,
                    emailVerificationToken TEXT,
                    emailVerificationTokenExpires TEXT,
                    passwordResetToken TEXT,
                    passwordResetTokenExpires TEXT
                );
                """)
                await db.execute("INSERT INTO users_new SELECT * FROM users;")
                await db.execute("DROP TABLE users;")
                await db.execute("ALTER TABLE users_new RENAME TO users;")
                await db.execute("PRAGMA foreign_keys=ON;")
                await db.commit()

            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_verify_token ON users(emailVerificationToken);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(passwordResetToken);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ipAddress TEXT,
                userAgent TEXT,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_userId ON audit_logs(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'gemini-1.5-flash',
                systemPrompt TEXT,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                isPinned INTEGER NOT NULL DEFAULT 0,
                isArchived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_userId ON conversations(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_updatedAt ON conversations(updatedAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversationId TEXT NOT NULL,
                userId TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                model TEXT,
                tokens INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (conversationId) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_convId ON messages(conversationId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_userId ON messages(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_createdAt ON messages(createdAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                filename TEXT NOT NULL,
                originalFilename TEXT NOT NULL,
                fileType TEXT NOT NULL,
                mimeType TEXT NOT NULL,
                fileSize INTEGER NOT NULL,
                storagePath TEXT NOT NULL,
                extractedText TEXT,
                summary TEXT,
                pageCount INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_userId ON files(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_createdAt ON files(createdAt);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_fileType ON files(fileType);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS generated_images (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                prompt TEXT NOT NULL,
                negativePrompt TEXT,
                model TEXT NOT NULL DEFAULT 'dall-e-3',
                aspectRatio TEXT NOT NULL DEFAULT '1:1',
                style TEXT NOT NULL DEFAULT 'photorealistic',
                imagePath TEXT NOT NULL,
                imageUrl TEXT NOT NULL,
                fileSize INTEGER NOT NULL DEFAULT 0,
                width INTEGER NOT NULL DEFAULT 1024,
                height INTEGER NOT NULL DEFAULT 1024,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_gen_images_userId ON generated_images(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_gen_images_createdAt ON generated_images(createdAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                instructions TEXT,
                color TEXT NOT NULL DEFAULT '#8B5CF6',
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_userId ON projects(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_updatedAt ON projects(updatedAt);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_notes (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_notes_projId ON project_notes(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_notes_userId ON project_notes(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_saved_outputs (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                outputType TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                metadata TEXT,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_outputs_projId ON project_saved_outputs(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_outputs_userId ON project_saved_outputs(userId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS project_items (
                id TEXT PRIMARY KEY,
                projectId TEXT NOT NULL,
                userId TEXT NOT NULL,
                itemType TEXT NOT NULL CHECK(itemType IN ('chat', 'file')),
                itemId TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE,
                UNIQUE (projectId, itemType, itemId)
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_items_projId ON project_items(projectId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_items_userId ON project_items(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_proj_items_item ON project_items(itemType, itemId);")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                userId TEXT PRIMARY KEY,
                displayName TEXT,
                preferredLanguage TEXT NOT NULL DEFAULT 'English',
                theme TEXT NOT NULL DEFAULT 'system',
                aiTone TEXT NOT NULL DEFAULT 'balanced',
                customInstructions TEXT,
                autoSpeakAudio INTEGER NOT NULL DEFAULT 0,
                codeTheme TEXT NOT NULL DEFAULT 'atom-one-dark',
                enableMemory INTEGER NOT NULL DEFAULT 1,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'preference',
                isActive INTEGER NOT NULL DEFAULT 1,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
            );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_memories_userId ON user_memories(userId);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_memories_active ON user_memories(userId, isActive);")
            await db.commit()
