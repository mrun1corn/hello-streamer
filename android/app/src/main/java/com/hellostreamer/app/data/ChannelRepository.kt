package com.hellostreamer.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.hellostreamer.app.model.Channel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

private val Context.dataStore by preferencesDataStore(name = "hello_streamer_prefs")

class ChannelRepository(private val context: Context) {
    private val gson = Gson()
    private val cachedFile = File(context.filesDir, "channels_cache.json")

    private val favoritesKey = stringSetPreferencesKey("favorites")
    private val recentsKey = stringPreferencesKey("recents")

    val favoritesFlow: Flow<Set<Int>> = context.dataStore.data.map { prefs ->
        prefs[favoritesKey]?.mapNotNull { it.toIntOrNull() }?.toSet() ?: emptySet()
    }

    val recentsFlow: Flow<List<Int>> = context.dataStore.data.map { prefs ->
        val json = prefs[recentsKey] ?: "[]"
        try {
            val type = object : TypeToken<List<Int>>() {}.type
            gson.fromJson<List<Int>>(json, type) ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    suspend fun toggleFavorite(channelId: Int) {
        context.dataStore.edit { prefs ->
            val current = prefs[favoritesKey]?.toMutableSet() ?: mutableSetOf()
            val idStr = channelId.toString()
            if (current.contains(idStr)) {
                current.remove(idStr)
            } else {
                current.add(idStr)
            }
            prefs[favoritesKey] = current
        }
    }

    suspend fun addRecent(channelId: Int) {
        context.dataStore.edit { prefs ->
            val json = prefs[recentsKey] ?: "[]"
            val currentList = try {
                val type = object : TypeToken<List<Int>>() {}.type
                gson.fromJson<List<Int>>(json, type)?.toMutableList() ?: mutableListOf()
            } catch (e: Exception) {
                mutableListOf()
            }
            currentList.remove(channelId)
            currentList.add(0, channelId)
            val trimmed = currentList.take(30)
            prefs[recentsKey] = gson.toJson(trimmed)
        }
    }

    suspend fun loadChannels(): List<Channel> = withContext(Dispatchers.IO) {
        // 1. Try loading cached file from previous remote sync
        if (cachedFile.exists()) {
            try {
                val json = cachedFile.readText(Charsets.UTF_8)
                val type = object : TypeToken<List<Channel>>() {}.type
                val parsed: List<Channel> = gson.fromJson(json, type)
                if (parsed.isNotEmpty()) return@withContext parsed
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // 2. Load from pre-seeded asset
        try {
            val assetJson = context.assets.open("channels.json").bufferedReader().use { it.readText() }
            val type = object : TypeToken<List<Channel>>() {}.type
            gson.fromJson<List<Channel>>(assetJson, type) ?: emptyList()
        } catch (e: Exception) {
            e.printStackTrace()
            emptyList()
        }
    }

    suspend fun syncRemoteChannels(): List<Channel>? = withContext(Dispatchers.IO) {
        val remoteUrl = "https://raw.githubusercontent.com/mrun1corn/hello-streamer/main/channels.json"
        try {
            val conn = URL(remoteUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "HelloStreamer-Android")

            if (conn.responseCode == HttpURLConnection.HTTP_OK) {
                val json = conn.inputStream.bufferedReader().use { it.readText() }
                val type = object : TypeToken<List<Channel>>() {}.type
                val parsed: List<Channel> = gson.fromJson(json, type)
                if (parsed.isNotEmpty()) {
                    cachedFile.writeText(json, Charsets.UTF_8)
                    return@withContext parsed
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        null
    }
}
