package com.freshkart.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ProductUiState(
    val checkingSession: Boolean = true,
    val userId: String? = null,
    val products: List<Product> = emptyList(),
    val busy: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class ProductViewModel(
    private val authRepository: AuthRepository,
    private val productRepository: ProductRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(ProductUiState())
    val state = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val result = authRepository.currentUserId()
            if (result.isFailure) {
                _state.update { it.copy(checkingSession = false) }
                fail(result.exceptionOrNull() ?: IllegalStateException("Could not restore the sign-in session."))
                return@launch
            }
            val userId = result.getOrNull()
            _state.update { it.copy(checkingSession = false, userId = userId) }
            if (userId != null) loadProducts()
        }
    }

    fun signIn(email: String, password: String) {
        viewModelScope.launch {
            beginAction()
            val result = authRepository.signIn(email.trim(), password)
            if (result.isFailure) fail(result.exceptionOrNull() ?: IllegalStateException("Sign-in failed."))
            else finishAuthentication()
            endAction()
        }
    }

    fun signUp(email: String, password: String) {
        viewModelScope.launch {
            beginAction()
            val signUpResult = authRepository.signUp(email.trim(), password)
            if (signUpResult.isFailure) {
                fail(signUpResult.exceptionOrNull() ?: IllegalStateException("Sign-up failed."))
            } else {
                val userIdResult = authRepository.currentUserId()
                if (userIdResult.isFailure) {
                    fail(userIdResult.exceptionOrNull() ?: IllegalStateException("Could not read the new session."))
                } else {
                    val userId = userIdResult.getOrNull()
                    if (userId == null) {
                        _state.update {
                            it.copy(message = "Account created. Check your email to confirm, then sign in.")
                        }
                    } else {
                        _state.update { it.copy(userId = userId) }
                        loadProducts()
                    }
                }
            }
            endAction()
        }
    }

    fun signOut() {
        viewModelScope.launch {
            beginAction()
            authRepository.signOut().fold(
                onSuccess = {
                    _state.update { ProductUiState(checkingSession = false) }
                },
                onFailure = { fail(it) },
            )
            endAction()
        }
    }

    fun refreshProducts() {
        viewModelScope.launch { loadProducts() }
    }

    fun addProduct(draft: ProductDraft) {
        mutate { productRepository.add(draft) }
    }

    fun toggleAvailability(product: Product) {
        mutate { productRepository.update(product.copy(isAvailable = !product.isAvailable)) }
    }

    fun deleteProduct(id: String) {
        mutate { productRepository.delete(id) }
    }

    fun dismissMessage() {
        _state.update { it.copy(error = null, message = null) }
    }

    private fun mutate(action: suspend () -> Result<Unit>) {
        viewModelScope.launch {
            beginAction()
            val result = action()
            if (result.isFailure) {
                fail(result.exceptionOrNull() ?: IllegalStateException("Product operation failed."))
            } else {
                loadProducts()
            }
            endAction()
        }
    }

    private suspend fun finishAuthentication() {
        val result = authRepository.currentUserId()
        if (result.isFailure) {
            fail(result.exceptionOrNull() ?: IllegalStateException("Could not read the signed-in session."))
            return
        }
        val userId = result.getOrNull()
        if (userId == null) {
            _state.update { it.copy(message = "Sign-in succeeded, but no user session was returned.") }
        } else {
            _state.update { it.copy(userId = userId, message = null) }
            loadProducts()
        }
    }

    private fun beginAction() {
        _state.update { it.copy(busy = true, error = null, message = null) }
    }

    private suspend fun loadProducts() {
        _state.update { it.copy(busy = true, error = null, message = null) }
        productRepository.getAll().fold(
            onSuccess = { products ->
                _state.update { it.copy(products = products) }
            },
            onFailure = { fail(it) },
        )
        endAction()
    }

    private fun endAction() {
        _state.update { it.copy(busy = false) }
    }

    private fun fail(error: Throwable) {
        _state.update {
            it.copy(error = error.message?.takeIf(String::isNotBlank) ?: "The request failed. Please try again.")
        }
    }
}
