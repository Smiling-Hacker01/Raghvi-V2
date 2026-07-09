package com.raghvi.assistant.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

@Serializable
data class StatusResponse(val status: String)

@Serializable
data class LoginRequest(val username: String, val password: String)

@Serializable
data class RefreshRequest(val refresh_token: String)

@Serializable
data class LogoutRequest(val refresh_token: String)

@Serializable
data class AuthTokens(
    val access_token: String,
    val refresh_token: String,
    val token_type: String
)

@Serializable
data class UserProfile(
    val id: String,
    val username: String,
    val email: String,
    val name: String? = null,
    val phone: String? = null,
    val preferences: JsonObject = JsonObject(emptyMap())
)

interface RaghviApiService {
    @GET("/health")
    suspend fun getHealth(): StatusResponse

    @GET("/ready")
    suspend fun getReady(): StatusResponse

    @POST("/auth/login")
    suspend fun login(@Body request: LoginRequest): AuthTokens

    @POST("/auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): AuthTokens

    @POST("/auth/logout")
    suspend fun logout(@Body request: LogoutRequest)

    @GET("/auth/me")
    suspend fun getMe(): UserProfile
}
