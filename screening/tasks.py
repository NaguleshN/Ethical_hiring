from celery import shared_task
import ffmpeg
import os
from django.conf import settings
from .models import VideoRecording
from google.cloud import speech_v1p1beta1 as speech

# SpeechRecognition works on Python 3.12; not compatible with Python 3.13+ (aifc/audioop removed).
# When available, we use it first (free, no API key) then fall back to Google Cloud / AssemblyAI.
import sys
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as _e:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None
    # Log once so Celery workers show why (e.g. Python 3.13 or missing package)
    print(f"[screening.tasks] SpeechRecognition not loaded (Python {sys.version_info.major}.{sys.version_info.minor}): {_e}")
# from pydub import AudioSegment  # Commented out due to Python 3.13 compatibility issues
import io
from assemblyai import Transcriber
import time
import random
import re


def get_gemini_llm():
    """Initialize and return Gemini LLM instance"""
    from dotenv import load_dotenv
    from llama_index.llms.gemini import Gemini
    
    load_dotenv()
    # Use gemini-2.5-flash (latest working model)
    return Gemini(
        api_key=os.getenv("GOOGLE_API_KEY"), 
        model="gemini-2.5-flash",  # Latest model with good quota availability
        temperature=0.7
    )


def execute_llm_with_retry(llm, query, max_retries=3, initial_wait=5):
    """Execute LLM query with exponential backoff retry logic for rate limiting"""
    for attempt in range(max_retries):
        try:
            response = llm.complete(query)
            return response
        except Exception as e:
            error_message = str(e)
            print(f"Error on attempt {attempt + 1}/{max_retries}: {error_message}")
            
            # Check if it's a rate limit error
            if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
                if attempt < max_retries - 1:
                    # Extract retry delay from error message or use exponential backoff
                    wait_time = initial_wait * (2 ** attempt)  # Exponential backoff
                    
                    # Try to extract suggested retry delay
                    if "retry in" in error_message.lower():
                        match = re.search(r'retry in (\d+(?:\.\d+)?)', error_message.lower())
                        if match:
                            suggested_wait = float(match.group(1))
                            wait_time = max(wait_time, suggested_wait)
                    
                    # Add jitter to avoid thundering herd
                    wait_time += random.uniform(0, 5)
                    print(f"⚠️ Rate limit hit. Waiting {wait_time:.2f} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ Rate limit exceeded after {max_retries} attempts")
                    raise
            else:
                # For non-rate-limit errors, don't retry
                raise
    
    raise Exception(f"Failed after {max_retries} attempts")



