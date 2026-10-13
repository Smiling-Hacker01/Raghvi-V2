package com.raghvi.assistant.ui.tasks

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.TaskCreateRequest
import com.raghvi.assistant.network.TaskItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TasksUiState(
    val tasks: List<TaskItem> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val selectedFilter: String? = null, // null = all, "pending" = pending, "completed" = completed
    val pendingCount: Int = 0,
    val completedCount: Int = 0
)

class TasksViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(TasksUiState())
    val uiState: StateFlow<TasksUiState> = _uiState.asStateFlow()

    init {
        loadTasks()
    }

    fun setFilter(filter: String?) {
        _uiState.update { it.copy(selectedFilter = filter) }
        loadTasks(filter)
    }

    fun loadTasks(filter: String? = _uiState.value.selectedFilter) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            try {
                val response = ApiClient.authApi.getTasks(status = filter)
                _uiState.update {
                    it.copy(
                        tasks = response.tasks,
                        pendingCount = response.pending_count,
                        completedCount = response.completed_count,
                        isLoading = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Failed to load tasks"
                    )
                }
            }
        }
    }

    fun createTask(
        title: String,
        description: String? = null,
        priority: String = "medium",
        dueDate: String? = null
    ) {
        if (title.isBlank()) return
        viewModelScope.launch {
            try {
                ApiClient.authApi.createTask(
                    TaskCreateRequest(
                        title = title.trim(),
                        description = description?.takeIf { it.isNotBlank() }?.trim(),
                        priority = priority,
                        due_date = dueDate?.takeIf { it.isNotBlank() }
                    )
                )
                loadTasks()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to create task: ${e.message}") }
            }
        }
    }

    fun completeTask(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.completeTask(id)
                loadTasks()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to complete task: ${e.message}") }
            }
        }
    }

    fun deleteTask(id: String) {
        viewModelScope.launch {
            try {
                ApiClient.authApi.deleteTask(id)
                loadTasks()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "Failed to delete task: ${e.message}") }
            }
        }
    }

    fun dismissError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
