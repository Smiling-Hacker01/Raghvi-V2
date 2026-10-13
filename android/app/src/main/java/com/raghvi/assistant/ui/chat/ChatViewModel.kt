package com.raghvi.assistant.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.ChatMessage
import com.raghvi.assistant.network.ChatSendRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isLoadingHistory: Boolean = false,
    val isSending: Boolean = false,
    val errorMessage: String? = null,
    val pendingMessageRetry: String? = null
)

class ChatViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
    }

    fun loadHistory() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingHistory = true, errorMessage = null) }
            try {
                val history = ApiClient.authApi.getChatHistory(limit = 50, offset = 0)
                _uiState.update {
                    it.copy(
                        messages = history.messages,
                        isLoadingHistory = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoadingHistory = false,
                        errorMessage = e.message ?: "Failed to load conversation history"
                    )
                }
            }
        }
    }

    fun sendMessage(content: String) {
        val trimmed = content.trim()
        if (trimmed.isBlank() || _uiState.value.isSending) return

        val optimisticUserMsg = ChatMessage(
            id = UUID.randomUUID().toString(),
            role = "user",
            content = trimmed,
            tokens_used = 0,
            created_at = java.time.Instant.now().toString()
        )

        _uiState.update {
            it.copy(
                messages = it.messages + optimisticUserMsg,
                isSending = true,
                errorMessage = null,
                pendingMessageRetry = null
            )
        }

        viewModelScope.launch {
            try {
                val response = ApiClient.authApi.sendMessage(ChatSendRequest(content = trimmed))
                val assistantMsg = ChatMessage(
                    id = UUID.randomUUID().toString(),
                    role = "assistant",
                    content = response.assistant_message,
                    tokens_used = response.tokens_used,
                    created_at = java.time.Instant.now().toString()
                )
                _uiState.update {
                    it.copy(
                        messages = it.messages + assistantMsg,
                        isSending = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isSending = false,
                        errorMessage = "Failed to deliver message. Tap retry to try again.",
                        pendingMessageRetry = trimmed
                    )
                }
            }
        }
    }

    fun retryFailedMessage() {
        val retryContent = _uiState.value.pendingMessageRetry ?: return
        sendMessage(retryContent)
    }

    fun dismissError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
