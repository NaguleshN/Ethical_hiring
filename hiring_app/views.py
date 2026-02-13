import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import auth
from django.contrib import messages
from hiring_app.tasks import get_score , send_email


@login_required
def home(request):
    project_path = settings.BASE_DIR
    some_file_path = project_path / 'uploads' / request.user.username
    print(f"Project path: {some_file_path}")
    if not request.user.is_superuser:
        if request.method == "POST":
            message_context = request.FILES.get('message')
            name = request.user.username
            
            if message_context and message_context.name.endswith('.pdf'):
                upload_dir = os.path.join(project_path / 'uploads' / request.user.username)
                print(f"Upload directory: {upload_dir}")
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                file_path = os.path.join(upload_dir, f'{name}_{message_context.name}')
                
                with open(file_path, 'wb+') as destination:
                    for chunk in message_context.chunks():
                        destination.write(chunk)

                check = ResumeCheck.objects.get(user = request.user)
                check.upload_status=1 
                check.save()
                if not FileResumePath.objects.filter(user=request.user).exists():
                    print(f'Creating new FileResumePath for user: {request.user}')
                    FileResumePath.objects.create(user = request.user ,path = upload_dir)
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
        if verify_uploaded == "0" or verify_uploaded == 0 :
            return render(request, "index.html")
        else :
            return redirect('success')
    else :
        return redirect("dashboard")

@login_required
def admin_dashboard(request):
    resume_info = ResumeDetails.objects.select_related('user').all()
    return render(request ,"index1.html" ,{"resume_info":resume_info})

# from django.core.mail import send_mail,EmailMessage
from Hiring_platform.settings import EMAIL_HOST_USER
from hiring_app.tasks import send_mail_user

@login_required
def send_mail(request, id):
    """
    Send email notification to candidate about interview shortlisting.
    """
    try:
        resume_info = ResumeDetails.objects.get(id=id)
        to_user = resume_info.emailid
        
        if not to_user:
            messages.error(request, f"❌ No email address found for candidate ID {id}")
            print(f"❌ No email address found for candidate ID {id}")
            return redirect("dashboard")
        
        print(f"📧 Queuing email to: {to_user}")
        
        # Queue the email task
        task = send_mail_user.delay(to_user)
        print(f"✅ Email task queued with ID: {task.id}")
        
        messages.success(request, f"✅ Email queued successfully for {to_user}")
        
    except ResumeDetails.DoesNotExist:
        messages.error(request, f"❌ Resume details not found for ID {id}")
        print(f"❌ Resume details not found for ID {id}")
    except Exception as e:
        error_msg = f"❌ Error queuing email: {str(e)}"
        messages.error(request, error_msg)
        print(error_msg)
        import traceback
        print(traceback.format_exc())
    
    return redirect("dashboard")


