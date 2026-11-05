package com.freshkart.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels

class MainActivity : ComponentActivity() {
    private val viewModel: ProductViewModel by viewModels {
        ProductViewModelFactory()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BuildConfig.SUPABASE_URL.isBlank() || BuildConfig.SUPABASE_ANON_KEY.isBlank()) {
            setContent {
                SupabaseConfigurationRequired()
            }
        } else {
            setContent {
                FreshKartApp(viewModel)
            }
        }
    }
}
