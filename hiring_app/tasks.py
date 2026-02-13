from celery import shared_task
from .models import *
import time
import random

def setup_llama_index():
    """Initialize LlamaIndex components with local embeddings"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Disable MPS on macOS to prevent SIGABRT crashes with Celery multiprocessing
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    from llama_index.core import Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.llms.gemini import Gemini
    
    # Use local Hugging Face embeddings (FREE - no API quota!)
    # Explicitly set device to 'cpu' to avoid MPS issues on macOS
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        device="cpu"  # Force CPU to avoid MPS/CUDA issues with Celery
    )
    
    # Still use Gemini for LLM (text generation only)
    # Use gemini-2.5-flash (latest working model)
    Settings.llm = Gemini(
        api_key=os.getenv("GOOGLE_API_KEY"), 
        model="gemini-2.5-flash",  # Latest model with good quota availability
        temperature=0.7
    )
    
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

def execute_query_with_timeout(query, query_engine, timeout=30, max_retries=3):
    """Execute query with timeout and retry logic for rate limiting"""
    import threading
    
    def execute_query(query, result_holder, query_engine):
        try:
            result_holder[0] = query_engine.query(query)
        except Exception as e:
            error_message = str(e)
            print(f"Error in query execution: {error_message}")
            result_holder[0] = None
            result_holder[1] = error_message  # Store error message
    
    for attempt in range(max_retries):
        result_holder = [None, None]  # [result, error_message]
        query_thread = threading.Thread(target=execute_query, args=(query, result_holder, query_engine))
        query_thread.start()
        query_thread.join(timeout=timeout)
        
        if query_thread.is_alive():
            print(f"⚠️ Query timed out after {timeout} seconds on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            continue
        
        # Check if we got a result or an error
        if result_holder[0] is not None:
            return result_holder[0]
        
        # Check if it's a rate limit error
        error_message = result_holder[1] or ""
        if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
            if attempt < max_retries - 1:
                # Extract retry delay from error message or use exponential backoff
                wait_time = 60  # Default wait time for rate limiting
                if "retry in" in error_message.lower():
                    import re
                    match = re.search(r'retry in (\d+(?:\.\d+)?)', error_message.lower())
                    if match:
                        wait_time = float(match.group(1))
                
                # Add some jitter
                wait_time += random.uniform(0, 5)
                print(f"⚠️ Rate limit hit. Waiting {wait_time:.2f} seconds before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)
            else:
                print(f"⚠️ Rate limit exceeded after {max_retries} attempts")
                return None
        elif result_holder[1]:  # Other errors
            print(f"Query failed with error: {result_holder[1]}")
            return None
        else:
            return result_holder[0]
    
    print(f"⚠️ Query failed after {max_retries} attempts")
    return None

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60}, retry_backoff=True, retry_jitter=True)
def get_score(self, file_path, user_id):
    print(file_path, user_id)
    print(f"get_score task started (attempt {self.request.retries + 1})")
    
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
    except Exception as e:
        error_message = str(e)
        print(f"Error creating query engine or executing query: {error_message}")
        
        # Check if it's a quota exceeded error
        if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
            print("⚠️ Google Gemini API quota exceeded. Please check your API limits or wait for quota reset.")
            print("Visit: https://ai.dev/usage?tab=rate-limit")
            
            # Set default scores as fallback - update the latest record
            from hiring_app.models import ResumeDetails
            from django.contrib.auth.models import User
            
            user_det = User.objects.get(id=user_id)
            
            # Get the latest ResumeDetails record and update it with pending status
            try:
                detail = ResumeDetails.objects.filter(user=user_det).latest('id')
                detail.score = 0
                detail.tech_skill_score = 0
                detail.exp_achieve_score = 0
                detail.cert_score = 0
                detail.project_score = 0
                detail.status = 'pending'
                detail.save()
                print(f"✅ Set default scores for existing ResumeDetails (ID: {detail.id}) - Manual review needed")
            except ResumeDetails.DoesNotExist:
                # Don't create a new record if it doesn't exist - ResumeDetails should be created
                # in the success view first. Just log a warning.
                print(f"⚠️ Warning: No ResumeDetails record found for user {user_det.username}")
                print(f"⚠️ Skipping score update - ResumeDetails should be created in success view first")
                print(f"⚠️ This usually means the user hasn't uploaded a resume yet")
            
            return
        else:
            raise
    
    try:
        
        # print(result)
        print(type(result))
        
        result1 = str(result)
        print(type(result1))
        # print(result1)
        import re
        import json
        import ast

        # Improved regex to match nested dictionaries (handles curly braces inside)
        # This pattern matches the outermost dictionary including nested structures
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result1, re.DOTALL)
        if match:
            result1 = match.group(0).strip()
        else:
            # Try to find dictionary-like structure with more flexible pattern
            match = re.search(r'\{.*\}', result1, re.DOTALL)
            if match:
                result1 = match.group(0).strip()
            else:
                print("❌ No valid dictionary found in the input string.")
                print(f"Result string: {result1[:500]}")  # Print first 500 chars for debugging
                raise ValueError("No valid dictionary format found in query result")
        
        # Clean up the string (remove markdown code blocks if present)
        result1 = result1.replace("```json", "").replace("```python", "").replace("```", "").strip()
        
        # Try to parse as JSON first (safer)
        try:
            my_dict = json.loads(result1)
        except json.JSONDecodeError:
            # If JSON fails, try ast.literal_eval (safer than eval)
            try:
                my_dict = ast.literal_eval(result1)
            except (ValueError, SyntaxError) as e:
                print(f"❌ Failed to parse result as dictionary: {e}")
                print(f"Result string: {result1[:500]}")
                raise ValueError(f"Failed to parse dictionary from result: {e}")
        
        # Validate that we have a dictionary with required keys
        required_keys = ["Tech Skills", "Experience&Achievements", "Certifications", "Projects"]
        if not isinstance(my_dict, dict):
            raise ValueError(f"Parsed result is not a dictionary: {type(my_dict)}")
        
        missing_keys = [key for key in required_keys if key not in my_dict]
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {missing_keys}")
        
        # Validate that values are numeric
        for key in required_keys:
            value = my_dict[key]
            if not isinstance(value, (int, float)):
                try:
                    my_dict[key] = float(value)
                except (ValueError, TypeError):
                    print(f"⚠️ Warning: {key} value '{value}' is not numeric, setting to 0")
                    my_dict[key] = 0
        
        sum_score = sum(my_dict.values())
        
        print(f"✅ Parsed scores: {my_dict}")
        print(f"✅ Sum score: {sum_score}")
        
        # Update database
        from hiring_app.models import ResumeDetails
        from django.contrib.auth.models import User
        
        print(user_id)
        user_det = User.objects.get(id=user_id)
        
        # Get the latest ResumeDetails record for this user and update it
        # Since user field is not unique, multiple records can exist - get the most recent one
        try:
            detail = ResumeDetails.objects.filter(user=user_det).latest('id')
            detail.tech_skill_score = my_dict["Tech Skills"]
            detail.exp_achieve_score = my_dict["Experience&Achievements"]
            detail.cert_score = my_dict["Certifications"]
            detail.project_score = my_dict["Projects"]
            detail.score = sum_score / 2
            detail.save()
            print(f"✅ Updated existing ResumeDetails (ID: {detail.id}) for user {user_det.username}")
        except ResumeDetails.DoesNotExist:
            # Don't create a new record if it doesn't exist - ResumeDetails should be created
            # in the success view first. Just log a warning.
            print(f"⚠️ Warning: No ResumeDetails record found for user {user_det.username}")
            print(f"⚠️ Skipping score update - ResumeDetails should be created in success view first")
            print(f"⚠️ This usually means the user hasn't uploaded a resume yet")
            return
        
        print(detail)
        print("Skills ", type(my_dict["Tech Skills"]))
        print(f"Scores saved - Tech: {detail.tech_skill_score}, Experience: {detail.exp_achieve_score}, Cert: {detail.cert_score}, Projects: {detail.project_score}, Total: {detail.score}")
        
        print("get_score task completed")
        
    except Exception as e:
        print(f"❌ Error in get_score task: {str(e)}")
        import traceback
        print(traceback.format_exc())
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

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60}, retry_backoff=True, retry_jitter=True)
def generating_questions(self, file_path, user_id):
    print(f"generating_questions task started (attempt {self.request.retries + 1})")
    
    try:
        # Create query engine
        query_engine = create_query_engine(file_path)
        
        query = "Based on the skills of the student that are also a required skill, generate 3 questions about that skills to test his knowledge. NOTE: Generate only the 3 questions and avoid any extra generations."
        
        # Execute query with timeout
        result = execute_query_with_timeout(query, query_engine)
        
        if result is None:
            print("Query failed or timed out")
            return
    except Exception as e:
        error_message = str(e)
        print(f"Error in generating_questions task: {error_message}")
        
        # Check if it's a quota exceeded error
        if "429" in error_message or "quota" in error_message.lower() or "ResourceExhausted" in error_message:
            print("⚠️ Google Gemini API quota exceeded for question generation.")
            print("Visit: https://ai.dev/usage?tab=rate-limit")
            
            # Create default questions as fallback
            from hiring_app.models import ResumeDetails
            from django.contrib.auth.models import User
            from screening.models import Question
            
            user_det = User.objects.get(id=user_id)
            
            # Check if questions already exist
            existing_questions = Question.objects.filter(user=user_det, status="not_attended").count()
            if existing_questions == 0:
                # Create generic placeholder questions
                default_questions = [
                    "1. Please describe your experience with the technologies mentioned in your resume.",
                    "2. Can you walk us through one of your most challenging projects?",
                    "3. How do you stay updated with the latest trends in your field?"
                ]
                
                for question_text in default_questions:
                    Question.objects.create(user=user_det, text=question_text, status="not_attended")
                    print(f"Created default question: {question_text}")
                
                print(f"Created default questions for user {user_det.username} - Manual review recommended")
            return
        else:
            raise
    
    try:
        
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

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60}, retry_backoff=True, retry_jitter=True)
def send_mail_user(self, to_user):
    """
    Send email notification to user about interview shortlisting.
    
    Args:
        to_user: Email address of the recipient
    """
    import os
    from django.core.mail import EmailMessage
    from django.core.mail import get_connection
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    from Hiring_platform.settings import EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
    
    print(f"📧 send_mail_user task started (attempt {self.request.retries + 1})")
    print(f"📧 Recipient: {to_user}")
    
    try:
        # Validate email configuration
        if not EMAIL_HOST_USER:
            error_msg = "❌ EMAIL_HOST_USER is not configured in environment variables"
            print(error_msg)
            raise ValueError(error_msg)
        
        if not EMAIL_HOST_PASSWORD:
            error_msg = "❌ EMAIL_HOST_PASSWORD is not configured in environment variables"
            print(error_msg)
            raise ValueError(error_msg)
        
        # Validate recipient email address
        if not to_user:
            error_msg = "❌ Recipient email address is empty"
            print(error_msg)
            raise ValueError(error_msg)
        
        try:
            validate_email(to_user)
        except ValidationError:
            error_msg = f"❌ Invalid email address format: {to_user}"
            print(error_msg)
            raise ValueError(error_msg)
        
        # Create email message
        subject = "Greeting on the resume evaluation team"
        message = f"""
        Dear Candidate,

        We are pleased to inform you that you have been shortlisted for the next round of the interview process based on your profile and performance in the previous stage.

        Congratulations on reaching this stage! 🎉
        Your skills, experience, and qualifications have been found to be a strong match for the role, and we would like to proceed further with your candidature.

        The details regarding the next round, including the interview format, date, time, and platform/venue, will be shared with you shortly.

        If you have any questions in the meantime, please feel free to reach out to us.

        We wish you the very best for the upcoming round and look forward to interacting with you soon."""

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=EMAIL_HOST_USER,
            to=[to_user],  # Ensure it's a list
        )
        
        # Test connection before sending
        try:
            connection = get_connection(
                host=os.environ.get('EMAIL_HOST', 'smtp.gmail.com'),
                port=int(os.environ.get('EMAIL_PORT', 587)),
                username=EMAIL_HOST_USER,
                password=EMAIL_HOST_PASSWORD,
                use_tls=os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true',
            )
            connection.open()
            connection.close()
            print("✅ Email connection test successful")
        except Exception as conn_error:
            error_msg = f"❌ Email connection failed: {str(conn_error)}"
            print(error_msg)
            raise ConnectionError(error_msg) from conn_error
        
        # Send email
        email.fail_silently = False
        result = email.send()
        
        if result == 1:
            print(f"✅ Email sent successfully to {to_user}")
            return {"status": "success", "recipient": to_user}
        else:
            error_msg = f"❌ Email sending returned unexpected result: {result}"
            print(error_msg)
            raise Exception(error_msg)
            
    except ValueError as e:
        # Configuration or validation errors - don't retry
        error_msg = f"❌ Email configuration error: {str(e)}"
        print(error_msg)
        print("💡 Please check your .env file and ensure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set")
        raise
    except ConnectionError as e:
        # Connection errors - will retry
        error_msg = f"❌ Email connection error: {str(e)}"
        print(error_msg)
        print("💡 Please check your email server settings and network connection")
        raise
    except Exception as e:
        # Other errors - will retry
        error_msg = f"❌ Error sending email to {to_user}: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        raise