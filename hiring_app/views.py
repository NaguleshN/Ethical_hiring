from django.shortcuts import render
from django.conf import settings
import os

# Create your views here.

def home(request):
    if request.method=="POST":
        message_context = request.FILES.get('message')
        name =request.user.username
        print(name)
        # file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', name)
        
        # with open(file_path, 'wb+') as destination:
        #     for chunk in message_context.chunks():
        #         destination.write(chunk)
        # print(message_context.name)
    return render(request , "login.html")


def login(request):
    return render(request, "login.html")