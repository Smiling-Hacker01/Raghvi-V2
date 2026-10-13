package com.raghvi.assistant.ui

import com.raghvi.assistant.network.ChatMessage
import com.raghvi.assistant.network.MemoryItem
import com.raghvi.assistant.network.RegisterRequest
import com.raghvi.assistant.network.TaskItem
import com.raghvi.assistant.ui.chat.ChatUiState
import com.raghvi.assistant.ui.memories.MemoriesUiState
import com.raghvi.assistant.ui.tasks.TasksUiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UiStateTests {

    @Test
    fun testChatUiStateLifecycle() {
        val initial = ChatUiState()
        assertTrue(initial.messages.isEmpty())
        assertFalse(initial.isLoadingHistory)
        assertFalse(initial.isSending)
        assertNull(initial.errorMessage)

        val userMessage = ChatMessage(
            id = "msg-1",
            role = "user",
            content = "Hello Raghvi",
            created_at = "2026-10-12T10:00:00Z"
        )
        val assistantMessage = ChatMessage(
            id = "msg-2",
            role = "assistant",
            content = "Hello! I am here to assist you.",
            created_at = "2026-10-12T10:00:02Z"
        )

        val updated = initial.copy(
            messages = listOf(userMessage, assistantMessage),
            isSending = false
        )

        assertEquals(2, updated.messages.size)
        assertEquals("user", updated.messages[0].role)
        assertEquals("assistant", updated.messages[1].role)

        val failed = updated.copy(
            errorMessage = "Connection timeout",
            pendingMessageRetry = "Failed draft"
        )
        assertNotNull(failed.errorMessage)
        assertEquals("Failed draft", failed.pendingMessageRetry)
    }

    @Test
    fun testMemoriesUiStateTabSwitchAndCounts() {
        val initial = MemoriesUiState()
        assertEquals(0, initial.selectedTab)
        assertTrue(initial.approvedMemories.isEmpty())
        assertTrue(initial.pendingMemories.isEmpty())

        val approved = MemoryItem(
            id = "mem-1",
            content = "Prefers coffee over tea",
            is_sensitive = false,
            is_approved = true,
            created_at = "2026-10-12T10:00:00Z",
            updated_at = "2026-10-12T10:00:00Z"
        )
        val pending = MemoryItem(
            id = "mem-2",
            content = "Home address: 123 Main St",
            is_sensitive = true,
            is_approved = false,
            created_at = "2026-10-12T10:05:00Z",
            updated_at = "2026-10-12T10:05:00Z"
        )

        val loaded = initial.copy(
            approvedMemories = listOf(approved),
            pendingMemories = listOf(pending),
            selectedTab = 1
        )

        assertEquals(1, loaded.selectedTab)
        assertEquals(1, loaded.approvedMemories.size)
        assertEquals(1, loaded.pendingMemories.size)
        assertTrue(loaded.pendingMemories[0].is_sensitive)
    }

    @Test
    fun testTasksUiStateFilteringAndStatus() {
        val initial = TasksUiState()
        assertNull(initial.selectedFilter)

        val task1 = TaskItem(
            id = "task-1",
            title = "File quarterly taxes",
            status = "pending",
            priority = "high",
            created_at = "2026-10-12T09:00:00Z",
            updated_at = "2026-10-12T09:00:00Z"
        )
        val task2 = TaskItem(
            id = "task-2",
            title = "Morning run",
            status = "completed",
            priority = "low",
            created_at = "2026-10-12T07:00:00Z",
            updated_at = "2026-10-12T08:00:00Z",
            completed_at = "2026-10-12T08:00:00Z"
        )

        val state = initial.copy(
            tasks = listOf(task1, task2),
            pendingCount = 1,
            completedCount = 1,
            selectedFilter = "pending"
        )

        assertEquals("pending", state.selectedFilter)
        assertEquals(1, state.pendingCount)
        assertEquals(1, state.completedCount)
        assertEquals(2, state.tasks.size)
    }

    @Test
    fun testRegisterRequestSanitization() {
        val request = RegisterRequest(
            username = "VishalSingh",
            email = "Vishal@Example.Com",
            password = "securePassword123",
            name = "Vishal Singh"
        )

        assertEquals("VishalSingh", request.username)
        assertTrue(request.email.contains("@"))
        assertTrue(request.password.length >= 8)
    }
}
