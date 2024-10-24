import json
from pymilvus import MilvusClient, Collection, connections, MilvusException
import time
import gc
from src.settings import settings
from src.core_search.publication_categories import publication_categories 
import google.generativeai as genai
import uuid
from src.database.connections import connections

vector_data_pmc = Collection(name="vector_data_pmc")
vector_data_biorxiv = Collection(name="vector_data_biorxiv")
vector_data_plos = Collection(name="vector_data_plos")

collections  = {
        "pubmed" : "vector_data_pmc",
        "biorxiv" : "vector_data_biorxiv",
        "plos": "vector_data_plos"
    }

def create_session():
    return str(uuid.uuid4())

def answer_query(question,id,session_id,source,history):
    context = ''
    if len(history) == 0:
        article = connections.milvus_client.get(
        collection_name=collections[source],
        ids=[id]
        )  
        context = json.dumps(article[0]['body_content'])  + json.dumps(article[0]['abstract_content'])
    prompt = context +"\n\n" +  question
    generation_config = {
        "temperature": 0.5,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
        }
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction="Think yourself as an research assistant.You will receieve data related to life sciences.Analyze it and answer only if a valid question is asked after that",
        safety_settings="BLOCK_NONE",
    )
    chat_session = model.start_chat(
        history=history
    )

    response = chat_session.send_message(prompt,stream=True)
    for chunk in response:
        temp = {
            "session_id" : session_id,
            "answer" : chunk.text
        }
        temp = json.dumps(temp)
        yield temp.encode("utf-8")
    history = []
    for i in chat_session.history:
          temp = {}
          temp["role"] = i.role
          temp["parts"] = [part.text for part in i.parts]
          history.append(temp)
    yield history
    
async def get_article(id,source):
    article = connections.milvus_client.get(
    collection_name=collections[source],
    ids=[id]
    )  
    article = article[0]
    article.pop('vector_data')
    return article