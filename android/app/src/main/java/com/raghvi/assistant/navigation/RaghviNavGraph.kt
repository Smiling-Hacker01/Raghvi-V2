package com.raghvi.assistant.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.raghvi.assistant.ui.backendstatus.BackendStatusScreen
import com.raghvi.assistant.ui.splash.SplashScreen
import com.raghvi.assistant.ui.welcome.WelcomeScreen

object RaghviDestinations {
    const val SPLASH = "splash"
    const val WELCOME = "welcome"
    const val BACKEND_STATUS = "backend_status"
}

@Composable
fun RaghviNavGraph(modifier: Modifier = Modifier) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = RaghviDestinations.SPLASH,
        modifier = modifier
    ) {
        composable(RaghviDestinations.SPLASH) {
            SplashScreen(
                onTimeout = {
                    navController.navigate(RaghviDestinations.WELCOME) {
                        popUpTo(RaghviDestinations.SPLASH) { inclusive = true }
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