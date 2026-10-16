package com.raghvi.assistant.voice

import com.raghvi.assistant.network.AudioPayload
import com.raghvi.assistant.network.ChatMessage
import com.raghvi.assistant.network.ChatSendWithVoiceResponse
import com.raghvi.assistant.network.LiveGeminiVoiceRequest
import com.raghvi.assistant.network.LiveGeminiVoiceResponse
import com.raghvi.assistant.network.VoiceSettings
import com.raghvi.assistant.ui.chat.ChatUiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceAudioIntegrationTest {

    @Test
    fun testAudioPlaybackStateTransitions() {
        val initial = AudioPlaybackState()
        assertFalse(initial.isPlaying)
        assertNull(initial.activeMessageId)
        assertNull(initial.errorMessage)

        val playing = initial.copy(isPlaying = true, activeMessageId = "msg-123")
        assertTrue(playing.isPlaying)
        assertEquals("msg-123", playing.activeMessageId)

        val stopped = playing.copy(isPlaying = false, activeMessageId = null)
        assertFalse(stopped.isPlaying)
        assertNull(stopped.activeMessageId)

        val error = stopped.copy(errorMessage = "Corrupt audio stream")
        assertEquals("Corrupt audio stream", error.errorMessage)
    }

    @Test
    fun testVoiceInputStateTransitions() {
        val initial = VoiceInputState()
        assertFalse(initial.isListening)
        assertEquals(0f, initial.rmsLevel, 0.001f)
        assertEquals("", initial.partialText)

        val listening = initial.copy(
            isListening = true,
            rmsLevel = 4.5f,
            partialText = "kya haal hai"
        )
        assertTrue(listening.isListening)
        assertEquals(4.5f, listening.rmsLevel, 0.001f)
        assertEquals("kya haal hai", listening.partialText)
    }

    @Test
    fun testChatMessageWithVoiceAudio() {
        val audioMsg = ChatMessage(
            id = "msg-voice-1",
            role = "assistant",
            content = "नमस्ते! मैं राघवी हूँ।",
            created_at = "2026-10-16T12:00:00Z",
            audio_base64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",
            audio_provider = "IndicF5 (AI4Bharat Cloned Voice)"
        )

        assertNotNull(audioMsg.audio_base64)
        assertEquals("IndicF5 (AI4Bharat Cloned Voice)", audioMsg.audio_provider)
        assertEquals("assistant", audioMsg.role)
    }

    @Test
    fun testLiveGeminiVoiceRequestAndResponse() {
        val req = LiveGeminiVoiceRequest(
            message = "kya kar rahi ho raghvi?",
            mode = "chat",
            history = listOf(mapOf("role" to "user", "content" to "hi")),
            speed = 1.0f
        )
        assertEquals("kya kar rahi ho raghvi?", req.message)
        assertEquals("chat", req.mode)
        assertEquals(1, req.history.size)

        val res = LiveGeminiVoiceResponse(
            user_message = req.message,
            assistant_message = "मैं बस आपकी मदद के लिए उपस्थित हूँ।",
            hindi_text = "मैं बस आपकी मदद के लिए उपस्थित हूँ।",
            audio_base64 = "base64_sound_bytes",
            provider = "Gemini Live + IndicF5"
        )
        assertEquals("मैं बस आपकी मदद के लिए उपस्थित हूँ।", res.assistant_message)
        assertEquals("Gemini Live + IndicF5", res.provider)
        assertNotNull(res.audio_base64)
    }

    @Test
    fun testVoiceSettingsDefaults() {
        val settings = VoiceSettings()
        assertTrue(settings.voice_enabled)
        assertEquals("conversational", settings.speaking_style)
        assertEquals("hi", settings.language)
        assertTrue(settings.allow_interruptions)
        assertTrue(settings.personalized_voice_enabled)
    }

    @Test
    fun testChatUiStateVoiceToggles() {
        val state = ChatUiState()
        assertTrue(state.isVoiceAutoPlayEnabled)
        assertTrue(state.isLiveGeminiMode)

        val toggled = state.copy(
            isVoiceAutoPlayEnabled = false,
            isLiveGeminiMode = false,
            activePlayingMessageId = "msg-voice-1"
        )
        assertFalse(toggled.isVoiceAutoPlayEnabled)
        assertFalse(toggled.isLiveGeminiMode)
        assertEquals("msg-voice-1", toggled.activePlayingMessageId)
    }

    @Test
    fun testAudioPayloadModel() {
        val payload = AudioPayload(
            data_base64 = "base64_wav",
            provider = "hi-IN-SwaraNeural",
            sample_rate = 24000,
            mime_type = "audio/wav"
        )
        assertEquals("base64_wav", payload.data_base64)
        assertEquals("hi-IN-SwaraNeural", payload.provider)
        assertEquals(24000, payload.sample_rate)

        val resp = ChatSendWithVoiceResponse(
            user_message = "hello",
            assistant_message = "hi there",
            audio = payload
        )
        assertNotNull(resp.audio)
        assertEquals("hi-IN-SwaraNeural", resp.audio?.provider)
    }

    @Test
    fun testActionProposalInChatMessage() {
        val proposal = com.raghvi.assistant.network.ActionProposalPayload(
            proposal_id = "prop-456",
            action_type = "schedule_meeting",
            meet_link = "https://meet.google.com/abc-defg-hij",
            description = "Team Sync"
        )
        val msg = ChatMessage(
            id = "msg-proposal",
            role = "assistant",
            content = "हाँ, मैंने मीटिंग शेड्यूल कर दी है।",
            created_at = "2026-10-16T12:00:00Z",
            action_proposal = proposal
        )
        assertNotNull(msg.action_proposal)
        assertEquals("schedule_meeting", msg.action_proposal?.action_type)
        assertEquals("https://meet.google.com/abc-defg-hij", msg.action_proposal?.meet_link)
    }

    @Test
    fun testTasksAndMemoriesCrudUiStates() {
        val tasksState = com.raghvi.assistant.ui.tasks.TasksUiState(
            pendingCount = 3,
            completedCount = 5,
            selectedFilter = "pending"
        )
        assertEquals(3, tasksState.pendingCount)
        assertEquals("pending", tasksState.selectedFilter)

        val memoriesState = com.raghvi.assistant.ui.memories.MemoriesUiState(
            selectedTab = 1
        )
        assertEquals(1, memoriesState.selectedTab)
    }
}
