package com.freshkart.app

import io.github.jan.supabase.SupabaseClient
import io.github.jan.supabase.postgrest.from
import kotlinx.coroutines.CancellationException

class ProductRepository(
    private val supabase: SupabaseClient,
) {
    suspend fun getAll(): Result<List<Product>> = safely {
        supabase.from("products")
            .select()
            .decodeList<Product>()
            .sortedByDescending { it.createdAt }
    }

    suspend fun add(item: ProductDraft): Result<Unit> = safely {
        supabase.from("products").insert(item)
    }

    suspend fun update(item: Product): Result<Unit> = safely {
        supabase.from("products").update({
            set("name", item.name)
            set("category", item.category)
            set("price", item.price)
            set("unit", item.unit)
            set("stock", item.stock)
            set("description", item.description)
            set("is_available", item.isAvailable)
        }) {
            filter {
                eq("id", item.id)
                eq("user_id", item.userId)
            }
        }
    }

    suspend fun delete(id: String): Result<Unit> = safely {
        supabase.from("products").delete {
            filter { eq("id", id) }
        }
    }
}

private suspend fun <T> safely(block: suspend () -> T): Result<T> =
    try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (exception: Exception) {
        Result.failure(exception)
    }
