package com.raghvi.assistant.network

import android.content.Context
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL

class BiometricAuthWindow(
    private val windowMillis: Long = REAUTH_WINDOW_MILLIS
) {
    fun isFresh(lastAuthenticatedAtMillis: Long?, nowMillis: Long): Boolean {
        if (lastAuthenticatedAtMillis == null) return false
        if (nowMillis < lastAuthenticatedAtMillis) return false
        return nowMillis - lastAuthenticatedAtMillis <= windowMillis
    }

    companion object {
        const val REAUTH_WINDOW_MILLIS = 30_000L
    }
}

class BiometricAuthManager(
    private val tokenManager: TokenManager,
    private val authWindow: BiometricAuthWindow = BiometricAuthWindow(),
    private val clock: () -> Long = { System.currentTimeMillis() }
) {
    fun canAuthenticate(context: Context): Boolean {
        val result = androidx.biometric.BiometricManager.from(context).canAuthenticate(
            BIOMETRIC_STRONG or DEVICE_CREDENTIAL
        )
        return result == androidx.biometric.BiometricManager.BIOMETRIC_SUCCESS
    }

    fun requiresReauthentication(): Boolean {
        return !authWindow.isFresh(tokenManager.getLastBiometricAuthAt(), clock())
    }

    fun markAuthenticated() {
        tokenManager.markBiometricAuthenticated(clock())
    }
}
