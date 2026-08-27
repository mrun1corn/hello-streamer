package com.hellostreamer.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = CyanNeon,
    secondary = AmberAccent,
    tertiary = RedLive,
    background = BgDark,
    surface = SurfaceDark,
    surfaceVariant = Surface2Dark,
    onPrimary = BgDark,
    onSecondary = BgDark,
    onBackground = TextLight,
    onSurface = TextLight,
    outline = BorderDark,
    outlineVariant = Border2Dark
)

@Composable
fun HelloStreamerTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content
    )
}
