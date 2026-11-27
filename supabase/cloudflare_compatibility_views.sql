-- Compatibility views: keep the existing FreshKart Python SQL names while
-- storing all application data in the fresh Supabase fk_* tables.
-- Run this only after confirming the fk_* columns and ID defaults.

CREATE OR REPLACE VIEW public.users AS
SELECT id, username, password_hash, role, full_name, address,
       phone_number, is_active
FROM public.fk_users;

CREATE OR REPLACE VIEW public.products AS
SELECT id, farmer_id, name, category, price, unit, stock,
       description, image, deleted
FROM public.fk_products;

CREATE OR REPLACE VIEW public.orders AS
SELECT id, customer_id, total, delivery_charge, address, delivery_date,
       payment_method, status, created_at, customer_phone,
       cashfree_order_id, cashfree_session_id, payment_status, stock_released
FROM public.fk_orders;

CREATE OR REPLACE VIEW public.order_items AS
SELECT id, order_id, product_id, quantity, price
FROM public.fk_order_items;

CREATE OR REPLACE VIEW public.app_settings AS
SELECT key, value
FROM public.fk_app_settings;
