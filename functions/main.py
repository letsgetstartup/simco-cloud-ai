from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import google.generativeai as genai
import pandas as pd
import json
import os
import requests

initialize_app()

METRICS_SERVICE_URL = "https://metrics-service-362561211484.us-central1.run.app"

@https_fn.on_request(secrets=["GEMINI_API_KEY"], memory=512)
def ask(req):
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
        
        # Priority: 1. Request Payload, 2. Environment Secret
        api_key = data.get('api_key') or os.environ.get('GEMINI_API_KEY')

        if not api_key or not question_raw:
            return https_fn.Response(json.dumps({'error': 'Missing API Key. Please provide it in the sidebar or set GEMINI_API_KEY secret.'}), status=400, headers=headers)

        # 0. Intent Detection for BigQuery Metrics
        # Normalize question by removing punctuation for keyword matching
        clean_q = "".join(c for c in question if c.isalnum() or c.isspace())
        bq_keywords = {"reasons", "why", "stop", "stopped", "downtime", "metric", "calculation", "uptime", "distribution", "analysis", "compare", "most", "highest", "lowest", "trend", "hour", "which", "machine"}
        question_words = set(clean_q.split())
        
        if any(kw in question_words for kw in bq_keywords) or "by machine" in question or "per hour" in question:
            print(f"Bq Intent: {question}")
            try:
                # Call Cloud Run Metrics Service
                response = requests.post(
                    f"{METRICS_SERVICE_URL}/ask",
                    json={
                        "question": question_raw,
                        "tenant_id": data.get("tenant_id", "test_tenant"),
                        "site_id": data.get("site_id", "test_site"),
                        "machine_id": data.get("machine_id")
                    },
                    timeout=15
                )
                if response.status_code == 200:
                    metrics_data = response.json()
                    
                    # 1. Use Gemini ONLY to explain the data
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-pro')
                    
                    explain_prompt = f"""
                    You are a Manufacturing Data Analyst for SolidCamAI.
                    User Question: "{question_raw}"
                    Data: {json.dumps(metrics_data, indent=2)}
                    
                    Instructions:
                    1. Respond ONLY with a valid JSON object.
                    2. Keys: "answer" (string), "visualization" (object).
                    3. "answer": Professional Markdown explanation. ALWAYS end with: "This analysis was computed from Google BigQuery (Job ID: {metrics_data.get('source', {}).get('job_id')})."
                    4. "visualization": Chart.js config (type, labels, datasets).
                    """
                    
                    res = model.generate_content(explain_prompt).text
                    
                    # Robust JSON extraction: Find the first { and last }
                    try:
                        start_idx = res.find('{')
                        end_idx = res.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            json_str = res[start_idx:end_idx+1]
                            structured_response = json.loads(json_str)
                        else:
                            raise ValueError("No JSON found")
                    except Exception as e:
                        print(f"Gemini JSON Parse Error: {e}")
                        structured_response = {"answer": res, "visualization": None}

                    explanation = structured_response.get("answer", "")
                    viz_data = structured_response.get("visualization")
                    
                    # Programmatic Citation Enforcer
                    job_id = metrics_data.get('source', {}).get('job_id')
                    citation = f"This analysis was computed from Google BigQuery (Job ID: {job_id})."
                    if job_id and citation not in explanation:
                        explanation = explanation.strip() + f"\n\n{citation}"
                    
                    # FALLBACK: If visualization is missing or invalid, build it manually from rows
                    rows = metrics_data.get("rows", [])
                    if (not viz_data or not viz_data.get("labels")) and rows:
                        print("Building Fallback Visualization...")
                        keys = list(rows[0].keys())
                        # Priority keys for labels and values
                        label_key = next((k for k in keys if any(x in k.lower() for x in ['id', 'name', 'reason', 'bucket', 'machine'])), keys[0])
                        value_key = next((k for k in keys if any(x in k.lower() for x in ['duration', 'count', 'minutes', 'uptime', 'seconds', 'seconds'])), keys[-1])
                        
                        viz_data = {
                            "type": "bar",
                            "title": f"Comparison ({label_key.replace('_', ' ').title()})",
                            "labels": [str(r.get(label_key)) for r in rows],
                            "datasets": [{
                                "label": value_key.replace('_', ' ').title(),
                                "data": [round(float(r.get(value_key, 0)), 2) for r in rows]
                            }]
                        }

                    return https_fn.Response(json.dumps({
                        "answer": explanation,
                        "visualization": viz_data,
                        "source": metrics_data.get("source"),
                        "follow_up": [
                            "What machine has the most downtime?",
                            "Show me the hourly trend.",
                            "Why did M001 stop?"
                        ]
                    }), status=200, headers=headers)
            except Exception as e:
                print(f"Metrics service error: {e}")
                # Fallback to standard Gemini pipeline if metrics service fails

        # 1. Fetch data from ALL collections (Unified View)
        collections_to_fetch = ['machines', 'jobs', 'events', 'tools', 'signals']
        unified_data = {}
        
        for col_name in collections_to_fetch:
            docs = db.collection(col_name).limit(30).stream()
            data_list = [doc.to_dict() for doc in docs]
            if data_list:
                df = pd.DataFrame(data_list)
                unified_data[col_name] = df.to_dict(orient="records")
            else:
                unified_data[col_name] = []

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
        1. Analyze the unified data to answer the question.
        2. Perform calculations and cross-references.
        3. Format the text answer in Markdown with a professional structure.
        4. ALWAYS generate a relevant data visualization (chart) configuration if quantifiable data is involved.
        
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
