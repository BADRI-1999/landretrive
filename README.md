Here’s a README-style section you can drop straight into your repo.

---

##  Architecture & Data Flow

This project is a small end-to-end prototype of a **land record search engine** for Telangana, built with:

* **Python + FastAPI** – backend API
* **Elasticsearch** – search index for land/property data
* **Redis** – query caching
* **Angular** – frontend search UI
* **CSV + Python scripts** – offline data collection & synthetic data generation

###  Indexing into Elasticsearch



* Connects to ES:

  ```py
  es = Elasticsearch("http://localhost:9200")
  ```

* Creates index `telangana_properties` with a custom mapping:

  * `district_id`, `mandal_id`, `village_id`, `survey_no`, `khata_id` as `keyword`
  * `district_name_en`, `mandal_name_en`, `village_name_en`, pattadar names as `text` + `keyword` subfields
  * `total_extent_ac_gts` as `float`
  * `market_value_inr` as `long`
  * `created_at` as `date`

* **Bulk indexing** is done in chunks for large datasets (e.g., 10k rows per batch) via `elasticsearch.helpers.bulk`.

* Each document gets a deterministic `_id`:

  ```py
  # for properties:
  doc_id = f"{district_id}_{mandal_id}_{village_id}_{survey_no}_{khata_id}"
  ```

  So the same physical land parcel always overwrites/updates the same ES document.

* Missing values (e.g., no khata) are normalized to `None` before indexing to avoid `NaN` parse errors.

###  Backend API (FastAPI + Redis + ES)

Main service: `main.py` (FastAPI app)

#### Endpoint

```http
GET /properties/search?district=...&mandal=...&village=...&survey_no=...
```

**Flow:**

1. **Build cache key** from query parameters:

   ```py
   cache_key = f"property:{district}|{mandal}|{village}|{survey_no}"
   ```

2. **Redis lookup**:

   * If present, parse the cached JSON and return:

     ```json
     {
       "count": 1,
       "results": [ { ...property fields... } ]
     }
     ```

3. If not cached, **query Elasticsearch**:

   ```py
   body = {
     "query": {
       "bool": {
         "must": [
           {"match": {"district_name": district}},
           {"match": {"mandal_name": mandal}},
           {"match": {"village_name": village}},
           {"term":  {"survey_no": survey_no}}
         ]
       }
     }
   }

   resp = es.search(index="telangana_properties", body=body, size=100)
   hits = [h["_source"] for h in resp["hits"]["hits"]]
   ```

4. **Normalize fields** (e.g., map `pattadar_name_en` → `pattadar_name`) into a `Property` Pydantic model.

5. Wrap result into `SearchResponse`:

   ```py
   class SearchResponse(BaseModel):
       count: int
       results: list[Property]
   ```

6. Cache the response in Redis with TTL (e.g., 5 minutes) and return to the client.

This gives:

* Low latency queries
* ES only hit on cache misses
* A stable, typed API for the frontend

###  Frontend (Angular 16+ Standalone Components)

Component: `PropertySearchComponent` (standalone)

* Binds inputs using `[(ngModel)]` to:

  * `district_name`
  * `mandal_name`
  * `village_name`
  * `survey_no`

* On **Search**:

  ```ts
  this.propertyService.searchByNames(
    this.district_name.trim(),
    this.mandal_name.trim(),
    this.village_name.trim(),
    this.survey_no.trim(),
  ).subscribe(...)
  ```

* `PropertySearchService` sends:

  ```ts
  GET http://localhost:8000/properties/search?district=...&mandal=...&village=...&survey_no=...
  ```

* The component displays the properties in a card layout:

  * Location chips: district / mandal / village
  * Survey & Khata
  * Pattadar & Father/Husband name
  * Extent & Land type
  * Market value (₹ formatted)
  * PPB + eKYC status
  * Status badge for Signed / Not Signed

---

## 🚀 How I’d Scale This as Part of the Team

Right now this is a **single-node local prototype**.

### 1. Data Pipeline & Freshness

**Today:**

* CSV + scripts + manual runs

**Next steps:**

1. **Ingestion service**:

   * Async workers (Celery / RQ / Kafka consumers) that:

     * Fetch land records from state portals (where legally allowed)
     * Respect rate limits & captchas (probably via official bulk APIs / RTI / data partnerships instead of scraping at scale)
     * Persist **raw HTML/JSON** to object storage (GCS/S3) for replay

