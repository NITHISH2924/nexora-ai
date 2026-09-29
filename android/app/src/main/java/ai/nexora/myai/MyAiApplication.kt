package ai.nexora.myai

import android.app.Application
import android.webkit.WebView
import ai.nexora.myai.security.SecureStorageManager

/**
 * NEXORA AI Application class.
 * Initializes secure KeyStore storage, WebKit debugging flags, and network security profiles.
 */
class MyAiApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        
        // Initialize Encrypted Storage
        SecureStorageManager.getInstance(this)

        // Enable WebView debugging only in debug builds
        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true)
        }
    }
}
