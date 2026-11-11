# Deploying AI Social Publisher on Vercel + Neon + Vercel Blob

This guide explains how to deploy the **AI Social Publisher** platform on **Vercel** (Hobby Free Tier, no credit card required) paired with **Neon PostgreSQL** and **Vercel Blob**.

---

## Architecture Overview

* **Compute (Vercel Serverless Functions)**: Runs the Flask application via `api/index.py` and `vercel.json`.
* **Database (Neon PostgreSQL)**: Stores all users, workspaces, posts, approvals, analytics, and encrypted Meta Page tokens.
* **Media Storage (Vercel Blob)**: Stores all uploaded images and AI-generated banners with instant public HTTPS CDN URLs.

---

## Step 1: Initialize Your Neon Database Schema

Before deploying to Vercel, run the initialization script once from your computer pointing to your Neon **direct** connection URL (`DATABASE_URL`) so all tables and default subscription plans are created.

In PowerShell (from the project root):
```powershell
$env:DATABASE_URL="postgresql://<your-neon-direct-url>?sslmode=require"
python backend/init_db.py
```

*(You only need to run this once! Afterward, clear it with `Remove-Item Env:\DATABASE_URL` if you continue using your local database locally).*

---

## Step 2: Push Your Repository to GitHub

Ensure all files (including `api/index.py`, `vercel.json`, `requirements.txt`, and `.vercelignore`) are committed and pushed to GitHub:

```bash
git add .
git commit -m "Configure Vercel serverless + Neon + Vercel Blob"
git push origin main
```

---

## Step 3: Import Project into Vercel

1. Log in to **[vercel.com](https://vercel.com)** with GitHub.
2. Click **Add New...** ➔ **Project**.
3. Select your **SM-automation** repository and click **Import**.
4. Keep **Framework Preset** as **Other** and **Root Directory** as `./` (the repo root).
5. **Before clicking Deploy**, expand **Environment Variables** and add:

| Variable Name | Value | Notes |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Enables production security & proxy handling |
| `DATABASE_URL_POOLED` | `postgresql://...@ep-...-pooler.../neondb?sslmode=require` | **Important:** Use your Neon **Pooled** connection string |
| `SECRET_KEY` | *(Any random 32+ character string)* | Signs Flask user sessions & CSRF tokens |
| `CREDENTIAL_ENCRYPTION_KEY` | *(Run `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)* | Encrypts Meta Page Access Tokens |
| `CRON_SECRET` | *(Any random secret string)* | Protects `/api/v1/cron/publish-scheduled` |
| `OPENAI_API_KEY` | *(Optional)* | Leave blank to use built-in mock AI generator |

6. Click **Deploy**.

---

## Step 4: Enable Vercel Blob Storage (For Images)

1. Once the project is created in Vercel, open the project dashboard and click the **Storage** tab at the top.
2. Click **Create Database** ➔ Select **Blob** ➔ **Continue**.
3. Name it `sm-automation-media` and click **Create**.
4. Connect it to your project (`All Environments`: Production, Preview, Development).
   * Vercel automatically adds the `BLOB_READ_WRITE_TOKEN` environment variable to your project!
5. Go to **Deployments** ➔ click the `...` menu on your latest deployment ➔ **Redeploy** so the live app picks up `BLOB_READ_WRITE_TOKEN`.

---

## Step 5: Scheduled Posts (Optional Frequent Cron)

Vercel's free Hobby plan limits built-in `vercel.json` cron jobs to once per day (`0 9 * * *`).
If you want scheduled posts checked every 5 minutes for free:
1. Create a free account on **[cron-job.org](https://cron-job.org)**.
2. Create a cron job targeting:
   * **URL**: `https://<your-app>.vercel.app/api/v1/cron/publish-scheduled`
   * **Schedule**: Every 5 minutes
   * **Header**: `X-Cron-Secret: <your CRON_SECRET value>`

---

## Step 6: Update Your Mobile App URL

To connect your Expo mobile app to the live Vercel deployment:
1. Open the app on your phone ➔ Login screen ➔ **Configure Server URL**.
2. Enter `https://<your-app>.vercel.app`.