def login(request):
    if request.method =="POST":
        username=request.POST.get("username")
        password=request.POST.get("password")
        print(username,"-->",password)
        user=auth.authenticate(username=username,password=password)
        if user is not None:
            print(" --Accepted-- ")
            auth.login(request,user)
            messages.success(request, 'You are successfully logged in.')
            print('You are successfully logged in.')
            return redirect('home')
        else:
            error_message = "Invalid username and password."
            print(error_message)
            messages.error(request ,error_message)
            return redirect("login")
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def success(request):
    try:
        user_detail = ResumeDetails.objects.filter(user=request.user)
        print(user_detail)
        if not user_detail.exists():
            import os
            from dotenv import load_dotenv

            load_dotenv()

            from llama_index.core import SimpleDirectoryReader
            from llama_index.core import Settings

            file = FileResumePath.objects.get(user=request.user)
            file_path = file.path

            documents = SimpleDirectoryReader(file_path).load_data()
            nodes = Settings.node_parser.get_nodes_from_documents(documents)


            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            from llama_index.llms.gemini import Gemini

            # Disable MPS on macOS to prevent crashes
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'

            # Use local embeddings (FREE - no API quota!)
            Settings.embed_model = HuggingFaceEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                device="cpu"  # Force CPU to avoid MPS issues on macOS
            )
            print(os.getenv("GOOGLE_API_KEY"))
            Settings.llm = Gemini(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.7)

            from llama_index.core import StorageContext

            storage_context = StorageContext.from_defaults()
            storage_context.docstore.add_documents(nodes)


            from llama_index.core import SimpleKeywordTableIndex, VectorStoreIndex

            vector_index = VectorStoreIndex(nodes, storage_context=storage_context)
            keyword_index = SimpleKeywordTableIndex(nodes, storage_context=storage_context)


            from llama_index.core import QueryBundle
            from llama_index.core.schema import NodeWithScore

            from llama_index.core.retrievers import (
                BaseRetriever,
                VectorIndexRetriever,
                KeywordTableSimpleRetriever,
            )

            from typing import List

            class CustomRetriever(BaseRetriever):
                def __init__(
                    self,
                    vector_retriever: VectorIndexRetriever,
                    keyword_retriever: KeywordTableSimpleRetriever,
                    mode: str = "AND") -> None:
                
                    self._vector_retriever = vector_retriever
                    self._keyword_retriever = keyword_retriever
                    if mode not in ("AND", "OR"):
                        raise ValueError("Invalid mode.")
                    self._mode = mode
                    super().__init__()

                def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
                    vector_nodes = self._vector_retriever.retrieve(query_bundle)
                    keyword_nodes = self._keyword_retriever.retrieve(query_bundle)

                    vector_ids = {n.node.node_id for n in vector_nodes}
                    keyword_ids = {n.node.node_id for n in keyword_nodes}

                    combined_dict = {n.node.node_id: n for n in vector_nodes}
                    combined_dict.update({n.node.node_id: n for n in keyword_nodes})

                    retrieve_ids = vector_ids.union(keyword_ids)

                    retrieve_nodes = [combined_dict[r_id] for r_id in retrieve_ids]
                    return retrieve_nodes

            from llama_index.core import get_response_synthesizer
            from llama_index.core.query_engine import RetrieverQueryEngine

            vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=2)
            keyword_retriever = KeywordTableSimpleRetriever(index=keyword_index)

            custom_retriever = CustomRetriever(vector_retriever, keyword_retriever)

            response_synthesizer = get_response_synthesizer()

            custom_query_engine = RetrieverQueryEngine(
                retriever=custom_retriever,
                response_synthesizer=response_synthesizer,
            )


            import threading
            import time

            def execute_query(query, result_holder, query_engine = custom_query_engine):
                
                result_holder[0] = query_engine.query(query)

            query = """
                    Return an array with exactly 12 comma-separated string values in the following order.  
                    If a field is missing, use `"None"` (as a string).  

                    **Order of fields in the array:**  
                    1. Name  
                    2. Institution  
                    3. City  
                    4. Passout Year  
                    5. CGPA  (give me 0 if not available and values ranges from 0 to 10)
                    6. Degree  
                    7. Skills (comma-separated if multiple, else `"None"`)  
                    8. Work Experience (comma-separated if multiple, else `"None"`)  
                    9. Projects (comma-separated if multiple, else `"None"`)  
                    10. Achievements (comma-separated if multiple, else `"None"`)  
                    11. Email ID  
                    12. Phone Number  

                    **Example Output:**  
                    [  
                    "John Doe",  
                    "XYZ University",  
                    "New York",  
                    "2023",  
                    "3.8",  
                    "B.Tech in Computer Science",  
                    "Python, SQL, JavaScript",  
                    "Intern at ABC Corp, Freelance Developer",  
                    "Chatbot Development, Weather App",  
                    "Hackathon Winner, Dean's List",  
                    "john@example.com",  
                    "+1234567890"  
                    ]  

                    **Rules:**  
                    - Every array must have 12 strings.  
                    - Empty/missing fields = `"None"`.  
                    - For lists (skills, projects, etc.), join items with commas.  
                    """

            if query == "exit":
                print("Exiting...")

            result_holder = [None]

            query_thread = threading.Thread(target=execute_query, args=(query, result_holder))
            query_thread.start()

            # Increased timeout to 30 seconds for local embeddings (first run may be slower)
            query_thread.join(timeout=30)

            if query_thread.is_alive():
                print("Query timed out after 30 seconds.")
                # Return error message to user
                return render(request, "upload.html", {"error": "Resume processing timed out. Please try again."})
            else:
                result = result_holder[0]

            # Check if result is None
            if result is None:
                print("Query returned None")
                return render(request, "upload.html", {"error": "Failed to process resume. Please try again."})

            print(type(result))
            result1=str(result)
            print(type(result1))
            print(result1)
            
            import ast
            result1_cleaned = result1.replace("```json", "").replace("```", "").strip()

            try:
                array = ast.literal_eval(result1_cleaned)
            except (ValueError, SyntaxError) as e:
                print(f"Error parsing result: {e}")
                return render(request, "upload.html", {"error": "Failed to parse resume data. Please try again."})
            print(array)
            print(type(array))

            name= array[0]
            institution =array[1]
            city =array[2]
            passing_out_year=array[3]
            Cgpa=array[4]
            Degree=array[5]
            skills=array[6]
            work_experience=array[7]
            projects=array[8]
            achievements=array[9]
            emailid=array[10]
            phone_number=array[11]

            print(name,institution,city ,passing_out_year,Cgpa ,Degree ,skills ,work_experience ,projects ,achievements ,emailid ,phone_number)

            try:
                if(Cgpa == "None"):
                    Cgpa = 0
                if(passing_out_year == "None"):
                    passing_out_year = 0
                if(phone_number == "None"):
                    phone_number = 0
                ResumeDetails.objects.create(user=request.user ,name=name,institution=institution,city=city ,passing_out_year=passing_out_year,Cgpa=Cgpa ,Degree =Degree,skills=skills ,work_experience=work_experience ,projects=projects ,achievements=achievements ,emailid=emailid ,phone_number=phone_number, status ="pending")
                print("created successfully")
                return redirect("response")
            except Exception as e:
                print("Error:", e)
                print("Error occured in object creation")
            return  render (request , "upload.html" )
        else:
            return redirect("response")
    except Exception as e:
        print("Hello",e) 
        print("Error occured in getting user details")
        return render(request, "upload.html")

