// Simco AI - Frontend Logic

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    // const datasetSelect = document.getElementById('dataset-select'); // Removed

    // Complex Multi-Table Starter Questions (Unified View)
    const STARTER_QUESTIONS = [
        "Correlate frequent alarm events with specific job IDs to identify high-risk production runs.",
        "Compare the average cycle time variance of VMC Mills vs Turning Centers across all active jobs.",
        "Identify the machine with the highest operational cost per produced unit, factoring in tool wear and energy signals.",
        "Analyze the impact of spindle load anomalies (signals) on tool breakage frequency (tools).",
        "Which production shift has the highest efficiency rating when normalizing for job complexity?",
        "Detect correlations between temperature spikes in signals and subsequent downtime events on critical machines.",
        "Identify the top 3 bottlenecks in the shop floor by cross-referencing job delays and machine alarm logs.",
        "Calculate the estimated vs actual cost variance for all jobs running on machines exceeding 80% utilization.",
        "Predict upcoming tool replacements based on current job run rates and remaining tool life expectancy.",
        "Analyze the relationship between specific machine models and the frequency of 'Critical' severity events."
    ];

    // Auto-resize textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
    });

    // Helper: Show Follow-up Chips
    const showFollowUpQuestions = (questions) => {
        if (!questions || questions.length === 0) return;

        const container = document.createElement('div');
        container.className = 'follow-up-container';

        const label = document.createElement('div');
        label.className = 'follow-up-label';
        label.innerHTML = '<i class="fas fa-lightbulb"></i> Suggested Follow-ups:';
        container.appendChild(label);

        const chipsDiv = document.createElement('div');
        chipsDiv.className = 'chips-wrapper';

        questions.forEach(q => {
            const chip = document.createElement('button');
            chip.className = 'suggestion-chip';
            chip.textContent = q;
            chip.onclick = () => {
                userInput.value = q;
                handleSend(); // Auto-send when clicked
            };
            chipsDiv.appendChild(chip);
        });

        container.appendChild(chipsDiv);
        chatMessages.appendChild(container); // Append *after* the assistant message
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    // Helper: Add Message
    const addMessage = (role, content) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = role === 'assistant' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        // Use marked.js if assistant, plain text if user (for safety)
        if (role === 'assistant') {
            contentDiv.innerHTML = marked.parse(content);
        } else {
            contentDiv.textContent = content;
        }

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(contentDiv);
        chatMessages.appendChild(msgDiv);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const handleSend = async () => {
        const question = userInput.value.trim();
        // const collection = datasetSelect.value; // Removed as per instruction

        if (!question) return;

        // Remove any existing follow-up containers to keep UI clean
        const existingFollowUps = document.querySelectorAll('.follow-up-container');
        existingFollowUps.forEach(el => el.remove());

        // UI state
        addMessage('user', question);
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;

        // Loading message
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant loading';
        loadingDiv.innerHTML = '<div class="avatar"><i class="fas fa-robot"></i></div><div class="content"><i class="fas fa-circle-notch fa-spin"></i> Analyzing unified shop floor data...</div>';
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            // Function URL - In local testing it's usually localhost:5001/solidcam-f58bc/us-central1/ask_gemini
            // In production, we use the rewrite path /ask
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question }) // No interaction with collection anymore
            });

            const data = await response.json();
            chatMessages.removeChild(loadingDiv);

            if (data.answer) {
                addMessage('assistant', data.answer);

                // Show Follow-up Questions from Backend
                if (data.follow_up && Array.isArray(data.follow_up)) {
                    showFollowUpQuestions(data.follow_up);
                }
            } else if (data.error) {
                addMessage('assistant', `❌ Error: ${data.error}`);
            }
        } catch (error) {
            chatMessages.removeChild(loadingDiv);
            addMessage('assistant', '❌ Failed to connect to the backend. Ensure the deployment is complete.');
            console.error('Fetch error:', error);
        } finally {
            sendBtn.disabled = false;
        }
    };

    // Initial Starter Quesitons Display
    const updateStarterQuestions = () => {
        // Strategy: If chat is empty, show them.
        if (chatMessages.children.length <= 1) { // 1 because of welcome message
            const starterContainer = document.querySelector('.starter-container');
            if (starterContainer) starterContainer.remove();

            if (STARTER_QUESTIONS.length > 0) {
                const container = document.createElement('div');
                container.className = 'starter-container follow-up-container';

                const label = document.createElement('div');
                label.className = 'follow-up-label';
                label.innerHTML = `<i class="fas fa-layer-group"></i> <b>Unified Analysis</b> - Try these complex inquiries:`;
                container.appendChild(label);

                const chipsDiv = document.createElement('div');
                chipsDiv.className = 'chips-wrapper';

                STARTER_QUESTIONS.forEach(q => {
                    const chip = document.createElement('button');
                    chip.className = 'suggestion-chip';
                    chip.textContent = q;
                    chip.onclick = () => {
                        userInput.value = q;
                        handleSend();
                    };
                    chipsDiv.appendChild(chip);
                });
                container.appendChild(chipsDiv);
                chatMessages.appendChild(container);
            }
        }
    };

    sendBtn.addEventListener('click', handleSend);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Removed datasetSelect.addEventListener('change', ...) as per instruction

    // Init Logic
    // Add initial welcome message
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message assistant';
    welcomeDiv.innerHTML = `<div class="avatar"><i class="fas fa-robot"></i></div><div class="content">Hello! I am **SolidComAI**. I have full visibility into your **Machines, Jobs, Events, Tools, and Signals**.<br><br>Ask me complex questions that cross-reference your data!</div>`;
    chatMessages.appendChild(welcomeDiv);

    updateStarterQuestions();
});
