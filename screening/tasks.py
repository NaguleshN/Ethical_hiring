from celery import shared_task
import ffmpeg
import os
from django.conf import settings
from .models import VideoRecording
from google.cloud import speech_v1p1beta1 as speech
import speech_recognition as sr
from pydub import AudioSegment
from django.conf import settings
import io
from assemblyai import Transcriber


@shared_task
def extract_audio_from_video(video_id):
    try:
        # Retrieve the video from the database
        video_recording = VideoRecording.objects.get(id=video_id)
        video_path = video_recording.video.path

        # Define the path for the extracted audio file
        audio_path = video_path.replace('.webm', '.mp3')

        # Use ffmpeg to extract the audio
        ffmpeg.input(video_path).output(audio_path).run()

        # Ensure the audio file is saved and the model is updated
        with open(audio_path, 'rb') as audio_file:
            video_recording.audio_file.save(os.path.basename(audio_path), audio_file)
            video_recording.save()

            convert_speech_to_text.delay(video_recording.id)
        print(f'Audio extraction successful for video ID {video_id}')
        
        # Optional: Remove the audio file after saving to avoid clutter
        os.remove(audio_path)
    
    except Exception as e:
        print(f'An error occurred: {e}')

@shared_task
def convert_speech_to_text(recording_id):
    try:
        # Fetch the VideoRecording instance
        recording = VideoRecording.objects.get(id=recording_id)

        # Define file paths
        audio_file = recording.audio_file.path
        file_extension = os.path.splitext(audio_file)[1].lower()

        # Convert non-wav audio to wav format
        if file_extension != '.wav':
            sound = AudioSegment.from_file(audio_file)
            temp_wav_path = 'temp.wav'  # Temporary wav file
            sound.export(temp_wav_path, format='wav')
            audio_file = temp_wav_path  # Update to the temp wav file path

        # Recognize the audio
        r = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio = r.record(source)

        # Try recognizing the speech in the audio
        try:
            text = r.recognize_google(audio)
            print(f"Transcription: {text}")
            recording.transcript_text = text  # Save the transcribed text to the model
            recording.save()  # Save the changes to the database

        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand the audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")

        # Clean up the temporary file if it was created
        if file_extension != '.wav' and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

    except Exception as e:
        print(f"An error occurred: {e}")