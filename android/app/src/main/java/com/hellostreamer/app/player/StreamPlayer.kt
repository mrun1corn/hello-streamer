package com.hellostreamer.app.player

import android.content.Context
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import com.hellostreamer.app.model.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed class PlaybackState {
    object Idle : PlaybackState()
    object Buffering : PlaybackState()
    object Playing : PlaybackState()
    data class Error(val message: String, val canRetry: Boolean, val hasNextBackup: Boolean) : PlaybackState()
}

@OptIn(UnstableApi::class)
class StreamPlayer(private val context: Context) {

    private val _playbackState = MutableStateFlow<PlaybackState>(PlaybackState.Idle)
    val playbackState: StateFlow<PlaybackState> = _playbackState.asStateFlow()

    private val _currentChannel = MutableStateFlow<Channel?>(null)
    val currentChannel: StateFlow<Channel?> = _currentChannel.asStateFlow()

    private val _currentBackupIndex = MutableStateFlow(0)
    val currentBackupIndex: StateFlow<Int> = _currentBackupIndex.asStateFlow()

    val exoPlayer: ExoPlayer by lazy {
        val loadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(
                /* minBufferMs = */ 15_000,
                /* maxBufferMs = */ 45_000,
                /* bufferForPlaybackMs = */ 1_500,
                /* bufferForPlaybackAfterRebufferMs = */ 3_000
            )
            .build()

        ExoPlayer.Builder(context)
            .setLoadControl(loadControl)
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(C.WAKE_MODE_NETWORK)
            .build().apply {
                playWhenReady = true
                addListener(object : Player.Listener {
                    override fun onPlaybackStateChanged(state: Int) {
                        when (state) {
                            Player.STATE_BUFFERING -> _playbackState.value = PlaybackState.Buffering
                            Player.STATE_READY -> _playbackState.value = PlaybackState.Playing
                            Player.STATE_ENDED -> _playbackState.value = PlaybackState.Idle
                            Player.STATE_IDLE -> {
                                if (_playbackState.value !is PlaybackState.Error) {
                                    _playbackState.value = PlaybackState.Idle
                                }
                            }
                        }
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        error.printStackTrace()
                        handleError("Playback Error: ${error.message ?: "Offline"}")
                    }
                })
            }
    }

    private val dataSourceFactory = DefaultHttpDataSource.Factory()
        .setUserAgent("HelloStreamer-Android/1.0 (Linux; Android)")
        .setConnectTimeoutMs(8000)
        .setReadTimeoutMs(8000)
        .setAllowCrossProtocolRedirects(true)

    fun playChannel(channel: Channel, backupIndex: Int = 0) {
        val urls = channel.allUrls
        if (backupIndex >= urls.size) {
            _playbackState.value = PlaybackState.Error(
                message = "All ${urls.size} stream sources for ${channel.name} are offline.",
                canRetry = true,
                hasNextBackup = false
            )
            return
        }

        _currentChannel.value = channel
        _currentBackupIndex.value = backupIndex
        _playbackState.value = PlaybackState.Buffering

        val targetUrl = urls[backupIndex]
        val mediaItem = MediaItem.fromUri(targetUrl)
        val mediaSource = HlsMediaSource.Factory(dataSourceFactory)
            .setAllowChunklessPreparation(true)
            .createMediaSource(mediaItem)

        exoPlayer.setMediaSource(mediaSource)
        exoPlayer.prepare()
        exoPlayer.play()
    }

    private fun handleError(reason: String) {
        val channel = _currentChannel.value
        val currentIndex = _currentBackupIndex.value

        if (channel != null && currentIndex + 1 < channel.allUrls.size) {
            // Auto-failover to next backup stream
            playChannel(channel, currentIndex + 1)
        } else {
            _playbackState.value = PlaybackState.Error(
                message = reason,
                canRetry = true,
                hasNextBackup = false
            )
        }
    }

    fun retry() {
        val channel = _currentChannel.value ?: return
        playChannel(channel, _currentBackupIndex.value)
    }

    fun tryNextBackup() {
        val channel = _currentChannel.value ?: return
        playChannel(channel, _currentBackupIndex.value + 1)
    }

    fun pause() {
        exoPlayer.pause()
    }

    fun resume() {
        exoPlayer.play()
    }

    fun release() {
        exoPlayer.release()
    }
}
