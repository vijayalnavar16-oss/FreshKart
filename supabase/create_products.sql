create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    name text not null check (length(trim(name)) > 0),
    category text not null,
    price numeric(12, 2) not null check (price >= 0),
    unit text not null,
    stock integer not null default 0 check (stock >= 0),
    description text not null default '',
    is_available boolean not null default true,
    created_at timestamptz not null default now()
);

alter table public.products enable row level security;

drop policy if exists "Users can read their own products" on public.products;
create policy "Users can read their own products"
    on public.products for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert their own products" on public.products;
create policy "Users can insert their own products"
    on public.products for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own products" on public.products;
create policy "Users can update their own products"
    on public.products for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own products" on public.products;
create policy "Users can delete their own products"
    on public.products for delete to authenticated
    using ((select auth.uid()) = user_id);

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.products to authenticated;
