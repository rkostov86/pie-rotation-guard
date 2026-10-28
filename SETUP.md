# Setup: secrets for alerts

The monitor needs 4 secrets. GitHub stores them encrypted; nobody (including me) can read them back after you save them.

| Secret name | What to put in it |
|---|---|
| `NTFY_TOPIC` | Your ntfy topic name (phone alerts) |
| `SMTP_USER` | The Gmail address that sends the email |
| `SMTP_APP_PASSWORD` | A 16-character Google *app password* (not your normal password) |
| `ALERT_EMAIL_TO` | Where the alert emails go |

## Step 1 — ntfy topic (phone)

1. Open the ntfy app on your phone.
2. Tap **+** (Subscribe to topic).
3. Type a new, hard-to-guess name, e.g. `pie-guard-7k3x9q`. Anyone who knows a topic name can read it, so don't use a simple word.
4. Tap **Subscribe**. Write the name down — that is your `NTFY_TOPIC`.

(You can reuse your old trading-desk topic instead, but a separate one keeps pie alerts apart.)

## Step 2 — Google app password (email)

1. Go to **myaccount.google.com → Security**.
2. Make sure **2-Step Verification** is ON (app passwords need it).
3. Search the settings for **App passwords** (or open myaccount.google.com/apppasswords).
4. Name it `pie-rotation-guard` and click **Create**.
5. Copy the 16-character password shown (spaces don't matter). This is `SMTP_APP_PASSWORD`. Google shows it only once.

## Step 3 — Add the secrets to GitHub

1. Open **github.com/rkostov86/pie-rotation-guard**.
2. Click **Settings** (top bar of the repo) → in the left menu **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. Name: `NTFY_TOPIC`, Secret: your topic name → **Add secret**.
5. Repeat for `SMTP_USER`, `SMTP_APP_PASSWORD`, `ALERT_EMAIL_TO`.

Names must match exactly (capital letters, underscores).

## Step 3b — FRED API key (only if Claude asks for it)

FRED (the source for the 10-year yield and credit spreads) sometimes times out from GitHub's servers. A free key makes it reliable:

1. Go to **fredaccount.stlouisfed.org**, create a free account and sign in.
2. Open **API Keys** → **Request API Key**, describe it as "personal portfolio monitor", accept the terms.
3. Copy the 32-character key and add it as repository secret `FRED_API_KEY` (same way as Step 3).

## Step 4 — Check two repo settings

1. **Settings → Actions → General → Workflow permissions**: select **Read and write permissions** → **Save**. (The monitor commits its state file and opens a GitHub issue when a switch fires.)
2. **Settings → General → Features**: make sure **Issues** is ticked.

## Step 5 — Tell Claude "secrets done"

Claude then sends one test alert of each type (routine, watch, switch, data error) so you can confirm they reach your phone and inbox.
