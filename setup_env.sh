#!/bin/bash
# Setup script for Python 3.12 environment with SpeechRecognition support

cd "$(dirname "$0")"

echo "🚀 Setting up Python 3.12 environment for SpeechRecognition compatibility..."

# Check if Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 is not installed. Please install it first:"
    echo "   brew install python@3.12"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv312" ]; then
    echo "📦 Creating Python 3.12 virtual environment..."
    python3.12 -m venv venv312
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv312/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements in batches to avoid resolution-too-deep errors
echo "📥 Installing dependencies in batches (this may take a while)..."
echo "Installing core Django packages..."
pip install Django==5.1.1 asgiref==3.8.1 sqlparse==0.5.1 python-dotenv==1.0.1
echo "Installing authentication packages..."
pip install django-allauth==64.2.1 social-auth-app-django==5.4.2 social-auth-core==4.5.4 oauthlib==3.2.2 python3-openid==3.2.0 requests-oauthlib==2.0.0 PyJWT==2.9.0
echo "Installing HTTP and networking..."
pip install requests==2.32.3 urllib3==2.2.2 certifi==2024.8.30 charset-normalizer==3.3.2 idna==3.8 cryptography==43.0.1 cffi==1.17.1
echo "Installing data processing..."
pip install pillow==10.4.0 pypdf==4.3.1 pandas==2.2.2 numpy==1.26.4 python-dateutil==2.9.0.post0 pytz==2024.1 six==1.16.0
echo "Installing Google services..."
pip install google-generativeai==0.8.5 google-ai-generativelanguage==0.6.15 google-api-core==2.25.1 google-api-python-client==2.182.0 google-auth==2.40.3 google-auth-httplib2==0.2.0 googleapis-common-protos==1.70.0
echo "Installing Google Cloud Speech..."
pip install google-cloud-speech==2.33.0 grpcio==1.75.0 grpcio-status==1.71.2 proto-plus==1.26.1 protobuf==5.29.5
echo "Installing Celery..."
pip install celery==5.4.0 kombu==5.4.2 billiard==4.2.1 vine==5.1.0 redis==5.0.8 amqp==5.3.1
echo "Installing audio/video processing..."
pip install assemblyai==0.33.0 ffmpeg-python==0.2.0 SpeechRecognition==3.10.0
echo "Installing video processing..."
pip install moviepy==1.0.3 imageio==2.35.1 imageio-ffmpeg==0.5.1 opencv-python==4.10.0.84 proglog==0.1.10
echo "Installing utilities..."
pip install SQLAlchemy==2.0.34 decorator==4.4.2 future==1.0.0 jsonpatch==1.33 jsonpointer==3.0.0 psutil==6.0.0 pyasn1==0.6.0 pyasn1_modules==0.4.0 pyparsing==3.1.4 rsa==4.9 tzdata==2024.1 uritemplate==4.1.1 websockets==15.0.1 httplib2==0.22.0
echo "Installing HTTP clients..."
pip install httpx==0.28.1 httpcore==1.0.9 h11==0.16.0 anyio==4.10.0 sniffio==1.3.1
echo "Installing data validation..."
pip install pydantic==2.11.9 pydantic-core==2.33.2 annotated-types==0.7.0 typing-extensions==4.15.0 typing-inspection==0.4.1
echo "Installing click and UI..."
pip install click==8.3.0 click-didyoumean==0.3.1 click-plugins==1.1.1 click-repl==0.3.0 prompt_toolkit==3.0.47 wcwidth==0.2.13 defusedxml==0.8.0rc2 pycparser==2.22 cachetools==5.5.2 tqdm==4.67.1
echo "Installing LlamaIndex core..."
pip install llama-index-core==0.12.13 llama-index-llms-gemini==0.4.1 llama-index-embeddings-gemini==0.3.1
echo "Installing ML packages..."
pip install llama-index==0.12.13 --no-deps
pip install sentence-transformers==5.1.2 transformers==4.57.1 torch==2.9.0
pip install llama-index-embeddings-huggingface==0.5.0 || pip install llama-index-embeddings-huggingface --no-deps

# Verify SpeechRecognition
echo "✅ Verifying SpeechRecognition installation..."
python -c "import speech_recognition as sr; print('✅ SpeechRecognition works!')" && echo "✅ Setup complete!" || echo "❌ SpeechRecognition installation failed"

echo ""
echo "To activate this environment, run:"
echo "  source venv312/bin/activate"
echo ""
echo "To run Django:"
echo "  python manage.py runserver"
