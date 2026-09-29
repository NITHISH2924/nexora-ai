import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator

class PasswordValidatorMixin:
    @field_validator("password", mode="before", check_fields=False)
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Password must be a string")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

class UserRegisterRequest(BaseModel, PasswordValidatorMixin):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    rememberMe: bool = False

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8, max_length=128)

    @field_validator("newPassword")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1)

class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8, max_length=128)

    @field_validator("newPassword")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

# Safe User profile exposed to frontend
class UserResponse(BaseModel):
    userId: str
    email: str
    role: str # 'USER' or 'OWNER'
    accountCreatedAt: str
    lastLoginAt: Optional[str] = None
    loginCount: int
    accountStatus: str # 'ACTIVE', 'PENDING_VERIFICATION', 'SUSPENDED'
    emailVerified: bool

class AuthResponse(BaseModel):
    user: UserResponse
    token: str
    tokenType: str = "Bearer"
    message: str

class MessageResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None

class UserStatusUpdateRequest(BaseModel):
    accountStatus: str = Field(..., pattern=r"^(ACTIVE|PENDING_VERIFICATION|SUSPENDED)$")

class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(USER|OWNER|CEO|ADMIN)$")

class ActivityLogResponse(BaseModel):
    id: int
    action: str
    details: Optional[str] = None
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    createdAt: str

# Phase 2: Chat and Conversation Models
class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = "gemini-1.5-flash"
    systemPrompt: Optional[str] = None

class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    isPinned: Optional[bool] = None
    isArchived: Optional[bool] = None
    model: Optional[str] = None

class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    model: Optional[str] = None
    systemPrompt: Optional[str] = None
    fileIds: Optional[List[str]] = None

class ChatMessageEditRequest(BaseModel):
    content: str = Field(..., min_length=1)

class MessageItem(BaseModel):
    id: str
    conversationId: str
    userId: str
    role: str
    content: str
    model: Optional[str] = None
    tokens: int = 0
    fileIds: Optional[List[str]] = None
    createdAt: str

class ConversationSummary(BaseModel):
    id: str
    userId: str
    title: str
    model: str
    systemPrompt: Optional[str] = None
    createdAt: str
    updatedAt: str
    isPinned: bool
    isArchived: bool
    messageCount: int = 0
    lastMessage: Optional[str] = None

class ConversationDetail(BaseModel):
    id: str
    userId: str
    title: str
    model: str
    systemPrompt: Optional[str] = None
    createdAt: str
    updatedAt: str
    isPinned: bool
    isArchived: bool
    messages: List[MessageItem] = []

# Phase 3: Files & Document Intelligence Models
class FileSummary(BaseModel):
    id: str
    userId: str
    filename: str
    originalFilename: str
    fileType: str  # 'pdf', 'docx', 'txt', 'csv', 'image'
    mimeType: str
    fileSize: int
    pageCount: int = 0
    hasExtractedText: bool = False
    hasSummary: bool = False
    createdAt: str

class FileDetail(BaseModel):
    id: str
    userId: str
    filename: str
    originalFilename: str
    fileType: str
    mimeType: str
    fileSize: int
    pageCount: int = 0
    extractedText: Optional[str] = None
    summary: Optional[str] = None
    createdAt: str
    downloadUrl: Optional[str] = None

class FileAIActionRequest(BaseModel):
    action: str = Field(..., pattern=r"^(summarize|qa|extract|explain|notes|questions)$")
    query: Optional[str] = None
    model: Optional[str] = None
    systemPrompt: Optional[str] = None

class FileAIActionResponse(BaseModel):
    fileId: str
    filename: str
    action: str
    result: str
    model: str
    query: Optional[str] = None

class ImageAnalysisRequest(BaseModel):
    action: Optional[str] = Field("describe", pattern=r"^(describe|screenshot|ocr|diagram|qa|analyze)$")
    query: Optional[str] = None
    model: Optional[str] = None
    fileId: Optional[str] = None
    imageBase64: Optional[str] = None

class ImageAnalysisResponse(BaseModel):
    fileId: Optional[str] = None
    action: str
    result: str
    model: str
    dimensions: Optional[str] = None
    format: Optional[str] = None

