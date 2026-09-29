package ai.nexora.myai.bridge;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.speech.tts.TextToSpeech;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

import ai.nexora.myai.security.SecureStorageManager;

/**
 * High-performance JavaScript bridge exposed to WebKit as `window.AndroidBridge`.
 * Seamlessly interfaces the web view with native Android hardware and system services.
 */
public class WebAppInterface {
    private final Activity activity;
    private final WebView webView;
    private final SecureStorageManager secureStorage;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private TextToSpeech textToSpeech;
    private boolean isTtsReady = false;

    private AudioRecord audioRecord;
    private final AtomicBoolean isRecording = new AtomicBoolean(false);
    private Thread recordingThread;
    private final ByteArrayOutputStream audioBufferStream = new ByteArrayOutputStream();

    public WebAppInterface(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        this.secureStorage = SecureStorageManager.getInstance(activity);
        initTextToSpeech();
    }

    private void initTextToSpeech() {
        textToSpeech = new TextToSpeech(activity.getApplicationContext(), new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS) {
                    textToSpeech.setLanguage(Locale.US);
                    isTtsReady = true;
                }
            }
        });
    }

    // --- SECURE AUTHENTICATION STORAGE ---

    @JavascriptInterface
    public void saveToken(String token) {
        secureStorage.saveAuthToken(token);
    }

    @JavascriptInterface
    public String getToken() {
        String token = secureStorage.getAuthToken();
        return token != null ? token : "";
    }

    @JavascriptInterface
    public void clearToken() {
        secureStorage.clearAuthToken();
    }

    // --- SERVER URL CONFIGURATION ---

    @JavascriptInterface
    public String getServerUrl() {
        return secureStorage.getServerUrl();
    }

    @JavascriptInterface
    public void setServerUrl(final String url) {
        secureStorage.saveServerUrl(url);
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                showToast("Server updated to: " + url, false);
                webView.reload();
            }
        });
    }

    @JavascriptInterface
    public String getAppVersion() {
        return "1.0.0 (Release)";
    }

    // --- HAPTIC FEEDBACK ---

    @JavascriptInterface
    public void vibrate(String type) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                VibratorManager vibratorManager = (VibratorManager) activity.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
                if (vibratorManager != null) {
                    Vibrator vibrator = vibratorManager.getDefaultVibrator();
                    if ("heavy".equalsIgnoreCase(type)) {
                        vibrator.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK));
                    } else if ("light".equalsIgnoreCase(type)) {
                        vibrator.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_TICK));
                    } else {
                        vibrator.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK));
                    }
                }
            } else {
                Vibrator vibrator = (Vibrator) activity.getSystemService(Context.VIBRATOR_SERVICE);
                if (vibrator != null && vibrator.hasVibrator()) {
                    if ("heavy".equalsIgnoreCase(type)) {
                        vibrator.vibrate(60);
                    } else if ("light".equalsIgnoreCase(type)) {
                        vibrator.vibrate(15);
                    } else {
                        vibrator.vibrate(30);
                    }
                }
            }
        } catch (Exception ignored) {
        }
    }

    // --- NATIVE SHARE SHEET ---

    @JavascriptInterface
    public void shareText(final String title, final String content) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                Intent sendIntent = new Intent();
                sendIntent.setAction(Intent.ACTION_SEND);
                sendIntent.putExtra(Intent.EXTRA_TITLE, title != null ? title : "NEXORA AI");
                sendIntent.putExtra(Intent.EXTRA_TEXT, content != null ? content : "");
                sendIntent.setType("text/plain");
                Intent shareIntent = Intent.createChooser(sendIntent, title != null ? title : "Share with");
                activity.startActivity(shareIntent);
            }
        });
    }

    // --- NATIVE TOAST ---

    @JavascriptInterface
    public void showToast(final String message, final boolean isLong) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(activity, message != null ? message : "", isLong ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT).show();
            }
        });
    }

    // --- NATIVE TEXT TO SPEECH ---

    @JavascriptInterface
    public void speakText(final String text) {
        if (text == null || text.trim().isEmpty() || !isTtsReady) return;
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                if (textToSpeech != null) {
                    textToSpeech.stop();
                    textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "nexora_tts_" + System.currentTimeMillis());
                }
            }
        });
    }

    @JavascriptInterface
    public void stopSpeaking() {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                if (textToSpeech != null) {
                    textToSpeech.stop();
                }
            }
        });
    }

    // --- NATIVE MICROPHONE RECORDING (MIC TO 16kHz PCM WAV) ---

    @JavascriptInterface
    public boolean startVoiceRecording() {
        if (isRecording.get()) return true;
        try {
            int sampleRate = 16000;
            int channelConfig = AudioFormat.CHANNEL_IN_MONO;
            int audioFormat = AudioFormat.ENCODING_PCM_16BIT;
            final int bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat);
            if (bufferSize <= 0) return false;

            audioRecord = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    sampleRate,
                    channelConfig,
                    audioFormat,
                    bufferSize * 2
            );

            if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
                return false;
            }

            audioBufferStream.reset();
            isRecording.set(true);
            audioRecord.startRecording();

            recordingThread = new Thread(new Runnable() {
                @Override
                public void run() {
                    byte[] buffer = new byte[bufferSize];
                    while (isRecording.get()) {
                        int read = audioRecord != null ? audioRecord.read(buffer, 0, buffer.length) : 0;
                        if (read > 0) {
                            synchronized (audioBufferStream) {
                                audioBufferStream.write(buffer, 0, read);
                            }
                        }
                    }
                }
            });
            recordingThread.start();
            vibrate("light");
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public String stopVoiceRecording() {
        if (!isRecording.get()) return "";
        try {
            isRecording.set(false);
            if (audioRecord != null) {
                audioRecord.stop();
                audioRecord.release();
                audioRecord = null;
            }
            if (recordingThread != null) {
                recordingThread.join(500);
                recordingThread = null;
            }

            byte[] pcmBytes;
            synchronized (audioBufferStream) {
                pcmBytes = audioBufferStream.toByteArray();
            }

            if (pcmBytes.length == 0) return "";

            byte[] wavBytes = pcmToWav(pcmBytes, 16000, 1, 16);
            vibrate("light");
            return Base64.encodeToString(wavBytes, Base64.NO_WRAP);
        } catch (Exception e) {
            return "";
        }
    }

    private byte[] pcmToWav(byte[] pcmData, int sampleRate, int channels, int bitsPerSample) {
        int totalAudioLen = pcmData.length;
        int totalDataLen = totalAudioLen + 36;
        int byteRate = sampleRate * channels * bitsPerSample / 8;
        int blockAlign = channels * bitsPerSample / 8;

        ByteBuffer header = ByteBuffer.allocate(44);
        header.order(ByteOrder.LITTLE_ENDIAN);
        header.put((byte) 'R'); header.put((byte) 'I'); header.put((byte) 'F'); header.put((byte) 'F');
        header.putInt(totalDataLen);
        header.put((byte) 'W'); header.put((byte) 'A'); header.put((byte) 'V'); header.put((byte) 'E');
        header.put((byte) 'f'); header.put((byte) 'm'); header.put((byte) 't'); header.put((byte) ' ');
        header.putInt(16); // Subchunk1Size
        header.putShort((short) 1); // AudioFormat (1 = PCM)
        header.putShort((short) channels);
        header.putInt(sampleRate);
        header.putInt(byteRate);
        header.putShort((short) blockAlign);
        header.putShort((short) bitsPerSample);
        header.put((byte) 'd'); header.put((byte) 'a'); header.put((byte) 't'); header.put((byte) 'a');
        header.putInt(totalAudioLen);

        ByteArrayOutputStream wavStream = new ByteArrayOutputStream(44 + totalAudioLen);
        wavStream.write(header.array(), 0, 44);
        wavStream.write(pcmData, 0, totalAudioLen);
        return wavStream.toByteArray();
    }

    // --- ACCOUNT DELETION CONFIRMATION DIALOG (PLAY STORE COMPLIANCE) ---

    @JavascriptInterface
    public void confirmAccountDeletion() {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                new AlertDialog.Builder(activity)
                        .setTitle("Permanently Delete Account?")
                        .setMessage("This action will immediately and permanently erase all your chat history, uploaded files, generated images, projects, and personal AI memories. This action cannot be undone.")
                        .setPositiveButton("Delete Everything", new DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(DialogInterface dialog, int which) {
                                webView.evaluateJavascript("window.executeAccountDeletion();", null);
                            }
                        })
                        .setNegativeButton("Cancel", null)
                        .show();
            }
        });
    }

    public void destroy() {
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
            textToSpeech = null;
        }
        if (isRecording.get()) {
            isRecording.set(false);
            if (audioRecord != null) {
                audioRecord.release();
                audioRecord = null;
            }
        }
    }
}
