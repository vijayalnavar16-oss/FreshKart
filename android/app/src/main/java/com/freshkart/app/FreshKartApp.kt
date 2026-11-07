package com.freshkart.app

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import java.util.Locale

private val FreshGreen = Color(0xFF087443)
private val FreshDark = Color(0xFF123D2B)
private val FreshBackground = Color(0xFFF5F8F5)
private val FreshMint = Color(0xFFE5F3E9)
private val FreshAmber = Color(0xFFFFF2D9)

@Composable
fun SupabaseConfigurationRequired() {
    FreshKartTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = FreshBackground) {
            Column(
                modifier = Modifier.fillMaxSize().padding(28.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("🌱", style = MaterialTheme.typography.displayLarge)
                Spacer(Modifier.height(16.dp))
                Text("One setup step left", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    "FreshKart needs your Supabase project details before it can connect.",
                    modifier = Modifier.padding(top = 10.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Add SUPABASE_URL and SUPABASE_ANON_KEY to android/local.properties, then rebuild the app.",
                    modifier = Modifier.padding(top = 16.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun FreshKartTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = FreshGreen,
            onPrimary = Color.White,
            secondary = FreshDark,
            background = FreshBackground,
            surface = Color.White,
            onSurface = FreshDark,
            surfaceVariant = FreshMint,
        ),
        content = content,
    )
}

@Composable
fun FreshKartApp(viewModel: ProductViewModel) {
    val state by viewModel.state.collectAsState()
    FreshKartTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = FreshBackground) {
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
        CircularProgressIndicator(color = FreshGreen)
    }
}

@Composable
private fun LoginScreen(state: ProductUiState, viewModel: ProductViewModel) {
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var isSignUp by rememberSaveable { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Surface(color = FreshMint, shape = RoundedCornerShape(24.dp), modifier = Modifier.size(68.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Text("🌿", style = MaterialTheme.typography.headlineLarge)
            }
        }
        Spacer(Modifier.height(22.dp))
        Text("FreshKart", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.ExtraBold, color = FreshDark)
        Text(
            "Farm fresh. Direct to you.",
            style = MaterialTheme.typography.titleMedium,
            color = FreshGreen,
            modifier = Modifier.padding(top = 6.dp, bottom = 26.dp),
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White),
            elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(if (isSignUp) "Create farmer account" else "Welcome back", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    if (isSignUp) "Join FreshKart to manage your products." else "Sign in to manage your farm products.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 5.dp, bottom = 20.dp),
                )
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email address") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth(),
                )
                state.error?.let { InlineStatus(it, isError = true) }
                state.message?.let { InlineStatus(it, isError = false) }
                Spacer(Modifier.height(18.dp))
                Button(
                    onClick = {
                        viewModel.dismissMessage()
                        if (isSignUp) viewModel.signUp(email, password)
                        else viewModel.signIn(email, password)
                    },
                    enabled = !state.busy && email.isNotBlank() && password.length >= 6,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = FreshGreen),
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    if (state.busy) CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                    else Text(if (isSignUp) "Create account" else "Sign in", fontWeight = FontWeight.SemiBold)
                }
                TextButton(
                    onClick = {
                        isSignUp = !isSignUp
                        viewModel.dismissMessage()
                    },
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                ) {
                    Text(if (isSignUp) "Already registered? Sign in" else "New farmer? Create an account")
                }
            }
        }
        Text(
            "FRESH KART  •  FARMER TO CUSTOMER",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 24.dp),
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProductListScreen(state: ProductUiState, viewModel: ProductViewModel) {
    var showAddDialog by rememberSaveable { mutableStateOf(false) }
    var searchText by rememberSaveable { mutableStateOf("") }
    var selectedFilter by rememberSaveable { mutableStateOf("All") }
    var productToDelete by rememberSaveable { mutableStateOf<String?>(null) }

    val availableCount = state.products.count { it.isAvailable }
    val stockCount = state.products.sumOf { it.stock }
    val visibleProducts = state.products.filter { product ->
        val matchesSearch = product.name.contains(searchText, ignoreCase = true) ||
            product.category.contains(searchText, ignoreCase = true)
        val matchesFilter = when (selectedFilter) {
            "Available" -> product.isAvailable
            "Unavailable" -> !product.isAvailable
            else -> true
        }
        matchesSearch && matchesFilter
    }

    Scaffold(
        containerColor = FreshBackground,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("FreshKart", fontWeight = FontWeight.Bold, color = FreshDark)
                        Text("Farmer product manager", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                },
                actions = {
                    TextButton(onClick = viewModel::signOut, enabled = !state.busy) {
                        Text("Sign out", color = FreshGreen)
                    }
                },
            )
        },
        floatingActionButton = {
            Button(
                onClick = { showAddDialog = true },
                shape = RoundedCornerShape(18.dp),
                colors = ButtonDefaults.buttonColors(containerColor = FreshGreen),
                modifier = Modifier.height(52.dp),
            ) {
                Text("+  Add product", fontWeight = FontWeight.SemiBold)
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Column {
                    Text("Your farm store", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, color = FreshDark)
                    Text("Keep your products and stock up to date.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    SummaryCard("Products", state.products.size.toString(), "In your catalogue", Modifier.weight(1f))
                    SummaryCard("Available", availableCount.toString(), "Ready to sell", Modifier.weight(1f))
                    SummaryCard("Total stock", stockCount.toString(), "Units in stock", Modifier.weight(1f))
                }
            }
            item {
                OutlinedTextField(
                    value = searchText,
                    onValueChange = { searchText = it },
                    label = { Text("Search products or categories") },
                    singleLine = true,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("All", "Available", "Unavailable").forEach { filter ->
                        FilterChip(
                            selected = selectedFilter == filter,
                            onClick = { selectedFilter = filter },
                            label = { Text(filter) },
                        )
                    }
                }
            }
            item {
                state.error?.let { InlineStatus(it, isError = true) }
                state.message?.let { InlineStatus(it, isError = false) }
                if (state.busy) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = FreshGreen)
                        Text("  Updating your store…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            if (visibleProducts.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                    ) {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(28.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(if (state.products.isEmpty()) "🥬" else "🔎", style = MaterialTheme.typography.displaySmall)
                            Spacer(Modifier.height(10.dp))
                            Text(
                                if (state.products.isEmpty()) "Your store is waiting" else "No matching products",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                if (state.products.isEmpty()) "Add your first farm-fresh product to get started." else "Try another search or filter.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            if (state.error != null) {
                                OutlinedButton(onClick = viewModel::refreshProducts) { Text("Try again") }
                            }
                        }
                    }
                }
            } else {
                items(visibleProducts, key = Product::id) { product ->
                    ProductCard(
                        product = product,
                        enabled = !state.busy,
                        onAvailabilityChange = { viewModel.toggleAvailability(product) },
                        onDelete = { productToDelete = product.id },
                    )
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

    productToDelete?.let { id ->
        AlertDialog(
            onDismissRequest = { if (!state.busy) productToDelete = null },
            title = { Text("Delete this product?") },
            text = { Text("This product will be removed from your farmer catalogue. This action cannot be undone.") },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.deleteProduct(id)
                        productToDelete = null
                    },
                    enabled = !state.busy,
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                ) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { productToDelete = null }, enabled = !state.busy) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun SummaryCard(title: String, value: String, caption: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = FreshGreen)
            Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold, color = FreshDark)
            Text(caption, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ProductCard(
    product: Product,
    enabled: Boolean,
    onAvailabilityChange: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(product.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = FreshDark)
                    Text(product.category, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Surface(
                    color = if (product.isAvailable) FreshMint else FreshAmber,
                    shape = RoundedCornerShape(50),
                ) {
                    Text(
                        if (product.isAvailable) "Available" else "Unavailable",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        color = if (product.isAvailable) FreshGreen else Color(0xFF946200),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "₹${String.format(Locale.getDefault(), "%.2f", product.price)}",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = FreshGreen,
                )
                Text(" / ${product.unit}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.width(12.dp))
                Text("Stock: ${product.stock} ${product.unit}", color = FreshDark, style = MaterialTheme.typography.bodyMedium)
            }
            if (product.description.isNotBlank()) {
                Text(product.description, modifier = Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Selling", style = MaterialTheme.typography.labelLarge, color = FreshDark)
                    Switch(
                        checked = product.isAvailable,
                        onCheckedChange = { onAvailabilityChange() },
                        enabled = enabled,
                    )
                }
                TextButton(onClick = onDelete, enabled = enabled) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
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
        title = { Text("Add a product", fontWeight = FontWeight.Bold) },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(name, { name = it }, label = { Text("Product name") }, singleLine = true)
                OutlinedTextField(category, { category = it }, label = { Text("Category") }, singleLine = true)
                OutlinedTextField(
                    price, { price = it }, label = { Text("Price (₹)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                )
                OutlinedTextField(unit, { unit = it }, label = { Text("Unit (kg, bunch, piece)") }, singleLine = true)
                OutlinedTextField(
                    stock, { stock = it }, label = { Text("Stock quantity") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
                OutlinedTextField(description, { description = it }, label = { Text("Description (optional)") })
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
                colors = ButtonDefaults.buttonColors(containerColor = FreshGreen),
            ) { Text("Save product") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun InlineStatus(message: String, isError: Boolean) {
    Surface(
        color = if (isError) MaterialTheme.colorScheme.errorContainer else FreshMint,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
    ) {
        Text(
            message,
            color = if (isError) MaterialTheme.colorScheme.onErrorContainer else FreshGreen,
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
