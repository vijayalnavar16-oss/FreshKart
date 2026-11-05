package com.freshkart.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class ProductViewModelFactory : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (!modelClass.isAssignableFrom(ProductViewModel::class.java)) {
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
        val client = SupabaseClientProvider.client
        return ProductViewModel(
            authRepository = AuthRepository(client),
            productRepository = ProductRepository(client),
        ) as T
    }
}
