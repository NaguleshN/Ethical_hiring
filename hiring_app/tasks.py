from celery import shared_task
from .models import *

def setup_llama_index():
    """Initialize LlamaIndex components"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    from llama_index.core import Settings
    from llama_index.embeddings.gemini import GeminiEmbedding
    from llama_index.llms.gemini import Gemini
    
    Settings.embed_model = GeminiEmbedding(
        model_name="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY")
    )
    Settings.llm = Gemini(api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.7)
    
    return Settings

def create_query_engine(file_path):
    """Create and return a query engine for the given file path"""
    from llama_index.core import SimpleDirectoryReader, StorageContext
    from llama_index.core import SimpleKeywordTableIndex, VectorStoreIndex
    from llama_index.core import QueryBundle, get_response_synthesizer
    from llama_index.core.schema import NodeWithScore
    from llama_index.core.retrievers import (
        BaseRetriever, VectorIndexRetriever, KeywordTableSimpleRetriever
    )
    from llama_index.core.query_engine import RetrieverQueryEngine
    from typing import List
    
    # Setup LlamaIndex
    settings = setup_llama_index()
    
    # Load documents
    documents = SimpleDirectoryReader(file_path).load_data()
    nodes = settings.node_parser.get_nodes_from_documents(documents)
    
    # Create storage context
    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(nodes)
    
    # Create indices
    vector_index = VectorStoreIndex(nodes, storage_context=storage_context)
    keyword_index = SimpleKeywordTableIndex(nodes, storage_context=storage_context)
    
    class CustomRetriever(BaseRetriever):
        def __init__(
            self,
            vector_retriever: VectorIndexRetriever,
            keyword_retriever: KeywordTableSimpleRetriever,
            mode: str = "AND"
        ) -> None:
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
    
    # Create retrievers
    vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=2)
    keyword_retriever = KeywordTableSimpleRetriever(index=keyword_index)
    custom_retriever = CustomRetriever(vector_retriever, keyword_retriever)
    
    # Create query engine
    response_synthesizer = get_response_synthesizer()
    query_engine = RetrieverQueryEngine(
        retriever=custom_retriever,
        response_synthesizer=response_synthesizer,
    )
    
    return query_engine

def execute_query_with_timeout(query, query_engine, timeout=5):
    """Execute query with timeout"""
    import threading
    
    def execute_query(query, result_holder, query_engine):
        result_holder[0] = query_engine.query(query)
    
    result_holder = [None]
    query_thread = threading.Thread(target=execute_query, args=(query, result_holder, query_engine))
    query_thread.start()
    query_thread.join(timeout=timeout)
    
    if query_thread.is_alive():
        print("Query timed out, returning null.")
        return None
    else:
        return result_holder[0]

@shared_task
def get_score(file_path, user_id):
    print(file_path, user_id)
    print("get_score task started")
    
    try:
        query_engine = create_query_engine(file_path)
        
        # query = "Compare the skills listed by student with the provided Required Skills, also based on the score metrics for those skills, calculate the scores for student skills in required and other metrics such as experience, projects. Give only the total percentage for each category provided in the criteria context and the total percentage for each category should be out of 100%. NOTE: Give the categpries (Tech Skills, Experience&Achievements, Certifications, Projects) and their percentage out of 100 from the requirements in each category n. Give this is in a dictionary format without any quotes."
        query ="""Analyze this candidate profile and provide scores strictly in this format:
            {
            'Tech Skills': 0-100, 
            'Experience&Achievements': 0-100,
            'Certifications': 0-100,
            'Projects': 0-100
            }

            Scoring Rules:
            1. Tech Skills: Evaluate programming languages, tools, frameworks (0 if none found)
            2. Experience&Achievements: Years of relevant work experience + notable accomplishments
            3. Certifications: Industry-recognized credentials (0 if none)
            4. Projects: Complexity and relevance of completed projects (0 if none)


            Important:
            - Return ONLY the Python dictionary format shown above
            - Never omit categories - use 0 when no evidence exists
            - Score relative to industry standards for their experience level
            - No additional text or explanations"""
        
        result = execute_query_with_timeout(query, query_engine)
        
        if result is None:
            print("Query failed or timed out")
            return
        
        # print(result)
        print(type(result))
        
        result1 = str(result)
        print(type(result1))
        # print(result1)
        import re
        import json

        match = re.search(r'\{[^{}]*\}', result1, re.DOTALL)
        if match:
            result1 =  match.group(0).strip()
        else:
            print("No valid dictionary found in the input string.")
            # Optionally, you can raise an exception or handle this case as needed
        # return None
        # Parse the result as dictionary
        # print(result1)
        my_dict = eval(result1)
        sum_score = sum(my_dict.values())
        
        print(sum_score)
        print(my_dict)
        print(type(my_dict))
        
        # Update database
        from hiring_app.models import ResumeDetails
        from django.contrib.auth.models import User
        
        print(user_id)
        user_det = User.objects.get(id=user_id)
        # print(user_det)
        # print(user_det.username)
        detail = ResumeDetails.objects.get(user=user_det)
        print(detail)
        print("Skills ", type(my_dict["Tech Skills"]))
        
        detail.tech_skill_score = my_dict["Tech Skills"]
        detail.exp_achieve_score = my_dict["Experience&Achievements"]
        detail.cert_score = my_dict["Certifications"]
        detail.project_score = my_dict["Projects"]
        detail.score = sum_score / 2
        detail.save()
        
        print("get_score task completed")
        
    except Exception as e:
        print(f"Error in get_score task: {str(e)}")
        raise


@shared_task
def send_email(to_user):
    from django.core.mail import EmailMessage
    from Hiring_platform import settings
    
    email = EmailMessage(
        "Greeting on the resume evaluation",
        " This message is for shortlisting you for next round of interview .",
        settings.EMAIL_HOST_USER,
        [to_user],     
    )
    email.fail_silently = False
    email.send()
    print(" Email sent successfully ")

@shared_task
def generating_questions(file_path, user_id):
    print("generating_questions task started")
    
    try:
        # Create query engine
        query_engine = create_query_engine(file_path)
        
        query = "Based on the skills of the student that are also a required skill, generate 3 questions about that skills to test his knowledge. NOTE: Generate only the 3 questions and avoid any extra generations."
        
        # Execute query with timeout
        result = execute_query_with_timeout(query, query_engine)
        
        if result is None:
            print("Query failed or timed out")
            return
        
        print(result)
        print(type(result))
        
        result1 = str(result)
        print(type(result1))
        print(result1)
        
        # Update database
        from hiring_app.models import ResumeDetails
        from django.contrib.auth.models import User
        from screening.models import Question
        
        print(user_id)
        user_det = User.objects.get(id=user_id)
        print(user_det)
        print(user_det.username)
        detail = ResumeDetails.objects.get(user=user_det)
        print(detail)
        
        result2 = result1.strip("\n")
        questions = result2.split('\n')
        
        for i in questions:
            print(i)
            if i.strip():  # Check if question is not empty
                Question.objects.create(user=user_det, text=i, status="not_attended")
                print(i, "created successfully")
            else:
                print(i, "not created successfully")
                
        print("generating_questions task completed")
        
    except Exception as e:
        print(f"Error in generating_questions task: {str(e)}")
        raise

@shared_task
def send_mail_user(to_user):
    from django.core.mail import EmailMessage
    from Hiring_platform.settings import EMAIL_HOST_USER
    
    email = EmailMessage(
        "Greeting on the resume evaluation team",
        f"Hello {to_user} ,This message is for shortlisting you for next round of interview .",
        EMAIL_HOST_USER,
        [to_user],
    )
    email.fail_silently = False
    email.send()