package com.raghvi.assistant.ui.meetings

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.MeetingActionItem
import com.raghvi.assistant.network.MeetingCreateRequest
import com.raghvi.assistant.network.MeetingNoteItem
import com.raghvi.assistant.network.MeetingUpdateRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

data class MeetingsUiState(
    val meetings: List<MeetingNoteItem> = emptyList(),
    val isLoading: Boolean = false,
    val isUploading: Boolean = false,
    val uploadProgressMessage: String? = null,
    val searchQuery: String = "",
    val statusMessage: String? = null,
    val errorMessage: String? = null
)

class MeetingsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(MeetingsUiState())
    val uiState: StateFlow<MeetingsUiState> = _uiState.asStateFlow()

    init {
        loadMeetings()
    }

    fun loadMeetings(query: String? = null) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            try {
                val response = ApiClient.authApi.getMeetings(query = query?.ifBlank { null })
                _uiState.update {
                    it.copy(
                        meetings = response.meetings,
                        isLoading = false,
                        searchQuery = query ?: ""
                    )
                }
            } catch (e: Exception) {
                Log.e("MeetingsViewModel", "Failed to load meetings", e)
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Failed to load meeting notes: ${e.message}"
                    )
                }
            }
        }
    }

    fun uploadAudioFile(context: Context, uri: Uri, customTitle: String? = null) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isUploading = true,
                    uploadProgressMessage = "Reading audio file from device...",
                    errorMessage = null
                )
            }
            try {
                val fileName = queryFileName(context, uri) ?: "meeting_recording.m4a"
                val meetingTitle = customTitle?.ifBlank { null }
                    ?: fileName.substringBeforeLast(".").replace("_", " ").replace("-", " ")
                        .replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }

                val inputStream = context.contentResolver.openInputStream(uri)
                    ?: throw IllegalArgumentException("Cannot open audio stream from URI")
                val audioBytes = inputStream.use { it.readBytes() }

                if (audioBytes.isEmpty()) {
                    throw IllegalArgumentException("Selected audio file is empty.")
                }

                _uiState.update {
                    it.copy(uploadProgressMessage = "Transcribing with Whisper & generating meeting notes...")
                }

                val mimeType = context.contentResolver.getType(uri) ?: "audio/*"
                val requestFile = audioBytes.toRequestBody(mimeType.toMediaTypeOrNull())
                val multipartFile = MultipartBody.Part.createFormData("file", fileName, requestFile)
                val titlePart = meetingTitle.toRequestBody("text/plain".toMediaTypeOrNull())

                val newNote = ApiClient.authApi.uploadMeetingAudio(multipartFile, titlePart)

                _uiState.update { current ->
                    current.copy(
                        meetings = listOf(newNote) + current.meetings,
                        isUploading = false,
                        uploadProgressMessage = null,
                        statusMessage = "Meeting notes for '${newNote.title}' generated successfully!"
                    )
                }
            } catch (e: Exception) {
                Log.e("MeetingsViewModel", "Audio upload failed", e)
                _uiState.update {
                    it.copy(
                        isUploading = false,
                        uploadProgressMessage = null,
                        errorMessage = "Audio processing failed: ${e.message}"
                    )
                }
            }
        }
    }

    fun createMeetingFromText(title: String, transcript: String) {
        if (title.isBlank() || transcript.isBlank()) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isUploading = true,
                    uploadProgressMessage = "Extracting summary, decisions, and action items...",
                    errorMessage = null
                )
            }
            try {
                val newNote = ApiClient.authApi.createMeeting(
                    MeetingCreateRequest(
                        title = title.trim(),
                        transcript = transcript.trim()
                    )
                )
                _uiState.update { current ->
                    current.copy(
                        meetings = listOf(newNote) + current.meetings,
                        isUploading = false,
                        uploadProgressMessage = null,
                        statusMessage = "Meeting notes created for '${newNote.title}'!"
                    )
                }
            } catch (e: Exception) {
                Log.e("MeetingsViewModel", "Text note creation failed", e)
                _uiState.update {
                    it.copy(
                        isUploading = false,
                        uploadProgressMessage = null,
                        errorMessage = "Failed to create meeting notes: ${e.message}"
                    )
                }
            }
        }
    }

    fun updateMeeting(id: String, title: String, summary: String) {
        viewModelScope.launch {
            try {
                val updated = ApiClient.authApi.updateMeeting(
                    id = id,
                    request = MeetingUpdateRequest(
                        title = title.trim(),
                        summary = summary.trim()
                    )
                )
                _uiState.update { current ->
                    current.copy(
                        meetings = current.meetings.map { if (it.id == id) updated else it },
                        statusMessage = "Meeting notes updated."
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Update failed: ${e.message}") }
            }
        }
    }

    fun deleteMeeting(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.deleteMeeting(id)
                _uiState.update { current ->
                    current.copy(
                        meetings = current.meetings.filter { it.id != id },
                        statusMessage = "Meeting note removed."
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Delete failed: ${e.message}") }
            }
        }
    }

    fun exportMarkdown(context: Context, note: MeetingNoteItem) {
        val markdown = buildString {
            appendLine("# Meeting Notes: ${note.title}")
            appendLine("**Date:** ${note.meeting_date} | **Confidence:** ${(note.confidence_score * 100).toInt()}%")
            appendLine()
            appendLine("## Executive Summary")
            appendLine(note.summary)
            appendLine()
            if (note.key_decisions.isNotEmpty()) {
                appendLine("## Key Decisions")
                note.key_decisions.forEach { appendLine("- $it") }
                appendLine()
            }
            if (note.discussion_points.isNotEmpty()) {
                appendLine("## Discussion Points")
                note.discussion_points.forEach { appendLine("- $it") }
                appendLine()
            }
            if (note.action_items.isNotEmpty()) {
                appendLine("## Action Items")
                note.action_items.forEach { item ->
                    appendLine("- [ ] **${item.owner}**: ${item.task}")
                }
                appendLine()
            }
            if (!note.uncertainty_notes.isNullOrBlank()) {
                appendLine("> *Note on accuracy: ${note.uncertainty_notes}*")
            }
        }

        val sendIntent = Intent().apply {
            action = Intent.ACTION_SEND
            putExtra(Intent.EXTRA_SUBJECT, "Meeting Notes: ${note.title}")
            putExtra(Intent.EXTRA_TEXT, markdown)
            type = "text/plain"
        }
        val shareIntent = Intent.createChooser(sendIntent, "Share Meeting Notes")
        context.startActivity(shareIntent)
    }

    fun clearStatus() {
        _uiState.update { it.copy(statusMessage = null, errorMessage = null) }
    }

    private fun queryFileName(context: Context, uri: Uri): String? {
        var result: String? = null
        if (uri.scheme == "content") {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) {
                        result = cursor.getString(index)
                    }
                }
            }
        }
        if (result == null) {
            result = uri.path
            val cut = result?.lastIndexOf('/') ?: -1
            if (cut != -1) {
                result = result?.substring(cut + 1)
            }
        }
        return result
    }
}
