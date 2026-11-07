# FreshKart

FreshKart is a Flask and SQLite vegetable-market application.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADMIN_USERNAME = "VIJAY"
$env:ADMIN_PASSWORD = "Freshkart@26"
python app.py
```

Open `http://127.0.0.1:5000`. The administrator creates customer and farmer
accounts from the admin interface.

## Deploy on Render

1. Connect this repository to Render and create a Blueprint from `render.yaml`.
2. Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` as secret environment values.
3. Wait for the first deployment, then sign in and create customer accounts.

### Store production data in Supabase

The app uses PostgreSQL for hosted storage, so Supabase works without a separate
Supabase SDK. Create a Supabase project, then copy its PostgreSQL connection
string from **Connect**. Use the session pooler connection string if your hosting
provider cannot connect to Supabase's direct database address.

In the Render web service, add `DATABASE_URL` as a secret environment variable
with that connection string, then deploy. Keep the URL private; do not use the
Supabase project URL or anon/publishable key for `DATABASE_URL`. On startup, the
app creates and updates its tables without dropping existing records. It
refuses to start on Render without `DATABASE_URL`, rather than silently using
temporary SQLite.

User accounts and password hashes, farmer profiles, products and stock, carts,
orders and order items, delivery and payment details, settings, notifications,
and new product photos are stored in the database. Product image bytes are
stored alongside their database paths, so they survive app redeploys. Local
development continues to use `freshkart.db` unless `DATABASE_PATH` is set.

### Groq shopping assistant

The customer dashboard includes an optional Groq-powered shopping assistant.
Set `GROQ_API_KEY` as a secret environment variable in Render; the API base URL
and model default to `https://api.groq.com/openai/v1` and
`llama-3.3-70b-versatile`. You can override them with `GROQ_API_BASE_URL` and
`GROQ_MODEL`. The key stays on the server, and chat questions and answers are
not stored as chat history. If the key is missing or the API request fails, the
customer sees an error message instead.

### Migrate existing SQLite data to Supabase

The existing production database at `/instance/freshkart.db` must be copied
before switching the service to Supabase. Download that file and the existing
`static/uploads` directory from the running service, then run the one-time
import from a machine that can reach your Supabase database:

```powershell
$env:DATABASE_URL = "your-postgresql-connection-url"
python database.py --migrate-sqlite "C:\path\freshkart.db" --uploads-dir "C:\path\uploads"
```

The import preserves existing IDs, hashes, products, orders, settings, and
uploaded images. It does not modify the SQLite source and refuses to import if
the Supabase application tables already contain records. After verifying the
import, set the same `DATABASE_URL` as a secret in Render. Do not paste database
credentials into source files or commit them.

## Android app icon

The Android launcher icon is generated from `resources/icon-only.png`,
`resources/icon-foreground.png`, and `resources/icon-background.png`. After
changing these source images, run:

```powershell
npm install
npm run android:assets
npm run android:sync
```

### Build a downloadable APK with GitHub Actions

Push the project, including `android/`, `resources/`, `capacitor.config.json`,
`package.json`, and `package-lock.json`, to the GitHub repository. In GitHub, open
**Actions** → **Build Android APK** → **Run workflow**. No Supabase Actions
secrets are required for the full-marketplace APK. When the workflow completes,
open its run, download the `FreshKart-Android-APK` artifact, and extract
`app-debug.apk` to install it on your phone. The artifact is available for
14 days. The workflow also runs automatically when relevant Android files are
pushed to the `main` or `master` branch.

Alternatively, open the `android` folder in Android Studio and build a new APK.
Updating project files does not change an APK that was already downloaded.

## Android app

The Android launcher opens the complete hosted FreshKart Flask marketplace
inside a Capacitor WebView using the URL in `capacitor.config.json`.
Customers, farmers, and administrators use the same website routes, login
system, database, products, orders, and settings as the web version. This avoids
maintaining a separate Android-only product database.

The Android build does not require the optional native Supabase farmer-manager
credentials. The older Kotlin/Jetpack Compose farmer product-manager source files
remain in the repository as a separate sample, but they are not launched by the
FreshKart APK.

