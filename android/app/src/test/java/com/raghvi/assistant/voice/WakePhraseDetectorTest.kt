package com.raghvi.assistant.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WakePhraseDetectorTest {

    @Test
    fun testDetectExactWakePhrases() {
        assertTrue(WakePhraseDetector.isWakePhrase("Hey Raghvi"))
        assertTrue(WakePhraseDetector.isWakePhrase("Raghvi"))
        assertTrue(WakePhraseDetector.isWakePhrase("Aur Raghvi, sun rahi ho?"))
        assertTrue(WakePhraseDetector.isWakePhrase("Hey Raghavi"))
    }

    @Test
    fun testDetectWakePhraseWithFollowUpCommand() {
        val result = WakePhraseDetector.detect("Hey Raghvi, what is the weather today?")
        assertTrue(result.isDetected)
        assertEquals("hey raghvi", result.matchedPhrase)
        assertEquals("what is the weather today", result.remainingCommand)

        val hindiResult = WakePhraseDetector.detect("Aur Raghvi, sun rahi ho? Mera schedule batao")
        assertTrue(hindiResult.isDetected)
        assertEquals("aur raghvi sun rahi ho", hindiResult.matchedPhrase)
        assertEquals("mera schedule batao", hindiResult.remainingCommand)
    }

    @Test
    fun testIgnoresNonWakePhrases() {
        assertFalse(WakePhraseDetector.isWakePhrase("Good morning world"))
        assertFalse(WakePhraseDetector.isWakePhrase("What time is the meeting?"))
        assertFalse(WakePhraseDetector.isWakePhrase("Raghav is coming over"))
    }
}
