package ai.nexora.myai

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.view.View
import android.webkit.ConsoleMessage
import android.webkit.PermissionRequest
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import ai.nexora.myai.bridge.WebAppInterface
import ai.nexora.myai.databinding.ActivityMainBinding
import ai.nexora.myai.security.SecureStorageManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var webAppInterface: WebAppInterface
    private lateinit var secureStorage: SecureStorageManager

    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null
    private var cameraImageUri: Uri? = null
    private var backPressedOnce = false
    private val backHandler = Handler(Looper.getMainLooper())
    private var pendingPermissionRequest: PermissionRequest? = null

    // Permission Launchers
    private val requestMediaPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val grantedMic = permissions[Manifest.permission.RECORD_AUDIO] ?: false
        val grantedCamera = permissions[Manifest.permission.CAMERA] ?: false
        
        pendingPermissionRequest?.let { request ->
            val grantedResources = mutableListOf<String>()
            if (grantedMic && request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                grantedResources.add(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
            }
            if (grantedCamera && request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                grantedResources.add(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
            }
            if (grantedResources.isNotEmpty()) {
                request.grant(grantedResources.toTypedArray())
            } else {
                request.deny()
            }
            pendingPermissionRequest = null
        }
    }

    private val filePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (fileUploadCallback == null) return@registerForActivityResult

        var results: Array<Uri>? = null
        if (result.resultCode == RESULT_OK) {
            val data = result.data
            if (data == null || data.data == null) {
                // Check if camera captured an image
                cameraImageUri?.let { uri ->
                    results = arrayOf(uri)
                }
            } else {
                data.data?.let { uri ->
                    results = arrayOf(uri)
                } ?: run {
                    val clipData = data.clipData
                    if (clipData != null) {
                        val uriList = ArrayList<Uri>()
                        for (i in 0 until clipData.itemCount) {
                            uriList.add(clipData.getItemAt(i).uri)
                        }
                        results = uriList.toTypedArray()
                    }
                }
            }
        }
        fileUploadCallback?.onReceiveValue(results)
        fileUploadCallback = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // 1. Android 12+ Splash Screen integration
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        secureStorage = SecureStorageManager.getInstance(this)
        webAppInterface = WebAppInterface(this, binding.webView)

        setupWindowInsets()
        setupBackNavigation()
        setupWebView()
        setupSwipeRefresh()
        setupErrorHandling()

        // Notification permission for Android 13+
        requestNotificationPermission()

        // Load Application
        loadApp()
    }

    private fun setupWindowInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(binding.rootContainer) { view, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            WindowInsetsCompat.CONSUMED
        }
    }

    private fun setupBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // First: Check if Web application can handle back (e.g. close open drawer, close modal)
                binding.webView.evaluateJavascript("window.handleAndroidBack ? window.handleAndroidBack() : false") { result ->
                    val handledByWeb = result == "true"
                    if (!handledByWeb) {
                        if (binding.webView.canGoBack()) {
                            binding.webView.goBack()
                        } else {
                            // Double back to exit
                            if (backPressedOnce) {
                                isEnabled = false
                                onBackPressedDispatcher.onBackPressed()
                            } else {
                                backPressedOnce = true
                                Toast.makeText(this@MainActivity, getString(R.string.exit_confirm_toast), Toast.LENGTH_SHORT).show()
                                backHandler.postDelayed({ backPressedOnce = false }, 2000)
                            }
                        }
                    }
                }
            }
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val webView = binding.webView
        val settings = webView.settings

        settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mediaPlaybackRequiresUserGesture = false
            useWideViewPort = true
            loadWithOverviewMode = true
            displayZoomControls = false
            builtInZoomControls = false
            setSupportZoom(false)
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            userAgentString = "${settings.userAgentString} MY_AI_ANDROID_APP/${BuildConfig.VERSION_NAME}"
        }

        // Add Native JavaScript Bridge
        webView.addJavascriptInterface(webAppInterface, "AndroidBridge")

        // Custom WebChromeClient for Camera/File upload and WebKit Permissions
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.progressBar.progress = newProgress
                } else {
                    binding.progressBar.visibility = View.GONE
                    binding.swipeRefresh.isRefreshing = false
                }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                fileUploadCallback?.onReceiveValue(null)
                fileUploadCallback = filePathCallback

                launchUnifiedFilePicker(fileChooserParams)
                return true
            }

            override fun onPermissionRequest(request: PermissionRequest?) {
                if (request == null) return
                val resources = request.resources
                val neededPermissions = mutableListOf<String>()

                if (resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                    if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                        neededPermissions.add(Manifest.permission.RECORD_AUDIO)
                    }
                }
                if (resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                    if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                        neededPermissions.add(Manifest.permission.CAMERA)
                    }
                }

                if (neededPermissions.isEmpty()) {
                    request.grant(resources)
                } else {
                    pendingPermissionRequest = request
                    requestMediaPermissionLauncher.launch(neededPermissions.toTypedArray())
                }
            }

            override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                return super.onConsoleMessage(consoleMessage)
            }
        }

        // Custom WebViewClient for Security & URL Navigation
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url ?: return false
                val scheme = url.scheme?.lowercase(Locale.ROOT) ?: ""
                val host = url.host?.lowercase(Locale.ROOT) ?: ""

                // Handle mailto:, tel:, market:
                if (scheme == "mailto" || scheme == "tel" || scheme == "market") {
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, url))
                    } catch (e: ActivityNotFoundException) {
                        Toast.makeText(this@MainActivity, "No app available to handle this action", Toast.LENGTH_SHORT).show()
                    }
                    return true
                }

                // Internal app pages stay within the WebView
                if (url.toString().startsWith("file:///android_asset/")) {
                    return false
                }

                // Check external domains vs server domain
                val serverUri = Uri.parse(secureStorage.getServerUrl())
                if (host.isNotEmpty() && !host.equals(serverUri.host, ignoreCase = true) && !host.contains("nexora.ai") && !host.contains("myai.com") && !host.contains("127.0.0.1") && !host.contains("10.0.2.2")) {
                    // Open external links in device browser
                    val browserIntent = Intent(Intent.ACTION_VIEW, url)
                    startActivity(browserIntent)
                    return true
                }

                return false
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                binding.errorView.visibility = View.GONE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                binding.errorView.visibility = View.GONE
                // Sync token from KeyStore to web session on finish
                val token = secureStorage.getAuthToken()
                if (!token.isNullOrBlank()) {
                    view?.evaluateJavascript("if (typeof TokenManager !== 'undefined') { TokenManager.setToken('$token'); }", null)
                }
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) {
                    showErrorState(getString(R.string.error_server_title), getString(R.string.error_server_desc))
                }
            }

            override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, error: SslError?) {
                if (BuildConfig.STRICT_HTTPS) {
                    // Strict SSL enforcement for Production / Play Store builds
                    handler?.cancel()
                    showErrorState(getString(R.string.error_ssl_title), getString(R.string.error_ssl_desc))
                } else {
                    // Allowed in debug builds for local testing
                    handler?.proceed()
                }
            }
        }
    }

    private fun setupSwipeRefresh() {
        binding.swipeRefresh.setColorSchemeColors(
            ContextCompat.getColor(this, R.color.primary),
            ContextCompat.getColor(this, R.color.secondary)
        )
        binding.swipeRefresh.setProgressBackgroundColorSchemeColor(
            ContextCompat.getColor(this, R.color.surface_dark)
        )
        binding.swipeRefresh.setOnRefreshListener {
            binding.webView.reload()
        }
    }

    private fun setupErrorHandling() {
        binding.btnRetry.setOnClickListener {
            binding.errorView.visibility = View.GONE
            loadApp()
        }
    }

    private fun showErrorState(title: String, description: String) {
        binding.errorTitle.text = title
        binding.errorDescription.text = description
        binding.errorView.visibility = View.VISIBLE
        binding.swipeRefresh.isRefreshing = false
    }

    private fun loadApp() {
        // Load embedded mobile app assets
        binding.webView.loadUrl("file:///android_asset/app.html")
    }

    private fun launchUnifiedFilePicker(params: WebChromeClient.FileChooserParams?) {
        val intents = ArrayList<Intent>()

        // 1. Camera photo capture intent
        val takePictureIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        try {
            val photoFile = createTempImageFile()
            cameraImageUri = FileProvider.getUriForFile(
                this,
                "${applicationContext.packageName}.fileprovider",
                photoFile
            )
            takePictureIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraImageUri)
            intents.add(takePictureIntent)
        } catch (e: Exception) {
            cameraImageUri = null
        }

        // 2. Document & Image picker intent
        val contentSelectionIntent = Intent(Intent.ACTION_GET_CONTENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(Intent.EXTRA_MIME_TYPES, arrayOf(
                "image/*",
                "application/pdf",
                "text/plain",
                "text/csv",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "audio/*"
            ))
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
        }

        val chooserIntent = Intent(Intent.ACTION_CHOOSER).apply {
            putExtra(Intent.EXTRA_INTENT, contentSelectionIntent)
            putExtra(Intent.EXTRA_TITLE, "Select Document or Photo")
            if (intents.isNotEmpty()) {
                putExtra(Intent.EXTRA_INITIAL_INTENTS, intents.toTypedArray())
            }
        }

        filePickerLauncher.launch(chooserIntent)
    }

    private fun createTempImageFile(): File {
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val storageDir = File(cacheDir, "images").apply { mkdirs() }
        return File.createTempFile("NEXORA_CAM_${timeStamp}_", ".jpg", storageDir)
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                registerForActivityResult(ActivityResultContracts.RequestPermission()) {}.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    override fun onDestroy() {
        webAppInterface.destroy()
        binding.webView.destroy()
        super.onDestroy()
    }
}
