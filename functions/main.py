from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import google.generativeai as genai
import pandas as pd
import json
import os

initialize_app()

@https_fn.on_request(secrets=["GEMINI_API_KEY"])
def ask_gemini(req):
    db = firestore.client()
    # CORS headers
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

        # 1. Fetch data from Firestore
        docs = db.collection(collection_name).limit(60).stream()
        data_list = [doc.to_dict() for doc in docs]
        
        if not data_list:
            return https_fn.Response(json.dumps({'answer': f"No data found in the '{collection_name}' collection. Please ensure you have uploaded your data."}), status=200, headers=headers)

        df = pd.DataFrame(data_list)
        data_context = df.to_json(orient="records")

        # 2. Call Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        prompt = f"""
        You are a Manufacturing Data Analyst for Simco.
        
        I have a dataset from the '{collection_name}' table. 
        Here is a sample of the data:
        {data_context}
        
        User Question: "{question}"
        
        Instructions:
        1. Analyze the data to provide a high-value answer for a machine shop manager.
        2. Focus on cost reduction, efficiency, outliers, and actionable insights.
        3. Format the 'answer' part in Markdown.
        4. Generate 3 complex, data-driven follow-up questions for the next investigation.
        
        IMPORTANT: Return the response as a valid JSON object with NO Markdown formatting (no ```json code blocks).
        Structure:
        {{
            "answer": "markdown string of the analysis",
            "follow_up": ["Question 1?", "Question 2?", "Question 3?"]
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
