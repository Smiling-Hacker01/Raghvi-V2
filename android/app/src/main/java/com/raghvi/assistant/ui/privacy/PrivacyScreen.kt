package com.raghvi.assistant.ui.privacy

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import android.content.Intent
import android.net.Uri
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.BriefingPreferences
import com.raghvi.assistant.network.VoiceSettings
import androidx.core.content.ContextCompat
import com.raghvi.assistant.voice.RaghviVoiceDaemonService
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrivacyScreen(
    onNavigateBack: () -> Unit = {},
    onNavigateToTab: ((String) -> Unit)? = null,
    onAccountDeleted: () -> Unit = {}
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var isBriefingOptedIn by remember { mutableStateOf(false) }
    var voiceSettings by remember { mutableStateOf(VoiceSettings()) }
    var isLoading by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var showDeleteConfirmDialog by remember { mutableStateOf(false) }
    var customVoiceName by remember { mutableStateOf("") }
    var isCloningVoice by remember { mutableStateOf(false) }

    val voicePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            scope.launch {
                isCloningVoice = true
                statusMessage = "Reading voice sample and uploading for cloning..."
                try {
                    val stream = context.contentResolver.openInputStream(uri)
                        ?: throw IllegalArgumentException("Cannot open voice file stream")
                    val bytes = stream.use { it.readBytes() }
                    val mime = context.contentResolver.getType(uri) ?: "audio/wav"
                    val filePart = MultipartBody.Part.createFormData(
                        "audio_file",
                        "custom_voice_sample.wav",
                        bytes.toRequestBody(mime.toMediaTypeOrNull())
                    )
                    val nameToUse = customVoiceName.ifBlank { "My Cloned Voice" }
                    val namePart = nameToUse.toRequestBody("text/plain".toMediaTypeOrNull())

                    val res = ApiClient.authApi.cloneCustomVoice(filePart, namePart)
                    if (res.voice_settings != null) {
                        voiceSettings = res.voice_settings
                    }
                    statusMessage = res.message
                    customVoiceName = ""
                } catch (e: Exception) {
                    statusMessage = "Voice cloning failed: ${e.message}"
                } finally {
                    isCloningVoice = false
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        try {
            val prefs = ApiClient.authApi.getBriefingPreferences()
            isBriefingOptedIn = prefs.opt_in
        } catch (_: Exception) {}

        try {
            val vs = ApiClient.authApi.getVoiceSettings()
            voiceSettings = vs
            if (vs.voice_activation_enabled) {
                try {
                    val serviceIntent = Intent(context, RaghviVoiceDaemonService::class.java)
                    ContextCompat.startForegroundService(context, serviceIntent)
                } catch (_: Exception) {}
            }
        } catch (_: Exception) {}
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Privacy & Account") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainer
                )
            )
        },
        bottomBar = {
            if (onNavigateToTab != null) {
                com.raghvi.assistant.ui.components.RaghviBottomBar(
                    currentDestination = "privacy",
                    onNavigate = onNavigateToTab
                )
            }
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            statusMessage?.let {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        it,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            // Proactive Briefing Opt-In
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Proactive Daily Briefing", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Receive daily morning summaries of pending tasks and reminders. Quiet hours (10 PM to 7 AM) are strictly respected.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Enable Morning Briefings")
                        Switch(
                            checked = isBriefingOptedIn,
                            onCheckedChange = { checked ->
                                isBriefingOptedIn = checked
                                scope.launch {
                                    try {
                                        ApiClient.authApi.updateBriefingPreferences(
                                            BriefingPreferences(opt_in = checked)
                                        )
                                        statusMessage = if (checked) "Briefings enabled" else "Briefings disabled"
                                    } catch (e: Exception) {
                                        statusMessage = "Failed to update preferences: ${e.message}"
                                    }
                                }
                            }
                        )
                    }
                }
            }

            // Voice & Speech Synthesis Preferences
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Voice & Speech Synthesis", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Configure AI speech responses (IndicF5 cloned voice & Swara Neural) and voice wake phrase detection.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Enable Voice Responses")
                        Switch(
                            checked = voiceSettings.voice_enabled,
                            onCheckedChange = { checked ->
                                val updated = voiceSettings.copy(voice_enabled = checked)
                                voiceSettings = updated
                                scope.launch {
                                    try {
                                        ApiClient.authApi.updateVoiceSettings(updated)
                                        statusMessage = if (checked) "Voice speech enabled" else "Voice speech disabled"
                                    } catch (e: Exception) {
                                        statusMessage = "Failed to update voice settings: ${e.message}"
                                    }
                                }
                            }
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Wake Phrase Activation")
                            Text("Listen for 'Hey Raghvi' / 'Aur Raghvi'", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(
                            checked = voiceSettings.voice_activation_enabled,
                            onCheckedChange = { checked ->
                                val updated = voiceSettings.copy(voice_activation_enabled = checked)
                                voiceSettings = updated
                                val serviceIntent = Intent(context, RaghviVoiceDaemonService::class.java)
                                if (checked) {
                                    try {
                                        ContextCompat.startForegroundService(context, serviceIntent)
                                    } catch (_: Exception) {}
                                } else {
                                    try {
                                        context.stopService(serviceIntent)
                                    } catch (_: Exception) {}
                                }
                                scope.launch {
                                    try {
                                        ApiClient.authApi.updateVoiceSettings(updated)
                                        statusMessage = if (checked) "Wake phrase activation enabled (listening in background)" else "Wake phrase disabled"
                                    } catch (e: Exception) {
                                        statusMessage = "Failed to update wake phrase: ${e.message}"
                                    }
                                }
                            }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                    androidx.compose.material3.HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                    Spacer(modifier = Modifier.height(6.dp))

                    Text(
                        "Custom Voice Cloning (Feed Manual Voice Sample)",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Upload a 10–30s recording of your own voice (.mp3, .wav, .m4a). IndicF5 will clone your voice so Raghvi talks in your exact voice!",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // Active Voice Status Chip
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (voiceSettings.selected_voice_id == "custom") {
                            SuggestionChip(
                                onClick = {},
                                label = { Text("Active: ${voiceSettings.custom_voice_name ?: "Your Cloned Voice"}") }
                            )
                            TextButton(
                                onClick = {
                                    scope.launch {
                                        try {
                                            val res = ApiClient.authApi.resetDefaultVoice()
                                            if (res.voice_settings != null) {
                                                voiceSettings = res.voice_settings
                                            }
                                            statusMessage = "Reset to default Raghvi voice."
                                        } catch (e: Exception) {
                                            statusMessage = "Failed to reset voice: ${e.message}"
                                        }
                                    }
                                }
                            ) {
                                Icon(Icons.Filled.RestartAlt, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Reset to Default")
                            }
                        } else {
                            SuggestionChip(
                                onClick = {},
                                label = { Text("Active: Official Raghvi (IndicF5 Clone)") }
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    OutlinedTextField(
                        value = customVoiceName,
                        onValueChange = { customVoiceName = it },
                        label = { Text("Custom Voice Label (e.g. Vishal's Voice)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    if (isCloningVoice) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(vertical = 4.dp)
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Cloning your voice... Please wait", style = MaterialTheme.typography.bodySmall)
                        }
                    } else {
                        Button(
                            onClick = { voicePickerLauncher.launch("audio/*") },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Filled.RecordVoiceOver, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Feed Voice Audio for Cloning")
                        }
                    }
                }
            }

            // Connected Accounts & Communications Integration Card
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Connected Accounts & Communications", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Integrate Gmail, Google Calendar / Meet, and WhatsApp so Raghvi can schedule meetings and draft context-aware messages.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    // Google OAuth 1-Click
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Google Workspace (Gmail & Meet)", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "Link your Google account for meeting scheduling and email sync.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        val authResp = ApiClient.authApi.getGoogleOAuthAuthorizeUrl()
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(authResp.authorization_url)).apply {
                                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                        }
                                        context.startActivity(intent)
                                    } catch (e: Exception) {
                                        statusMessage = "Failed to launch Google auth: ${e.message}"
                                    }
                                }
                            }
                        ) {
                            Text("Connect")
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // WhatsApp Integration Status & Permission
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("WhatsApp Message Sync", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "Sync incoming notifications so Raghvi can suggest contextual replies.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        OutlinedButton(
                            onClick = {
                                try {
                                    val intent = Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS").apply {
                                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    statusMessage = "Could not open notification settings: ${e.message}"
                                }
                            }
                        ) {
                            Text("Permissions")
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Sync Emails
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Email Inbox Sync", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "Fetch latest email messages from connected inboxes.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        OutlinedButton(
                            onClick = {
                                scope.launch {
                                    try {
                                        val syncResults = ApiClient.authApi.syncAllConnectedAccounts()
                                        val totalSynced = syncResults.sumOf { it.new_messages_count }
                                        statusMessage = "Email sync complete! $totalSynced new emails fetched."
                                    } catch (e: Exception) {
                                        statusMessage = "Email sync error: ${e.message}"
                                    }
                                }
                            }
                        ) {
                            Text("Sync Now")
                        }
                    }
                }
            }

            // Data Export
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Data Portability & Export", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Download a structured JSON archive of all your personal data, including chat history, memories, tasks, and subscriptions.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = {
                            scope.launch {
                                isLoading = true
                                try {
                                    val export = ApiClient.authApi.exportUserData()
                                    statusMessage = "Export generated successfully (${export.size} top-level categories)."
                                } catch (e: Exception) {
                                    statusMessage = "Export failed: ${e.message}"
                                } finally {
                                    isLoading = false
                                }
                            }
                        },
                        enabled = !isLoading
                    ) {
                        Text("Export My Data")
                    }
                }
            }

            // Danger Zone — Delete Account
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Danger Zone", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "Permanently delete your account and all associated conversations, memories, and task records. This action cannot be undone.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = { showDeleteConfirmDialog = true },
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                    ) {
                        Text("Delete Account Permanently")
                    }
                }
            }
        }
    }

    if (showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmDialog = false },
            title = { Text("Delete Account?") },
            text = { Text("Are you absolutely sure you want to permanently delete your Raghvi account? All stored memories and history will be instantly erased.") },
            confirmButton = {
                Button(
                    onClick = {
                        showDeleteConfirmDialog = false
                        scope.launch {
                            try {
                                ApiClient.authApi.deleteAccount()
                                ApiClient.tokens().clearTokens()
                                onAccountDeleted()
                            } catch (e: Exception) {
                                statusMessage = "Deletion failed: ${e.message}"
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Delete Forever")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showDeleteConfirmDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}
