package com.freshkart.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import java.util.Locale

@Composable
fun SupabaseConfigurationRequired() {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text("Supabase is not configured", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "Add SUPABASE_URL and SUPABASE_ANON_KEY to android/local.properties, then rebuild.",
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
        }
    }
}

@Composable
fun FreshKartApp(viewModel: ProductViewModel) {
    val state by viewModel.state.collectAsState()
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            when {
                state.checkingSession -> CenteredProgress()
                state.userId == null -> LoginScreen(state, viewModel)
                else -> ProductListScreen(state, viewModel)
            }
        }
    }
}

@Composable
private fun CenteredProgress() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
private fun LoginScreen(state: ProductUiState, viewModel: ProductViewModel) {
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var isSignUp by rememberSaveable { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("FreshKart", style = MaterialTheme.typography.headlineLarge)
        Text(
            "Manage your farm products",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
        )
        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        state.error?.let { InlineStatus(it, isError = true) }
        state.message?.let { InlineStatus(it, isError = false) }
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = {
                viewModel.dismissMessage()
                if (isSignUp) viewModel.signUp(email, password)
                else viewModel.signIn(email, password)
            },
            enabled = !state.busy && email.isNotBlank() && password.length >= 6,
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (state.busy) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
            } else {
                Text(if (isSignUp) "Create account" else "Sign in")
            }
        }
        TextButton(
            onClick = {
                isSignUp = !isSignUp
                viewModel.dismissMessage()
            },
            modifier = Modifier.align(Alignment.CenterHorizontally),
        ) {
            Text(if (isSignUp) "Already have an account? Sign in" else "New farmer? Create an account")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProductListScreen(state: ProductUiState, viewModel: ProductViewModel) {
    var showAddDialog by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My products") },
                actions = {
                    TextButton(onClick = viewModel::signOut, enabled = !state.busy) {
                        Text("Sign out")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showAddDialog = true },
                content = { Text("+", style = MaterialTheme.typography.headlineMedium) },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
        ) {
            state.error?.let { InlineStatus(it, isError = true) }
            state.message?.let { InlineStatus(it, isError = false) }
            if (state.busy) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .align(Alignment.CenterHorizontally)
                        .padding(12.dp),
                )
            }
            if (state.products.isEmpty() && !state.busy) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(bottom = 48.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("No products yet", style = MaterialTheme.typography.titleLarge)
                    Text("Tap + to add your first product.")
                    if (state.error != null) {
                        OutlinedButton(onClick = viewModel::refreshProducts) {
                            Text("Try again")
                        }
                    }
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(state.products, key = Product::id) { product ->
                        ProductCard(
                            product = product,
                            enabled = !state.busy,
                            onAvailabilityChange = { viewModel.toggleAvailability(product) },
                            onDelete = { viewModel.deleteProduct(product.id) },
                        )
                    }
                }
            }
        }
    }

    if (showAddDialog) {
        AddProductDialog(
            busy = state.busy,
            onDismiss = { showAddDialog = false },
            onAdd = { draft ->
                viewModel.addProduct(draft)
                showAddDialog = false
            },
        )
    }
}

@Composable
private fun ProductCard(
    product: Product,
    enabled: Boolean,
    onAvailabilityChange: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(product.name, style = MaterialTheme.typography.titleLarge)
                    Text("${product.category}  •  ₹${String.format(Locale.getDefault(), "%.2f", product.price)}/${product.unit}")
                    Text("Stock: ${product.stock} ${product.unit}")
                }
                Switch(
                    checked = product.isAvailable,
                    onCheckedChange = { onAvailabilityChange() },
                    enabled = enabled,
                )
            }
            if (product.description.isNotBlank()) {
                Text(
                    product.description,
                    modifier = Modifier.padding(top = 8.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Text(
                if (product.isAvailable) "Available" else "Unavailable",
                style = MaterialTheme.typography.labelMedium,
            )
            TextButton(
                onClick = onDelete,
                enabled = enabled,
                modifier = Modifier.align(Alignment.End),
            ) {
                Text("Delete")
            }
        }
    }
}

@Composable
private fun AddProductDialog(
    busy: Boolean,
    onDismiss: () -> Unit,
    onAdd: (ProductDraft) -> Unit,
) {
    var name by rememberSaveable { mutableStateOf("") }
    var category by rememberSaveable { mutableStateOf("") }
    var price by rememberSaveable { mutableStateOf("") }
    var unit by rememberSaveable { mutableStateOf("kg") }
    var stock by rememberSaveable { mutableStateOf("") }
    var description by rememberSaveable { mutableStateOf("") }
    val parsedPrice = price.toDoubleOrNull()
    val parsedStock = stock.toIntOrNull()
    val valid = name.isNotBlank() && category.isNotBlank() &&
        parsedPrice != null && parsedPrice >= 0.0 &&
        parsedStock != null && parsedStock >= 0 && unit.isNotBlank()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add a product") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
                OutlinedTextField(category, { category = it }, label = { Text("Category") }, singleLine = true)
                OutlinedTextField(
                    price,
                    { price = it },
                    label = { Text("Price (INR)") },
                    singleLine = true,
                )
                OutlinedTextField(unit, { unit = it }, label = { Text("Unit (kg, bunch)") }, singleLine = true)
                OutlinedTextField(
                    stock,
                    { stock = it },
                    label = { Text("Stock") },
                    singleLine = true,
                )
                OutlinedTextField(
                    description,
                    { description = it },
                    label = { Text("Description (optional)") },
                )
            }
        },
        confirmButton = {
            Button(
                enabled = valid && !busy,
                onClick = {
                    onAdd(
                        ProductDraft(
                            name = name.trim(),
                            category = category.trim(),
                            price = parsedPrice!!,
                            unit = unit.trim(),
                            stock = parsedStock!!,
                            description = description.trim(),
                        ),
                    )
                },
            ) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !busy) {
                Text("Cancel")
            }
        },
    )
}

@Composable
private fun InlineStatus(message: String, isError: Boolean) {
    Text(
        message,
        color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp),
        style = MaterialTheme.typography.bodyMedium,
    )
}
