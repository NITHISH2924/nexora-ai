package ai.nexora.myai;

import android.app.Application;
import android.webkit.WebView;

import ai.nexora.myai.security.SecureStorageManager;

/**
 * Application class for NEXORA AI Android Platform.
 */
public class MyAiApplication extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        SecureStorageManager.getInstance(this);
    }
}
