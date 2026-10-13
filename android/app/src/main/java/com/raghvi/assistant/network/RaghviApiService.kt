package com.raghvi.assistant.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.POST
import retrofit2.http.Query

@Serializable
data class StatusResponse(val status: String)

@Serializable
data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    val name: String? = null,
    val phone: String? = null
)

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
    val token_type: String = "bearer"
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

// M2 — Chat Models
@Serializable
data class ChatSendRequest(
    val content: String
)

@Serializable
data class ChatSendResponse(
    val user_message: String,
    val assistant_message: String,
    val tokens_used: Int? = null
)

@Serializable
data class ChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val tokens_used: Int? = null,
    val created_at: String
)

@Serializable
data class ChatHistoryResponse(
    val messages: List<ChatMessage> = emptyList(),
    val total: Int = 0,
    val has_more: Boolean = false
)

@Serializable
data class ConversationMetadata(
    val id: String,
    val user_id: String,
    val title: String,
    val created_at: String,
    val updated_at: String,
    val message_count: Int = 0
)

// M3 — Memory Models
@Serializable
data class MemoryItem(
    val id: String,
    val content: String,
    val is_sensitive: Boolean = false,
    val is_approved: Boolean = false,
    val created_at: String,
    val updated_at: String
)

@Serializable
data class MemoryListResponse(
    val memories: List<MemoryItem> = emptyList(),
    val total: Int = 0,
    val approved_count: Int = 0,
    val pending_count: Int = 0,
    val deleted_count: Int = 0
)

@Serializable
data class MemoryCreateRequest(
    val content: String
)

@Serializable
data class MemoryApprovalRequest(
    val approved: Boolean
)

// M4 — Task Models
@Serializable
data class TaskItem(
    val id: String,
    val title: String,
    val description: String? = null,
    val status: String = "pending",
    val priority: String = "medium",
    val created_at: String,
    val updated_at: String,
    val due_date: String? = null,
    val completed_at: String? = null,
    val tags: String? = null,
    val auto_extracted: Boolean = false
)

@Serializable
data class TaskListResponse(
    val tasks: List<TaskItem> = emptyList(),
    val total: Int = 0,
    val pending_count: Int = 0,
    val in_progress_count: Int = 0,
    val completed_count: Int = 0
)

@Serializable
data class TaskCreateRequest(
    val title: String,
    val description: String? = null,
    val priority: String = "medium",
    val due_date: String? = null,
    val tags: String? = null
)

@Serializable
data class TaskUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val status: String? = null,
    val priority: String? = null,
    val due_date: String? = null,
    val tags: List<String>? = null
)

interface RaghviApiService {
    @GET("/health")
    suspend fun getHealth(): StatusResponse

    @GET("/ready")
    suspend fun getReady(): StatusResponse

    // M1 — Auth
    @POST("/auth/register")
    suspend fun register(@Body request: RegisterRequest): AuthTokens

    @POST("/auth/signup")
    suspend fun signup(@Body request: RegisterRequest): AuthTokens

    @POST("/auth/login")
    suspend fun login(@Body request: LoginRequest): AuthTokens

    @POST("/auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): AuthTokens

    @POST("/auth/logout")
    suspend fun logout(@Body request: LogoutRequest)

    @POST("/auth/revoke-all")
    suspend fun revokeAll()

    @GET("/auth/me")
    suspend fun getMe(): UserProfile

    // M2 — Chat
    @POST("/chat/send")
    suspend fun sendMessage(@Body request: ChatSendRequest): ChatSendResponse

    @GET("/chat/history")
    suspend fun getChatHistory(
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): ChatHistoryResponse

    @GET("/chat/")
    suspend fun getConversation(): ConversationMetadata

    // M3 — Memories
    @GET("/memories")
    suspend fun getApprovedMemories(@Query("limit") limit: Int = 50): MemoryListResponse

    @GET("/memories/pending")
    suspend fun getPendingMemories(): MemoryListResponse

    @POST("/memories")
    suspend fun createMemory(@Body request: MemoryCreateRequest)

    @POST("/memories/{id}/approve")
    suspend fun approveMemory(
        @Path("id") id: String,
        @Body request: MemoryApprovalRequest
    ): MemoryItem

    @DELETE("/memories/{id}")
    suspend fun deleteMemory(@Path("id") id: String)

    // M4 — Tasks
    @GET("/tasks")
    suspend fun getTasks(@Query("status") status: String? = null): TaskListResponse

    @POST("/tasks")
    suspend fun createTask(@Body request: TaskCreateRequest): TaskItem

    @PATCH("/tasks/{id}")
    suspend fun updateTask(
        @Path("id") id: String,
        @Body request: TaskUpdateRequest
    ): TaskItem

    @POST("/tasks/{id}/complete")
    suspend fun completeTask(@Path("id") id: String): TaskItem

    @DELETE("/tasks/{id}")
    suspend fun deleteTask(@Path("id") id: String)

    // M5 — Briefings
    @GET("/briefings/today")
    suspend fun getTodayBriefing(): BriefingResponse

    @GET("/briefings/preferences")
    suspend fun getBriefingPreferences(): BriefingPreferences

    @PATCH("/briefings/preferences")
    suspend fun updateBriefingPreferences(@Body prefs: BriefingPreferences): BriefingPreferences

    // M6 — Safe Actions
    @POST("/actions/propose")
    suspend fun proposeAction(@Body request: ActionProposalRequest): ActionProposalResponse

    @GET("/actions/{id}")
    suspend fun getActionProposal(@Path("id") id: String): ActionProposalResponse

    @POST("/actions/{id}/confirm")
    suspend fun confirmAction(
        @Path("id") id: String,
        @Body request: ActionConfirmationRequest
    ): ActionProposalResponse

    // M7 — Privacy & Lifecycle
    @GET("/users/export")
    suspend fun exportUserData(): JsonObject

    @DELETE("/users/me")
    suspend fun deleteAccount()
}

// M5 Data Models
@Serializable
data class BriefingPreferences(
    val opt_in: Boolean = false,
    val quiet_hours_start: Int = 22,
    val quiet_hours_end: Int = 7,
    val morning_time: String = "08:00"
)

@Serializable
data class BriefingTaskItem(
    val id: String,
    val title: String,
    val priority: String = "medium",
    val due_date: String? = null
)

@Serializable
data class BriefingResponse(
    val date: String,
    val greeting: String,
    val summary: String,
    val pending_tasks_count: Int = 0,
    val overdue_tasks_count: Int = 0,
    val tasks: List<BriefingTaskItem> = emptyList(),
    val is_quiet_hours: Boolean = false,
    val opted_in: Boolean = false
)

// M6 Data Models
@Serializable
data class ActionProposalRequest(
    val action_type: String,
    val parameters: JsonObject = JsonObject(emptyMap()),
    val description: String? = null
)

@Serializable
data class ActionConfirmationRequest(
    val confirmed: Boolean
)

@Serializable
data class ActionProposalResponse(
    val id: String,
    val user_id: String,
    val action_type: String,
    val parameters: JsonObject = JsonObject(emptyMap()),
    val status: String,
    val description: String? = null,
    val expires_at: String,
    val created_at: String,
    val confirmed_at: String? = null
)

