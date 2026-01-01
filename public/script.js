// Simco AI - Frontend Logic

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const datasetSelect = document.getElementById('dataset-select');

    // Starter Questions for Value-Driven Conversations
    const STARTER_QUESTIONS = {
        'machines': [
            "Compare the hourly operational costs of VMC Mills vs Turning Centers.",
            "Identify machines with the highest downtime frequency.",
            "Analyze the efficiency rating spread across all machine groups."
        ],
        'jobs': [
            "Which jobs have the highest variance between estimated and actual cycle time?",
            "Identify the top 3 most expensive jobs currently in production.",
            "Analyze the production bottleneck based on active job status."
        ],
        'events': [
            "What are the most frequent alarm types triggered in the last 24 hours?",
            "Correlate operational status changes with specific machine IDs.",
            "Identify shifts with the highest density of critical events."
        ],
        'tools': [
            "Which tools are approaching their end-of-life expectancy?",
            "Analyze tool usage patterns across high-volume jobs.",
            "Identify potential tool breakage risks based on current load."
        ],
        'signals': [
            "Detect anomalies in spindle load signals for the past hour.",
            "Correlate temperature spikes with specific machine operations.",
            "Analyze the signal noise ratio for key sensor inputs."
        ]
    };

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
        const collection = datasetSelect.value;

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
        loadingDiv.innerHTML = '<div class="avatar"><i class="fas fa-robot"></i></div><div class="content"><i class="fas fa-circle-notch fa-spin"></i> Analyzing data...</div>';
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            // Function URL - In local testing it's usually localhost:5001/solidcam-f58bc/us-central1/ask_gemini
            // In production, we use the rewrite path /ask
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, collection })
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
        const dataset = datasetSelect.value;
        const questions = STARTER_QUESTIONS[dataset] || [];

        // Remove old starters if any (in a real app, maybe only show if chat is empty)
        // For now, let's just log or optional: display them if chat is empty. 
        // Strategy: If chat is empty, show them.
        if (chatMessages.children.length <= 1) { // 1 because of welcome message
            // Don't auto-show as chips to avoid clutter, maybe user wants to type.
            // But user requested: "so users will see the most advances questions as an option to start a conversation"
            // Let's create a special "Starter Container"
            const starterContainer = document.querySelector('.starter-container');
            if (starterContainer) starterContainer.remove();

            if (questions.length > 0) {
                const container = document.createElement('div');
                container.className = 'starter-container follow-up-container';
                // Reusing follow-up styling for basics

                const label = document.createElement('div');
                label.className = 'follow-up-label';
                label.innerHTML = `<i class="fas fa-star"></i> Suggested specific specific questions for <b>${dataset}</b>:`;
                container.appendChild(label);

                const chipsDiv = document.createElement('div');
                chipsDiv.className = 'chips-wrapper';

                questions.forEach(q => {
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

    // Update starters when dataset changes
    datasetSelect.addEventListener('change', () => {
        // Clear chat? Or just show new starters?
        // Let's reset chat for clean context switch as implied by "start a conversation"
        chatMessages.innerHTML = '';
        // Add welcome back
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'message assistant';
        welcomeDiv.innerHTML = `<div class="avatar"><i class="fas fa-robot"></i></div><div class="content">Hello! I am **SolidComAI**. I am ready to analyze your <b>${datasetSelect.value}</b> data using your permanent Gemini 2.5 Pro key.<br><br>Ask me anything!</div>`;
        chatMessages.appendChild(welcomeDiv);

        updateStarterQuestions();
    });

    // Init Logic
    updateStarterQuestions();
});
