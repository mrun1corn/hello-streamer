package com.hellostreamer.app.model

import com.google.gson.annotations.SerializedName

data class Channel(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("group") val group: String,
    @SerializedName("logo") val logo: String = "",
    @SerializedName("url") val url: String,
    @SerializedName("backups") val backups: List<String> = emptyList()
) {
    val allUrls: List<String>
        get() = listOf(url) + backups
}