def response(request):
    resume_info = ResumeDetails.objects.get(user=request.user)
    if resume_info.status == "approved" :
        return redirect("screen")
    return render(request,"response.html")


def upload_creteria(request):
    if request.method == "POST":
        message_context = request.FILES.get("message")
        if not message_context:
            return render(request, "upload_creteria.html", {"error": "No file uploaded"})
            
        file_paths = FileResumePath.objects.all()
        
        for i in file_paths:
            upload_dir = i.path
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
                                
            file_path = os.path.join(upload_dir, f'{request.user.username}_{message_context.name}')
                                
            with open(file_path, 'wb+') as destination:
                for chunk in message_context.chunks():
                    destination.write(chunk)
        
        for i in file_paths:
            # file_path = os.path.join(i.path, f'{request.user.username}_{message_context.name}')
            file_path = i.path
            print("Getting scores...")
            print(f"File path: {file_path}, User ID: {i.user.id}")
            
            try:
                # print(get_score)
                # task = get_score(file_path, i.user.id)
                task = get_score.delay(file_path, i.user.id)
                # print(f"Task queued with ID: {task.id}")

                # from celery.result import AsyncResult
                # result = AsyncResult(task.id)
                # print(f"Task state: {result.state}")
            except Exception as e:
                print(f"Error queuing task: {e}")
            
            print("Task queued...")
        
        return redirect("dashboard")
    
    return render(request, "upload_creteria.html")

from hiring_app.tasks import generating_questions
def approve(request,id):
    resume_detail = ResumeDetails.objects.get(id=id)
    resume_detail.status = "approved"
    user=resume_detail.user
    resume_detail.save()
    file_path_info = FileResumePath.objects.get(user=user)
    file_path = file_path_info.path

    generating_questions.delay(file_path,user.id)
    return redirect("dashboard")


def reject(request,id):
    resume_detail = ResumeDetails.objects.get(id=id)
    resume_detail.status = "rejected"
    resume_detail.save()
    return redirect("dashboard")