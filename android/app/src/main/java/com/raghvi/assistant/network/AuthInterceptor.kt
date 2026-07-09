package com.raghvi.assistant.network

import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val tokenStore: AuthTokenStore,
    private val refreshApi: Lazy<RaghviApiService>,
    private val onAuthenticationRequired: () -> Unit = {}
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val accessToken = tokenStore.getAccessToken()
        val authenticatedRequest = if (accessToken.isNullOrBlank()) {
            originalRequest
        } else {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $accessToken")
                .build()
        }

        val response = chain.proceed(authenticatedRequest)
        if (response.code != 401 || accessToken.isNullOrBlank()) {
            return response
        }

        val refreshedTokens = refreshTokens()
        if (refreshedTokens == null) {
            tokenStore.clearTokens()
            onAuthenticationRequired()
            return response
        }

        response.close()
        val retryRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer ${refreshedTokens.access_token}")
            .build()
        return chain.proceed(retryRequest)
    }

    private fun refreshTokens(): AuthTokens? {
        val refreshToken = tokenStore.getRefreshToken() ?: return null
        return runBlocking {
            try {
                val tokens = refreshApi.value.refresh(RefreshRequest(refreshToken))
                tokenStore.saveTokens(tokens.access_token, tokens.refresh_token)
                tokens
            } catch (_: Exception) {
                null
            }
        }
    }
}