@shared_task
def extract_audio_from_video(video_id):
    """
    Extract audio from video file and save it, then trigger transcription
    """
    audio_path = None
    try:
        video_recording = VideoRecording.objects.get(id=video_id)
        print(f"Starting audio extraction for video ID: {video_id}")
        
        if not video_recording.video:
            print(f"❌ Error: No video file found for recording {video_id}")
            return

        video_path = video_recording.video.path
        
        if not os.path.exists(video_path):
            print(f"❌ Error: Video file does not exist at path: {video_path}")
            return

        print(f"Video file found: {video_path}")
        
        # Generate audio file path
        base_name = os.path.splitext(video_path)[0]
        audio_path = f"{base_name}.mp3"
        
        print(f"Extracting audio to: {audio_path}")
        
        # Extract audio using ffmpeg
        try:
            ffmpeg.input(video_path).output(audio_path, acodec='mp3', audio_bitrate='192k').run(overwrite_output=True, quiet=True)
            print("✅ Audio extraction successful")
        except Exception as e:
            print(f"❌ Error during ffmpeg audio extraction: {e}")
            import traceback
            print(traceback.format_exc())
            return

        # Check if audio file was created
        if not os.path.exists(audio_path):
            print(f"❌ Error: Audio file was not created at {audio_path}")
            return

        # Save audio file to the model
        with open(audio_path, 'rb') as audio_file:
            audio_filename = os.path.basename(audio_path)
            video_recording.audio_file.save(audio_filename, audio_file, save=True)
            print(f"✅ Audio file saved to database: {audio_filename}")

        # Trigger transcription task
        print(f"Triggering transcription task for recording {video_recording.id}")
        convert_speech_to_text.delay(video_recording.id)
        
    except VideoRecording.DoesNotExist:
        print(f"❌ Error: VideoRecording with ID {video_id} does not exist")
    except Exception as e:
        print(f"❌ Error in extract_audio_from_video: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        # Clean up temporary audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"Cleaned up temporary audio file: {audio_path}")
            except Exception as e:
                print(f"Warning: Could not remove temp audio file {audio_path}: {e}")


@shared_task
def convert_speech_to_text(recording_id):
    """
    Convert speech to text. On Python 3.12: tries SpeechRecognition first (free),
    then Google Cloud Speech API, then AssemblyAI.
    """
    temp_wav_path = None
    transcription_success = False
    
    try:
        recording = VideoRecording.objects.get(id=recording_id)
        print(f"Starting transcription for recording ID: {recording_id}")

        # Check if audio file exists
        if not recording.audio_file:
            print(f"❌ Error: No audio file found for recording {recording_id}")
            recording.transcript_text = ""
            recording.save()
            return

        audio_file_path = recording.audio_file.path
        
        if not os.path.exists(audio_file_path):
            print(f"❌ Error: Audio file does not exist at path: {audio_file_path}")
            recording.transcript_text = ""
            recording.save()
            return

        print(f"Audio file found: {audio_file_path}")
        file_extension = os.path.splitext(audio_file_path)[1].lower()

        # Convert to WAV format for Google Cloud Speech API using ffmpeg
        if file_extension != '.wav':
            # Use unique temp file name to avoid conflicts
            temp_wav_path = f'temp_{recording_id}_{int(time.time())}.wav'
            print(f"Converting audio to WAV format: {temp_wav_path}")
            try:
                ffmpeg.input(audio_file_path).output(temp_wav_path, acodec='pcm_s16le', ar=16000).run(overwrite_output=True, quiet=True)
                audio_file = temp_wav_path
                print("✅ Audio conversion successful")
            except Exception as e:
                print(f"❌ Error converting audio to WAV: {e}")
                # Try with original file
                audio_file = audio_file_path
        else:
            audio_file = audio_file_path

        def _try_speech_recognition():
            """Use SpeechRecognition library (free, works on Python 3.12). Returns transcript or None."""
            if not SPEECH_RECOGNITION_AVAILABLE or sr is None:
                return None
            speech_audio_file = audio_file
            if not audio_file.endswith('.wav'):
                if temp_wav_path and os.path.exists(temp_wav_path):
                    speech_audio_file = temp_wav_path
                else:
                    speech_wav_path = f'temp_speech_{recording_id}_{int(time.time())}.wav'
                    try:
                        ffmpeg.input(audio_file).output(speech_wav_path, acodec='pcm_s16le', ar=16000).run(overwrite_output=True, quiet=True)
                        speech_audio_file = speech_wav_path
                    except Exception:
                        return None
            try:
                recognizer = sr.Recognizer()
                with sr.AudioFile(speech_audio_file) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language="en-US")
                if speech_audio_file != audio_file and speech_audio_file != temp_wav_path and os.path.exists(speech_audio_file):
                    try:
                        os.remove(speech_audio_file)
                    except Exception:
                        pass
                return text.strip() if text else None
            except (sr.UnknownValueError, sr.RequestError, Exception):
                return None

        # Method 1: Try SpeechRecognition first when available (Python 3.12 – free, no API key)
        if not transcription_success and SPEECH_RECOGNITION_AVAILABLE:
            print("Attempting transcription with SpeechRecognition (free, no API key)...")
            try:
                text = _try_speech_recognition()
                if text:
                    print(f"✅ SpeechRecognition transcription successful: {text[:100]}...")
                    recording.transcript_text = text
                    recording.save()
                    transcription_success = True
                else:
                    print("⚠️ SpeechRecognition returned no text")
            except Exception as e3:
                print(f"❌ SpeechRecognition error: {e3}")
                import traceback
                print(traceback.format_exc())

        # Method 2: Google Cloud Speech API
        if not transcription_success:
            print("Attempting transcription with Google Cloud Speech API...")
            try:
                google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if not google_creds and not os.path.exists(os.path.expanduser('~/.config/gcloud/application_default_credentials.json')):
                    print("⚠️ Google Cloud credentials not found. Skipping.")
                    raise Exception("Google Cloud credentials not configured")

                client = speech.SpeechClient()
                with open(audio_file, 'rb') as audio_file_obj:
                    content = audio_file_obj.read()
                if len(content) == 0:
                    raise Exception("Audio file is empty")
                audio = speech.RecognitionAudio(content=content)
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    language_code="en-US",
                )
                response = client.recognize(config=config, audio=audio)
                text = ""
                if response.results:
                    for result in response.results:
                        if result.alternatives:
                            text += result.alternatives[0].transcript + " "
                    text = text.strip()
                if text:
                    print(f"✅ Google Cloud Speech API transcription successful: {text[:100]}...")
                    recording.transcript_text = text
                    recording.save()
                    transcription_success = True
                else:
                    print("⚠️ Google Cloud Speech API returned no results")
            except Exception as e:
                print(f"❌ Google Cloud Speech API error: {e}")
                import traceback
                print(traceback.format_exc())

        # Method 3: AssemblyAI fallback
        if not transcription_success:
            print("Attempting transcription with AssemblyAI (fallback)...")
            try:
                from dotenv import load_dotenv
                load_dotenv()
                assemblyai_api_key = os.getenv('ASSEMBLYAI_API_KEY')
                if not assemblyai_api_key:
                    print("⚠️ ASSEMBLYAI_API_KEY not found. Skipping.")
                    raise Exception("AssemblyAI API key not configured")

                transcriber = Transcriber(api_key=assemblyai_api_key)
                with open(audio_file, 'rb') as f:
                    transcript = transcriber.transcribe(f)
                max_wait_time = 300
                wait_time = 0
                while transcript.status not in ['completed', 'error'] and wait_time < max_wait_time:
                    time.sleep(2)
                    wait_time += 2
                    try:
                        transcript = transcriber.get_transcript(transcript.id)
                    except Exception as poll_error:
                        print(f"Error polling transcript status: {poll_error}")
                        break
                if transcript.status == 'error':
                    raise Exception(getattr(transcript, 'error', 'Unknown error'))
                if transcript.status == 'completed':
                    text = getattr(transcript, 'text', '')
                    if text:
                        print(f"✅ AssemblyAI transcription successful: {text[:100]}...")
                        recording.transcript_text = text
                        recording.save()
                        transcription_success = True
                    else:
                        print("⚠️ AssemblyAI returned empty transcript")
                else:
                    print(f"⚠️ AssemblyAI status: {transcript.status}")
            except Exception as e2:
                print(f"❌ AssemblyAI error: {e2}")
                import traceback
                print(traceback.format_exc())

        if not SPEECH_RECOGNITION_AVAILABLE and not transcription_success:
            print("💡 SpeechRecognition not available (Python 3.13+). Use Python 3.12 for free transcription, or set GOOGLE_APPLICATION_CREDENTIALS / ASSEMBLYAI_API_KEY")

        # If all methods failed, set empty transcript
        if not transcription_success:
            print(f"❌ All transcription methods failed for recording {recording_id}")
            print(f"💡 Tip: On Python 3.12, SpeechRecognition (free) is tried first. Otherwise set GOOGLE_APPLICATION_CREDENTIALS or ASSEMBLYAI_API_KEY.")
            recording.transcript_text = ""
            recording.save()

    except VideoRecording.DoesNotExist:
        print(f"❌ Error: VideoRecording with ID {recording_id} does not exist")
    except Exception as e:
        print(f"❌ Unexpected error in convert_speech_to_text: {e}")
        import traceback
        print(traceback.format_exc())
        try:
            recording = VideoRecording.objects.get(id=recording_id)
            recording.transcript_text = ""
            recording.save()
        except:
            pass
    finally:
        # Clean up temporary file
        if temp_wav_path and os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
                print(f"Cleaned up temporary file: {temp_wav_path}")
            except Exception as e:
                print(f"Warning: Could not remove temp file {temp_wav_path}: {e}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60}, retry_backoff=True, retry_jitter=True)
def generate_score(self, user_id):
    try:
        from hiring_app.models import ResumeDetails, User
        from .models import Question
        
        print(f"generate_score task started (attempt {self.request.retries + 1})")
        
        # Initialize LLM inside the task
        llm = get_gemini_llm()
        
        user_info = User.objects.get(id=user_id)
        questions = Question.objects.filter(user=user_info)
        video_records = VideoRecording.objects.filter(user=user_info)
        
        total_score = 0 
        question_count = 0
        
        for video_record in video_records:
            # Skip if no transcript available
            if not video_record.transcript_text or not video_record.transcript_text.strip():
                print(f"Skipping video {video_record.id} - no transcript available")
                continue
                
            user_answer = video_record.transcript_text
            
            # Get the associated question
            if hasattr(video_record, 'question') and video_record.question:
                question_obj = video_record.question
                given_question = question_obj.text
            else:
                print(f"Skipping video {video_record.id} - no associated question")
                continue

            # Generate AI response for comparison with retry logic
            query1 = f'''Consider you are a applicant for an interview in a specific company for a role.
            Given a question below, answer for the question with a maximum of 5 lines like you are a applicant for the interview. 
            NOTE: You are not allowed to copy the question in the answer and avoid any extra generation other than the answer for the question.
            Question : {given_question}'''

            try:
                AI_response = execute_llm_with_retry(llm, query1, max_retries=3, initial_wait=10)
                print(f"AI Response: {AI_response.text}")
            except Exception as e:
                error_message = str(e)
                print(f"Error generating AI response after retries: {error_message}")
                
                # Check if it's a rate limit error
                if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
                    print("⚠️ Rate limit exceeded for video scoring. Setting default score.")
                    # Continue with next video instead of failing completely
                    continue
                else:
                    # For other errors, continue with next video
                    continue

            # Generate score by comparing answers with retry logic
            query2 = f'''Consider you are a interviewer in a specific company.
            Given a question, actual answer and the answer generated by the applicant.
            Compare both the answers for the question and provide your feedback on the answer generated by the applicant in the form of a score out of 100.
            NOTE: You are not allowed to copy the question, actual answer and avoid any extra generation other than the score for the answer. Format should be like score/100
            Question : {given_question}
            Actual Answer : {AI_response.text}
            Applicant Answer : {user_answer}'''

            try:
                score_response = execute_llm_with_retry(llm, query2, max_retries=3, initial_wait=10)
                print(f"Score Response: {score_response.text}")
                
                # Extract numeric score from response
                score_text = score_response.text.strip()
                
                # Try to extract score in different formats
                if '/' in score_text:
                    # Format: "85/100"
                    score = float(score_text.split('/')[0])
                else:
                    # Try to extract first number found
                    numbers = re.findall(r'\d+(?:\.\d+)?', score_text)
                    if numbers:
                        score = float(numbers[0])
                        # If score seems to be out of 100, keep it; if out of other scale, normalize
                        if score > 100:
                            score = min(score, 100)  # Cap at 100
                    else:
                        print(f"Could not extract score from: {score_text}")
                        score = 0
                
                total_score += score
                question_count += 1
                print(f"Extracted score: {score}")
                
            except Exception as e:
                error_message = str(e)
                print(f"Error generating or parsing score after retries: {error_message}")
                
                # Check if it's a rate limit error
                if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
                    print("⚠️ Rate limit exceeded for score generation. Skipping this video.")
                continue
        
        print(f"Total score: {total_score}, Question count: {question_count}")
        
        # Calculate average score
        if question_count > 0:
            average_score = total_score / question_count
            
            # Update resume details
            resume_details = ResumeDetails.objects.get(user=user_info)
            resume_details.video_score = average_score
            resume_details.save()
            
            print(f"Video score updated: {average_score}")
            print("Successfully scored the video")
        else:
            print("No valid video responses found to score")
            # Set video score to 0 if no videos could be scored
            try:
                resume_details = ResumeDetails.objects.get(user=user_info)
                if resume_details.video_score is None:
                    resume_details.video_score = 0
                    resume_details.save()
            except:
                pass
            
    except Exception as e:
        print(f"Error in generate_score task: {e}")
        raise