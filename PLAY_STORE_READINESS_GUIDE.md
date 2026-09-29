# NEXORA AI — Google Play Store Submission & Readiness Guide

## 1. Executive Summary

The **NEXORA AI** Android application has been converted from the production web platform into a high-performance native Android application. It connects securely to your existing FastAPI backend, enforcing strict multi-tenant isolation, HTTPS-only network policies, zero client-side secret exposure, hardware-backed token storage (KeyStore / Encrypted Preferences), native microphone recording, camera photo capture, and complete Google Play policy compliance.

---

## 2. Platform Leadership & Governance

| Role | Name | Title |
| :--- | :--- | :--- |
| **👑 Owner** | `Nithish Kumar R` | Founder &amp; Platform Architect |
| **🚀 CEO** | `Dhanushiya S` | Chief Executive Officer |

---

## 3. Android Project Architecture

| Component | Path | Description |
| :--- | :--- | :--- |
| **Package Name** | `ai.nexora.myai` | Official Application ID |
| **App Name** | `NEXORA AI` | Official display name |
| **Target SDK** | `34` (Android 14) | Compliant with Google Play 2026 requirements |
| **Min SDK** | `26` (Android 8.0+) | Covers 95%+ of active Android devices |
| **Release APK** | `android/app/build/outputs/apk/release/app-release.apk` | Signed and 4-byte zip-aligned |
| **Keystore** | `android/myai-release-key.jks` | RSA 2048-bit production signing key |
| **Network Security** | `android/app/src/main/res/xml/network_security_config.xml` | Enforces `cleartextTrafficPermitted="false"` |
| **Backup Security** | `android/app/src/main/res/xml/data_extraction_rules.xml` | `allowBackup="false"` to prevent token leakage |

---

## 3. Implemented Features & Technical Details

### 🎨 App Icon & Branding
- **Adaptive Icons**: Vector foreground (`ic_launcher_foreground.xml`) & background (`ic_launcher_background.xml`) with quantum neural spark aesthetic.
- **Raster Mipmaps**: Density-scaled PNG assets for `mdpi` (48px), `hdpi` (72px), `xhdpi` (96px), `xxhdpi` (144px), and `xxxhdpi` (192px).
- **Splash Screen**: Animated branded splash screen with dark glassmorphic palette.

### 🔐 Authentication & Session Security
- **JWT Storage**: Managed via native hardware-backed KeyStore and sandbox storage (`SecureStorageManager`).
- **Server Mediation**: **Zero API keys embedded inside APK**. All AI requests are mediated by the backend.
- **Secure Logout**: Wipes local tokens, invalidates session, resets native bridge cache.
- **Account Deletion**: In-app confirmation dialog (`window.AndroidBridge.confirmAccountDeletion()`) and external web request flow (`/delete-account`).

### 💬 AI Chat & Multi-Turn Workspace
- **Real-Time Streaming**: Server-Sent Events (SSE) streaming engine with auto-reconnect and markdown rendering.
- **Chat History**: Full drawer navigation with search, rename, delete, and conversation branch editing.
- **Multi-Model Routing**: Seamless selection between high-performance neural models.

### 📁 Documents, Camera & Vision Intelligence
- **Native File Picker**: Supports PDF, DOCX, TXT, CSV, Audio, and Images with MIME validation.
- **Camera Integration**: Direct photo and diagram capture with secure `MyAiFileProvider`.
- **Document AI**: In-app actions for summarize, Q&A, entity extraction, study notes, and quizzes.

### 🎙️ Voice & Audio Intelligence
- **Native Audio Recorder**: Captures microphone input at 16kHz mono PCM, compiles standard RIFF WAV, and streams to `/api/voice/stt`.
- **Text-to-Speech**: Native Android `TextToSpeech` playback engine and server PCM waveform synthesis.

### 🗂️ Projects & Controlled Personalization
- **Projects Studio**: Dedicated workspace for organizing notes, snippets, and associated chats.
- **Memory Subsystem**: Transparent memory inspection, categorical storage, manual toggle, and complete memory purge.

---

## 4. Google Play Console Compliance Checklist

### 📋 Data Safety Form Answers
| Question | Answer | Details |
| :--- | :--- | :--- |
| **Does your app collect or share data?** | **Yes** | Account info (email), user content (prompts/files), audio (voice input). |
| **Is all user data encrypted in transit?** | **Yes** | HTTPS / TLS 1.2+ is strictly enforced via Network Security Config. |
| **Do you provide a way for users to request data deletion?** | **Yes** | In-app **Settings > Delete Account** and Web URL: `https://your-domain.com/delete-account`. |
| **Data Types Collected:** | | |
| • Email Address | Collected for Account Management / Authentication. |
| • Audio Data | Collected temporarily for Voice Dictation (not stored or sold). |
| • Files / Documents | Collected for user-requested Document AI and Multimodal Vision. |

### 📜 Legal URLs for Play Console Listing
- **Privacy Policy URL**: `https://your-domain.com/privacy`
- **Terms of Service URL**: `https://your-domain.com/terms`
- **Account Deletion URL**: `https://your-domain.com/delete-account`

---

## 5. Rebuilding & Testing the Release APK

To re-run the build pipeline and test suite at any time:

```powershell
# 1. Rebuild release APK
py scratch/build_release_apk.py

# 2. Run comprehensive Play Store & Android readiness tests
py tests/test_android_readiness.py

# 3. Run backend integration tests
py tests/test_live_http.py
```
