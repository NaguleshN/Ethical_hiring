from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import VideoRecording, Question
from .tasks import extract_audio_from_video
import json


def screen(request):
        # answered_questions = request.session.get('answered_questions', [])
        unanswered_questions = Question.objects.filter(user=request.user,status="not_attended")

        questions = Question.objects.all()

        # unanswered_questions = [q for q in questions if q.id not in answered_questions]
        # quest_answered =Question.objects.get(user=request.user)

        if not unanswered_questions:
            return render(request, 'completed.html')

        current_question = unanswered_questions[0]

        return render(request, 'screen.html', {
            'question': current_question,
            'questions': json.dumps(list(questions.values('id', 'text')))
        })


@csrf_exempt
def upload_video(request):
    if request.method == 'POST':
        video_file = request.FILES.get('video')
        question_id = request.POST.get('question_id')
        if video_file and question_id:
            question = Question.objects.get(id=question_id)
            question.status = "attended"
            question.save()
            question = Question.objects.get(id=question_id)
            video_recording = VideoRecording.objects.create(
                user=request.user,
                question=question,
                video=video_file
            )

            extract_audio_from_video.delay(video_recording.id)

            answered_questions = request.session.get('answered_questions', [])
            if question.id not in answered_questions:
                answered_questions.append(question.id)
                request.session['answered_questions'] = answered_questions

            return JsonResponse({'status': 'success', 'video_id': video_recording.id})
        else:
            return JsonResponse({'status': 'error', 'message': 'No video file or question_id provided'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


#  celery -A Hiring_platform worker --loglevel=info