# Phase 4: AI Search Models
class SearchResultSource(BaseModel):
    index: Optional[int] = None
    title: str
    url: str
    snippet: str
    domain: Optional[str] = None
    icon: Optional[str] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    model: Optional[str] = None
    maxResults: int = Field(5, ge=1, le=10)
    searchDepth: Optional[str] = "standard"

class SearchResponse(BaseModel):
    query: str
    synthesis: str
    sources: List[SearchResultSource]
    model: str
    timestamp: str
    searchDepth: Optional[str] = "standard"
    totalSourcesFound: Optional[int] = 0

# Phase 4: Coding Assistant Models
class CodeAssistRequest(BaseModel):
    action: str = Field(..., pattern=r"^(generate|debug|explain|refactor|optimize|error_analysis)$")
    language: str = Field("python", min_length=1, max_length=50)
    code: Optional[str] = None
    prompt: Optional[str] = None
    errorMessage: Optional[str] = None
    model: Optional[str] = None

class CodeAssistResponse(BaseModel):
    action: str
    language: str
    result: str
    code: Optional[str] = None
    explanation: Optional[str] = None
    model: str

class CodeExecutionRequest(BaseModel):
    language: str = Field("python", pattern=r"^(python|javascript|js)$")
    code: str = Field(..., min_length=1, max_length=20000)
    stdin: Optional[str] = None

class CodeExecutionResponse(BaseModel):
    status: str  # 'success', 'error', 'timeout'
    output: str
    error: Optional[str] = None
    executionTimeMs: float
    exitCode: int
    success: Optional[bool] = True
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    durationMs: Optional[float] = None

# Phase 4: Writing Assistant Models
class WritingAssistRequest(BaseModel):
    action: str = Field(..., pattern=r"^(rewrite|grammar|summarize|expand|shorten|professional|email|resume|cover_letter|translate)$")
    text: Optional[str] = ""
    tone: Optional[str] = "professional"
    targetLanguage: Optional[str] = "English"
    recipient: Optional[str] = None
    jobTitle: Optional[str] = None
    companyName: Optional[str] = None
    model: Optional[str] = None

class WritingAssistResponse(BaseModel):
    action: str
    result: str
    originalWordCount: int = 0
    resultWordCount: int = 0
    inputWords: Optional[int] = 0
    outputWords: Optional[int] = 0
    model: str

# Phase 5: Image Generation Models
class ImageGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    negativePrompt: Optional[str] = None
    model: Optional[str] = "dall-e-3"
    aspectRatio: Optional[str] = "1:1"  # '1:1', '16:9', '9:16', '4:3'
    style: Optional[str] = "photorealistic"  # 'photorealistic', 'anime', 'cyberpunk', '3d_render', 'cinematic', 'minimalist', 'oil_painting'
    width: Optional[int] = 1024
    height: Optional[int] = 1024

class ImageGenResponse(BaseModel):
    id: str
    userId: Optional[str] = None
    prompt: str
    negativePrompt: Optional[str] = None
    model: str
    aspectRatio: str
    style: str
    imagePath: Optional[str] = None
    imageUrl: str
    downloadUrl: str
    width: int
    height: int
    fileSize: int
    createdAt: str

# Phase 5: Voice Intelligence Models (STT, TTS & Pipeline)
class VoiceTranscribeResponse(BaseModel):
    transcript: str
    text: Optional[str] = None
    language: Optional[str] = "en"
    durationSeconds: Optional[float] = None
    provider: str

    def __init__(self, **data):
        super().__init__(**data)
        if not self.text:
            self.text = self.transcript

class VoiceSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: Optional[str] = "alloy"  # 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'
    speed: Optional[float] = 1.0
    model: Optional[str] = "tts-1"

class VoiceSynthesizeResponse(BaseModel):
    audioId: str
    audioUrl: str
    audioPath: Optional[str] = None
    audioBase64: Optional[str] = None
    format: str = "wav"
    durationSeconds: Optional[float] = None
    provider: str

class VoicePipelineRequest(BaseModel):
    audioBase64: Optional[str] = None
    voice: Optional[str] = "alloy"
    model: Optional[str] = None
    conversationId: Optional[str] = None
    systemPrompt: Optional[str] = None

