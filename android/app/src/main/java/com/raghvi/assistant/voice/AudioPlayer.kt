package com.raghvi.assistant.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Base64
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File
import java.io.FileOutputStream

data class AudioPlaybackState(
    val isPlaying: Boolean = false,
    val activeMessageId: String? = null,
    val errorMessage: String? = null
)

object AudioPlayer {
    private const val TAG = "RaghviAudioPlayer"
    private var mediaPlayer: MediaPlayer? = null
    private var currentTempFile: File? = null
    private var onCompletionCallback: (() -> Unit)? = null

    private val _playbackState = MutableStateFlow(AudioPlaybackState())
    val playbackState: StateFlow<AudioPlaybackState> = _playbackState.asStateFlow()

    /**
     * Decodes Base64 audio string, caches it locally, and streams playback.
     */
    fun playBase64(
        context: Context,
        messageId: String,
        base64Audio: String,
        onFinished: () -> Unit = {}
    ) {
        stop()

        try {
            val audioBytes = Base64.decode(base64Audio, Base64.DEFAULT)
            if (audioBytes == null || audioBytes.isEmpty()) {
                _playbackState.update {
                    it.copy(isPlaying = false, errorMessage = "Empty audio payload")
                }
                return
            }

            // Create temporary cache file
            val tempFile = File.createTempFile("raghvi_voice_", ".wav", context.cacheDir)
            FileOutputStream(tempFile).use { fos ->
                fos.write(audioBytes)
                fos.flush()
            }
            currentTempFile = tempFile
            onCompletionCallback = onFinished

            val player = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                        .build()
                )
                setDataSource(tempFile.absolutePath)
                setOnPreparedListener { mp ->
                    mp.start()
                    _playbackState.update {
                        it.copy(
                            isPlaying = true,
                            activeMessageId = messageId,
                            errorMessage = null
                        )
                    }
                }
                setOnCompletionListener {
                    stop()
                    onCompletionCallback?.invoke()
                }
                setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "MediaPlayer error: what=$what extra=$extra")
                    stop()
                    _playbackState.update {
                        it.copy(
                            isPlaying = false,
                            errorMessage = "Audio playback failed (code $what)"
                        )
                    }
                    true
                }
                prepareAsync()
            }
            mediaPlayer = player

        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize audio playback", e)
            _playbackState.update {
                it.copy(
                    isPlaying = false,
                    errorMessage = e.message ?: "Failed to play audio"
                )
            }
        }
    }

    /**
     * Stops audio playback and clears temp resources.
     */
    fun stop() {
        try {
            mediaPlayer?.let {
                if (it.isPlaying) {
                    it.stop()
                }
                it.reset()
                it.release()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Exception during mediaPlayer release", e)
        } finally {
            mediaPlayer = null
        }

        try {
            currentTempFile?.delete()
        } catch (_: Exception) {}
        currentTempFile = null

        _playbackState.update {
            it.copy(isPlaying = false, activeMessageId = null)
        }
    }

    /**
     * Toggle play/pause for a specific message.
     */
    fun togglePlay(
        context: Context,
        messageId: String,
        base64Audio: String,
        onFinished: () -> Unit = {}
    ) {
        if (_playbackState.value.isPlaying && _playbackState.value.activeMessageId == messageId) {
            stop()
        } else {
            playBase64(context, messageId, base64Audio, onFinished)
        }
    }
}
