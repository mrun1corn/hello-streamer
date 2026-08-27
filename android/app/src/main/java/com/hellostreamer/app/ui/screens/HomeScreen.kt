package com.hellostreamer.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hellostreamer.app.data.ChannelRepository
import com.hellostreamer.app.model.Channel
import com.hellostreamer.app.player.PlaybackState
import com.hellostreamer.app.player.StreamPlayer
import com.hellostreamer.app.ui.components.ChannelCard
import com.hellostreamer.app.ui.components.VideoPlayerView
import com.hellostreamer.app.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(
    channelRepository: ChannelRepository,
    streamPlayer: StreamPlayer,
    onEnterPiP: () -> Unit,
    onToggleFullscreen: () -> Unit,
    modifier: Modifier = Modifier
) {
    val coroutineScope = rememberCoroutineScope()

    var channels by remember { mutableStateOf<List<Channel>>(emptyList()) }
    var selectedGroup by remember { mutableStateOf("All") }
    var searchQuery by remember { mutableStateOf("") }
    var isSyncing by remember { mutableStateOf(false) }

    val favorites by channelRepository.favoritesFlow.collectAsState(initial = emptySet())
    val recents by channelRepository.recentsFlow.collectAsState(initial = emptyList())

    val playbackState by streamPlayer.playbackState.collectAsState()
    val currentChannel by streamPlayer.currentChannel.collectAsState()
    val currentBackupIndex by streamPlayer.currentBackupIndex.collectAsState()

    // Initial load & remote sync
    LaunchedEffect(Unit) {
        channels = channelRepository.loadChannels()
        coroutineScope.launch {
            isSyncing = true
            val updated = channelRepository.syncRemoteChannels()
            if (updated != null) {
                channels = updated
            }
            isSyncing = false
        }
    }

    // Dynamic category tabs
    val dynamicGroups = remember(channels) {
        listOf("All", "⭐ Favorites", "🕒 Recent") + channels.map { it.group }.distinct().filter { it.isNotBlank() }
    }

    // Filtered channels list
    val filteredChannels = remember(channels, selectedGroup, searchQuery, favorites, recents) {
        val baseList = when (selectedGroup) {
            "⭐ Favorites" -> channels.filter { favorites.contains(it.id) }
            "🕒 Recent" -> recents.mapNotNull { id -> channels.find { it.id == id } }
            "All" -> channels
            else -> channels.filter { it.group == selectedGroup }
        }

        val q = searchQuery.trim().lowercase()
        if (q.isEmpty()) {
            baseList
        } else {
            baseList.filter {
                it.name.lowercase().contains(q) || it.group.lowercase().contains(q)
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BgDark)
    ) {
        // Video Viewport Area (16:9 Aspect Ratio)
        VideoPlayerView(
            streamPlayer = streamPlayer,
            playbackState = playbackState,
            currentChannel = currentChannel,
            currentBackupIndex = currentBackupIndex,
            isFavorite = currentChannel?.let { favorites.contains(it.id) } ?: false,
            onToggleFavorite = {
                currentChannel?.let {
                    coroutineScope.launch { channelRepository.toggleFavorite(it.id) }
                }
            },
            onEnterPiP = onEnterPiP,
            onToggleFullscreen = onToggleFullscreen,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f)
        )

        // Header (Logo, Live Indicator, Channel Counter)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(SurfaceDark)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "Hello ",
                    color = CyanNeon,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "Streamer",
                    color = AmberAccent,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(RedLive)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = "LIVE",
                    color = RedLive,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "${channels.size} channels",
                    color = TextMuted,
                    fontSize = 11.sp
                )
                IconButton(
                    onClick = {
                        coroutineScope.launch {
                            isSyncing = true
                            val updated = channelRepository.syncRemoteChannels()
                            if (updated != null) channels = updated
                            isSyncing = false
                        }
                    },
                    modifier = Modifier.size(28.dp).padding(start = 4.dp)
                ) {
                    if (isSyncing) {
                        CircularProgressIndicator(color = CyanNeon, modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(imageVector = Icons.Default.Refresh, contentDescription = "Sync", tint = TextMuted, modifier = Modifier.size(16.dp))
                    }
                }
            }
        }

        // Search Input Bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search channels…", color = TextDark, fontSize = 13.sp) },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search", tint = TextDark) },
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(onClick = { searchQuery = "" }) {
                        Icon(Icons.Default.Close, contentDescription = "Clear", tint = TextDark)
                    }
                }
            },
            singleLine = true,
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = Surface2Dark,
                unfocusedContainerColor = Surface2Dark,
                focusedBorderColor = CyanNeon,
                unfocusedBorderColor = BorderDark,
                focusedTextColor = TextLight,
                unfocusedTextColor = TextLight
            ),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
        )

        // Horizontal Category Tabs
        LazyRow(
            contentPadding = PaddingValues(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(bottom = 8.dp)
        ) {
            items(dynamicGroups) { group ->
                val isSelected = (group == selectedGroup)
                Surface(
                    color = if (isSelected) CyanDim else Surface2Dark,
                    shape = RoundedCornerShape(20.dp),
                    border = androidx.compose.foundation.BorderStroke(
                        width = 1.dp,
                        color = if (isSelected) CyanNeon else BorderDark
                    ),
                    modifier = Modifier.clickable {
                        selectedGroup = group
                    }
                ) {
                    Text(
                        text = group,
                        color = if (isSelected) CyanNeon else TextMuted,
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp)
                    )
                }
            }
        }

        // Channel List
        if (filteredChannels.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (selectedGroup == "⭐ Favorites") "No favorite channels added yet." else "No channels found",
                    color = TextDark,
                    fontSize = 13.sp
                )
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.weight(1f)
            ) {
                items(
                    items = filteredChannels,
                    key = { it.id }
                ) { channel ->
                    val isSelected = (currentChannel?.id == channel.id)
                    val isFav = favorites.contains(channel.id)

                    ChannelCard(
                        channel = channel,
                        isSelected = isSelected,
                        isFavorite = isFav,
                        onClick = {
                            streamPlayer.playChannel(channel, 0)
                            coroutineScope.launch { channelRepository.addRecent(channel.id) }
                        },
                        onToggleFavorite = {
                            coroutineScope.launch { channelRepository.toggleFavorite(channel.id) }
                        }
                    )
                }
            }
        }
    }
}
