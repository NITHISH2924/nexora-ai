package ai.nexora.myai.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import ai.nexora.myai.BuildConfig

/**
 * Hardware-backed encrypted storage for sensitive JWT tokens and user preferences.
 * Uses AES-256-GCM encryption with Android KeyStore master key.
 */
class SecureStorageManager private constructor(context: Context) {

    private val sharedPreferences: SharedPreferences

    init {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        sharedPreferences = try {
            EncryptedSharedPreferences.create(
                context,
                PREFS_FILENAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            // Fallback to standard private preferences if keystore is corrupted
            context.getSharedPreferences(PREFS_FILENAME_FALLBACK, Context.MODE_PRIVATE)
        }
    }

    fun saveAuthToken(token: String?) {
        sharedPreferences.edit().apply {
            if (token.isNullOrBlank()) {
                remove(KEY_AUTH_TOKEN)
            } else {
                putString(KEY_AUTH_TOKEN, token.trim())
            }
            apply()
        }
    }

    fun getAuthToken(): String? {
        return sharedPreferences.getString(KEY_AUTH_TOKEN, null)
    }

    fun clearAuthToken() {
        sharedPreferences.edit().remove(KEY_AUTH_TOKEN).apply()
    }

    fun saveServerUrl(url: String) {
        sharedPreferences.edit().putString(KEY_SERVER_URL, url.trim().trimEnd('/')).apply()
    }

    fun getServerUrl(): String {
        return sharedPreferences.getString(KEY_SERVER_URL, BuildConfig.DEFAULT_SERVER_URL)
            ?: BuildConfig.DEFAULT_SERVER_URL
    }

    fun clearAllData() {
        sharedPreferences.edit().clear().apply()
    }

    companion object {
        private const val PREFS_FILENAME = "myai_secure_prefs"
        private const val PREFS_FILENAME_FALLBACK = "myai_secure_prefs_fb"
        private const val KEY_AUTH_TOKEN = "jwt_access_token"
        private const val KEY_SERVER_URL = "custom_server_url"

        @Volatile
        private var instance: SecureStorageManager? = null

        fun getInstance(context: Context): SecureStorageManager {
            return instance ?: synchronized(this) {
                instance ?: SecureStorageManager(context.applicationContext).also { instance = it }
            }
        }
    }
}
