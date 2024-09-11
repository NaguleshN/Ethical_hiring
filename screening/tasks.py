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
        video_recording = VideoRecording.objects.get(id=video_id)
        video_path = video_recording.video.path

        audio_path = video_path.replace('.webm', '.mp3')

        ffmpeg.input(video_path).output(audio_path).run()

        with open(audio_path, 'rb') as audio_file:
            video_recording.audio_file.save(os.path.basename(audio_path), audio_file)
            video_recording.save()

            convert_speech_to_text.delay(video_recording.id)
        print(f'Audio extraction successful for video ID {video_id}')

        os.remove(audio_path)

    except Exception as e:
        print(f'An error occurred: {e}')


@shared_task
def convert_speech_to_text(recording_id):
    try:
        recording = VideoRecording.objects.get(id=recording_id)

        audio_file = recording.audio_file.path
        file_extension = os.path.splitext(audio_file)[1].lower()

        if file_extension != '.wav':
            sound = AudioSegment.from_file(audio_file)
            temp_wav_path = 'temp.wav' 
            sound.export(temp_wav_path, format='wav')
            audio_file = temp_wav_path 

        r = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio = r.record(source)

        try:
            text = r.recognize_google(audio)
            print(f"Transcription: {text}")
            recording.transcript_text = text 
            recording.save()  

        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand the audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")

        if file_extension != '.wav' and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

    except Exception as e:
        print(f"An error occurred: {e}")