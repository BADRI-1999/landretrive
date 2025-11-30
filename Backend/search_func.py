import os
import time
from typing import Any
from elasticsearch import Elasticsearch # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()

ES_URL = os.getenv("ES_URL")



def es_search_properties(
    district: str,
    mandal: str,
    village: str,
    survey_no: str,
    es: Elasticsearch,
) -> list[dict[str, Any]]:
    
    """
    Query Elasticsearch for exact survey_no and fuzzy-ish name matches.
    Tune this query as needed.
    """
    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"district_name": district}},
                    {"match": {"mandal_name": mandal}},
                    {"match": {"village_name": village}},
                    {"term": {"survey_no": survey_no}},
                ]
            }
        }
    }

    
    print("ES Query Body:", body)
    start = time.time()
    resp = es.search(index=os.getenv('telangan_index'), body=body, size=100)
    elapsed_ms = (time.time() - start) * 1000.0
    print(f"ES Response time: {elapsed_ms:.1f} ms")
    hits = resp.get("hits", {}).get("hits", [])
    return [hit["_source"] for hit in hits]




def surevey_search(district: str,    mandal: str,    village: str,    es: Elasticsearch,index:str ) -> list[dict[str, Any]]:
    """
    Query Elasticsearch for exact survey_no and fuzzy-ish name matches.
    Tune this query as needed.
    """
    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"district_name": district}},
                    {"match": {"mandal_name": mandal}},
                    {"match": {"village_name": village}}
                ]
            }
        }
    }

    start = time.time()
    resp = es.search(index=index, body=body, size=50)
    elapsed_ms = (time.time() - start) * 1000.0
    print(f"Survey ES Response time: {elapsed_ms:.1f} ms")
    hits = resp.get("hits", {}).get("hits", [])
    return [hit["_source"] for hit in hits]
