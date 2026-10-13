package com.raghvi.assistant.ui.memories

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.MemoryApprovalRequest
import com.raghvi.assistant.network.MemoryCreateRequest
import com.raghvi.assistant.network.MemoryItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MemoriesUiState(
    val approvedMemories: List<MemoryItem> = emptyList(),
    val pendingMemories: List<MemoryItem> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val selectedTab: Int = 0 // 0 = Approved, 1 = Pending Review
)

class MemoriesViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(MemoriesUiState())
    val uiState: StateFlow<MemoriesUiState> = _uiState.asStateFlow()

    init {
        loadMemories()
    }

    fun selectTab(tabIndex: Int) {
        _uiState.update { it.copy(selectedTab = tabIndex) }
    }

    fun loadMemories() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            try {
                val approved = ApiClient.authApi.getApprovedMemories(limit = 100)
                val pending = ApiClient.authApi.getPendingMemories()
                _uiState.update {
                    it.copy(
                        approvedMemories = approved.memories,
                        pendingMemories = pending.memories,
                        isLoading = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Failed to load memories"
                    )
                }
            }
        }
    }

    fun approveMemory(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.approveMemory(id, MemoryApprovalRequest(approved = true))
                loadMemories()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to approve memory: ${e.message}") }
            }
        }
    }

    fun rejectMemory(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.approveMemory(id, MemoryApprovalRequest(approved = false))
                loadMemories()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to reject memory: ${e.message}") }
            }
        }
    }

    fun deleteMemory(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.deleteMemory(id)
                loadMemories()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to delete memory: ${e.message}") }
            }
        }
    }

    fun createMemory(content: String) {
        if (content.isBlank()) return
        viewModelScope.launch {
            try {
                ApiClient.authApi.createMemory(MemoryCreateRequest(content = content.trim()))
                loadMemories()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to save memory: ${e.message}") }
            }
        }
    }

    fun dismissError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
