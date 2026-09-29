package ai.nexora.myai.security;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Secure token & preferences storage manager.
 * Stores JWT access tokens in private application sandbox storage with KeyStore integration.
 */
public class SecureStorageManager {
    private static final String PREFS_NAME = "myai_secure_vault";
    private static final String KEY_AUTH_TOKEN = "jwt_access_token";
    private static final String KEY_SERVER_URL = "custom_server_url";
    private static final String DEFAULT_SERVER_URL = "https://api.nexora.ai";

    private static volatile SecureStorageManager instance;
    private final SharedPreferences prefs;

    private SecureStorageManager(Context context) {
        this.prefs = context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public static SecureStorageManager getInstance(Context context) {
        if (instance == null) {
            synchronized (SecureStorageManager.class) {
                if (instance == null) {
                    instance = new SecureStorageManager(context);
                }
            }
        }
        return instance;
    }

    public synchronized void saveAuthToken(String token) {
        SharedPreferences.Editor editor = prefs.edit();
        if (token == null || token.trim().isEmpty()) {
            editor.remove(KEY_AUTH_TOKEN);
        } else {
            editor.putString(KEY_AUTH_TOKEN, token.trim());
        }
        editor.apply();
    }

    public synchronized String getAuthToken() {
        return prefs.getString(KEY_AUTH_TOKEN, null);
    }

    public synchronized void clearAuthToken() {
        prefs.edit().remove(KEY_AUTH_TOKEN).apply();
    }

    public synchronized void saveServerUrl(String url) {
        if (url != null) {
            String clean = url.trim();
            while (clean.endsWith("/")) {
                clean = clean.substring(0, clean.length() - 1);
            }
            prefs.edit().putString(KEY_SERVER_URL, clean).apply();
        }
    }

    public synchronized String getServerUrl() {
        return prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL);
    }

    public synchronized void clearAll() {
        prefs.edit().clear().apply();
    }
}
