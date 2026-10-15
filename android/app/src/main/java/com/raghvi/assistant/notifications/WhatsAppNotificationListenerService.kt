package com.raghvi.assistant.notifications

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.network.SeedCommunicationRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class WhatsAppNotificationListenerService : NotificationListenerService() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    companion object {
        private const val TAG = "RaghviWhatsAppListener"
        private const val WHATSAPP_PKG = "com.whatsapp"
        private const val WHATSAPP_BIZ_PKG = "com.whatsapp.w4b"
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val pkg = sbn.packageName
        if (pkg != WHATSAPP_PKG && pkg != WHATSAPP_BIZ_PKG) return

        val extras = sbn.notification.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: return
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
            ?: extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()
            ?: return

        // Skip generic WhatsApp system notifications
        if (title.isBlank() || text.isBlank() || title.contains("WhatsApp", ignoreCase = true)) {
            return
        }

        val accountLabel = if (pkg == WHATSAPP_BIZ_PKG) "WhatsApp (Business)" else "WhatsApp (Personal)"
        Log.d(TAG, "Captured real $accountLabel message from $title: $text")

        // Sync to Raghvi backend so Raghvi knows the message context in real time
        serviceScope.launch {
            try {
                ApiClient.authApi.seedCommunication(
                    SeedCommunicationRequest(
                        channel = "whatsapp",
                        sender = title,
                        sender_name = title,
                        body = text,
                        account_label = accountLabel
                    )
                )
                Log.d(TAG, "Successfully synced incoming $accountLabel notification to Raghvi")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to sync WhatsApp notification to backend: ${e.message}")
            }
        }
    }
}
