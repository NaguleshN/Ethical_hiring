import os
import threading
from dotenv import load_dotenv
load_dotenv()

from llama_index.core import SimpleDirectoryReader, Settings, StorageContext, SimpleKeywordTableIndex, VectorStoreIndex, QueryBundle, get_response_synthesizer
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import BaseRetriever, VectorIndexRetriever, KeywordTableSimpleRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from typing import List
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.gemini import Gemini

class CustomRetriever(BaseRetriever):
    def __init__(self, vector_retriever: VectorIndexRetriever, keyword_retriever: KeywordTableSimpleRetriever, mode: str = "AND") -> None:
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

        if self._mode == "AND":
            retrieve_ids = vector_ids.intersection(keyword_ids)
        else:
            retrieve_ids = vector_ids.union(keyword_ids)

        retrieve_nodes = [combined_dict[r_id] for r_id in retrieve_ids]
        return retrieve_nodes

def execute_query(query_engine, query, result_holder):
    result_holder[0] = query_engine.query(query)


def query_details_fetch(name):
    print(name)
    documents = SimpleDirectoryReader(f'/home/nagulesh/Documents/Projects/Ethical_hiring/Hiring_platform/uploads/{name}').load_data()
    print(documents)
    nodes = Settings.node_parser.get_nodes_from_documents(documents)
    Settings.embed_model = GeminiEmbedding(
    model_name="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY")
    )


    Settings.llm = Gemini(api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.7)

    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(nodes)

    vector_index = VectorStoreIndex(nodes, storage_context=storage_context)
    keyword_index = SimpleKeywordTableIndex(nodes, storage_context=storage_context)

    vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=2)
    keyword_retriever = KeywordTableSimpleRetriever(index=keyword_index)

    custom_retriever = CustomRetriever(vector_retriever, keyword_retriever)
    response_synthesizer = get_response_synthesizer()

    custom_query_engine = RetrieverQueryEngine(
        retriever=custom_retriever,
        response_synthesizer=response_synthesizer,
    )
    # query_set= ["What is name of the student in the data context" ,"what is name of the institution in the data context" ,"what is the city in the data"]

    # for i in query_set:
    i= "what is name of the student in the data context"
    if i == "exit":
        print("Exiting...")
        # break
    print(i)

    result_holder = [None]

    query_thread = threading.Thread(target=execute_query, args=(custom_query_engine, i, result_holder))
    query_thread.start()
    print(i)
    query_thread.join(timeout=5)
    print(i)
    if query_thread.is_alive():
        print("Query timed out, returning null.")
        result = None
    else:
        result = result_holder[0]

    print(result)

    return result

query_details_fetch("nagulesh03")

# while True:
#     # print(dir(VectorIndexRetriever))
#     query_set= ["What is the name of candidate in the data " ,"what is the name of the institution in the data " ,"what is the city in the data"]
#     for i in query_set:
#         # query = input("Enter query: ")
        
#         if i == "exit":
#             print("Exiting...")
#             break

#         result_holder = [None]

#         query_thread = threading.Thread(target=execute_query, args=(custom_query_engine, i, result_holder))
#         query_thread.start()

#         query_thread.join(timeout=5)

#         if query_thread.is_alive():
#             print("Query timed out, returning null.")
#             result = None
#         else:
#             result = result_holder[0]

#         print(result)