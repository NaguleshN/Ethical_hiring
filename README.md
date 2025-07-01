# Ethical Hiring Platform (Django)

A Django-based hiring platform with asynchronous task processing using Celery for resume scoring and evaluation.


## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Setup the env file](#setup-the-env-file)
- [Running the Application](#running-the-application)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)


## Features

Ethical Hiring Platform: Develop a generative AI-powered recruitment platform
that screens resumes and interview processes for biases and suggests diverse
and qualified candidates.

Our platform includes,
Our problem statement is to design a Ethical Hiring platform comes under SDG- 9 "industry, innovation and infrastructure",
aims to bring transparency and fairness to reduce bias in recruitment by:
 1. Automating resume scoring based on skill , achievements ,projects invloved.
 2. Providing an recruiter (admin) dashboard for reviewing scores and approving candidates for video screening assessment.
 3. Conducting AI-powered video assessments with questions generated from the candidate's resume.
 4. Using transcripts of the video responses to score candidates fairly and efficiently.


## Prerequisites

Before running this application, make sure you have the following installed:

- Python 3.8+
- Redis Server


## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/NaguleshN/Ethical_hiring.git
cd hiring-platform
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```


### 4. Install Redis Server

**Windows:**
```bash
# Using Chocolatey
choco install redis-64

# Or download from: https://github.com/microsoftarchive/redis/releases
```

**macOS:**
```bash
brew install redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
```

## Setup the env file

Create a `.env` file for application settings:

```bash
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=your_google_oauth2_key
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET=your_google_oauth2_secret
SECRET_KEY=django-insecure-ai!^cols@8c+izyuk5@8$wrlzsb%l0^uvea3_&2av4@b33(&r-
GOOGLE_API_KEY=your_google_gemini_api_key
EMAIL_HOST_USER=your_google_host_email
EMAIL_HOST_PASSWORD=your_google_email_host_password
```


## Running the Application

### 1. Database Setup

```bash
# Apply migrations
python manage.py migrate
```

### 2. Start Django Development Server

```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`

### 3. Start Celery Tasks Worker (New Tab)

```bash
celery -A Hiring_platform worker --loglevel=info --pool=solo
```

### 4. Monitor Celery (Optional)

For monitoring Celery tasks:

```bash
# Install flower
pip install flower

# Start flower
celery -A your_project flower
```

Access Flower at `http://localhost:5555`


### Directory Structure

```
hiring-platform/
├── hiring_app/
│   ├── migrations/
│   ├── templates/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tasks.py
│   ├── tests.py
│   ├── views.py
│   └── urls.py
├── hiring_platform/
│   ├── __init__.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── screening/
│   ├── migrations/
│   ├── templates/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tasks.py
│   ├── tests.py
│   ├── views.py
│   └── urls.py
├── uploads/
├── venv/
├── .env
├── .gitignore
├── db.sqlite3
├── manage.py
├── README.md
└── requirements.txt
```


## Troubleshooting

### Common Issues

1. **Celery tasks not executing:**
   ```bash
   # Check if Redis is running
   redis-cli ping
   
   # Check Celery worker status
   celery -A Hiring_platform inspect active
   
   # Restart Celery worker
   celery -A Hiring_platform worker --loglevel=debug
   ```

2. **Database issues:**
   ```bash
   # Reset database
   rm db.sqlite3
   python manage.py migrate
   ```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the development team.

