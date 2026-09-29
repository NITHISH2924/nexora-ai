package ai.nexora.myai.bridge

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import ai.nexora.myai.BuildConfig
import ai.nexora.myai.R
import ai.nexora.myai.security.SecureStorageManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Native JavaScript Interface exposed to WebKit as `window.AndroidBridge`.
 * Seamlessly connects web UI to device hardware (Mic, TTS, Haptics, Secure KeyStore, Share Sheet).
 */
class WebAppInterface(
    private val activity: Activity,
    private val webView: WebView
) {
    private val secureStorage = SecureStorageManager.getInstance(activity)
    private val mainHandler = Handler(Looper.getMainLooper())
    
    // Text To Speech
    private var textToSpeech: TextToSpeech? = null
    private var isTtsInitialized = false

    // Voice Audio Recording
    private var audioRecord: AudioRecord? = null
    private val isRecording = AtomicBoolean(false)
    private var recordingThread: Thread? = null
    private val audioBufferStream = ByteArrayOutputStream()

    init {
        initTts()
    }

    private fun initTts() {
        textToSpeech = TextToSpeech(activity.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                textToSpeech?.language = Locale.US
                isTtsInitialized = true
            }
        }
    }

    // --- SECURE AUTHENTICATION STORAGE ---

    @JavascriptInterface
    fun saveToken(token: String?) {
        secureStorage.saveAuthToken(token)
    }

    @JavascriptInterface
    fun getToken(): String {
        return secureStorage.getAuthToken() ?: ""
    }

    @JavascriptInterface
    fun clearToken() {
        secureStorage.clearAuthToken()
    }

    // --- SERVER URL CONFIGURATION ---

    @JavascriptInterface
    fun getServerUrl(): String {
        return secureStorage.getServerUrl()
    }

    @JavascriptInterface
    fun setServerUrl(url: String) {
        secureStorage.saveServerUrl(url)
        mainHandler.post {
            showToast("Server updated to: $url", false)
            webView.reload()
        }
    }

    @JavascriptInterface
    fun getAppVersion(): String {
        return "v${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE})"
    }

    // --- HAPTIC FEEDBACK ---

    @JavascriptInterface
    fun vibrate(type: String?) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = activity.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                val vibrator = vibratorManager?.defaultVibrator
                when (type) {
                    "light" -> vibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_TICK))
                    "heavy" -> vibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK))
                    else -> vibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK))
                }
            } else {
                @Suppress("DEPRECATION")
                val vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                when (type) {
                    "light" -> vibrator?.vibrate(15)
                    "heavy" -> vibrator?.vibrate(60)
                    else -> vibrator?.vibrate(30)
                }
            }
        } catch (e: Exception) {
            // Ignore vibration errors on unsupported hardware
        }
    }

    // --- NATIVE SHARE SHEET ---

    @JavascriptInterface
    fun shareText(title: String?, content: String?) {
        mainHandler.post {
            val sendIntent = Intent().apply {
                action = Intent.ACTION_SEND
                putExtra(Intent.EXTRA_TITLE, title ?: "NEXORA AI")
                putExtra(Intent.EXTRA_TEXT, content ?: "")
                type = "text/plain"
            }
            val shareIntent = Intent.createChooser(sendIntent, title ?: "Share via")
            activity.startActivity(shareIntent)
        }
    }

    // --- NATIVE TOAST ---

    @JavascriptInterface
    fun showToast(message: String?, isLong: Boolean) {
        mainHandler.post {
            Toast.makeText(
                activity,
                message ?: "",
                if (isLong) Toast.LENGTH_LONG else Toast.LENGTH_SHORT
            ).show()
        }
    }

    // --- NATIVE TEXT TO SPEECH ---

    @JavascriptInterface
    fun speakText(text: String?) {
        if (text.isNullOrBlank() || !isTtsInitialized) return
        mainHandler.post {
            textToSpeech?.stop()
            textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "nexora_tts_${System.currentTimeMillis()}")
        }
    }

    @JavascriptInterface
    fun stopSpeaking() {
        mainHandler.post {
            textToSpeech?.stop()
        }
    }

    // --- NATIVE VOICE RECORDER (MIC TO PCM / WAV) ---

    @JavascriptInterface
    fun startVoiceRecording(): Boolean {
        if (isRecording.get()) return true
        try {
            val sampleRate = 16000
            val channelConfig = AudioFormat.CHANNEL_IN_MONO
            val audioFormat = AudioFormat.ENCODING_PCM_16BIT
            val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
            
            if (bufferSize <= 0) return false

            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize * 2
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                return false
            }

            audioBufferStream.reset()
            isRecording.set(true)
            audioRecord?.startRecording()

            recordingThread = Thread {
                val buffer = ByteArray(bufferSize)
                while (isRecording.get()) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0) {
                        synchronized(audioBufferStream) {
                            audioBufferStream.write(buffer, 0, read)
                        }
                    }
                }
            }
            recordingThread?.start()
            vibrate("light")
            return true
        } catch (e: SecurityException) {
            return false
        } catch (e: Exception) {
            return false
        }
    }

    @JavascriptInterface
    fun stopVoiceRecording(): String {
        if (!isRecording.get()) return ""
        try {
            isRecording.set(false)
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null
            recordingThread?.join(500)
            recordingThread = null

            val pcmBytes: ByteArray
            synchronized(audioBufferStream) {
                pcmBytes = audioBufferStream.toByteArray()
            }

            if (pcmBytes.isEmpty()) return ""

            // Wrap raw PCM 16-bit 16kHz mono into standard RIFF WAV bytes
            val wavBytes = pcmToWav(pcmBytes, sampleRate = 16000, channels = 1, bitsPerSample = 16)
            vibrate("light")
            return Base64.encodeToString(wavBytes, Base64.NO_WRAP)
        } catch (e: Exception) {
            return ""
        }
    }

    private fun pcmToWav(pcmData: ByteArray, sampleRate: Int, channels: Int, bitsPerSample: Int): ByteArray {
        val totalAudioLen = pcmData.size
        val totalDataLen = totalAudioLen + 36
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val blockAlign = channels * bitsPerSample / 8

        val header = ByteBuffer.allocate(44).apply {
            order(ByteOrder.LITTLE_ENDIAN)
            put('R'.code.toByte()); put('I'.code.toByte()); put('F'.code.toByte()); put('F'.code.toByte())
            putInt(totalDataLen)
            put('W'.code.toByte()); put('A'.code.toByte()); put('V'.code.toByte()); put('E'.code.toByte())
            put('f'.code.toByte()); put('m'.code.toByte()); put('t'.code.toByte()); put(' '.code.toByte())
            putInt(16) // SubChunk1Size (16 for PCM)
            putShort(1.toShort()) // AudioFormat (1 = PCM)
            putShort(channels.toShort())
            putInt(sampleRate)
            putInt(byteRate)
            putShort(blockAlign.toShort())
            putShort(bitsPerSample.toShort())
            put('d'.code.toByte()); put('a'.code.toByte()); put('t'.code.toByte()); put('a'.code.toByte())
            putInt(totalAudioLen)
        }.array()

        val wavStream = ByteArrayOutputStream(44 + totalAudioLen)
        wavStream.write(header)
        wavStream.write(pcmData)
        return wavStream.toByteArray()
    }

    // --- ACCOUNT DELETION CONFIRMATION DIALOG (PLAY STORE COMPLIANCE) ---

    @JavascriptInterface
    fun confirmAccountDeletion() {
        mainHandler.post {
            MaterialAlertDialogBuilder(activity)
                .setTitle("Permanently Delete Account?")
                .setMessage("This action will immediately and permanently erase all your chat history, uploaded files, generated images, projects, and personal AI memories. This action cannot be reversed.")
                .setPositiveButton("Delete Everything") { _, _ ->
                    webView.evaluateJavascript("window.executeAccountDeletion();", null)
                }
                .setNegativeButton("Cancel", null)
                .show()
        }
    }

    fun destroy() {
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        textToSpeech = null
        if (isRecording.get()) {
            isRecording.set(false)
            audioRecord?.release()
            audioRecord = null
        }
    }
}
