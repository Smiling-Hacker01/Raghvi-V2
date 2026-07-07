package com.raghvi.assistant.ui.backendstatus

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.raghvi.assistant.network.ApiClient
import kotlinx.coroutines.launch

private sealed interface BackendCheckState {
    data object Loading : BackendCheckState
    data class Success(val health: String, val ready: String) : BackendCheckState
    data class Error(val message: String) : BackendCheckState
}

@Composable
fun BackendStatusScreen() {
    var state by remember { mutableStateOf<BackendCheckState>(BackendCheckState.Loading) }
    val scope = rememberCoroutineScope()

    suspend fun checkBackend() {
        state = BackendCheckState.Loading
        state = try {
            val health = ApiClient.healthApi.getHealth().status
            val ready = ApiClient.healthApi.getReady().status
            BackendCheckState.Success(health, ready)
        } catch (e: Exception) {
            BackendCheckState.Error(e.message ?: "Unknown error")
        }
    }

    LaunchedEffect(Unit) { checkBackend() }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Backend Status", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(16.dp))
        when (val current = state) {
            is BackendCheckState.Loading -> CircularProgressIndicator()
            is BackendCheckState.Success -> {
                Text("Health: ${current.health}")
                Text("Ready: ${current.ready}")
            }
            is BackendCheckState.Error -> {
                Text("Error: ${current.message}", color = MaterialTheme.colorScheme.error)
            }
        }
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = { scope.launch { checkBackend() } }) {
            Text("Retry")
        }
    }
}