import streamlit as st
import pandas as pd
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Simco Cloud AI", page_icon="☁️", layout="wide")

# --- AUTHENTICATION HANDLER ---
# This ensures the app works both Locally (using file) and Online (using Secrets)
def get_db():
    try:
        # Check if app is already initialized
        if not firebase_admin._apps:
            if "firebase" in st.secrets:
                key_dict = dict(st.secrets["firebase"])
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(key_dict)
            elif os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")
            else:
                available_keys = list(st.secrets.keys())
                st.error(f"Authentication Error: No 'firebase' secret found. Available keys in Streamlit Secrets: {available_keys}")
                st.info("Ensure you have a [firebase] section in your Secrets.")
                return None
            firebase_admin.initialize_app(cred)
        
        return firestore.client()
    except Exception as e:
        st.error(f"Failed to connect to Database: {e}")
        return None

# --- AI LOGIC ---
def ask_gemini(api_key, dataframe, question, collection_name):
    """
    Sends a sample of the data + the user question to Gemini.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # We convert the dataframe to a string representation (JSON)
    # We limit to 50 rows to prevent token overflow, assuming the user asks about recent trends
    # or general aggregation.
    data_context = dataframe.head(60).to_json(orient="records")
    
    prompt = f"""
    You are a Manufacturing Data Analyst.
    
    I have a dataset from the '{collection_name}' table. 
    Here is a sample of the data in JSON format:
    {data_context}
    
    User Question: "{question}"
    
    Instructions:
    1. Analyze the data provided to answer the question.
    2. If the answer requires calculation (like sums or averages), perform them on the data provided.
    3. If the data provided is insufficient (e.g., asking for a record not in the top 60), explain that you are looking at a sample.
    4. Format the output nicely using Markdown.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error from Gemini: {e}"

# --- MAIN UI ---
def main():
    st.title("🏭 Simco Cloud Intelligence")
    st.markdown("### Ask questions about your manufacturing data stored in the Cloud.")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("Gemini API Key", type="password")
        st.info("Get your key from [Google AI Studio](https://aistudio.google.com/)")
        st.divider()
        st.markdown("**Status:**")
        
        # Connect to DB
        db = get_db()
        if db:
            st.success("Connected to Firebase Cloud 🟢")
        else:
            st.stop()

    # Main Area
    if api_key:
        # 1. Collection Selector
        collection_option = st.selectbox(
            "Which dataset do you want to analyze?",
            ["machines", "jobs", "events", "tools", "signals"]
        )
        
        # 2. Fetch Data from Cloud
        # We use st.cache_data to prevent re-fetching from Firebase on every interaction
        @st.cache_data(ttl=600)
        def load_data(col_name):
            try:
                docs = db.collection(col_name).stream()
                data = [doc.to_dict() for doc in docs]
                return pd.DataFrame(data)
            except Exception as e:
                st.error(f"Error loading data: {e}")
                return pd.DataFrame()

        with st.spinner(f"Loading '{collection_option}' data from cloud..."):
            df = load_data(collection_option)
        
        if df.empty:
            st.warning(f"No data found in '{collection_option}'. Did you run the upload script?")
        else:
            # Show Preview
            with st.expander(f"View Data Preview ({len(df)} records total)"):
                st.dataframe(df)

            # 3. Chat Interface
            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Display history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Input
            if prompt := st.chat_input(f"Ask about {collection_option}..."):
                # Add user message
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Generate Answer
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing data..."):
                        response_text = ask_gemini(api_key, df, prompt, collection_option)
                        st.markdown(response_text)
                        
                        # Add assistant message
                        st.session_state.messages.append({"role": "assistant", "content": response_text})

    else:
        st.warning("👈 Please enter your Gemini API Key in the sidebar to start.")

if __name__ == "__main__":
    main()
