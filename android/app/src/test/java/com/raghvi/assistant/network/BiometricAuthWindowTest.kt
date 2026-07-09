package com.raghvi.assistant.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BiometricAuthWindowTest {
    private val window = BiometricAuthWindow(windowMillis = 30_000L)

    @Test
    fun isFresh_returnsFalseWhenThereIsNoPreviousAuth() {
        assertFalse(window.isFresh(lastAuthenticatedAtMillis = null, nowMillis = 10_000L))
    }

    @Test
    fun isFresh_returnsTrueInsideThirtySecondWindow() {
        assertTrue(window.isFresh(lastAuthenticatedAtMillis = 10_000L, nowMillis = 39_999L))
    }

    @Test
    fun isFresh_returnsFalseAfterThirtySecondWindow() {
        assertFalse(window.isFresh(lastAuthenticatedAtMillis = 10_000L, nowMillis = 40_001L))
    }

    @Test
    fun isFresh_returnsFalseWhenClockMovesBackwards() {
        assertFalse(window.isFresh(lastAuthenticatedAtMillis = 10_000L, nowMillis = 9_999L))
    }
}
