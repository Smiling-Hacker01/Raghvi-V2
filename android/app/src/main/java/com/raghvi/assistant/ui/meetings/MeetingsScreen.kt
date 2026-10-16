package com.raghvi.assistant.ui.meetings

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Notes
import androidx.compose.material.icons.filled.Audiotrack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.raghvi.assistant.network.MeetingActionItem
import com.raghvi.assistant.network.MeetingNoteItem
import com.raghvi.assistant.ui.components.RaghviBottomBar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MeetingsScreen(
    onNavigateBack: () -> Unit = {},
    onNavigateToTab: ((String) -> Unit)? = null,
    viewModel: MeetingsViewModel = viewModel()
) {
    val context = LocalContext.current
    val uiState by viewModel.uiState.collectAsState()

    var customTitle by remember { mutableStateOf("") }
    var rawTranscriptText by remember { mutableStateOf("") }
    var isRawTextInputVisible by remember { mutableStateOf(false) }

    // Dialog state
    var editingMeeting by remember { mutableStateOf<MeetingNoteItem?>(null) }
    var deletingMeeting by remember { mutableStateOf<MeetingNoteItem?>(null) }

    // Search query state
    var searchInput by remember { mutableStateOf("") }

    val audioPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            viewModel.uploadAudioFile(context, uri, customTitle.ifBlank { null })
            customTitle = ""
        }
    }

    LaunchedEffect(uiState.statusMessage, uiState.errorMessage) {
        if (uiState.statusMessage != null || uiState.errorMessage != null) {
            kotlinx.coroutines.delay(4000)
            viewModel.clearStatus()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Meeting Notes & Audio") },
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
                RaghviBottomBar(
                    currentDestination = "meetings",
                    onNavigate = onNavigateToTab
                )
            }
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            // Status banners
            uiState.statusMessage?.let { msg ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp)
                ) {
                    Text(
                        text = msg,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                }
            }

            uiState.errorMessage?.let { err ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp)
                ) {
                    Text(
                        text = err,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                }
            }

            // Audio Upload / Processing Progress
            if (uiState.isUploading) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = MaterialTheme.colorScheme.primary,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = uiState.uploadProgressMessage ?: "Processing audio...",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            color = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    }
                }
            }

            // Feed Manual Audio Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 12.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        text = "Feed Manual Audio & Generate Notes",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Upload any recorded meeting, phone call, or voice memo (.mp3, .m4a, .wav). Whisper will transcribe it and extract executive decisions and action items.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    OutlinedTextField(
                        value = customTitle,
                        onValueChange = { customTitle = it },
                        label = { Text("Meeting Title (optional)") },
                        placeholder = { Text("e.g. Q4 Sprint Planning") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = { audioPickerLauncher.launch("audio/*") },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                        ) {
                            Icon(Icons.Filled.UploadFile, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("Upload Audio")
                        }

                        OutlinedButton(
                            onClick = { isRawTextInputVisible = !isRawTextInputVisible }
                        ) {
                            Icon(Icons.AutoMirrored.Filled.Notes, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Paste Text")
                        }
                    }

                    // Expandable Raw Text Input
                    AnimatedVisibility(visible = isRawTextInputVisible) {
                        Column(modifier = Modifier.padding(top = 10.dp)) {
                            OutlinedTextField(
                                value = rawTranscriptText,
                                onValueChange = { rawTranscriptText = it },
                                label = { Text("Raw Transcript / Conversation") },
                                placeholder = { Text("Paste conversation or meeting notes text...") },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(110.dp),
                                maxLines = 5
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Button(
                                onClick = {
                                    val title = customTitle.ifBlank { "Meeting Notes (${java.time.LocalDate.now()})" }
                                    viewModel.createMeetingFromText(title, rawTranscriptText)
                                    rawTranscriptText = ""
                                    customTitle = ""
                                    isRawTextInputVisible = false
                                },
                                enabled = rawTranscriptText.isNotBlank(),
                                modifier = Modifier.align(Alignment.End)
                            ) {
                                Text("Process Transcript")
                            }
                        }
                    }
                }
            }

            // Search Bar
            OutlinedTextField(
                value = searchInput,
                onValueChange = {
                    searchInput = it
                    viewModel.loadMeetings(it)
                },
                placeholder = { Text("Search meeting notes, decisions, topics...") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                trailingIcon = {
                    if (searchInput.isNotEmpty()) {
                        IconButton(onClick = {
                            searchInput = ""
                            viewModel.loadMeetings(null)
                        }) {
                            Icon(Icons.Filled.Clear, contentDescription = "Clear")
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                singleLine = true
            )

            // Meeting Notes List
            if (uiState.isLoading && uiState.meetings.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (uiState.meetings.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(top = 32.dp),
                    contentAlignment = Alignment.TopCenter
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Filled.Audiotrack,
                            contentDescription = null,
                            modifier = Modifier.size(56.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = if (searchInput.isBlank()) "No meeting notes yet" else "No matching meeting notes",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Upload an audio recording or paste a transcript above to extract structured notes.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.meetings, key = { it.id }) { note ->
                        MeetingNoteCard(
                            note = note,
                            onExport = { viewModel.exportMarkdown(context, note) },
                            onEdit = { editingMeeting = note },
                            onDelete = { deletingMeeting = note }
                        )
                    }
                }
            }
        }
    }

    // Edit Meeting Dialog
    editingMeeting?.let { note ->
        var editTitle by remember { mutableStateOf(note.title) }
        var editSummary by remember { mutableStateOf(note.summary) }

        AlertDialog(
            onDismissRequest = { editingMeeting = null },
            title = { Text("Edit Meeting Note") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = editTitle,
                        onValueChange = { editTitle = it },
                        label = { Text("Title") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = editSummary,
                        onValueChange = { editSummary = it },
                        label = { Text("Executive Summary") },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(130.dp),
                        maxLines = 6
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.updateMeeting(note.id, editTitle, editSummary)
                        editingMeeting = null
                    }
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                TextButton(onClick = { editingMeeting = null }) {
                    Text("Cancel")
                }
            }
        )
    }

    // Delete Confirmation Dialog
    deletingMeeting?.let { note ->
        AlertDialog(
            onDismissRequest = { deletingMeeting = null },
            title = { Text("Delete Meeting Note?") },
            text = { Text("Are you sure you want to delete '${note.title}'? This action cannot be undone.") },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.deleteMeeting(note.id)
                        deletingMeeting = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { deletingMeeting = null }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun MeetingNoteCard(
    note: MeetingNoteItem,
    onExport: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var isTranscriptExpanded by remember { mutableStateOf(false) }
    val checkedActions = remember { mutableStateMapOf<Int, Boolean>() }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = note.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    val formattedDate = note.meeting_date.take(16).replace("T", " ")
                    Text(
                        text = formattedDate.ifBlank { note.created_at.take(10) },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                SuggestionChip(
                    onClick = {},
                    label = { Text("${(note.confidence_score * 100).toInt()}% confidence") }
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Executive Summary
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f))
                    .padding(12.dp)
            ) {
                Column {
                    Text(
                        text = "Executive Summary",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = note.summary,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }

            // Key Decisions
            if (note.key_decisions.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "Key Decisions",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                note.key_decisions.forEach { decision ->
                    Row(
                        modifier = Modifier.padding(vertical = 2.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        Icon(
                            imageVector = Icons.Filled.CheckCircle,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = decision,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }

            // Action Items
            if (note.action_items.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "Action Items",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                note.action_items.forEachIndexed { index, item ->
                    val isChecked = checkedActions[index] ?: false
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 1.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Checkbox(
                            checked = isChecked,
                            onCheckedChange = { checkedActions[index] = it }
                        )
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = item.task,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Medium
                            )
                            if (item.owner.isNotBlank() && item.owner != "Unassigned") {
                                Text(
                                    text = "Owner: ${item.owner}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                }
            }

            // Expandable Raw Transcript
            if (note.raw_transcript.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                TextButton(
                    onClick = { isTranscriptExpanded = !isTranscriptExpanded },
                    modifier = Modifier.padding(0.dp)
                ) {
                    Icon(
                        imageVector = if (isTranscriptExpanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(if (isTranscriptExpanded) "Hide Transcript" else "View Raw Transcript")
                }

                AnimatedVisibility(visible = isTranscriptExpanded) {
                    Text(
                        text = note.raw_transcript,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
                            .padding(8.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Action Buttons Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedButton(onClick = onExport) {
                    Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Export Markdown")
                }
                Spacer(modifier = Modifier.width(8.dp))
                IconButton(onClick = onEdit) {
                    Icon(Icons.Filled.Edit, contentDescription = "Edit", tint = MaterialTheme.colorScheme.primary)
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Filled.Delete, contentDescription = "Delete", tint = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}