class VoicePipelineResponse(BaseModel):
    transcript: str
    aiResponse: str
    transcribedText: Optional[str] = None
    aiResponseText: Optional[str] = None
    audioId: Optional[str] = None
    audioUrl: Optional[str] = None
    audioBase64: Optional[str] = None
    durationSeconds: Optional[float] = None
    model: str

    def __init__(self, **data):
        super().__init__(**data)
        if not self.transcribedText:
            self.transcribedText = self.transcript
        if not self.aiResponseText:
            self.aiResponseText = self.aiResponse

class VoiceStatusResponse(BaseModel):
    speechToTextConfigured: bool
    textToSpeechConfigured: bool
    sttAvailable: Optional[bool] = None
    ttsAvailable: Optional[bool] = None
    sttProvider: Optional[str] = None
    ttsProvider: Optional[str] = None
    defaultProvider: str
    supportedVoices: List[str]
    voices: Optional[List[str]] = None
    setupGuide: Optional[str] = None
    setupMessage: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.sttAvailable is None:
            self.sttAvailable = self.speechToTextConfigured
        if self.ttsAvailable is None:
            self.ttsAvailable = self.textToSpeechConfigured
        if self.voices is None:
            self.voices = self.supportedVoices
        if not self.setupMessage:
            self.setupMessage = self.setupGuide

# ==============================================================================
# Phase 6: Projects, Personalization & Controlled Memory Models
# ==============================================================================

# Projects Models
class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    instructions: Optional[str] = None
    color: Optional[str] = "#8B5CF6"

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    instructions: Optional[str] = None
    color: Optional[str] = None

class ProjectNoteCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)

class ProjectNoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None

class ProjectNoteResponse(BaseModel):
    id: str
    projectId: str
    userId: str
    title: str
    content: str
    createdAt: str
    updatedAt: str

class ProjectSavedOutputCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    outputType: str = Field("text", pattern=r"^(text|code|summary|image_url|search|notes)$")
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None

class ProjectSavedOutputResponse(BaseModel):
    id: str
    projectId: str
    userId: str
    title: str
    outputType: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    createdAt: str

class ProjectAssociateItemRequest(BaseModel):
    itemType: str = Field(..., pattern=r"^(chat|file)$")
    itemId: str = Field(..., min_length=1)

class ProjectSummary(BaseModel):
    id: str
    userId: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    color: str = "#8B5CF6"
    chatCount: int = 0
    fileCount: int = 0
    noteCount: int = 0
    outputCount: int = 0
    createdAt: str
    updatedAt: str

class ProjectDetail(BaseModel):
    id: str
    userId: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    color: str = "#8B5CF6"
    createdAt: str
    updatedAt: str
    chats: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    notes: List[ProjectNoteResponse] = []
    savedOutputs: List[ProjectSavedOutputResponse] = []

# Personalization & User Preferences Models
class UserPreferencesRequest(BaseModel):
    displayName: Optional[str] = None
    preferredLanguage: Optional[str] = "English"
    theme: Optional[str] = "system"
    aiTone: Optional[str] = "balanced"  # 'balanced', 'concise', 'detailed', 'technical', 'creative'
    customInstructions: Optional[str] = None
    autoSpeakAudio: Optional[bool] = False
    codeTheme: Optional[str] = "atom-one-dark"
    enableMemory: Optional[bool] = True

class UserPreferencesResponse(BaseModel):
    userId: str
    displayName: Optional[str] = None
    preferredLanguage: str = "English"
    theme: str = "system"
    aiTone: str = "balanced"
    customInstructions: Optional[str] = None
    autoSpeakAudio: bool = False
    codeTheme: str = "atom-one-dark"
    enableMemory: bool = True
    updatedAt: str

# Controlled Memory Architecture Models
class MemoryCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=2000)
    category: Optional[str] = "preference"  # 'preference', 'context', 'skill', 'instruction', 'project'

class MemoryUpdateRequest(BaseModel):
    key: Optional[str] = Field(None, min_length=1, max_length=100)
    value: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = None
    isActive: Optional[bool] = None

class MemoryItemResponse(BaseModel):
    id: str
    userId: str
    key: str
    value: str
    category: str
    isActive: bool
    createdAt: str
    updatedAt: str

class MemoryListResponse(BaseModel):
    memories: List[MemoryItemResponse]
    memoryEnabled: bool = True
    total: int





