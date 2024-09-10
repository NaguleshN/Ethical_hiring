import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import *

# Create your views here.
@login_required
def home(request):
    if request.method == "POST":
        message_context = request.FILES.get('message')
        name = request.user.username
        
        if message_context and message_context.name.endswith('.pdf'):
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            file_path = os.path.join(upload_dir, f'{name}_{message_context.name}')
            
            with open(file_path, 'wb+') as destination:
                for chunk in message_context.chunks():
                    destination.write(chunk)

            check = ResumeCheck.objects.get(user = request.user)
            check.upload_status =1 
            check.save()
            print(f'Uploaded file: {message_context.name}')
            return redirect('success') 
        else:
            print('Uploaded file is not a PDF')
            return redirect('home') 
    try :
        ResumeCheck.objects.get(user = request.user)
    except :
        ResumeCheck.objects.create(user = request.user ,upload_status = 0)
        print(request.user)
        print(type(request.user))
    
    check = ResumeCheck.objects.get(user = request.user)
    print(check.upload_status)
    verify_uploaded = check.upload_status
    if verify_uploaded == "0" :
        return render(request, "index.html")
    else :
        return redirect('success')


def login(request):
    return render(request, "login.html")

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def success(request):
    return render(request ,"upload.html")