### Optional legacy native Android product manager

The following Supabase setup applies only if you later decide to restore and use
the separate native Kotlin farmer product manager. It is not required to build
or run the current full-marketplace APK. Its `public.products` schema differs
from the Flask app's existing `products` table; use a separate Supabase project
for this optional sample unless you plan and test a schema/auth migration.

1. In a new Supabase project, run [`supabase/create_products.sql`](./supabase/create_products.sql)
   in **SQL Editor**. It creates the products table, enables RLS, and grants
   authenticated users CRUD access only to rows whose `user_id` matches
   `auth.uid()`.
2. In **Authentication → Providers → Email**, enable Email. For local testing,
   you may temporarily turn off **Confirm email**; turn it back on for
   production. When confirmation is enabled, signup asks the farmer to confirm
   their email before signing in.
3. Copy the project URL and the client-side anon/publishable key (never the
   `service_role` key) into `android/local.properties`, alongside any
   `sdk.dir` entry Android Studio already wrote:

   ```properties
   SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
   SUPABASE_ANON_KEY=YOUR_CLIENT_SIDE_KEY
   ```

   `android/local.properties` is ignored by Git. Gradle exposes these values as
   `BuildConfig` fields; the source code contains no credentials.
4. To build an APK with GitHub Actions, add repository Actions secrets named
   `SUPABASE_URL` and `SUPABASE_ANON_KEY` with the same client values. Push the
   Android app and workflow to `main` or `master`, then open **Actions** →
   **Build Android APK** and run the workflow (or wait for the push build).
   Download the `FreshKart-Android-APK` artifact from the successful run. It is
   retained for 14 days. The workflow fails with an explicit message if either
   secret is missing, and writes credentials only to the ignored
   `android/local.properties` file on the build runner.
5. Alternatively, open `android/` in Android Studio, create
   `android/local.properties` as above, and run the `app` configuration. The
   app provides sign-up/sign-in, product listing, add, availability toggle, and
   delete. The module uses supabase-kt 3.9.0, Kotlin 2.4.21, Ktor 3.6.0, and
   kotlinx.serialization 1.11.0; check the
   [supabase-kt releases](https://github.com/supabase-community/supabase-kt/releases)
   and [installation guide](https://supabase.com/docs/reference/kotlin/installing)
   for newer stable versions before upgrading. The SDK requires Android API 26
   or newer.

The Android implementation lives under
`android/app/src/main/java/com/freshkart/app/`. The Supabase client,
repositories, model, ViewModel, Compose UI, and activity are separate Kotlin
files there. `android/app/src/main/AndroidManifest.xml` includes the INTERNET
permission.

### Supabase Android verification

- Confirm `public.products` exists and RLS is enabled in the Supabase dashboard.
- Create two test accounts. Sign in as each account and verify each sees only
  their own products.
- Add a product; verify its `user_id` equals the signed-in user's Auth UUID.
- Toggle availability and verify `is_available` changes in the table.
- Delete the product and verify it is removed.
- While signed in as one user, try to select/update/delete the other user's row
  through the SQL Editor using an authenticated client context; RLS must deny
  access. SQL Editor queries as the database owner bypass RLS, so use the app
  or a user JWT to test policies.
- If the app returns 401, check the project URL/client key and sign in again.
  Never replace the client key with `service_role`.
- If reads are empty, check the active user, row `user_id`, RLS policies, and
  that `products` is exposed in the Supabase Data API settings.
- If requests fail to connect, verify INTERNET permission and network access.
  This app uses HTTPS; do not enable cleartext traffic to fix a wrong URL.

### Reset admin credentials without Shell access

If you cannot access the service shell, set `RESET_ADMIN_CREDENTIALS_ON_STARTUP`
to `1` in the service's environment, verify `ADMIN_USERNAME` and `ADMIN_PASSWORD`,
and deploy. The startup reset updates the matching admin account or creates it if
the configured username does not exist. After the deployment succeeds, remove
`RESET_ADMIN_CREDENTIALS_ON_STARTUP` (or set it to `0`) and deploy again. This
setting should only be enabled temporarily.