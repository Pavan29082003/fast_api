from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient, Collection, connections, MilvusException
import time
import gc
from src.settings import settings
from src.core_search.publication_categories import publication_categories 
ip = settings.ip
client = MilvusClient(uri="http://" + ip + ":19530")
connections.connect(host=ip, port="19530")

vector_data_pmc = Collection(name="vector_data_pmc")
vector_data_biorxiv = Collection(name="vector_data_biorxiv")
vector_data_plos = Collection(name="vector_data_plos")

sbert_model = SentenceTransformer("all-MiniLM-L6-v2")

def search_milvus(collection, query_embedding):
    field_names = {
        "vector_data_pmc": [
            "pmid", "pmc", "abstract_content", "publication_date",
            "publication_type", "figures", "article_title"
        ],
        "vector_data_biorxiv": [
            "bioRxiv_id", "source", "abstract_content", "publication_date",
            "publication_type", "figures", "article_title"
        ],
        "vector_data_plos": [
            "plos_id", "source", "abstract_content", "publication_date",
            "publication_type", "figures", "article_title"
        ],
    }
    start_time = time.time()
    res = collection.search(
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        data=query_embedding,
        anns_field="vector_data",
        limit=100,
        output_fields=field_names[str(collection.name)],
    )
    end_time = time.time()
    print(f"Time for {collection.name} search:", end_time - start_time)
    return res


def hit_to_dict(hit):
    hit_dict = {"similarity_score": hit.score}
    field_names = [
        "pmid", "pmc", "biorxiv_id", "plos_id", "source",
        "body_content", "abstract_content", "publication_date",
        "publication_type", "figures", "article_title"
    ]

    for field_name in field_names:
        try:
            value = getattr(hit, field_name, None)
            if not isinstance(value, (str, int, list, dict)):
                hit_dict[field_name] = list(value)
            else:
                hit_dict[field_name] = value
        except MilvusException:
            continue
    if "pmid" in hit_dict.keys():
        hit_dict['source'] = "pubmed"
    return hit_dict

def apply_filters(articles, filters):
    filtered_articles = articles
    if filters.get('article_type'):
        article_type_filtered_articles = []
        if isinstance(filters.get('article_type'), str):
            article_type = [filters['article_type']]
        for article in articles:
            for publication_type in article.get("publication_type"):
                for filter in article_type:
                    print(filter)
                    if publication_type in publication_categories[filter] and article not in article_type_filtered_articles:
                        article_type_filtered_articles.append(article)                
                        break
        filtered_articles = article_type_filtered_articles            

    if filters.get('source') :
        source_filtered_articles  = []
        for article in filtered_articles:
            if article.get("source") == filters['source']:
                source_filtered_articles.append(article)    
        filtered_articles = source_filtered_articles
                
    if filters.get('date_filter'):
        current_date = datetime.now()
        if filters['date_filter'] == "10 years":
            from_date = current_date - timedelta(days=365 * 10)
            to_date = current_date
        elif filters['date_filter'] == "5 years":
            from_date = current_date - timedelta(days=365 * 5)
            to_date = current_date
        elif filters['date_filter'] == "1 year":
            from_date = current_date - timedelta(days=365)
            to_date = current_date
        else:
            from_date = datetime.strptime(filters['from_date'], "%d-%m-%Y")
            to_date = datetime.strptime(filters['to_date'], "%d-%m-%Y")
        date_filtered_articles = []
        for article in filtered_articles:
            if from_date and to_date:
                months = {
                'Jan': "01",
                'Feb': "02",
                'Mar': "03",
                'Apr': "04",
                'May': "05",
                'Jun': "06",
                'Jul': "07",
                'Aug': "08",
                'Sep': "09",
                'Oct': "10",
                'Nov': "11",
                'Dec': "12",
            }      
            pub_date = article.get('publication_date', None)
            pub_date = pub_date.split("-")
            pub_date = str(pub_date[0]) + "-" + str(months[pub_date[1]]) +"-"+ str(pub_date[2])

            pub_date = datetime.strptime(pub_date, "%d-%m-%Y")
            if (from_date <= pub_date <= to_date):
                date_filtered_articles.append(article)
        filtered_articles = date_filtered_articles

    return filtered_articles

def get_data(query_params):
    query_embedding = sbert_model.encode([query_params.get("term")])

    with ThreadPoolExecutor(max_workers=3) as executor:
        search_results = list(
            executor.map(
                lambda collection: search_milvus(collection, query_embedding),
                [vector_data_pmc, vector_data_biorxiv, vector_data_plos],
            )
        )

    res_pmc, res_biorxiv, res_plos = search_results
    relevant_articles = []

    for hits_pmc, hits_biorxiv, hits_plos in zip(res_pmc, res_biorxiv, res_plos):
        for hit_pmc, hit_biorxiv, hit_plos in zip(hits_pmc, hits_biorxiv, hits_plos):
            relevant_articles.extend(
                [hit_to_dict(hit_pmc), hit_to_dict(hit_biorxiv), hit_to_dict(hit_plos)]
            )

    articles = sorted(
        relevant_articles, key=lambda x: x["similarity_score"], reverse=True
    )

    for article in articles:
        article["similarity_score"] = ((article["similarity_score"] + 1) / 2) * 100
    articles = apply_filters(articles, query_params)
    return articles
