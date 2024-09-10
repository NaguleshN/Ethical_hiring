import os
import threading
from dotenv import load_dotenv
load_dotenv()

from llama_index.core import SimpleDirectoryReader
from llama_index.core import Settings

documents = SimpleDirectoryReader('uploads').load_data()
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
    def _init_(
        self,
        vector_retriever: VectorIndexRetriever,
        keyword_retriever: KeywordTableSimpleRetriever,
        mode: str = "AND") -> None:
       
        self._vector_retriever = vector_retriever
        self._keyword_retriever = keyword_retriever
        if mode not in ("AND", "OR"):
            raise ValueError("Invalid mode.")
        self._mode = mode
        super()._init_()

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
    



from llama_index.core import get_response_synthesizer
from llama_index.core.query_engine import RetrieverQueryEngine

vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=2)
keyword_retriever = KeywordTableSimpleRetriever(index=keyword_index)

# custom retriever => combine vector and keyword retriever

custom_retriever = CustomRetriever(vector_retriever, keyword_retriever)

response_synthesizer = get_response_synthesizer()

custom_query_engine = RetrieverQueryEngine(
    retriever=custom_retriever,
    response_synthesizer=response_synthesizer,
)



# query = "what does the data context contain?"
# print(custom_query_engine.query(query))

# while True:
#     query = input("Enter query: ")
#     if query == "exit":
#         print("Exiting...")
#         break
#     response = custom_query_engine.query(query)
#     print(response)


import threading
import time

def execute_query(query_engine, query, result_holder):
    result_holder[0] = query_engine.query(query)

while True:
    print(dir(VectorIndexRetriever))

    query = input("Enter query: ")
    
    if query == "exit":
        print("Exiting...")
        break

    result_holder = [None]

    query_thread = threading.Thread(target=execute_query, args=(custom_query_engine, query, result_holder))
    query_thread.start()

    query_thread.join(timeout=5)

    if query_thread.is_alive():
        print("Query timed out, returning null.")
        result = None
    else:
        result = result_holder[0]

    print(result)