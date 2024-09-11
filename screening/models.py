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