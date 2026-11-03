# Deploying AI Social Publisher on Render.com

This guide explains how to deploy the **AI Social Publisher** platform on [Render.com](https://render.com).

---

## Architecture on Render

```
GitHub Repository
   ├── render.yaml (Blueprint spec)
   ├── backend/ (Flask application + Celery tasks)
   └── mobile/ (React Native companion app)
          │
          ├──> Render Web Service (Flask + Gunicorn)
          ├──> Render Background Worker (Celery Queue + Beat Scheduler)
          ├──> Render PostgreSQL (Managed DB)
          └──> Render Redis (Task queue & session store)
```

---

## Method 1: Instant Blueprint Deployment (Recommended)

Render Blueprints let you provision all 4 components (Web, Celery Worker, PostgreSQL, Redis) automatically from `render.yaml`.

### Step 1: Push Code to GitHub
Ensure your latest changes including `render.yaml` are pushed to your GitHub repository:
```bash
git add .
git commit -m "Configure Render.com deployment blueprint"
git push origin main
```

### Step 2: Create Blueprint Instance on Render
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your GitHub repository.
4. Render will read `render.yaml` and show the plan to create:
   - **ai-social-publisher-web** (Python Web Service)
   - **ai-social-publisher-worker** (Celery Background Worker)
   - **ai-social-publisher-db** (PostgreSQL Database)
   - **ai-social-publisher-redis** (Redis Instance)
5. Click **Apply**.
6. Render will automatically build the web service, initialize all PostgreSQL database tables, seed the subscription plans (via `init_db.py`), and start the Gunicorn server and Celery background workers.

---

## Method 2: Manual Web Service Setup (Without Blueprint)

If you prefer setting up services individually from the dashboard:

### 1. Create PostgreSQL Database
- Click **New +** -> **PostgreSQL**.
- Name: `ai-social-publisher-db`
- Database: `ai_social_publisher`
- User: `publisher`
- Plan: **Free**
- Click **Create Database** and copy the **Internal Database URL**.

### 2. Create Redis Instance
- Click **New +** -> **Redis**.
- Name: `ai-social-publisher-redis`
- Plan: **Free**
- Click **Create Redis** and copy the **Internal Redis URL**.

### 3. Create Web Service
- Click **New +** -> **Web Service**.
- Connect your GitHub repo.
- **Root Directory**: `backend`
- **Runtime**: `Python`
- **Build Command**: `pip install -r requirements.txt && python init_db.py`
- **Start Command**: `gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
- **Environment Variables**:
  - `FLASK_ENV`: `production`
  - `SECRET_KEY`: *(Generate a random 32-character string)*
  - `DATABASE_URL`: *(Paste your Internal Database URL from Step 1)*
  - `REDIS_URL`: *(Paste your Internal Redis URL from Step 2)*
  - `CREDENTIAL_ENCRYPTION_KEY`: *(Generate a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)*
  - `PYTHON_VERSION`: `3.10.4`

### 4. Create Background Worker (Celery)
- Click **New +** -> **Background Worker**.
- Connect the same repo.
- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `celery -A worker.celery worker --beat --loglevel=info`
- **Environment Variables**: Same `DATABASE_URL`, `REDIS_URL`, `CREDENTIAL_ENCRYPTION_KEY`, and `FLASK_ENV`.

---

## 100% Free Tier Mode (No Paid Background Worker)

On Render, **Background Workers** require a Starter tier ($7/month). If you want to run **100% on Render's free tier**:

1. Delete or pause the `ai-social-publisher-worker` service.
2. In the web service, the app automatically falls back to inline asynchronous task dispatching.
3. For scheduled publishing, create a free **Cron Job** on Render or [cron-job.org](https://cron-job.org):
   - **URL / Command**: `GET https://<your-render-app-url>.onrender.com/api/v1/cron/publish-scheduled`
   - **Interval**: Every 5 or 10 minutes.
   - **Header**: `X-Cron-Secret: <your PLATFORM_ADMIN_SECRET>`

---

## Post-Deployment Verification

1. Visit `https://<your-service>.onrender.com/auth/register` to create your initial owner account and workspace.
2. Verify that login, post generation, and the content calendar load without errors.
3. In your mobile app (`mobile/src/api/client.ts` or on the mobile Login screen), set the backend API URL to `https://<your-service>.onrender.com`.

