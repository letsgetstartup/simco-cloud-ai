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

    // Topic-Based Content
    const TOPIC_CONTENT = {
        'efficiency': {
            alerts: [
                { level: 'critical', title: 'OEE < 65%', time: 'Live', desc: 'Cell-3 Performance Drop', query: 'Analyze the root cause of OEE dropping below 65% in Cell-3 today.' },
                { level: 'warning', title: 'Idle Time', time: '1h ago', desc: 'VMC-2 excessive setup', query: 'Correlate VMC-2 setup times with recent job complexity.' }
            ],
            insights: [
                { metric: '-12%', title: 'OEE Trend', sub: 'Shift 2 vs Shift 1', query: 'Compare OEE performance between Shift 1 and Shift 2.' },
                { metric: '82%', title: 'Bottleneck', sub: 'Lathe-4 Capacity', query: 'Identify constraints at Lathe-4 and suggest load balancing breakdown.' }
            ]
        },
        'profitability': {
            alerts: [
                { level: 'critical', title: 'Cost Overrun', time: 'Active', desc: 'Job #504 Margin Risk', query: 'Analyze Job #504 cost structure. Why is it exceeding the quote?' },
                { level: 'warning', title: 'Scrap Rate', time: 'Today', desc: 'Material Waste > 5%', query: 'Calculate the financial impact of current scrap rates on monthly P&L.' }
            ],
            insights: [
                { metric: '$4.2k', title: 'Revenue at Risk', sub: 'Due to Delays', query: 'Which delayed jobs are putting the most revenue at risk this week?' },
                { metric: '+8%', title: 'Est. Margin', sub: 'High-Speed Milling', query: 'Analyze profitability of high-speed milling jobs vs standard machining.' }
            ]
        },
        'health': {
            alerts: [
                { level: 'critical', title: 'Spindle Overheat', time: '2m ago', desc: 'VMC-3 Temp > 85°C', query: 'Analyze critical Spindle Overheat on VMC-3. Show temp trend.' },
                { level: 'warning', title: 'Vibration Spike', time: '10m ago', desc: 'Lathe-1 Axis Z', query: 'Diagnose vibration anomaly on Lathe-1 Z-axis.' }
            ],
            insights: [
                { metric: '94%', title: 'Uptime', sub: 'Rolling 7-day Avg', query: 'Show machine uptime distribution for the last week.' },
                { metric: '3', title: 'Maint. Due', sub: 'Next 24 Hours', query: 'List machines requiring immediate maintenance intervention.' }
            ]
        },
        'tools': {
            alerts: [
                { level: 'critical', title: 'Tool Breakage', time: '4m ago', desc: 'Tool #12 Snap Risk', query: 'Investigate tool life history for Tool #12. Did signal anomalies precede risk?' },
                { level: 'warning', title: 'Inventory Low', time: 'AM Shift', desc: 'Solid Carbide Drills', query: 'Forecast consumption of Solid Carbide Drills vs current stock.' }
            ],
            insights: [
                { metric: '$850', title: 'Tool Spend', sub: 'Above Weekly Avg', query: 'Analyze top 5 tools driving excessive replacement costs.' },
                { metric: '15%', title: 'Life Optimization', sub: 'Potential Savings', query: 'How much can we save by optimizing speeds/feeds for extended tool life?' }
            ]
        },
        'workforce': {
            alerts: [
                { level: 'warning', title: 'Shift Gap', time: 'Next Week', desc: 'Operator Shortage', query: 'Analyze schedule gaps for next week based on current operator availability.' },
                { level: 'warning', title: 'Training Due', time: 'Urgent', desc: '5 Operators Expiring', query: 'List operators with expiring certifications and suggest training windows.' }
            ],
            insights: [
                { metric: '98%', title: 'Shift Efficiency', sub: 'Team Alpha', query: 'What makes Team Alpha the most efficient shift? Analyze their workflow.' },
                { metric: '4h', title: 'Overtime', sub: 'Avg per Operator', query: 'Is current overtime correlate with increased fatigue-related errors?' }
            ]
        },
        'energy': {
            alerts: [
                { level: 'critical', title: 'Peak Demand', time: 'Now', desc: 'Exceeding Setpoint', query: 'We are exceeding energy demand setpoint. Recommend load shedding actions.' },
                { level: 'warning', title: 'Idle Draw', time: 'Lunch', desc: 'Machines Left On', query: 'Calculate cost of machines left idle/on during lunch breaks.' }
            ],
            insights: [
                { metric: '+8.5%', title: 'Energy ROI', sub: 'Eco-Mode Saving', query: 'Quantify savings from recent Eco-Mode implementation.' },
                { metric: '12kW', title: 'Base Load', sub: 'Off-Shift', query: 'Why is off-shift base load 12kW? Identify "vampire" power sources.' }
            ]
        },
        'quality': {
            alerts: [
                { level: 'critical', title: 'Dim. Deviation', time: 'Job #99', desc: 'Out of Tolerance', query: 'Analyze dimensional drift on Job #99. Correlate with thermal expansion.' },
                { level: 'warning', title: 'Surface Finish', time: 'Insp. 4', desc: 'Ra > 1.6', query: 'Investigate surface finish degradation on recent aluminum parts.' }
            ],
            insights: [
                { metric: '99.2%', title: 'First Pass Yield', sub: 'All Cells', query: 'Show FPY trends for all production cells over the last month.' },
                { metric: 'Top 3', title: 'Defect Types', sub: 'Pareto Analysis', query: 'Perform a Pareto analysis of the top 3 defect types this week.' }
            ]
        }
    };

    // Render Logic defined later...


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

    // Thinking Process Steps - Detailed Shop Floor Logic
    const THINKING_STEPS = [
        "Initializing Unified Shop Floor Schema (Machines, Tools, Jobs)...",
        "Parsing Spindle Load & Vibration Signal Streams (500Hz)...",
        "Correlating Maintenance Logs with Historic Out-of-Tolerance Events...",
        "Validating Job Queue Metadata against CNC Controller Feedback...",
        "Simulating Tool Wear Degradation Curves (Pearson Correlation)...",
        "Aggregating OEE Data across VMC and HMC Work-centers...",
        "Identifying Bottleneck Latencies in Material Handling Handshakes...",
        "Calculating Financial Scrap Impact per Machine-Hour...",
        "Synthesizing Cross-Reference Insight (Signals x Tool Life)...",
        "Optimizing Visualization Parameters for Shop Floor Dashboard...",
        "Generating Final Engineering Recommendations..."
    ];

    let currentThinkingInterval;

    // Helper: Simulate Thinking (Accordion Style)
    const simulateThinking = (container) => {
        container.innerHTML = ''; // Clear default spinner

        const reasoningBox = document.createElement('div');
        reasoningBox.className = 'reasoning-container loading';

        const header = document.createElement('div');
        header.className = 'reasoning-header';
        header.innerHTML = `
            <span><i class="fas fa-brain"></i> Reasoning Engine - Shop Floor Logic</span>
            <i class="fas fa-chevron-down"></i>
        `;

        const content = document.createElement('div');
        content.className = 'reasoning-content';

        const log = document.createElement('div');
        log.className = 'reasoning-log';
        content.appendChild(log);

        reasoningBox.appendChild(header);
        reasoningBox.appendChild(content);
        container.appendChild(reasoningBox);

        // Accordion Toggle
        header.onclick = () => {
            reasoningBox.classList.toggle('collapsed');
        };

        let stepIndex = 0;
        const addStep = () => {
            if (stepIndex >= THINKING_STEPS.length) {
                clearInterval(currentThinkingInterval);
                return;
            }
            const step = document.createElement('div');
            step.className = 'reasoning-step';
            step.textContent = THINKING_STEPS[stepIndex];
            log.appendChild(step);
            log.scrollTop = log.scrollHeight;
            stepIndex++;
        };

        addStep();
        currentThinkingInterval = setInterval(addStep, 1000);
        return reasoningBox; // Return to finalize later
    };

    // Helper: Render Chart (visuals)
    const renderChart = (vizData) => {
        if (!vizData) return;

        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';

        const canvas = document.createElement('canvas');
        chartContainer.appendChild(canvas);

        chatMessages.appendChild(chartContainer);
        chatMessages.scrollTop = chatMessages.scrollHeight; // Scroll to show chart

        // Default Dark Theme Colors
        Chart.defaults.color = '#FFFFFF';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';

        new Chart(canvas, {
            type: vizData.type || 'bar',
            data: {
                labels: vizData.labels,
                datasets: vizData.datasets.map(ds => ({
                    ...ds,
                    borderWidth: 1,
                    // High-contrast vibrant palette: Gold, White, Soft Grey, Amber/Orange
                    backgroundColor: ds.backgroundColor || ['#FFFFD7', '#FFFFFF', '#E0E0E0', '#FFB74D', '#81C784']
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: vizData.title,
                        font: { size: 16 }
                    },
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                },
                scales: {
                    x: {
                        ticks: { color: 'rgba(255,255,255,0.7)' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        ticks: { color: 'rgba(255,255,255,0.7)' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
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

        // Loading message with Thinking Process
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant loading';
        chatMessages.appendChild(loadingDiv);

        // Start Reasoning Simulation
        const startTime = performance.now();
        simulateThinking(loadingDiv);
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

            // Stop Reasoning & Finalize UI
            clearInterval(currentThinkingInterval);

            const reasoningBox = loadingDiv.querySelector('.reasoning-container');
            if (reasoningBox) {
                reasoningBox.classList.remove('loading');
                reasoningBox.classList.add('collapsed'); // Collapse by default once done
                const headerSpan = reasoningBox.querySelector('.reasoning-header span');
                headerSpan.innerHTML = '<i class="fas fa-check-circle" style="color: #4CAF50"></i> Thought for ' + (Math.round(performance.now() - startTime) / 1000).toFixed(1) + 's';
            }

            loadingDiv.classList.remove('loading'); // Keep the reasoning box, just remove loading state

            if (data.answer) {
                addMessage('assistant', data.answer);

                // Render Chart if Visualization Data exists
                if (data.visualization) {
                    renderChart(data.visualization);
                }

                // Show Follow-up Questions from Backend
                if (data.follow_up && Array.isArray(data.follow_up)) {
                    showFollowUpQuestions(data.follow_up);
                }
            } else if (data.error) {
                addMessage('assistant', `❌ Error: ${data.error}`);
            }
        } catch (error) {
            clearInterval(thinkingInterval);
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
    welcomeDiv.innerHTML = `<div class="avatar"><i class="fas fa-robot"></i></div><div class="content">Hello! I am **SolidCamAI**. I have full visibility into your **Machines, Jobs, Events, Tools, and Signals**.<br><br>Ask me complex questions that cross-reference your data!</div>`;
    chatMessages.appendChild(welcomeDiv);

    updateStarterQuestions();

    updateStarterQuestions();

    // Render Sidebars Dynamic
    const renderSidebar = (topicKey) => {
        const data = TOPIC_CONTENT[topicKey] || TOPIC_CONTENT['health'];

        // Alerts
        const alertsContainer = document.getElementById('live-alerts');
        alertsContainer.innerHTML = ''; // Clear existing
        if (alertsContainer && data.alerts) {
            data.alerts.forEach(alert => {
                const card = document.createElement('div');
                card.className = `alert-card ${alert.level}`;
                card.innerHTML = `
                    <div class="alert-header">
                        <span>${alert.title}</span>
                        <span class="alert-time">${alert.time}</span>
                    </div>
                    <div class="alert-desc">${alert.desc}</div>
                `;
                card.onclick = () => {
                    userInput.value = alert.query;
                    handleSend();
                };
                alertsContainer.appendChild(card);
            });
        }

        // Insights
        const adminContainer = document.getElementById('admin-insights');
        adminContainer.innerHTML = ''; // Clear existing
        if (adminContainer && data.insights) {
            data.insights.forEach(insight => {
                const card = document.createElement('div');
                card.className = 'admin-card';
                card.innerHTML = `
                    <div class="admin-title"><i class="fas fa-chart-line"></i> ${insight.title}</div>
                    <div class="admin-metric">${insight.metric}</div>
                    <div class="admin-sub">${insight.sub}</div>
                `;
                card.onclick = () => {
                    userInput.value = insight.query;
                    handleSend();
                };
                adminContainer.appendChild(card);
            });
        }
    };

    // Initialize with default
    renderSidebar('health');

    // Listener
    const topicSelect = document.getElementById('topic-select');
    if (topicSelect) {
        topicSelect.addEventListener('change', (e) => {
            renderSidebar(e.target.value);
            // Optional: Feedback in chat
            // addMessage('assistant', `Switched context to **${e.target.options[e.target.selectedIndex].text}**. Analyzing specific data streams...`);
        });
    }
});
