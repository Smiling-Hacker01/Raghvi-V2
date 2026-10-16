package com.raghvi.assistant.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.util.Locale

data class VoiceInputState(
    val isListening: Boolean = false,
    val rmsLevel: Float = 0f,
    val partialText: String = "",
    val error: String? = null
)

class VoiceInputManager(private val context: Context) {
    private var speechRecognizer: SpeechRecognizer? = null

    private val _inputState = MutableStateFlow(VoiceInputState())
    val inputState: StateFlow<VoiceInputState> = _inputState.asStateFlow()

    var onResultListener: ((fullText: String, detectedWakeWord: String?, command: String) -> Unit)? = null
    var isContinuous: Boolean = false
    private var activeLanguage: String = "hi-IN"
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())

    init {
        initRecognizer()
    }

    private fun initRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
                setRecognitionListener(createListener())
            }
        } else {
            Log.w(TAG, "Speech recognition is not available on this device")
            _inputState.update { it.copy(error = "Speech recognition unavailable") }
        }
    }

    private fun createListener(): RecognitionListener {
        return object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                _inputState.update { it.copy(isListening = true, error = null, partialText = "") }
            }

            override fun onBeginningOfSpeech() {
                _inputState.update { it.copy(isListening = true) }
            }

            override fun onRmsChanged(rmsdB: Float) {
                _inputState.update { it.copy(rmsLevel = rmsdB) }
            }

            override fun onBufferReceived(buffer: ByteArray?) {}

            override fun onEndOfSpeech() {
                _inputState.update { it.copy(isListening = false, rmsLevel = 0f) }
            }

            override fun onError(error: Int) {
                val errorMsg = when (error) {
                    SpeechRecognizer.ERROR_AUDIO -> "Audio recording error"
                    SpeechRecognizer.ERROR_CLIENT -> "Client side error"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission required"
                    SpeechRecognizer.ERROR_NETWORK -> "Network connection error"
                    SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout"
                    SpeechRecognizer.ERROR_NO_MATCH -> "No speech recognized. Try again."
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognition service busy"
                    SpeechRecognizer.ERROR_SERVER -> "Server error"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech detected"
                    else -> "Speech recognition error ($error)"
                }
                _inputState.update {
                    it.copy(isListening = false, rmsLevel = 0f, error = errorMsg)
                }

                if (isContinuous) {
                    mainHandler.removeCallbacksAndMessages(null)
                    mainHandler.postDelayed({
                        if (isContinuous) startListening(activeLanguage)
                    }, 600)
                }
            }

            override fun onResults(results: Bundle?) {
                _inputState.update { it.copy(isListening = false, rmsLevel = 0f) }
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val spoken = matches?.firstOrNull()?.trim() ?: return

                val detection = WakePhraseDetector.detect(spoken)
                val command = if (detection.isDetected && detection.remainingCommand.isNotBlank()) {
                    detection.remainingCommand
                } else {
                    spoken
                }

                onResultListener?.invoke(spoken, detection.matchedPhrase, command)

                if (isContinuous) {
                    mainHandler.removeCallbacksAndMessages(null)
                    mainHandler.postDelayed({
                        if (isContinuous) startListening(activeLanguage)
                    }, 750)
                }
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val partial = matches?.firstOrNull() ?: ""
                _inputState.update { it.copy(partialText = partial) }
            }

            override fun onEvent(eventType: Int, params: Bundle?) {}
        }
    }

    /**
     * Start listening for voice input with Indian English & Hindi support.
     */
    fun startListening(languageCode: String = "hi-IN") {
        activeLanguage = languageCode
        if (speechRecognizer == null) {
            initRecognizer()
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageCode)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, languageCode)
            putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, false)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }

        try {
            speechRecognizer?.startListening(intent)
            _inputState.update { it.copy(isListening = true, error = null, partialText = "") }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start speech recognition", e)
            _inputState.update { it.copy(isListening = false, error = e.message) }
            if (isContinuous) {
                mainHandler.postDelayed({
                    if (isContinuous) startListening(activeLanguage)
                }, 1000)
            }
        }
    }

    fun stopListening() {
        isContinuous = false
        mainHandler.removeCallbacksAndMessages(null)
        try {
            speechRecognizer?.stopListening()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to stop listening", e)
        }
        _inputState.update { it.copy(isListening = false, rmsLevel = 0f) }
    }

    fun destroy() {
        try {
            speechRecognizer?.destroy()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to destroy speech recognizer", e)
        }
        speechRecognizer = null
    }

    companion object {
        private const val TAG = "VoiceInputManager"
    }
}
