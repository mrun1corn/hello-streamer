package com.hellostreamer.app.ui.components

import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.hellostreamer.app.model.Channel
import com.hellostreamer.app.player.PlaybackState
import com.hellostreamer.app.player.StreamPlayer
import com.hellostreamer.app.ui.theme.*

@OptIn(UnstableApi::class)
@Composable
fun VideoPlayerView(
    streamPlayer: StreamPlayer,
    playbackState: PlaybackState,
    currentChannel: Channel?,
    currentBackupIndex: Int,
    isFavorite: Boolean,
    onToggleFavorite: () -> Unit,
    onEnterPiP: () -> Unit,
    onToggleFullscreen: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(Color.Black),
        contentAlignment = Alignment.Center
    ) {
        if (currentChannel != null) {
            AndroidView(
                factory = { context ->
                    PlayerView(context).apply {
                        player = streamPlayer.exoPlayer
                        useController = true
                        resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                        layoutParams = FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT
                        )
                    }
                },
                modifier = Modifier.fillMaxSize()
            )
        } else {
            // Idle State Placeholder
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
                modifier = Modifier.padding(24.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Tv,
                    contentDescription = "Select Channel",
                    tint = TextMuted,
                    modifier = Modifier.size(64.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = "Pick a channel to start streaming",
                    color = TextLight,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "Live TV • Sports • News • Movies • Music",
                    color = TextDark,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        // Top Controls Overlay
        if (currentChannel != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    .padding(8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Channel Title / Backup Badge
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (currentBackupIndex > 0) {
                        Surface(
                            color = AmberDim,
                            shape = RoundedCornerShape(4.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, AmberAccent),
                            modifier = Modifier.padding(end = 8.dp)
                        ) {
                            Text(
                                text = "Backup #$currentBackupIndex",
                                color = AmberAccent,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }
                    }
                }

                // Action Buttons (Favorite, PiP, Fullscreen)
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    IconButton(onClick = onToggleFavorite) {
                        Icon(
                            imageVector = if (isFavorite) Icons.Default.Star else Icons.Default.StarBorder,
                            contentDescription = "Favorite",
                            tint = if (isFavorite) AmberAccent else TextLight
                        )
                    }
                    IconButton(onClick = onEnterPiP) {
                        Icon(
                            imageVector = Icons.Default.PictureInPictureAlt,
                            contentDescription = "Picture in Picture",
                            tint = TextLight
                        )
                    }
                    IconButton(onClick = onToggleFullscreen) {
                        Icon(
                            imageVector = Icons.Default.Fullscreen,
                            contentDescription = "Fullscreen",
                            tint = TextLight
                        )
                    }
                }
            }
        }

        // Buffering Spinner
        if (playbackState is PlaybackState.Buffering) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(
                    color = CyanNeon,
                    modifier = Modifier.size(48.dp),
                    strokeWidth = 3.dp
                )
            }
        }

        // Error Card Overlay
        if (playbackState is PlaybackState.Error) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.88f))
                    .padding(24.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Stream Offline",
                        tint = RedLive,
                        modifier = Modifier.size(48.dp)
                    )
                    Text(
                        text = "Stream Unavailable",
                        color = RedLive,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = playbackState.message,
                        color = TextMuted,
                        fontSize = 12.sp,
                        textAlign = TextAlign.Center
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(
                            onClick = { streamPlayer.retry() },
                            colors = ButtonDefaults.buttonColors(containerColor = AmberAccent)
                        ) {
                            Text("Try Again", color = BgDark, fontWeight = FontWeight.Bold)
                        }
                        if (playbackState.hasNextBackup) {
                            OutlinedButton(
                                onClick = { streamPlayer.tryNextBackup() },
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = TextLight)
                            ) {
                                Text("Next Backup")
                            }
                        }
                    }
                }
            }
        }
    }
}
