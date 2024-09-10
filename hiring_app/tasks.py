from celery import shared_task
from .models import *

@shared_task
def get_score(file_path):
        import os
        from dotenv import load_dotenv


        load_dotenv()

        from llama_index.core import SimpleDirectoryReader
        from llama_index.core import Settings

        # documents = SimpleDirectoryReader('/home/nagulesh/Documents/Projects/Ethical_hiring/Hiring_platform/uploads/nagulesh03').load_data()

        # file = FileResumePath.objects.get(user =request.user)
        # file_path = file.path

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

        query = "Compare the skills listed by Aravind with the provided Required Skills, also based on the score metrics for those skills, calculate the scores for Aravind skills in required and other metrics such as experience, projects. Give only the total scores for each category and provide a two line description indicating 'why the candidate is eligible for this job role' (based on their strengths) and dont generate anything other than that. NOTE: Scores must be calculated for every category that is mentioned in the provided criteria file in the context. Give score in a json format."
        
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
        print(result)
        print(type(result))
        result1=str(result)
        print(type(result1))