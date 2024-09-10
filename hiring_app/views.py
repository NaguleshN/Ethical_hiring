import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import auth
from django.contrib import messages


@login_required
def home(request):
    if not request.user.is_superuser:
        if request.method == "POST":
            message_context = request.FILES.get('message')
            name = request.user.username
            
            if message_context and message_context.name.endswith('.pdf'):
                upload_dir = os.path.join(settings.MEDIA_ROOT, f'uploads/{request.user.username}')
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                file_path = os.path.join(upload_dir, f'{name}_{message_context.name}')
                
                with open(file_path, 'wb+') as destination:
                    for chunk in message_context.chunks():
                        destination.write(chunk)

                check = ResumeCheck.objects.get(user = request.user)
                check.upload_status =1 
                check.save()

                set_path =f"/home/nagulesh/Documents/Projects/Ethical_hiring/Hiring_platform/uploads/{request.user.username}"
                path = FileResumePath.objects.create(user = request.user ,path =set_path)
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
    resume_info = ResumeDetails.objects.all()
    return render(request ,"index1.html" ,{"resume_info":resume_info})


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
    user_detail = ResumeDetails.objects.filter(user=request.user)
    if not user_detail.exists():
        import os
        from dotenv import load_dotenv


        load_dotenv()

        from llama_index.core import SimpleDirectoryReader
        from llama_index.core import Settings

        # documents = SimpleDirectoryReader('/home/nagulesh/Documents/Projects/Ethical_hiring/Hiring_platform/uploads/nagulesh03').load_data()

        file = FileResumePath.objects.get(user =request.user)
        file_path = file.path

        documents = SimpleDirectoryReader(file_path).load_data()
        nodes = Settings.node_parser.get_nodes_from_documents(documents)



        from llama_index.embeddings.gemini import GeminiEmbedding
        from llama_index.llms.gemini import Gemini

        Settings.embed_model = GeminiEmbedding(
            model_name="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY")
        )
        Settings.llm = Gemini(api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.7)



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

                # if self._mode == "AND":
                #     retrieve_ids = vector_ids.intersection(keyword_ids)
                # else:
                retrieve_ids = vector_ids.union(keyword_ids)

                retrieve_nodes = [combined_dict[r_id] for r_id in retrieve_ids]
                return retrieve_nodes
            



        from llama_index.core import get_response_synthesizer
        from llama_index.core.query_engine import RetrieverQueryEngine

        vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=2)
        keyword_retriever = KeywordTableSimpleRetriever(index=keyword_index)

        # custom retriever => combine vector and keyword retriever

        custom_retriever = CustomRetriever(vector_retriever, keyword_retriever)

        # define response synthesizer
        response_synthesizer = get_response_synthesizer()

        custom_query_engine = RetrieverQueryEngine(
            retriever=custom_retriever,
            response_synthesizer=response_synthesizer,
        )


        import threading
        import time

        # Function to handle the query
        def execute_query(query, result_holder, query_engine = custom_query_engine):
            # Execute the query and store the result in result_holder
            result_holder[0] = query_engine.query(query)

        # Main query loop with timeout logic
        # while True:
            # print(dir(VectorIndexRetriever))
        # query = input("Enter query: ")
        query = "give a array containing the name, institution, city, passout year, CGPA, Degree, skills, work experience, projects, achievements, emailID, phone number of the student Aravind G from the data context given. If he dont have any of these fill the array with None in the respective index"
        # query_set = ["what is the name of the student", "what is the name of the institution"]
        # out = []
        # for i in query_set :
        if query == "exit":
            print("Exiting...")

        result_holder = [None]

        query_thread = threading.Thread(target=execute_query, args=(query, result_holder))
        query_thread.start()

        query_thread.join(timeout=5)

        if query_thread.is_alive():
            print("Query timed out, returning null.")
            result = None
        else:
            result = result_holder[0]

        print(type(result))
        result1=str(result)
        print(type(result1))
        import ast
        array = ast.literal_eval(result1)
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
            ResumeDetails.objects.create(name=name,institution=institution,city=city ,passing_out_year=passing_out_year,Cgpa=Cgpa ,Degree =Degree,skills=skills ,work_experience=work_experience ,projects=projects ,achievements=achievements ,emailid=emailid ,phone_number=phone_number)
            print("created successfully")
            return redirect("response")
        except :
            print("Error occured in object creation")
        return  render (request , "upload.html" )
    else:
        return render(request,"upload.html")

def response(request):
    return render(request,"response.html")

from hiring_app.tasks import get_score
def upload_creteria(request):
    if request.method == "POST":
        message_context = request.FILES.get("message")
        file_paths= FileResumePath.objects.all()
        for i in file_paths:
            upload_dir = i.path
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
                    
            file_path = os.path.join(upload_dir, f'{request.user.username}_{message_context.name}')
                    
            with open(file_path, 'wb+') as destination:
                for chunk in message_context.chunks():
                    destination.write(chunk)

        for i in file_paths:
            file_path = i.path
            get_score.delay(file_path)

        return redirect("dashboard")
    
    return render(request,"upload_creteria.html")