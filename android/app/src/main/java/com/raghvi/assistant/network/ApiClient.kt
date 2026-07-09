package com.raghvi.assistant.network

import android.content.Context
import com.raghvi.assistant.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

object ApiClient {
    private val json = Json { ignoreUnknownKeys = true }
    private lateinit var tokenManager: TokenManager

    var onAuthenticationRequired: (() -> Unit)? = null

    fun initialize(context: Context, onAuthenticationRequired: (() -> Unit)? = null) {
        if (!::tokenManager.isInitialized) {
            tokenManager = TokenManager(context.applicationContext)
        }
        this.onAuthenticationRequired = onAuthenticationRequired
    }

    fun tokens(): TokenManager {
        check(::tokenManager.isInitialized) { "ApiClient.initialize must be called first." }
        return tokenManager
    }

    private val refreshRetrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    private val refreshApi: RaghviApiService by lazy {
        refreshRetrofit.create(RaghviApiService::class.java)
    }

    private val authenticatedClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .addInterceptor(
                AuthInterceptor(
                    tokenStore = tokens(),
                    refreshApi = lazy { refreshApi },
                    onAuthenticationRequired = {
                        onAuthenticationRequired?.invoke()
                    }
                )
            )
            .build()
    }

    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(authenticatedClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    val healthApi: RaghviApiService by lazy { retrofit.create(RaghviApiService::class.java) }
    val authApi: RaghviApiService by lazy { retrofit.create(RaghviApiService::class.java) }
}
