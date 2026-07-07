package com.raghvi.assistant.ui.splash

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(onTimeout: () -> Unit) {
    LaunchedEffect(Unit) {
        delay(1000)
        onTimeout()
    }
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("Raghvi", style = MaterialTheme.typography.displaySmall)
    }
}