from fastapi import FastAPI, HTTPException # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from elasticsearch import Elasticsearch # type: ignore
import redis # type: ignore
import os
import json
from datetime import datetime
from search_func import es_search_properties,surevey_search
from models import SearchResponse,SurveyResponse
from dotenv import load_dotenv # type: ignore


load_dotenv()



ES_URL = os.getenv("ES_URL")
print("ES_URL:", ES_URL)
es = Elasticsearch(ES_URL)
survey_index= os.getenv("survey_index")
telangana_index= os.getenv("telangan_index")
REDIS_URL = os.getenv("REDIS_URL")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  



redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True, 
)

app = FastAPI(title="Telangana Property Search API")

origins = [
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_cache_key(info : list[str]
) -> str:
    """Stable key for Redis caching."""
    return (
        f"prop:" + ":".join(info)
    )


@app.get("/health", tags=["system"])
def health_check():
    """Basic health endpoint."""
    es_ok = es.ping()
    try:
        redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if (es_ok and redis_ok) else "degraded",
        "elasticsearch": es_ok,
        "redis": redis_ok,
    }

def get_redis_client():
    return redis_client


@app.get("/properties/search", response_model=SearchResponse,tags=["properties"])
def search_properties(district: str ,mandal: str ,village: str ,survey_no: str):
   
    cache_key = build_cache_key([district, mandal, village, survey_no])

    # 2) Try Redis
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return SearchResponse(**data)

    # 3) Query Elasticsearch
    try:
        results = es_search_properties(district, mandal, village, survey_no,es)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ES query failed: {e!r}")
    
    print("Results:", results)
    if not results:
        raise HTTPException(
            status_code=404,
            detail="No properties found for given filters.",
        )

    # 4) Build response
    response_payload = {
        "count": len(results),
        "results": results,
    }

    # 5) Cache in Redis
    redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(response_payload))

    return SearchResponse(**response_payload)


@app.get("/surveys/search", response_model=SurveyResponse,tags=["surveys"])
def search_survey(district: str ,mandal: str ,village: str):

    cache_key = build_cache_key([district, mandal, village])


    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return SurveyResponse(**data)

    try:
        index = 'telangana_survey'
        results = surevey_search(district, mandal, village,index,es)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ES query failed: {e!r}")

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No surveys found for given filters.",
        )

    # 4) Build response
    response_payload = {
        "count": len(results),
        "results": results,
    }

    # 5) Cache in Redis
    redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(response_payload))

    return SurveyResponse(**response_payload)