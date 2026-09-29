# Proguard / R8 Optimization Rules for NEXORA AI Android App

# Keep JavascriptInterface methods for WebKit bridge
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keep class ai.nexora.myai.bridge.** { *; }

# Keep models for JSON serialization with Gson
-keepattributes Signature
-keepattributes *Annotation*
-keepclassmembers enum * { *; }
-keep class com.google.gson.** { *; }
-keep class ai.nexora.myai.models.** { *; }

# OkHttp & Coroutines rules
-dontwarn okhttp3.**
-dontwarn okio.**
-keepnames class okhttp3.internal.publicsuffix.PublicSuffixDatabase
-dontwarn kotlinx.coroutines.**

# AndroidX Security Crypto & KeyStore
-keep class androidx.security.crypto.** { *; }

# WebKit & Material Design
-keep class androidx.webkit.** { *; }
-keep class com.google.android.material.** { *; }
-dontwarn com.google.android.material.**

# Remove Log calls in Release Builds for maximum security & performance
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
}
