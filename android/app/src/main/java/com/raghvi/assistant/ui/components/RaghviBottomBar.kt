package com.raghvi.assistant.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Checklist
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

enum class RaghviTab(val destination: String, val label: String) {
    CHAT("chat", "Chat"),
    MEMORIES("memories", "Memories"),
    TASKS("tasks", "Tasks"),
    PRIVACY("privacy", "Settings")
}

@Composable
fun RaghviBottomBar(
    currentDestination: String,
    onNavigate: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    NavigationBar(
        modifier = modifier,
        containerColor = MaterialTheme.colorScheme.surfaceContainer,
        contentColor = MaterialTheme.colorScheme.onSurface
    ) {
        NavigationBarItem(
            selected = currentDestination == RaghviTab.CHAT.destination,
            onClick = {
                if (currentDestination != RaghviTab.CHAT.destination) {
                    onNavigate(RaghviTab.CHAT.destination)
                }
            },
            icon = { Icon(Icons.Filled.ChatBubble, contentDescription = "Chat") },
            label = { Text(RaghviTab.CHAT.label) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                selectedTextColor = MaterialTheme.colorScheme.primary,
                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
        NavigationBarItem(
            selected = currentDestination == RaghviTab.MEMORIES.destination,
            onClick = {
                if (currentDestination != RaghviTab.MEMORIES.destination) {
                    onNavigate(RaghviTab.MEMORIES.destination)
                }
            },
            icon = { Icon(Icons.Filled.AutoAwesome, contentDescription = "Memories") },
            label = { Text(RaghviTab.MEMORIES.label) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                selectedTextColor = MaterialTheme.colorScheme.primary,
                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
        NavigationBarItem(
            selected = currentDestination == RaghviTab.TASKS.destination,
            onClick = {
                if (currentDestination != RaghviTab.TASKS.destination) {
                    onNavigate(RaghviTab.TASKS.destination)
                }
            },
            icon = { Icon(Icons.Filled.Checklist, contentDescription = "Tasks") },
            label = { Text(RaghviTab.TASKS.label) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                selectedTextColor = MaterialTheme.colorScheme.primary,
                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
        NavigationBarItem(
            selected = currentDestination == RaghviTab.PRIVACY.destination,
            onClick = {
                if (currentDestination != RaghviTab.PRIVACY.destination) {
                    onNavigate(RaghviTab.PRIVACY.destination)
                }
            },
            icon = { Icon(Icons.Filled.Security, contentDescription = "Settings") },
            label = { Text(RaghviTab.PRIVACY.label) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                selectedTextColor = MaterialTheme.colorScheme.primary,
                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
    }
}
