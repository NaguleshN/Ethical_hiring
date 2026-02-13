# Ethical Hiring Platform

A Django-based hiring platform with Celery for resume scoring and AI-powered video assessments.

## Setup

1. Create and activate virtual environment, install dependencies:

   ```bash
   cd /Users/nagulesh/Downloads/Hiring_platform
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example env and edit with your values:

   ```bash
   cp .env.example .env
   ```

3. Run migrations:

   ```bash
   python manage.py migrate
   ```

## Running the application

**Terminal 1 – activate env and start Django:**

```bash
cd /Users/nagulesh/Downloads/Hiring_platform && source venv/bin/activate
python manage.py runserver
```

**Terminal 2 – Celery worker:**

```bash
cd /Users/nagulesh/Downloads/Hiring_platform && source venv/bin/activate
celery -A Hiring_platform worker --loglevel=info
```

App: `http://localhost:8000`

## Example .env file

Create a `.env` file in the project root (or copy from `.env.example`). Example:

```bash
# Django
SECRET_KEY=your-secret-key-here

# Google OAuth
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=your-google-oauth2-key
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET=your-google-oauth2-secret

# Email (e.g. Gmail)
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True

# Google API (Gemini – resume scoring / AI)
GOOGLE_API_KEY=your-google-api-key

# Optional: Speech / transcription
# Google Cloud Speech
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
# AssemblyAI
# ASSEMBLYAI_API_KEY=your-assemblyai-key
```

Replace placeholder values with your own keys and secrets.
