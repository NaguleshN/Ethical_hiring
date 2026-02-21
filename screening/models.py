from django.db import models
from django.contrib.auth.models import User

class Question(models.Model):
    status_choice=(('attended','attended'),('not_attended','not_attended'))
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    status=models.CharField(max_length=20,  choices=status_choice, null=True)

    def _str_(self):
        return self.text

class VideoRecording(models.Model):
    user =models.ForeignKey(User ,on_delete=models.CASCADE ,null=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    video = models.FileField(upload_to='videos/')
    recorded_at = models.DateTimeField(auto_now_add=True)
    audio_file = models.FileField(upload_to='audios/', blank=True, null=True)
    transcript_text = models.TextField(blank=True)

    def _str_(self):
        return f"Recording from {self.recorded_at}"

class FaceReference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    aadhaar_image = models.ImageField(upload_to='aadhaar_cards/')
    face_crop = models.ImageField(upload_to='face_crops/', null=True, blank=True)
    webcam_capture = models.ImageField(upload_to='webcam_captures/', null=True, blank=True)
    webcam_face_crop = models.ImageField(upload_to='webcam_face_crops/', null=True, blank=True)
    embedding = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"FaceReference for {self.user.username}"