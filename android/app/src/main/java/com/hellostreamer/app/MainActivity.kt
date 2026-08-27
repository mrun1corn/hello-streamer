package com.hellostreamer.app

import android.app.PictureInPictureParams
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.util.Rational
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.hellostreamer.app.data.ChannelRepository
import com.hellostreamer.app.player.StreamPlayer
import com.hellostreamer.app.ui.screens.HomeScreen
import com.hellostreamer.app.ui.theme.BgDark
import com.hellostreamer.app.ui.theme.HelloStreamerTheme

class MainActivity : ComponentActivity() {

    private lateinit var channelRepository: ChannelRepository
    private lateinit var streamPlayer: StreamPlayer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        channelRepository = ChannelRepository(applicationContext)
        streamPlayer = StreamPlayer(applicationContext)

        setContent {
            HelloStreamerTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = BgDark
                ) {
                    HomeScreen(
                        channelRepository = channelRepository,
                        streamPlayer = streamPlayer,
                        onEnterPiP = { enterPiPMode() },
                        onToggleFullscreen = { toggleFullscreenOrientation() }
                    )
                }
            }
        }
    }

    private fun enterPiPMode() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val params = PictureInPictureParams.Builder()
                .setAspectRatio(Rational(16, 9))
                .build()
            enterPictureInPictureMode(params)
        }
    }

    private fun toggleFullscreenOrientation() {
        requestedOrientation = if (resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE) {
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        } else {
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        }
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (streamPlayer.currentChannel.value != null) {
            enterPiPMode()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        streamPlayer.release()
    }
}
