package com.raghvi.assistant.ui.chat

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.content.Intent
import android.net.Uri
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.VideoCall
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import com.raghvi.assistant.actions.ActionDispatcher
import com.raghvi.assistant.network.ActionProposalPayload
import com.raghvi.assistant.network.ChatMessage
import com.raghvi.assistant.voice.VoiceInputManager
import kotlinx.serialization.json.jsonPrimitive

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onNavigateToMeetings: () -> Unit = {},
    onNavigateToMemories: () -> Unit = {},
    onNavigateToTasks: () -> Unit = {},
    onNavigateToPrivacy: () -> Unit = {},
    onLogout: () -> Unit = {},
    chatViewModel: ChatViewModel = viewModel()
) {
    val uiState by chatViewModel.uiState.collectAsState()
    var inputText by remember { mutableStateOf("") }
    var showClearHistoryDialog by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val context = LocalContext.current

    // Voice recognition manager setup
    val voiceInputManager = remember {
        VoiceInputManager(context).apply {
            onResultListener = { fullText, wakeWord, command ->
                inputText = command
                chatViewModel.setVoiceListeningState(false)
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            voiceInputManager.destroy()
            chatViewModel.stopAudio()
        }
    }

    // Permission launcher for microphone
    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            chatViewModel.setVoiceListeningState(true)
            voiceInputManager.startListening("hi-IN")
        } else {
            Toast.makeText(context, "Microphone permission required for voice chat", Toast.LENGTH_SHORT).show()
        }
    }

    LaunchedEffect(uiState.messages.size, uiState.isSending) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Raghvi", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            // Mode Badge
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = if (uiState.isLiveGeminiMode) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.secondaryContainer,
                                modifier = Modifier.clickable { chatViewModel.toggleLiveGeminiMode() }
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.AutoAwesome,
                                        contentDescription = null,
                                        modifier = Modifier.size(11.dp),
                                        tint = if (uiState.isLiveGeminiMode) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSecondaryContainer
                                    )
                                    Text(
                                        if (uiState.isLiveGeminiMode) "IndicF5 Voice" else "Standard Chat",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = if (uiState.isLiveGeminiMode) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSecondaryContainer
                                    )
                                }
                            }
                        }
                        Text(
                            if (uiState.isSending) "Thinking & Synthesizing Voice..." else "Personal AI Companion",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    // Voice Auto-play toggle
                    IconButton(onClick = { chatViewModel.toggleVoiceAutoPlay() }) {
                        Icon(
                            imageVector = if (uiState.isVoiceAutoPlayEnabled) Icons.Default.VolumeUp else Icons.Default.VolumeOff,
                            contentDescription = "Toggle Auto-play Voice",
                            tint = if (uiState.isVoiceAutoPlayEnabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    // Clear History
                    IconButton(onClick = { showClearHistoryDialog = true }) {
                        Icon(
                            imageVector = Icons.Default.DeleteSweep,
                            contentDescription = "Clear Chat History",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    IconButton(onClick = onLogout) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Logout,
                            contentDescription = "Logout",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainer
                )
            )
        },
        bottomBar = {
            com.raghvi.assistant.ui.components.RaghviBottomBar(
                currentDestination = "chat",
                onNavigate = { destination ->
                    when (destination) {
                        "meetings" -> onNavigateToMeetings()
                        "memories" -> onNavigateToMemories()
                        "tasks" -> onNavigateToTasks()
                        "privacy" -> onNavigateToPrivacy()
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Error & Retry Banner
            if (uiState.errorMessage != null) {
                Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            uiState.errorMessage ?: "",
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f)
                        )
                        if (uiState.pendingMessageRetry != null) {
                            TextButton(onClick = { chatViewModel.retryFailedMessage(context) }) {
                                Text("Retry")
                            }
                        }
                        IconButton(onClick = { chatViewModel.dismissError() }) {
                            Text("✕", color = MaterialTheme.colorScheme.onErrorContainer)
                        }
                    }
                }
            }

            // Message history list
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                if (uiState.isLoadingHistory && uiState.messages.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else if (uiState.messages.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.padding(32.dp)
                        ) {
                            Text(
                                "नमस्ते! I am Raghvi.",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.primary
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                "Ask me anything in Hinglish, Hindi, or English. Tap the microphone to talk or type below!",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                } else {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(uiState.messages, key = { it.id }) { message ->
                            MessageBubble(
                                message = message,
                                isPlayingAudio = uiState.activePlayingMessageId == message.id,
                                onToggleAudio = {
                                    if (message.audio_base64 != null) {
                                        chatViewModel.playMessageAudio(context, message.id, message.audio_base64)
                                    }
                                }
                            )
                        }

                        if (uiState.isSending) {
                            item {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.Start
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(16.dp))
                                            .background(MaterialTheme.colorScheme.surfaceVariant)
                                            .padding(horizontal = 14.dp, vertical = 10.dp)
                                    ) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            CircularProgressIndicator(
                                                modifier = Modifier.size(14.dp),
                                                strokeWidth = 2.dp,
                                                color = MaterialTheme.colorScheme.primary
                                            )
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text(
                                                "Raghvi is responding & synthesizing speech...",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Listening Audio Pulse Banner
            AnimatedVisibility(
                visible = uiState.isListeningVoice,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        val pulse = rememberInfiniteTransition(label = "pulse").animateFloat(
                            initialValue = 0.8f,
                            targetValue = 1.2f,
                            animationSpec = infiniteRepeatable(tween(600), RepeatMode.Reverse),
                            label = "mic_pulse"
                        )
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .scale(pulse.value)
                                .background(MaterialTheme.colorScheme.primary, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Mic,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onPrimary
                            )
                        }
                        Text(
                            if (uiState.partialVoiceText.isNotBlank()) uiState.partialVoiceText else "Listening in Hindi/Hinglish... Speak now",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            voiceInputManager.stopListening()
                            chatViewModel.setVoiceListeningState(false)
                        }) {
                            Text("Done")
                        }
                    }
                }
            }

            // Message Composer Row
            Surface(
                tonalElevation = 3.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = { Text("Message Raghvi in Hinglish/Hindi...") },
                        modifier = Modifier.weight(1f),
                        maxLines = 4,
                        shape = RoundedCornerShape(24.dp)
                    )

                    // Microphone STT Button
                    FilledIconButton(
                        onClick = {
                            if (uiState.isListeningVoice) {
                                voiceInputManager.stopListening()
                                chatViewModel.setVoiceListeningState(false)
                            } else {
                                val hasPermission = ContextCompat.checkSelfPermission(
                                    context,
                                    Manifest.permission.RECORD_AUDIO
                                ) == PackageManager.PERMISSION_GRANTED

                                if (hasPermission) {
                                    chatViewModel.setVoiceListeningState(true)
                                    voiceInputManager.startListening("hi-IN")
                                } else {
                                    micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                }
                            }
                        },
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = if (uiState.isListeningVoice) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.secondaryContainer,
                            contentColor = if (uiState.isListeningVoice) MaterialTheme.colorScheme.onError else MaterialTheme.colorScheme.onSecondaryContainer
                        ),
                        modifier = Modifier.size(44.dp)
                    ) {
                        Icon(
                            imageVector = if (uiState.isListeningVoice) Icons.Default.MicOff else Icons.Default.Mic,
                            contentDescription = "Voice Input"
                        )
                    }

                    // Send Button
                    FilledIconButton(
                        onClick = {
                            val msg = inputText
                            inputText = ""
                            chatViewModel.sendMessage(msg, context)
                        },
                        enabled = inputText.isNotBlank() && !uiState.isSending,
                        modifier = Modifier.size(44.dp)
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Send"
                        )
                    }
                }
            }
        }
    }

    if (showClearHistoryDialog) {
        AlertDialog(
            onDismissRequest = { showClearHistoryDialog = false },
            title = { Text("Clear Conversation History?") },
            text = { Text("Are you sure you want to clear your current conversation? All past messages will be permanently deleted.") },
            confirmButton = {
                Button(
                    onClick = {
                        showClearHistoryDialog = false
                        chatViewModel.clearHistory()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Clear All")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showClearHistoryDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun MessageBubble(
    message: ChatMessage,
    isPlayingAudio: Boolean = false,
    onToggleAudio: () -> Unit = {}
) {
    val isUser = message.role.equals("user", ignoreCase = true)
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Column(
            modifier = Modifier.widthIn(max = 300.dp),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            Box(
                modifier = Modifier
                    .clip(
                        RoundedCornerShape(
                            topStart = 18.dp,
                            topEnd = 18.dp,
                            bottomStart = if (isUser) 18.dp else 4.dp,
                            bottomEnd = if (isUser) 4.dp else 18.dp
                        )
                    )
                    .background(
                        if (isUser) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.surfaceVariant
                    )
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Text(
                    text = message.content,
                    style = MaterialTheme.typography.bodyMedium,
                    lineHeight = 20.sp,
                    color = if (isUser) MaterialTheme.colorScheme.onPrimary
                    else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Action Proposal Card (Google Meet, WhatsApp, Email Draft)
            if (!isUser && message.action_proposal != null) {
                ActionProposalCard(action = message.action_proposal)
            }

            // Audio Player Controls for Assistant Messages
            if (!isUser && message.audio_base64 != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(start = 4.dp)
                ) {
                    Surface(
                        shape = RoundedCornerShape(16.dp),
                        color = if (isPlayingAudio) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.primaryContainer,
                        modifier = Modifier
                            .clip(RoundedCornerShape(16.dp))
                            .clickable { onToggleAudio() }
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp)
                        ) {
                            Icon(
                                imageVector = if (isPlayingAudio) Icons.Default.Pause else Icons.Default.PlayArrow,
                                contentDescription = if (isPlayingAudio) "Pause Voice" else "Play Voice",
                                modifier = Modifier.size(16.dp),
                                tint = if (isPlayingAudio) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onPrimaryContainer
                            )
                            Text(
                                if (isPlayingAudio) "Playing..." else "Play Voice",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (isPlayingAudio) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                    }

                    // Provider badge
                    Text(
                        message.audio_provider ?: "IndicF5",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.outline
                    )
                }
            }
        }
    }
}

@Composable
fun ActionProposalCard(
    action: ActionProposalPayload,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var isDispatched by remember { mutableStateOf(false) }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.primary.copy(alpha = 0.35f)
        )
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            when (action.action_type) {
                "schedule_meeting", "create_calendar_event" -> {
                    val title = action.parameters["title"]?.jsonPrimitive?.content ?: "Google Meet Meeting"
                    val date = action.parameters["date"]?.jsonPrimitive?.content ?: ""
                    val time = action.parameters["time"]?.jsonPrimitive?.content ?: action.parameters["start_time"]?.jsonPrimitive?.content ?: ""
                    val meetLink = action.meet_link ?: action.parameters["meet_link"]?.jsonPrimitive?.content

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.VideoCall,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "Google Meet Invitation",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        title,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    if (date.isNotBlank() || time.isNotBlank()) {
                        Text(
                            "⏰ $date $time".trim(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    if (!meetLink.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "🔗 $meetLink",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        if (!meetLink.isNullOrBlank()) {
                            Button(
                                onClick = {
                                    try {
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(meetLink)).apply {
                                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                        }
                                        context.startActivity(intent)
                                    } catch (e: Exception) {
                                        Toast.makeText(context, "Could not open Meet link: ${e.message}", Toast.LENGTH_SHORT).show()
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = MaterialTheme.colorScheme.primary
                                )
                            ) {
                                Text("Join Meet", fontSize = 12.sp)
                            }
                        }
                        Button(
                            onClick = {
                                val res = ActionDispatcher.dispatchAction(context, "schedule_meeting", action.parameters)
                                isDispatched = res.isSuccess
                                Toast.makeText(
                                    context,
                                    if (res.isSuccess) "Opened calendar event" else res.exceptionOrNull()?.message ?: "Failed",
                                    Toast.LENGTH_SHORT
                                ).show()
                            },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isDispatched) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.primaryContainer,
                                contentColor = if (isDispatched) MaterialTheme.colorScheme.onSecondary else MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        ) {
                            Text(if (isDispatched) "Added ✓" else "Add Calendar", fontSize = 12.sp)
                        }
                    }
                }

                "send_whatsapp_message" -> {
                    val recipient = action.parameters["recipient"]?.jsonPrimitive?.content ?: action.parameters["sender"]?.jsonPrimitive?.content ?: "Contact"
                    val msg = action.parameters["message"]?.jsonPrimitive?.content ?: action.parameters["suggested_reply"]?.jsonPrimitive?.content ?: ""

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Chat,
                            contentDescription = null,
                            tint = Color(0xFF25D366),
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "WhatsApp Draft Reply",
                            style = MaterialTheme.typography.labelLarge,
                            color = Color(0xFF1E8E3E),
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "To: $recipient",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    if (msg.isNotBlank()) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            "\"$msg\"",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Button(
                        onClick = {
                            val res = ActionDispatcher.dispatchAction(context, "send_whatsapp_message", action.parameters)
                            isDispatched = res.isSuccess
                            Toast.makeText(
                                context,
                                if (res.isSuccess) "Opened WhatsApp" else res.exceptionOrNull()?.message ?: "Failed",
                                Toast.LENGTH_SHORT
                            ).show()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF25D366),
                            contentColor = Color.White
                        )
                    ) {
                        Text(if (isDispatched) "Dispatched ✓" else "Send on WhatsApp", fontSize = 13.sp)
                    }
                }

                "draft_email", "send_email" -> {
                    val recipient = action.parameters["recipient"]?.jsonPrimitive?.content ?: ""
                    val subject = action.parameters["subject"]?.jsonPrimitive?.content ?: "Email Draft"
                    val body = action.parameters["body"]?.jsonPrimitive?.content ?: ""

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Email,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "Email Draft",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    if (recipient.isNotBlank()) {
                        Text(
                            "To: $recipient",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Text(
                        subject,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (body.isNotBlank()) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            body.take(120) + if (body.length > 120) "..." else "",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Button(
                        onClick = {
                            val res = ActionDispatcher.dispatchAction(context, "draft_email", action.parameters)
                            isDispatched = res.isSuccess
                            Toast.makeText(
                                context,
                                if (res.isSuccess) "Opened Email Client" else res.exceptionOrNull()?.message ?: "Failed",
                                Toast.LENGTH_SHORT
                            ).show()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary
                        )
                    ) {
                        Text(if (isDispatched) "Opened ✓" else "Open in Email App", fontSize = 13.sp)
                    }
                }

                else -> {
                    Text(
                        action.description ?: "Proposed Action: ${action.action_type}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}
