from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import google.generativeai as genai
import pandas as pd
import json
import os
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

initialize_app()

METRICS_SERVICE_URL = os.environ.get("METRICS_SERVICE_URL")

@https_fn.on_request(secrets=["GEMINI_API_KEY"], memory=512)
def ask(req):
    if not METRICS_SERVICE_URL:
        print("CRITICAL ERROR: METRICS_SERVICE_URL environment variable is not set.")
        return https_fn.Response(json.dumps({'error': 'INTERNAL_CONFIGURATION_ERROR', 'details': 'METRICS_SERVICE_URL is missing.'}), status=500, headers={'Access-Control-Allow-Origin': '*'})

    db = firestore.client()
    # CORS headers - Force Rebuild
    if req.method == 'OPTIONS':
        return https_fn.Response(status=204, headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        })

    headers = {
        'Access-Control-Allow-Origin': '*',
    }

    try:
        data = req.get_json()
        question_raw = data.get('question', '')
        question = question_raw.lower()
        
        # Use server-side secret exclusively
        api_key = os.environ.get('GEMINI_API_KEY')

        if not api_key:
             return https_fn.Response(json.dumps({'error': 'SERVER_CONFIG_ERROR', 'details': 'GEMINI_API_KEY secret is not configured on the server.'}), status=500, headers=headers)

        if not question_raw:
            return https_fn.Response(json.dumps({'error': 'MISSING_QUESTION', 'details': 'Please provide a question in the request body.'}), status=400, headers=headers)

        # 0. Deterministic Metric Routing
        query_type = data.get("query_type")
        time_range = data.get("time_range")
        
        # Identity Hardening: Extract tenant context from auth/headers, NEVER from client body
        # In a real setup, we would verify the JWT and extract claims.
        trusted_tenant_id = None
        auth_header = req.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Simulation: In production, use firebase_admin.auth.verify_id_token()
            trusted_tenant_id = req.headers.get("X-Tenant-ID") # Simplified for demo/emulator
        else:
            trusted_tenant_id = req.headers.get("X-Tenant-ID")

        if not trusted_tenant_id:
             return https_fn.Response(json.dumps({
                 'error': 'UNAUTHORIZED',
                 'details': 'Missing trusted tenant identity context.'
             }), status=401, headers=headers)

        if query_type:
            print(f"Deterministic Metric Request: {query_type} for Tenant: {trusted_tenant_id}")
            if not time_range:
                return https_fn.Response(json.dumps({
                    'error': 'MISSING_TIME_RANGE',
                    'details': 'time_range is mandatory for deterministic metrics.'
                }), status=400, headers=headers)

            try:
                # Call Cloud Run Metrics Service
                auth_req = Request()
                token = id_token.fetch_id_token(auth_req, METRICS_SERVICE_URL)

                metrics_req_payload = {
                    "query_type": query_type,
                    "tenant_id": trusted_tenant_id, # Use ONLY the trusted ID
                    "site_id": data.get("site_id", "test_site"),
                    "machine_id": data.get("machine_id"),
                    "time_range": time_range
                }

                response = requests.post(
                    f"{METRICS_SERVICE_URL}/execute",
                    json=metrics_req_payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Tenant-ID": trusted_tenant_id # Propagate identity for RLS enforcement
                    },
                    timeout=15
                )
                
                if response.status_code != 200:
                    print(f"Metrics Service Error: {response.status_code} - {response.text}")
                    return https_fn.Response(json.dumps({
                        'error': 'METRICS_SERVICE_ERROR',
                        'details': f'Calculation engine returned an error: {response.status_code}'
                    }), status=503, headers=headers)

                metrics_data = response.json()
                
                # 1. Use Gemini ONLY to explain the validated data (Explain-only pattern)
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash') 
                
                explain_prompt = f"""
                You are a Manufacturing Data Analyst for SolidCamAI.
                User Question: "{question_raw}"
                Data from BigQuery: {json.dumps(metrics_data.get('rows'), indent=2)}
                
                Instructions:
                1. Respond ONLY with a valid JSON object.
                2. Keys: "answer" (string), "extracted_numbers" (list of floats).
                3. "answer": Professional Markdown explanation. Do NOT invent numbers.
                4. "extracted_numbers": A list of every numeric value you mentioned in the "answer".
                """
                
                res = model.generate_content(explain_prompt).text
                
                # Extract JSON
                try:
                    start_idx = res.find('{')
                    end_idx = res.rfind('}')
                    structured_response = json.loads(res[start_idx:end_idx+1])
                except Exception as e:
                    print(f"LLM Response Parsing Error: {e}")
                    structured_response = {"answer": res.strip(), "extracted_numbers": []}

                # 2. Guardrail: Numeric Consistency Check
                answer_text = structured_response.get("answer", "")
                llm_numbers = structured_response.get("extracted_numbers", [])
                
                # Check if any LLM number is NOT in the raw data (simple set check)
                # We flatten the raw data values for comparison
                raw_values = []
                for row in metrics_data.get('rows', []):
                    raw_values.extend([v for v in row.values() if isinstance(v, (int, float))])
                
                hallucinated = [n for n in llm_numbers if n not in raw_values]
                
                final_answer = answer_text
                if hallucinated:
                    print(f"GUARDRAIL TRIGGERED: Hallucinated numbers detected: {hallucinated}")
                    # Strict Policy: Discard drifted narrative
                    final_answer = "An automated explanation was generated but discarded due to a detected numeric inconsistency. Please refer to the validated data and visualizations below."
                
                return https_fn.Response(json.dumps({
                    "answer": final_answer,
                    "visualization": data.get("visualization") or metrics_data.get("visualization"),
                    "audit": metrics_data.get("audit"),
                    "metric_version": metrics_data.get("metric_version"),
                    "confidence": metrics_data.get("confidence"),
                    "query_hash": metrics_data.get("audit", {}).get("query_hash"),
                    "citations": metrics_data.get("citations", []) + [{"type": "llm_explanation", "engine": "gemini-1.5-flash", "guarded": True}]
                }), status=200, headers=headers)

            except Exception as e:
                print(f"Metrics Failure: {e}")
                return https_fn.Response(json.dumps({'error': 'METRICS_SYSTEM_FAILURE', 'details': str(e)}), status=500, headers=headers)

        # 1. Fallback: Check for "leakage" of metric questions into conversational path
        bq_keywords = {"metric", "calculation"} # significantly relaxed to allow natural language questions
        clean_q = "".join(c for c in question if c.isalnum() or c.isspace())
        question_words = set(clean_q.split())
        
        # Logic Patch: Handle common machine_id shorthands for Bosch (M01 vs 01)
        # We proactively normalize this even if we don't return early
        question_raw = question_raw.replace("machine 0", "machine M0").replace("machine 1", "machine M01")

        if any(kw in question_words for kw in bq_keywords):
             return https_fn.Response(json.dumps({
                 "answer": "I've detected a request for raw metric calculation. To ensure accuracy, please select a specific metric from the dashboard.",
                 "suggestion": "For precise metric tracking, use the 'Settings' sidebar.",
                 "original_query": question_raw
             }), status=200, headers=headers)

        # 1. Fetch data from ALL collections (Unified View)
        collections_to_fetch = ['machines', 'jobs', 'tools']
        unified_data = {}
        
        # 1.1 Firestore Metadata
        for col_name in collections_to_fetch:
            docs = db.collection(col_name).limit(10).stream()
            data_list = [doc.to_dict() for doc in docs]
            unified_data[col_name] = data_list

        # 1.2 BigQuery Evidence (The source of truth for Bosch data)
        try:
            from google.cloud import bigquery
            bq_client = bigquery.Client(project="solidcam-f58bc")
            bq_query = f"""
                SELECT event_type, machine_id, start_ts, duration_seconds 
                FROM `solidcam-f58bc.simco_ai.events_fact` 
                WHERE tenant_id = '{trusted_tenant_id}'
                ORDER BY start_ts DESC LIMIT 20
            """
            bq_docs = bq_client.query(bq_query).result()
            unified_data["events"] = [dict(row) for row in bq_docs]
            # Convert datetime to string for JSON serialization
            for ev in unified_data["events"]:
                if 'start_ts' in ev and ev['start_ts']:
                    ev['start_ts'] = ev['start_ts'].isoformat()
        except Exception as bqe:
            print(f"BigQuery context fetch failed: {bqe}")
            unified_data["events"] = []

        data_context = json.dumps(unified_data, indent=2)

        # 2. Call Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        prompt = f"""
        You are a Manufacturing Data Analyst for Simco.
        
        I have a Unified Shop Floor Dataset containing Machines, Jobs, Events, Tools, and Signals.
        Here is a sample of the aggregated data:
        {data_context}
        
        User Question: "{question_raw}"
        
        Instructions:
        1. Analyze the unified data provided to answer the question.
        2. Perform calculations and cross-references.
        3. Format the text answer in Markdown with a professional structure.
        4. ALWAYS generate a relevant data visualization (chart) configuration if quantifiable data is involved.
        5. If there is NO DATA matching the query in the provided context, explain this in the "answer" text. Do NOT return an "error" key in the JSON.
        
        Return pure JSON with this structure:
        {{
            "answer": "Professional Markdown answer here...",
            "follow_up": ["Q1", "Q2", "Q3"],
            "visualization": {{
                "type": "bar", 
                "title": "Chart Title",
                "labels": ["L1", "L2"],
                "datasets": [{{ "label": "N1", "data": [10, 20] }}]
            }}
        }}
        """
        
        response = model.generate_content(prompt)
        
        # Parse the JSON response from Gemini
        try:
            clean_text = response.text.strip()
            if clean_text.startswith("```json"): clean_text = clean_text[7:]
            if clean_text.endswith("```"): clean_text = clean_text[:-3]
            response_json = json.loads(clean_text)
            return https_fn.Response(json.dumps(response_json), status=200, headers=headers)
        except:
            return https_fn.Response(json.dumps({"answer": response.text, "follow_up": []}), status=200, headers=headers)

    except Exception as e:
        print(f"Error: {e}")
        return https_fn.Response(json.dumps({'error': str(e)}), status=500, headers=headers)
