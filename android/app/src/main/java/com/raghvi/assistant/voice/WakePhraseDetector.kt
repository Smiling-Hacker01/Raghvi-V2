package com.raghvi.assistant.voice

import java.util.Locale

/**
 * Handles wake-word / wake-phrase recognition and intent stripping.
 *
 * Supported activation phrases:
 * - "Hey Raghvi" / "Hey Raghavi"
 * - "Raghvi" / "Raghavi"
 * - "Aur Raghvi, sun rahi ho?" / "Aur Raghvi sun rahi ho"
 */
data class WakePhraseResult(
    val isDetected: Boolean,
    val matchedPhrase: String? = null,
    val remainingCommand: String = ""
)

object WakePhraseDetector {

    private val SUPPORTED_PHRASES = listOf(
        "aur raghvi sun rahi ho",
        "aur raghavi sun rahi ho",
        "hey raghvi",
        "hey raghavi",
        "sun rahi ho raghvi",
        "raghvi",
        "raghavi"
    )

    /**
     * Normalizes an input string by removing punctuation and extra whitespaces.
     */
    fun normalize(input: String): String {
        return input.lowercase(Locale.ROOT)
            .replace(Regex("[?,.!;:\"'\\-_]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }

    /**
     * Evaluates whether an input contains an authorized wake phrase.
     */
    fun isWakePhrase(input: String): Boolean {
        val normalized = normalize(input)
        return SUPPORTED_PHRASES.any { phrase ->
            normalized == phrase || normalized.startsWith("$phrase ")
        }
    }

    /**
     * Evaluates input and extracts any command that follows the wake phrase.
     */
    fun detect(input: String): WakePhraseResult {
        val normalized = normalize(input)
        for (phrase in SUPPORTED_PHRASES) {
            if (normalized == phrase) {
                return WakePhraseResult(
                    isDetected = true,
                    matchedPhrase = phrase,
                    remainingCommand = ""
                )
            }
            if (normalized.startsWith("$phrase ")) {
                val remainder = normalized.removePrefix("$phrase ").trim()
                return WakePhraseResult(
                    isDetected = true,
                    matchedPhrase = phrase,
                    remainingCommand = remainder
                )
            }
        }
        return WakePhraseResult(isDetected = false)
    }
}
