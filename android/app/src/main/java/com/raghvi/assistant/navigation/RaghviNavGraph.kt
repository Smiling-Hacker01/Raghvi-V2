package com.raghvi.assistant.navigation

import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.raghvi.assistant.network.ApiClient
import com.raghvi.assistant.ui.backendstatus.BackendStatusScreen
import com.raghvi.assistant.ui.login.LoginScreen
import com.raghvi.assistant.ui.splash.SplashScreen
import com.raghvi.assistant.ui.welcome.WelcomeScreen

object RaghviDestinations {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val WELCOME = "welcome"
    const val BACKEND_STATUS = "backend_status"
}

@Composable
fun RaghviNavGraph(modifier: Modifier = Modifier) {
    val navController = rememberNavController()
    val context = LocalContext.current
    val mainHandler = remember { Handler(Looper.getMainLooper()) }

    ApiClient.initialize(context.applicationContext)

    DisposableEffect(navController) {
        ApiClient.onAuthenticationRequired = {
            mainHandler.post {
                navController.navigate(RaghviDestinations.LOGIN) {
                    popUpTo(navController.graph.id) { inclusive = true }
                }
            }
        }
        onDispose {
            ApiClient.onAuthenticationRequired = null
        }
    }

    NavHost(
        navController = navController,
        startDestination = RaghviDestinations.SPLASH,
        modifier = modifier
    ) {
        composable(RaghviDestinations.SPLASH) {
            SplashScreen(
                onTimeout = {
                    val destination = if (ApiClient.tokens().hasRefreshToken()) {
                        RaghviDestinations.BACKEND_STATUS
                    } else {
                        RaghviDestinations.LOGIN
                    }
                    navController.navigate(destination) {
                        popUpTo(RaghviDestinations.SPLASH) { inclusive = true }
                    }
                }
            )
        }
        composable(RaghviDestinations.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(RaghviDestinations.BACKEND_STATUS) {
                        popUpTo(RaghviDestinations.LOGIN) { inclusive = true }
                    }
                }
            )
        }
        composable(RaghviDestinations.WELCOME) {
            WelcomeScreen(
                onContinue = { navController.navigate(RaghviDestinations.BACKEND_STATUS) }
            )
        }
        composable(RaghviDestinations.BACKEND_STATUS) {
            BackendStatusScreen()
        }
    }
}
