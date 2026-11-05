package com.freshkart.app

import io.github.jan.supabase.auth.providers.builtin.Email
import kotlinx.coroutines.CancellationException

class AuthRepository(
    private val supabase: io.github.jan.supabase.SupabaseClient,
) {
    suspend fun signUp(email: String, password: String): Result<Unit> =
        safely {
            supabase.auth.signUpWith(Email) { this.email = email; this.password = password }
            Unit
        }

    suspend fun signIn(email: String, password: String): Result<Unit> =
        safely {
            supabase.auth.signInWith(Email) { this.email = email; this.password = password }
            Unit
        }

    suspend fun signOut(): Result<Unit> = safely {
        supabase.auth.signOut()
        Unit
    }

    suspend fun currentUserId(): Result<String?> =
        safely { supabase.auth.currentUserOrNull()?.id }
}

private suspend fun <T> safely(block: suspend () -> T): Result<T> =
    try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (exception: Exception) {
        Result.failure(exception)
    }