2. **Normalization layer**:

   * A `land_records` schema in Postgres/BigQuery:

     * `states`, `districts`, `mandals`, `villages`, `parcels`, `owners`, `transactions`
   * Idempotent upserts keyed by government IDs (districtId, mandalId, villageId, surveyNo, khataNo)

3. **Incremental updates**:

   * Instead of reindexing 20M rows, track:

     * “changed parcels” from incremental crawls or official diffs
     * Reindex only changed docs into ES

4. **Data quality & auditing**:

   * Validity checks: missing IDs, invalid extents, weird market values
   * Versioning: keep “as of date” snapshots for legal traceability

### 2. Elasticsearch at Scale

**Today:**

* Single-node ES
* One index per dataset (`telangana_properties`, `telangana_surveys`)

**Scaling plan:**

1. **Clusterization**:

   * At least **3-node ES cluster**:

     * 1 master, 2 data nodes (to start)
     * Use dedicated master nodes as cluster grows

2. **Sharding strategy**:

   * Shard on **state** or **district**:

     * Example index pattern: `land-parcels-v1-{state}`
     * Each index: `5` primary shards, `1` replica (tune based on data volume)
   * Future: use index lifecycle management (ILM) for old inactive records

3. **Search tuning**:

   * Use:

     * `keyword` for exact IDs and codes
     * `search_as_you_type` or n-gram analyzers for:

       * village/mandal names
       * owner names
   * Pre-compute normalized fields:

     * lowercased, ASCII-folded fields for robust search

4. **ES as a **projection**, not the source of truth**:

   * Canonical data lives in Postgres/BigQuery
   * ES is rebuilt/reindexed if needed

### 3. API & Backend Scaling

**Today:**

* Single FastAPI instance on localhost

**Scaling plan:**

1. **Containerization & orchestration**:

   * Package FastAPI + ES client + Redis client into a Docker image
   * Deploy on Kubernetes / ECS / Cloud Run:

     * Horizontal Pod Autoscaler driven by CPU/QPS
     * Liveness/readiness probes
     * Rolling updates, blue/green for schema changes

2. **Stateless API**:

   * No state in app memory; all in ES, Redis, DB
   * Makes horizontal scaling trivial

3. **Rate limiting & abuse protection**:

   * API gateway (Kong/Envoy/NGINX) in front
   * Request quotas per API key / IP
   * Backoff on ES timeouts / errors

4. **Versioned APIs**:

   * `/v1/properties/search` → stable
   * Future `/v2` can support multi-query, filters, sorting, etc.

### 4. Caching & Performance

**Today:**

* Redis-based per-query caching at the API level

**Scaling plan:**

1. **Redis cluster**:

   * Move to Redis cluster / managed Redis (e.g., ElastiCache / Memorystore)
   * Partition keys by state or hashed key

2. **Multi-layer caching**:

   * Edge cache / CDN for GET responses
   * Hot queries pre-warmed:

     * Most searched districts / villages / survey ranges

3. **Query optimization**:

   * Pre-aggregate some stats (min/max market value per survey, etc.)
   * Store them as separate “summary” docs in ES for fast dashboards

### 5. Observability & Reliability

1. **Metrics**:

   * API:

     * `p95`, `p99` latency for `/properties/search`
     * error rate (5xx)
   * ES:

     * query latency
     * queue size, heap usage
   * Redis:

     * hit/miss ratio, memory usage

2. **Tracing**:

   * OpenTelemetry to trace a request:

     * Angular → FastAPI → Redis → ES → FastAPI → Angular

3. **Logging**:

   * Structured logs with:

     * request_id, query parameters, ES took(ms), cache hit/miss
   * Centralized log aggregation (ELK / Loki)

4. **SLOs**:

   * Example:

     * 99% of property search requests < 500 ms
     * 99.9% availability for search API

### 6. Security & PII Handling

Given land records can involve sensitive ownership information:

1. **PII minimization**:

   * Store only fields needed for search/product
   * Consider hashing or tokenizing names if business allows
   * Encrypt sensitive columns at rest (KMS / TDE)

2. **Access control**:

   * API keys / OAuth for B2B usage
   * Role-based access: public vs partner-level detail

3. **Audit trail**:

   * Who searched what, when, from where
   * Required for compliance & abuse detection

### 7. Product Evolution

Once the core “search by district/mandal/village/survey” is stable, I’d expand:

* Fuzzy search by **owner name** + geography
* Timeline of **transactions** for a parcel (via EC data)
* Confidence scoring / data quality indicators per record
* Multi-state support with uniform schema (Telangana, AP, Karnataka, etc.)
* RAG-style “Explain this land record” chatbot for end-users (with strict grounding on ES results)

---

