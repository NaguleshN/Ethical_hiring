from django.shortcuts import render, HttpResponse ,redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import VideoRecording, Question, FaceReference
from .tasks import extract_audio_from_video 
import json

def screen(request):
        unanswered_questions = Question.objects.filter(user=request.user,status="not_attended")

        questions = Question.objects.all()

        if not unanswered_questions:
            return redirect('completed')

        current_question = unanswered_questions[0]

        # Check if face verification is done (session-based)
        face_verified = request.session.get('face_verified', False)

        # Check if user has a FaceReference (Aadhaar uploaded)
        has_face_ref = FaceReference.objects.filter(user=request.user).exists()

        return render(request, 'screen.html', {
            'question': current_question,
            'questions': json.dumps(list(questions.values('id', 'text'))),
            'face_verified': face_verified,
            'has_face_ref': has_face_ref,
        })


@csrf_exempt
def upload_aadhaar_view(request):
    """
    Accepts Aadhaar card image upload, detects face, generates embedding,
    and stores as FaceReference. Called from the verification page.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

    aadhaar_card = request.FILES.get('aadhaar_card')
    if not aadhaar_card:
        return JsonResponse({'status': 'error', 'message': 'No Aadhaar card image provided'})

    try:
        from screening.face_verify import (
            detect_face_with_coords, get_face_embedding, 
            serialize_embedding, mask_aadhaar_text
        )
        from PIL import Image
        from django.core.files.base import ContentFile
        import io
        import os
        import tempfile

        # Save uploaded Aadhaar to a temp file for processing
        temp_dir = tempfile.gettempdir()
        temp_aadhaar_path = os.path.join(temp_dir, f"aadhaar_raw_{request.user.id}.jpg")
        
        with open(temp_aadhaar_path, 'wb+') as f:
            for chunk in aadhaar_card.chunks():
                f.write(chunk)

        # 1. Detect face and get coordinates (so we don't mask the face)
        try:
            face_crop, face_coords = detect_face_with_coords(temp_aadhaar_path)
        except ValueError as e:
            if os.path.exists(temp_aadhaar_path): os.remove(temp_aadhaar_path)
            raise e

        # 2. Mask/Blur text in Aadhaar card using EasyOCR
        try:
            masked_aadhaar_pil = mask_aadhaar_text(temp_aadhaar_path, face_coords)
        except Exception as ocr_err:
            print(f"Warning: Masking failed ({ocr_err}), proceeding with original image.")
            masked_aadhaar_pil = Image.open(temp_aadhaar_path).convert('RGB')

        # 3. Generate embedding from the face crop
        embedding = get_face_embedding(face_crop)
        embedding_bytes = serialize_embedding(embedding)

        # 4. Prepare files for storage
        # Masked Aadhaar card
        masked_buffer = io.BytesIO()
        masked_aadhaar_pil.save(masked_buffer, format='JPEG')
        masked_buffer.seek(0)

        # Face crop
        face_buffer = io.BytesIO()
        face_crop.save(face_buffer, format='JPEG')
        face_buffer.seek(0)

        # 5. Create or update FaceReference
        name = request.user.username
        face_ref, created = FaceReference.objects.update_or_create(
            user=request.user,
            defaults={
                'embedding': embedding_bytes,
            }
        )
        
        # Save the MASKS version of Aadhaar
        face_ref.aadhaar_image.save(
            f'{name}_aadhaar_masked.jpg', ContentFile(masked_buffer.read()), save=False
        )
        # Save the face crop
        face_ref.face_crop.save(
            f'{name}_face_crop.jpg', ContentFile(face_buffer.read()), save=False
        )
        face_ref.save()

        # Cleanup temp file
        if os.path.exists(temp_aadhaar_path):
            os.remove(temp_aadhaar_path)

        print(f"✅ Masked Aadhaar reference created for user: {request.user.username}")
        print(f"✅ Face reference created for user: {request.user.username}")

        return JsonResponse({
            'status': 'success',
            'message': 'Aadhaar card processed successfully. Face detected!'
        })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Could not detect face in Aadhaar card: {str(e)}. Please upload a clearer image.'
        })
    except Exception as e:
        print(f"❌ Error processing Aadhaar card: {e}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': 'Error processing Aadhaar card. Please try again.'
        })


@csrf_exempt
def verify_face_view(request):
    """
    Accepts a base64-encoded webcam snapshot, uses DeepFace to
    directly verify against the stored Aadhaar face crop.
    Returns JSON with verification result.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

    try:
        import base64
        import tempfile
        import os
        from screening.face_verify import verify_faces_directly, VERIFICATION_THRESHOLD

        # Get base64 image from request
        body = json.loads(request.body)
        image_data = body.get('image')

        if not image_data:
            return JsonResponse({'status': 'error', 'message': 'No image provided'})

        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        # Decode and save temporarily
        image_bytes = base64.b64decode(image_data)
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name

            # Check if user has a face reference with a saved face crop
            try:
                face_ref = FaceReference.objects.get(user=request.user)
            except FaceReference.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No Aadhaar card on file. Please upload your Aadhaar card first.'
                })

            # Get the aadhaar face crop path for direct comparison
            if face_ref.face_crop and face_ref.face_crop.name:
                aadhaar_path = face_ref.face_crop.path
            elif face_ref.aadhaar_image and face_ref.aadhaar_image.name:
                aadhaar_path = face_ref.aadhaar_image.path
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Face reference not properly stored. Please re-upload your Aadhaar card.'
                })

            # Use DeepFace direct verification (includes internal liveness check)
            from screening.face_verify import verify_faces_directly
            result = verify_faces_directly(aadhaar_path, temp_path)

            # Check liveness first
            is_real = bool(result.get('is_real', True))
            if not is_real:
                return JsonResponse({
                    'status': 'error',
                    'verified': False,
                    'similarity': 0,
                    'is_real': False,
                    'message': result.get('message', 'Spoofing detected! Please show your live face, not a photo or screen.')
                })

            similarity = float(result['similarity'])
            is_verified = bool(result['verified'])

            print(f"Face verification for {request.user.username}: similarity={similarity:.2f}%, verified={is_verified}, is_real={is_real}, model={result.get('model')}")

            if is_verified:
                request.session['face_verified'] = True

                # Save webcam capture and cropped face to FaceReference
                from django.core.files.base import ContentFile
                from django.utils import timezone
                import numpy as np
                from PIL import Image as PILImage

                # Save raw webcam capture
                face_ref.webcam_capture.save(
                    f'{request.user.username}_webcam.jpg',
                    ContentFile(image_bytes),
                    save=False
                )

                # Extract and save the cropped face from webcam
                try:
                    from deepface import DeepFace
                    face_objs = DeepFace.extract_faces(
                        img_path=temp_path,
                        detector_backend='yolov8n',
                        align=True,
                        enforce_detection=True,
                    )
                    if face_objs:
                        best_face = max(face_objs, key=lambda f: f.get("confidence", 0))
                        face_array = (best_face["face"] * 255).astype(np.uint8)
                        face_img = PILImage.fromarray(face_array)

                        import io
                        face_buffer = io.BytesIO()
                        face_img.save(face_buffer, format='JPEG')
                        face_buffer.seek(0)

                        face_ref.webcam_face_crop.save(
                            f'{request.user.username}_webcam_face.jpg',
                            ContentFile(face_buffer.read()),
                            save=False
                        )
                except Exception as crop_err:
                    print(f"Warning: Could not save webcam face crop: {crop_err}")

                face_ref.verified_at = timezone.now()
                face_ref.save()

                # Privacy: Delete raw webcam capture after verification
                # We keep the masked Aadhaar and the face crops for record keeping
                try:
                    import os
                    # Delete the raw webcam capture as it's no longer needed after verification
                    if face_ref.webcam_capture and face_ref.webcam_capture.name:
                        if os.path.exists(face_ref.webcam_capture.path):
                            os.remove(face_ref.webcam_capture.path)
                        face_ref.webcam_capture = None
                    
                    face_ref.save()
                    print(f"Privacy cleanup: Raw webcam image for {request.user.username} deleted. Masked Aadhaar preserved.")
                except Exception as cleanup_err:
                    print(f"Warning: Privacy cleanup failed: {cleanup_err}")

            return JsonResponse({
                'status': 'success',
                'verified': is_verified,
                'similarity': similarity,
                'is_real': is_real,
                'message': f'Face match: {similarity:.1f}%' if is_verified else f'Face mismatch: {similarity:.1f}%. Minimum required: {VERIFICATION_THRESHOLD:.0f}%'
            })

        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'verified': False,
            'similarity': 0,
            'message': str(e)
        })
    except Exception as e:
        print(f"Face verification error: {e}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'verified': False,
            'similarity': 0,
            'message': 'Verification error. Please try again.'
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
from hiring_app.models import *
from screening.tasks import *
def completed_task(request):
    generate_score.delay(request.user.id)
    return render(request,"completed.html")
