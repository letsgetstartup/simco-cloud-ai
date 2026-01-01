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
        if not firebase_admin._apps:
            cred = None
            
            # 1. Try to find the secret in various common keys
            raw_data = None
            if "firebase" in st.secrets:
                raw_data = dict(st.secrets["firebase"])
            elif "FIREBASE_KEY" in st.secrets:
                try:
                    raw_data = json.loads(st.secrets["FIREBASE_KEY"])
                except:
                    st.error("FIREBASE_KEY found but it's not a valid JSON string.")
            
            # 2. Process and Clean the key
            if raw_data:
                # Ensure it's a dict
                key_dict = dict(raw_data)
                
                # The PEM error usually means the private_key string is malformed
                if "private_key" in key_dict:
                    pk = str(key_dict["private_key"])
                    
                    # Fix escaped newlines if they exist
                    pk = pk.replace("\\n", "\n")
                    
                    # CRISIS FIX: Some systems/users replace dashes with underscores or other chars
                    # The error "InvalidByte(4, 95)" means index 4 is an underscore (_)
                    # We will strictly normalize the header and footer
                    if "-----BEGIN PRIVATE KEY-----" not in pk:
                        # Strip all non-alphanumeric chars from the start until we find the base64 content
                        # But simpler: just force the standard header if it's missing or broken
                        content = pk.strip()
                        if "PRIVATE KEY" in content:
                            # Try to extract just the middle part if headers are broken
                            import re
                            match = re.search(r"KEY-*(.*?)---", content, re.DOTALL)
                            if match:
                                content = match.group(1).strip()
                            else:
                                # Remove anything that looks like a broken header
                                content = content.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip()
                                content = content.replace("_____BEGIN PRIVATE KEY_____", "").replace("_____END PRIVATE KEY_____", "").strip()
                        
                        pk = f"-----BEGIN PRIVATE KEY-----\n{content}\n-----END PRIVATE KEY-----\n"
                    
                    # Final sanity check: ensure no underscores in the actual header lines
                    lines = pk.splitlines()
                    if lines:
                        if "BEGIN" in lines[0]: lines[0] = "-----BEGIN PRIVATE KEY-----"
                        if "END" in lines[-1]: lines[-1] = "-----END PRIVATE KEY-----"
                    pk = "\n".join(lines)
                    
                    key_dict["private_key"] = pk
                    
                    # Safe diagnostic prefix
                    st.info(f"Diagnostic: Private key starts with `{pk[:10]}...`")
                
                try:
                    cred = credentials.Certificate(key_dict)
                except Exception as cert_err:
                    st.error(f"Credential Setup Error: {cert_err}")
                    st.info("💡 Tip: Ensure you used dashes `-` and not underscores `_` in your PEM headers.")

            # 3. Fallback to local if no secrets
            if not cred and os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")
            
            if cred:
                firebase_admin.initialize_app(cred)
            else:
                st.error("Authentication Error: No database credentials found.")
                st.info("Please Check: [share.streamlit.io] -> Settings -> Secrets.")
                return None
        
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
