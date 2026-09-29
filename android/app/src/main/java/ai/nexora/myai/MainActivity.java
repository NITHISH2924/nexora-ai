package ai.nexora.myai;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.view.View;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import ai.nexora.myai.bridge.WebAppInterface;
import ai.nexora.myai.security.SecureStorageManager;

public class MainActivity extends Activity {

    private static final int FILE_CHOOSER_REQ = 1001;
    private static final int PERMISSION_REQ = 1002;
    private static final int NOTIFICATION_REQ = 1003;

    private WebView webView;
    private ProgressBar progressBar;
    private View errorView;
    private TextView errorTitle;
    private TextView errorDesc;
    private Button btnRetry;

    private WebAppInterface webAppInterface;
    private SecureStorageManager secureStorage;

    private ValueCallback<Uri[]> fileUploadCallback;
    private Uri cameraImageUri;
    private boolean backPressedOnce = false;
    private final Handler backHandler = new Handler(Looper.getMainLooper());
    private PermissionRequest pendingPermissionRequest;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        secureStorage = SecureStorageManager.getInstance(this);

        initViews();
        setupWebView();
        requestNotificationPermission();

        loadApp();
    }

    private void initViews() {
        webView = findViewById(R.id.webView);
        progressBar = findViewById(R.id.progressBar);
        errorView = findViewById(R.id.errorView);
        errorTitle = findViewById(R.id.errorTitle);
        errorDesc = findViewById(R.id.errorDescription);
        btnRetry = findViewById(R.id.btnRetry);

        webAppInterface = new WebAppInterface(this, webView);

        btnRetry.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                errorView.setVisibility(View.GONE);
                loadApp();
            }
        });
    }

    @Override
    public void onBackPressed() {
        if (webView != null) {
            webView.evaluateJavascript("window.handleAndroidBack ? window.handleAndroidBack() : false", new ValueCallback<String>() {
                @Override
                public void onReceiveValue(String value) {
                    boolean handledByWeb = "true".equals(value);
                    if (!handledByWeb) {
                        if (webView.canGoBack()) {
                            webView.goBack();
                        } else {
                            if (backPressedOnce) {
                                MainActivity.super.onBackPressed();
                            } else {
                                backPressedOnce = true;
                                Toast.makeText(MainActivity.this, getString(R.string.exit_confirm_toast), Toast.LENGTH_SHORT).show();
                                backHandler.postDelayed(new Runnable() {
                                    @Override
                                    public void run() {
                                        backPressedOnce = false;
                                    }
                                }, 2000);
                            }
                        }
                    }
                }
            });
        } else {
            super.onBackPressed();
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setDisplayZoomControls(false);
        settings.setBuiltInZoomControls(false);
        settings.setSupportZoom(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " MY_AI_ANDROID_APP/1.0.0");

        webView.addJavascriptInterface(webAppInterface, "AndroidBridge");

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress < 100) {
                    progressBar.setVisibility(View.VISIBLE);
                    progressBar.setProgress(newProgress);
                } else {
                    progressBar.setVisibility(View.GONE);
                }
            }

            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (fileUploadCallback != null) {
                    fileUploadCallback.onReceiveValue(null);
                }
                fileUploadCallback = filePathCallback;
                launchUnifiedFilePicker();
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                if (request == null) return;
                List<String> needed = new ArrayList<>();
                for (String res : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res) &&
                            checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                        needed.add(Manifest.permission.RECORD_AUDIO);
                    }
                    if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res) &&
                            checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                        needed.add(Manifest.permission.CAMERA);
                    }
                }

                if (needed.isEmpty()) {
                    request.grant(request.getResources());
                } else {
                    pendingPermissionRequest = request;
                    requestPermissions(needed.toArray(new String[0]), PERMISSION_REQ);
                }
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (request == null || request.getUrl() == null) return false;
                Uri url = request.getUrl();
                String scheme = url.getScheme() != null ? url.getScheme().toLowerCase(Locale.ROOT) : "";
                String host = url.getHost() != null ? url.getHost().toLowerCase(Locale.ROOT) : "";

                if ("mailto".equals(scheme) || "tel".equals(scheme) || "market".equals(scheme)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, url));
                    } catch (ActivityNotFoundException e) {
                        Toast.makeText(MainActivity.this, "No app available to handle this request", Toast.LENGTH_SHORT).show();
                    }
                    return true;
                }

                if (url.toString().startsWith("file:///android_asset/")) {
                    return false;
                }

                Uri serverUri = Uri.parse(secureStorage.getServerUrl());
                if (!host.isEmpty() && !host.equalsIgnoreCase(serverUri.getHost()) &&
                        !host.contains("nexora.ai") && !host.contains("myai.com") && !host.contains("127.0.0.1") && !host.contains("10.0.2.2")) {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                    return true;
                }

                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                errorView.setVisibility(View.GONE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                errorView.setVisibility(View.GONE);
                String token = secureStorage.getAuthToken();
                if (token != null && !token.trim().isEmpty()) {
                    view.evaluateJavascript("if (typeof TokenManager !== 'undefined') { TokenManager.setToken('" + token + "'); }", null);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request != null && request.isForMainFrame()) {
                    showError(getString(R.string.error_server_title), getString(R.string.error_server_desc));
                }
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                showError(getString(R.string.error_ssl_title), getString(R.string.error_ssl_desc));
            }
        });
    }

    private void showError(String title, String desc) {
        errorTitle.setText(title);
        errorDesc.setText(desc);
        errorView.setVisibility(View.VISIBLE);
    }

    private void loadApp() {
        webView.loadUrl("file:///android_asset/app.html");
    }

    private void launchUnifiedFilePicker() {
        List<Intent> intents = new ArrayList<>();

        // Camera Intent
        Intent takePictureIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        try {
            File photoFile = createTempImageFile();
            cameraImageUri = Uri.fromFile(photoFile);
            takePictureIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraImageUri);
            intents.add(takePictureIntent);
        } catch (Exception e) {
            cameraImageUri = null;
        }

        // File / Document / Media Picker Intent
        Intent contentSelectionIntent = new Intent(Intent.ACTION_GET_CONTENT);
        contentSelectionIntent.addCategory(Intent.CATEGORY_OPENABLE);
        contentSelectionIntent.setType("*/*");
        contentSelectionIntent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "image/*",
                "application/pdf",
                "text/plain",
                "text/csv",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "audio/*"
        });
        contentSelectionIntent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);

        Intent chooserIntent = Intent.createChooser(contentSelectionIntent, "Select Document or Image");
        if (!intents.isEmpty()) {
            chooserIntent.putExtra(Intent.EXTRA_INITIAL_INTENTS, intents.toArray(new Intent[0]));
        }

        startActivityForResult(chooserIntent, FILE_CHOOSER_REQ);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQ) {
            if (fileUploadCallback == null) return;
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK) {
                if (data == null || data.getData() == null) {
                    if (cameraImageUri != null) {
                        results = new Uri[]{cameraImageUri};
                    }
                } else {
                    Uri uri = data.getData();
                    if (uri != null) {
                        results = new Uri[]{uri};
                    } else if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    }
                }
            }
            fileUploadCallback.onReceiveValue(results);
            fileUploadCallback = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQ && pendingPermissionRequest != null) {
            List<String> grantedList = new ArrayList<>();
            for (String res : pendingPermissionRequest.getResources()) {
                if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res) &&
                        checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    grantedList.add(PermissionRequest.RESOURCE_AUDIO_CAPTURE);
                }
                if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res) &&
                        checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    grantedList.add(PermissionRequest.RESOURCE_VIDEO_CAPTURE);
                }
            }
            if (!grantedList.isEmpty()) {
                pendingPermissionRequest.grant(grantedList.toArray(new String[0]));
            } else {
                pendingPermissionRequest.deny();
            }
            pendingPermissionRequest = null;
        }
    }

    private File createTempImageFile() {
        String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        File storageDir = new File(getCacheDir(), "images");
        if (!storageDir.exists()) {
            storageDir.mkdirs();
        }
        try {
            return File.createTempFile("NEXORA_IMG_" + timeStamp + "_", ".jpg", storageDir);
        } catch (Exception e) {
            return new File(storageDir, "NEXORA_IMG_" + timeStamp + ".jpg");
        }
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_REQ);
            }
        }
    }

    @Override
    protected void onDestroy() {
        if (webAppInterface != null) {
            webAppInterface.destroy();
        }
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
