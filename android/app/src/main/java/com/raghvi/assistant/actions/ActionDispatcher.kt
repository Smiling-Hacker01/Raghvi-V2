package com.raghvi.assistant.actions

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.CalendarContract
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

object ActionDispatcher {

    /**
     * Safely dispatches a confirmed user action using explicit Android Intents.
     * Prevents arbitrary shell execution or unsafe intents.
     */
    fun dispatchAction(
        context: Context,
        actionType: String,
        parameters: JsonObject
    ): Result<String> {
        return try {
            when (actionType) {
                "draft_email", "send_email" -> dispatchDraftEmail(context, parameters)
                "schedule_meeting", "create_calendar_event" -> dispatchScheduleMeeting(context, parameters)
                "send_whatsapp_message" -> dispatchWhatsApp(context, parameters)
                "open_maps" -> dispatchOpenMaps(context, parameters)
                "open_app" -> dispatchOpenApp(context, parameters)
                else -> Result.failure(IllegalArgumentException("Unsupported action type: $actionType"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun dispatchDraftEmail(context: Context, params: JsonObject): Result<String> {
        val recipient = params["recipient"]?.jsonPrimitive?.content ?: ""
        val subject = params["subject"]?.jsonPrimitive?.content ?: ""
        val body = params["body"]?.jsonPrimitive?.content ?: ""

        val emailIntent = Intent(Intent.ACTION_SENDTO).apply {
            data = Uri.parse("mailto:$recipient")
            if (subject.isNotBlank()) putExtra(Intent.EXTRA_SUBJECT, subject)
            if (body.isNotBlank()) putExtra(Intent.EXTRA_TEXT, body)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return if (emailIntent.resolveActivity(context.packageManager) != null || true) {
            context.startActivity(emailIntent)
            Result.success("Opened email client to draft message")
        } else {
            Result.failure(IllegalStateException("No email client application found on device"))
        }
    }

    private fun dispatchOpenMaps(context: Context, params: JsonObject): Result<String> {
        val destination = params["destination"]?.jsonPrimitive?.content
            ?: params["address"]?.jsonPrimitive?.content
            ?: ""

        if (destination.isBlank()) {
            return Result.failure(IllegalArgumentException("Destination address is required"))
        }

        val mapUri = Uri.parse("geo:0,0?q=" + Uri.encode(destination))
        val mapIntent = Intent(Intent.ACTION_VIEW, mapUri).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(mapIntent)
            Result.success("Opened navigation to $destination")
        } catch (e: Exception) {
            Result.failure(IllegalStateException("No map or browser application available", e))
        }
    }

    private fun dispatchOpenApp(context: Context, params: JsonObject): Result<String> {
        val packageName = params["package_name"]?.jsonPrimitive?.content
            ?: params["app_name"]?.jsonPrimitive?.content
            ?: ""

        if (packageName.isBlank()) {
            return Result.failure(IllegalArgumentException("Package or application name required"))
        }

        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
        return if (launchIntent != null) {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(launchIntent)
            Result.success("Launched application: $packageName")
        } else {
            Result.failure(IllegalStateException("Application '$packageName' is not installed"))
        }
    }

    private fun dispatchScheduleMeeting(context: Context, params: JsonObject): Result<String> {
        val title = params["title"]?.jsonPrimitive?.content ?: "Meeting"
        val description = params["description"]?.jsonPrimitive?.content ?: ""
        val meetLink = params["meet_link"]?.jsonPrimitive?.content ?: ""
        val attendees = try {
            params["attendees"]?.jsonArray?.map { it.jsonPrimitive.content }?.joinToString(",") ?: ""
        } catch (_: Exception) {
            ""
        }

        val fullDescription = if (meetLink.isNotBlank()) {
            if (description.isNotBlank()) "$description\n\nGoogle Meet: $meetLink" else "Google Meet: $meetLink"
        } else {
            description
        }

        val calIntent = Intent(Intent.ACTION_INSERT).apply {
            data = CalendarContract.Events.CONTENT_URI
            putExtra(CalendarContract.Events.TITLE, title)
            if (fullDescription.isNotBlank()) putExtra(CalendarContract.Events.DESCRIPTION, fullDescription)
            if (meetLink.isNotBlank()) putExtra(CalendarContract.Events.EVENT_LOCATION, meetLink)
            if (attendees.isNotBlank()) putExtra(Intent.EXTRA_EMAIL, attendees)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(calIntent)
            Result.success("Opened calendar to schedule meeting '$title'")
        } catch (e: Exception) {
            Result.failure(IllegalStateException("No calendar application found", e))
        }
    }

    private fun dispatchWhatsApp(context: Context, params: JsonObject): Result<String> {
        val phone = params["phone"]?.jsonPrimitive?.content
            ?: params["recipient"]?.jsonPrimitive?.content
            ?: ""
        val message = params["message"]?.jsonPrimitive?.content
            ?: params["text"]?.jsonPrimitive?.content
            ?: ""

        val cleanPhone = phone.replace("+", "").replace(" ", "").replace("-", "")
        val uri = if (cleanPhone.isNotBlank()) {
            Uri.parse("https://api.whatsapp.com/send?phone=$cleanPhone&text=" + Uri.encode(message))
        } else {
            Uri.parse("https://api.whatsapp.com/send?text=" + Uri.encode(message))
        }

        val waIntent = Intent(Intent.ACTION_VIEW, uri).apply {
            setPackage("com.whatsapp")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return try {
            context.startActivity(waIntent)
            Result.success("Opened WhatsApp to send message")
        } catch (_: Exception) {
            val fallback = Intent(Intent.ACTION_VIEW, uri).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(fallback)
            Result.success("Opened messaging to send message")
        }
    }
}
