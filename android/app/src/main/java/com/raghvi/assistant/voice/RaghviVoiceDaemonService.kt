package com.raghvi.assistant.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.raghvi.assistant.MainActivity
import com.raghvi.assistant.R
import com.raghvi.assistant.actions.ActionDispatcher
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.LiveGeminiVoiceRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Background Foreground Service that keeps Raghvi listening for "Hey Raghvi" / "Raghvi"
 * even when the app is minimized or closed.
 *
 * Behaves like Siri or Google Assistant:
 * - Detects wake phrase ("Hey Raghvi", "Raghvi")
 * - Dispatches voice command to backend live Gemini voice endpoint
 * - Plays cloned Hindi voice response directly via speaker
 * - Dispatches any calendar/email/WhatsApp action proposal
 */
class RaghviVoiceDaemonService : Service() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var voiceInputManager: VoiceInputManager? = null

    companion object {
        private const val TAG = "RaghviVoiceDaemon"
        private const val NOTIFICATION_ID = 2026
        private const val CHANNEL_ID = "raghvi_voice_daemon_channel"

        const val ACTION_START_LISTENING = "com.raghvi.assistant.START_BACKGROUND_LISTENING"
        const val ACTION_STOP_LISTENING = "com.raghvi.assistant.STOP_BACKGROUND_LISTENING"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Starting Raghvi Voice Daemon Service...")
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("Listening for 'Hey Raghvi'..."))

        initVoiceListener()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_LISTENING) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    private fun initVoiceListener() {
        voiceInputManager = VoiceInputManager(this).apply {
            isContinuous = true
            onResultListener = { spoken, detectedWakeWord, command ->
                Log.d(TAG, "Background voice heard: '$spoken' (wakeWord: $detectedWakeWord, command: '$command')")

                if (detectedWakeWord != null || WakePhraseDetector.isWakePhrase(spoken)) {
                    handleWakeActivation(command.ifBlank { spoken })
                }
            }
            startListening("hi-IN")
        }
    }

    private fun handleWakeActivation(command: String) {
        val cleanCommand = command.trim()
        val query = if (cleanCommand.isBlank() || WakePhraseDetector.isWakePhrase(cleanCommand)) {
            "Namaste Raghvi"
        } else {
            cleanCommand
        }

        updateNotification("Processing: $query...")

        serviceScope.launch(Dispatchers.IO) {
            try {
                val liveResponse = ApiClient.authApi.sendLiveGeminiVoice(
                    LiveGeminiVoiceRequest(
                        message = query,
                        mode = "chat"
                    )
                )

                // 1. Play cloned Hindi speech out loud even if app is closed!
                val audioBase64 = liveResponse.audio_base64
                if (!audioBase64.isNullOrBlank()) {
                    AudioPlayer.playBase64(applicationContext, "bg-wake-reply", audioBase64)
                }

                // 2. Dispatch any scheduled meeting / WhatsApp / email action
                val proposal = liveResponse.action_proposal
                if (proposal != null) {
                    ActionDispatcher.dispatchAction(applicationContext, proposal.action_type, proposal.parameters)
                }

                updateNotification("Raghvi: ${liveResponse.assistant_message.take(60)}...")
            } catch (e: Exception) {
                Log.e(TAG, "Error handling wake command in background", e)
                updateNotification("Listening for 'Hey Raghvi'...")
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Raghvi Voice Assistant Background Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Runs background microphone listening for hands-free 'Hey Raghvi' wake-phrase."
                setShowBadge(false)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(statusText: String): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingOpenIntent = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val stopIntent = Intent(this, RaghviVoiceDaemonService::class.java).apply {
            action = ACTION_STOP_LISTENING
        }
        val pendingStopIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Raghvi AI Assistant")
            .setContentText(statusText)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(pendingOpenIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", pendingStopIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }

    override fun onDestroy() {
        Log.i(TAG, "Stopping Raghvi Voice Daemon Service...")
        voiceInputManager?.stopListening()
        voiceInputManager?.destroy()
        voiceInputManager = null
        serviceScope.cancel()
        super.onDestroy()
    }
}
