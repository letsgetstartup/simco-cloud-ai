# SolidCamAI: Comprehensive R&D Documentation

SolidCamAI is an advanced manufacturing intelligence platform that leverages Large Language Models (LLMs) to provide real-time insights, anomaly detection, and cross-functional data analysis for shop floor operations.

---

## 1. Product Overview & User Flow

### High-Level Purpose
To bridge the gap between complex raw manufacturing data (Machines, Jobs, Tools, Signals) and actionable human-level insights using natural language processing.

### User Journey
1.  **Entry & Authentication**: Users access the dashboard (PWA-enabled) and authenticate via Firebase.
2.  **Context Selection**: Users select a "Focus Area" (e.g., Machine Health, Profitability) which tailors the live alerts and administrative insights.
3.  **Inquiry**: Users interact with the "Insight Engine" by asking natural language questions.
4.  **Deep Reasoning**: The system displays a transparent "Advanced Reasoning Engine" process, showing the steps taken to analyze the data.
5.  **Synthesis & Visualization**: The AI provides a formatted Markdown response, often accompanied by a dynamic chart (Bar, Line, etc.) for data visualization.
6.  **Follow-up**: Suggested follow-up questions are provided to guide the user into deeper analysis.

---

## 2. Core Features

### 📊 Unified Insight Engine
Unlike traditional siloes, SolidCamAI cross-references data across five major domains:
*   **Machines**: Status, utilization, and model info.
*   **Jobs**: Cycle times, job IDs, and production runs.
*   **Events**: Alarms, severity logs, and downtime reasons.
*   **Tools**: Tool life, breakage history, and inventory status.
*   **Signals**: High-frequency sensor data (Spindle load, Temperature, Vibration).

### 🧠 Advanced Reasoning Engine
A hierarchical logic simulator that visualizes the AI's internal "thought process":
1.  **Data Ingestion**: Syncing real-time streams.
2.  **Correlation**: Linking signal spikes to job variances.
3.  **Pattern Matching**: Detecting anomalies against baselines.
4.  **Financial Modeling**: Calculating cost impacts.
5.  **Synthesis**: Finalizing engineering recommendations.

### 📈 Dynamic Visualization
Automated chart generation using Chart.js based on data extracted by the LLM. The system handles color palettes (high-contrast for dark themes) and responsiveness automatically.

---

## 3. Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Vanilla JS, HTML5, CSS3 (Glassmorphism), PWA Support |
| **Backend** | Firebase Functions (Python 3.11) |
| **AI Model** | Gemini 2.5 Pro (via Google Generative AI SDK) |
| **Database** | Google Cloud Firestore (NoSQL) |
| **Hosting** | Firebase Hosting |
| **Analytics Libs** | Pandas (Backend), Chart.js (Frontend), Marked.js (Markdown Rendering) |

---

## 4. Technical Implementation

### Backend Architecture (`functions/main.py`)
The backend is a serverless function (`ask`) that:
1.  **Ingests Requests**: Receives user questions via a POST endpoint.
2.  **Harmonizes Data**: Streams data from multiple Firestore collections and creates a `pd.DataFrame` for each.
3.  **Prompt Engineering**: Constructs a rich prompt containing a sample of the aggregated dataset (~150 rows) and specific instructions for JSON output.
4.  **AI Invocation**: Calls Gemini 2.5 Pro with the context.
5.  **JSON Response**: Returns a structured payload containing `answer`, `follow_up`, and `visualization` config.

### Frontend Logic (`public/script.js`)
*   **State Management**: Manages chat history and UI loading states.
*   **Topic-Based Context**: Dynamically updates the sidebar content based on the selected "Focus Area" using local data objects (`TOPIC_CONTENT`).
*   **Reasoning UI**: Uses an asynchronous interval-based renderer to display the "thinking" steps while waiting for the API response.
*   **Chart Rendering**: A dedicated `renderChart` helper translates backend JSON into functional Chart.js instances.

---

## 5. Deployment & Configuration

### Environment Variables & Secrets
The project relies on Firebase Secrets for security:
*   `GEMINI_API_KEY`: Required for AI communication. Accessible via `os.environ.get('GEMINI_API_KEY')` in Python.

### Deployment Commands
```bash
# Deploy all components
firebase deploy

# Deploy only backend functions
firebase deploy --only functions

# Deploy only the web frontend
firebase deploy --only hosting
```

### Build Requirements
*   **Functions**: Requires `pip install -r functions/requirements.txt`.
*   **Hosting**: Static files in `public/`.

---

## 6. Best Practices & R&D Notes
*   **Context Management**: We limit Firestore streams to 30 documents per collection to stay within LLM token limits while maintaining a representational sample.
*   **Prompt Stability**: The prompt strictly enforces a JSON return format to ensure the frontend can parse visualizations and follow-ups reliably.
*   **PWA Compatibility**: The platform is built as a Progressive Web App, allowing it to be "installed" on mobile devices for shop-floor accessibility.
