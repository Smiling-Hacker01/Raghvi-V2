package com.raghvi.assistant.network

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class TokenManager(context: Context) : AuthTokenStore {
    private val appContext = context.applicationContext
    private val masterKey = MasterKey.Builder(appContext)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val preferences = EncryptedSharedPreferences.create(
        appContext,
        PREFERENCES_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    override fun saveTokens(accessToken: String, refreshToken: String) {
        preferences.edit()
            .putString(KEY_ACCESS_TOKEN, accessToken)
            .putString(KEY_REFRESH_TOKEN, refreshToken)
            .apply()
    }

    override fun getAccessToken(): String? = preferences.getString(KEY_ACCESS_TOKEN, null)

    override fun getRefreshToken(): String? = preferences.getString(KEY_REFRESH_TOKEN, null)

    fun hasRefreshToken(): Boolean = !getRefreshToken().isNullOrBlank()

    override fun clearTokens() {
        preferences.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_LAST_BIOMETRIC_AUTH_AT)
            .apply()
    }

    fun markBiometricAuthenticated(nowMillis: Long = System.currentTimeMillis()) {
        preferences.edit().putLong(KEY_LAST_BIOMETRIC_AUTH_AT, nowMillis).apply()
    }

    fun getLastBiometricAuthAt(): Long? {
        if (!preferences.contains(KEY_LAST_BIOMETRIC_AUTH_AT)) return null
        return preferences.getLong(KEY_LAST_BIOMETRIC_AUTH_AT, 0L)
    }

    companion object {
        private const val PREFERENCES_NAME = "raghvi_auth_tokens"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_LAST_BIOMETRIC_AUTH_AT = "last_biometric_auth_at"
    }
}
