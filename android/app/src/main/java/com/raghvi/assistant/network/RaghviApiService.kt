package com.raghvi.assistant.network

import kotlinx.serialization.Serializable
import retrofit2.http.GET

@Serializable
data class StatusResponse(val status: String)

interface RaghviApiService {
    @GET("/health")
    suspend fun getHealth(): StatusResponse

    @GET("/ready")
    suspend fun getReady(): StatusResponse
}