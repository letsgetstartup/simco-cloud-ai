from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import google.generativeai as genai
import pandas as pd
import json
import os

initialize_app()

@https_fn.on_request(secrets=["GEMINI_API_KEY"])
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
        question = data.get('question')
        collection_name = data.get('collection', 'machines')
        
        # Priority: 1. Request Payload, 2. Environment Secret
        api_key = data.get('api_key') or os.environ.get('GEMINI_API_KEY')

        if not api_key or not question:
            return https_fn.Response(json.dumps({'error': 'Missing API Key. Please provide it in the sidebar or set GEMINI_API_KEY secret.'}), status=400, headers=headers)

        # 1. Fetch data from ALL collections (Unified View)
        collections_to_fetch = ['machines', 'jobs', 'events', 'tools', 'signals']
        unified_data = {}
        
        for col_name in collections_to_fetch:
            # Limit to 30 docs per collection to manage context size (Total ~150 rows)
            docs = db.collection(col_name).limit(30).stream()
            data_list = [doc.to_dict() for doc in docs]
            if data_list:
                df = pd.DataFrame(data_list)
                unified_data[col_name] = df.to_dict(orient="records")
            else:
                unified_data[col_name] = []

        # Convert unified data to JSON string for the prompt
        data_context = json.dumps(unified_data, indent=2)

        # 2. Call Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        prompt = f"""
        You are a Manufacturing Data Analyst for Simco.
        
        I have a Unified Shop Floor Dataset containing Machines, Jobs, Events, Tools, and Signals.
        Here is a sample of the aggregated data:
        {data_context}
        
        User Question: "{question}"
        
        Instructions:
        1. Analyze the unified data to answer the question.
        2. Perform calculations and cross-references (e.g., correlations between signals and tools).
        3. Format the text answer in Markdown with a professional, industry-standard structure:
           - Use clear Titles (##) and Sub-titles (###).
           - Use Emojis as icons for key sections (e.g., 📊 Analysis, 🔧 Methodology, 🚀 Recommendations, 💰 Cost Impact).
           - Use Bold (**text**) for key metrics and findings.
           - Use Bullet points for lists.
           - Explicitly show calculation steps in a "Methodology" section if applicable.
        4. ALWAYS generate a relevant data visualization (chart) configuration if the answer involves quantifiable data.
           - Choose the best chart type: 'bar' (comparisons), 'line' (trends), 'pie' (distribution), or 'doughnut'.
           - Focus purely on 'title', 'labels', and numeric 'data' in datasets.
           - DO NOT provide colors; the frontend high-contrast engine handles presentation.
        
        Return pure JSON with this structure:
        {{
            "answer": "Professional Markdown answer here...",
            "follow_up": ["Complex Question 1", "Complex Question 2", "Complex Question 3"],
            "visualization": {{
                "type": "bar", 
                "title": "Chart Title",
                "labels": ["Label1", "Label2"],
                "datasets": [
                    {{ "label": "Series Name", "data": [10, 20] }}
                ]
            }}
        }}
        """
        
        response = model.generate_content(prompt)
        
        # Parse the JSON response from Gemini
        try:
            # Clean up potential markdown code blocks if the model adds them
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
                
            response_json = json.loads(clean_text)
            return https_fn.Response(json.dumps(response_json), status=200, headers=headers)
        except json.JSONDecodeError:
            # Fallback if model fails to return JSON
            return https_fn.Response(json.dumps({
                "answer": response.text, 
                "follow_up": []
            }), status=200, headers=headers)

    except Exception as e:
        print(f"Error: {e}")
        return https_fn.Response(json.dumps({'error': str(e)}), status=500, headers=headers)
