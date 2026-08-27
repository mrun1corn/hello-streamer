# Proguard rules for Hello Streamer
-keep class com.hellostreamer.app.model.** { *; }
-keepclassmembers class * {
    @androidx.media3.common.util.UnstableApi *;
}
