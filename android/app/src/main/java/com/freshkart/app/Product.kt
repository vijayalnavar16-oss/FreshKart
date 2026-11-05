package com.freshkart.app

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Product(
    val id: String,
    @SerialName("user_id") val userId: String,
    val name: String,
    val category: String,
    val price: Double,
    val unit: String,
    val stock: Int,
    val description: String,
    @SerialName("is_available") val isAvailable: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class ProductDraft(
    val name: String,
    val category: String,
    val price: Double,
    val unit: String,
    val stock: Int,
    val description: String = "",
)
