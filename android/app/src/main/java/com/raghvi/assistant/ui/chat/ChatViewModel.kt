package com.raghvi.assistant.ui.chat

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.ChatMessage
import com.raghvi.assistant.network.ChatSendRequest
import com.raghvi.assistant.network.LiveGeminiVoiceRequest
import com.raghvi.assistant.voice.AudioPlayer
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
    val pendingMessageRetry: String? = null,
    val isVoiceAutoPlayEnabled: Boolean = true,
    val isLiveGeminiMode: Boolean = true,
    val isListeningVoice: Boolean = false,
    val voiceRmsLevel: Float = 0f,
    val partialVoiceText: String = "",
    val activePlayingMessageId: String? = null
)

class ChatViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
        observeAudioPlayback()
    }

    private fun observeAudioPlayback() {
        viewModelScope.launch {
            AudioPlayer.playbackState.collect { playback ->
                _uiState.update {
                    it.copy(
                        activePlayingMessageId = if (playback.isPlaying) playback.activeMessageId else null
                    )
                }
            }
        }
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

    fun clearHistory() {
        viewModelScope.launch {
            try {
                ApiClient.authApi.clearChatHistory()
                _uiState.update { it.copy(messages = emptyList()) }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to clear history: ${e.message}") }
            }
        }
    }

    fun sendMessage(content: String, context: Context? = null) {
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
                if (_uiState.value.isLiveGeminiMode) {
                    // 🌟 Live Gemini AI Chat + IndicF5 Cloned Voice
                    val historyList = _uiState.value.messages.takeLast(10).map { msg ->
                        mapOf("role" to msg.role, "content" to msg.content)
                    }

                    val liveResponse = ApiClient.authApi.sendLiveGeminiVoice(
                        LiveGeminiVoiceRequest(
                            message = trimmed,
                            mode = "chat",
                            history = historyList
                        )
                    )

                    val assistantMsg = ChatMessage(
                        id = UUID.randomUUID().toString(),
                        role = "assistant",
                        content = liveResponse.assistant_message,
                        tokens_used = 0,
                        created_at = java.time.Instant.now().toString(),
                        audio_base64 = liveResponse.audio_base64,
                        audio_provider = liveResponse.provider ?: "Gemini Live + IndicF5",
                        action_proposal = liveResponse.action_proposal
                    )

                    _uiState.update {
                        it.copy(
                            messages = it.messages + assistantMsg,
                            isSending = false
                        )
                    }

                    // Auto-play voice if enabled
                    if (_uiState.value.isVoiceAutoPlayEnabled && liveResponse.audio_base64 != null && context != null) {
                        AudioPlayer.playBase64(context, assistantMsg.id, liveResponse.audio_base64)
                    }

                } else {
                    // 💬 Authenticated /chat/send-with-voice API
                    val response = ApiClient.authApi.sendMessageWithVoice(ChatSendRequest(content = trimmed))
                    val audioBase64 = response.audio?.data_base64
                    val provider = response.audio?.provider ?: "Raghvi Voice"

                    val assistantMsg = ChatMessage(
                        id = UUID.randomUUID().toString(),
                        role = "assistant",
                        content = response.assistant_message,
                        tokens_used = response.tokens_used,
                        created_at = java.time.Instant.now().toString(),
                        audio_base64 = audioBase64,
                        audio_provider = provider,
                        action_proposal = response.action_proposal
                    )

                    _uiState.update {
                        it.copy(
                            messages = it.messages + assistantMsg,
                            isSending = false
                        )
                    }

                    // Auto-play voice if enabled
                    if (_uiState.value.isVoiceAutoPlayEnabled && audioBase64 != null && context != null) {
                        AudioPlayer.playBase64(context, assistantMsg.id, audioBase64)
                    }
                }
            } catch (e: Exception) {
                // If live Gemini mode fails, fallback to standard send
                try {
                    val fallback = ApiClient.authApi.sendMessage(ChatSendRequest(content = trimmed))
                    val assistantMsg = ChatMessage(
                        id = UUID.randomUUID().toString(),
                        role = "assistant",
                        content = fallback.assistant_message,
                        tokens_used = fallback.tokens_used,
                        created_at = java.time.Instant.now().toString(),
                        action_proposal = fallback.action_proposal
                    )
                    _uiState.update {
                        it.copy(
                            messages = it.messages + assistantMsg,
                            isSending = false
                        )
                    }
                } catch (fallbackError: Exception) {
                    _uiState.update {
                        it.copy(
                            isSending = false,
                            errorMessage = "Failed to deliver message: ${e.message ?: "Network error"}. Tap retry to try again.",
                            pendingMessageRetry = trimmed
                        )
                    }
                }
            }
        }
    }

    fun playMessageAudio(context: Context, messageId: String, audioBase64: String) {
        AudioPlayer.togglePlay(context, messageId, audioBase64)
    }

    fun stopAudio() {
        AudioPlayer.stop()
    }

    fun toggleVoiceAutoPlay() {
        _uiState.update { it.copy(isVoiceAutoPlayEnabled = !it.isVoiceAutoPlayEnabled) }
    }

    fun toggleLiveGeminiMode() {
        _uiState.update { it.copy(isLiveGeminiMode = !it.isLiveGeminiMode) }
    }

    fun setVoiceListeningState(isListening: Boolean, rms: Float = 0f, partialText: String = "") {
        _uiState.update {
            it.copy(
                isListeningVoice = isListening,
                voiceRmsLevel = rms,
                partialVoiceText = partialText
            )
        }
    }

    fun retryFailedMessage(context: Context? = null) {
        val retryContent = _uiState.value.pendingMessageRetry ?: return
        sendMessage(retryContent, context)
    }

    fun dismissError() {
        _uiState.update { it.copy(errorMessage = null) }
    }

    override fun onCleared() {
        super.onCleared()
        AudioPlayer.stop()
    }
}
