/* ═══════════════════════════════════════════════════════════
   VOICE AGENT — MISSION CONTROL CONSOLE
   Dashboard Client Script
   ═══════════════════════════════════════════════════════════ */

// ─── STATE ───
const STATE = {
    IDLE: 'IDLE',
    CONNECTING: 'CONNECTING',
    LISTENING: 'LISTENING',
    PROCESSING: 'PROCESSING',
    SPEAKING: 'SPEAKING',
};

let currentState = STATE.IDLE;
let ws = null;
let mediaStream = null;
let audioContext = null;
let analyser = null;
let scriptProcessor = null;
let sessionStartTime = null;
let sessionTimer = null;
let messageCount = 0;
let ticketCount = 0;
let waveformAnimationId = null;
let isPaused = false;

// ─── DOM REFS ───
const callButton = document.getElementById('call-button');
const callButtonText = document.getElementById('call-button-text');
const pauseButton = document.getElementById('pause-button');
const pauseButtonText = document.getElementById('pause-button-text');
const stopButton = document.getElementById('stop-button');
const connectionDot = document.getElementById('connection-dot');
const connectionLabel = document.getElementById('connection-label');
const latencyValue = document.getElementById('latency-value');
const waveformCanvas = document.getElementById('waveform-canvas');
const waveformState = document.getElementById('waveform-state');
const transcriptContainer = document.getElementById('transcript-container');
const ticketsContainer = document.getElementById('tickets-container');
const metricDuration = document.getElementById('metric-duration');
const metricMessages = document.getElementById('metric-messages');
const metricTickets = document.getElementById('metric-tickets');
const metricState = document.getElementById('metric-state');

const sttDot = document.getElementById('stt-dot');
const llmDot = document.getElementById('llm-dot');
const ttsDot = document.getElementById('tts-dot');
const dbDot = document.getElementById('db-dot');
const sttStatus = document.getElementById('stt-status');
const llmStatus = document.getElementById('llm-status');
const ttsStatus = document.getElementById('tts-status');
const dbStatus = document.getElementById('db-status');

// ─── WAVEFORM VISUALIZER ───
const canvasCtx = waveformCanvas.getContext('2d');
let waveformData = new Float32Array(128).fill(0);

function resizeCanvas() {
    const rect = waveformCanvas.parentElement.getBoundingClientRect();
    waveformCanvas.width = rect.width * window.devicePixelRatio;
    waveformCanvas.height = rect.height * window.devicePixelRatio;
    canvasCtx.scale(window.devicePixelRatio, window.devicePixelRatio);
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

function getWaveformColor() {
    switch (currentState) {
        case STATE.LISTENING: return '#00A8A8'; // Teal
        case STATE.SPEAKING: return '#00A8A8'; // Teal
        case STATE.PROCESSING: return '#E2A100'; // Amber
        default: return 'rgba(0, 168, 168, 0.2)';
    }
}

function drawWaveform() {
    const width = waveformCanvas.width / window.devicePixelRatio;
    const height = waveformCanvas.height / window.devicePixelRatio;

    canvasCtx.clearRect(0, 0, width, height);

    const color = getWaveformColor();
    const centerY = height / 2;
    const barCount = 64;
    const barWidth = width / barCount;

    // Draw bars
    canvasCtx.fillStyle = color;
    for (let i = 0; i < barCount; i++) {
        let value;
        if (analyser && (currentState === STATE.LISTENING || currentState === STATE.SPEAKING)) {
            const dataIndex = Math.floor(i * (waveformData.length / barCount));
            value = Math.abs(waveformData[dataIndex]) * 2;
        } else if (currentState === STATE.PROCESSING) {
            // Pulsing sine wave while processing
            const time = Date.now() / 400;
            value = (Math.sin(time + i * 0.3) + 1) * 0.15;
        } else {
            // Idle: subtle ambient noise
            value = Math.random() * 0.03;
        }

        const barHeight = Math.max(1, value * height * 0.8);
        const x = i * barWidth + 1;
        const barW = Math.max(1, barWidth - 2);

        canvasCtx.globalAlpha = 0.6 + value * 0.4;
        canvasCtx.fillRect(x, centerY - barHeight / 2, barW, barHeight);
    }

    // Draw center reference line
    canvasCtx.globalAlpha = 0.1;
    canvasCtx.fillStyle = color;
    canvasCtx.fillRect(0, centerY, width, 1);
    canvasCtx.globalAlpha = 1;

    // Glow effect on edges for active states
    if (currentState === STATE.LISTENING || currentState === STATE.SPEAKING) {
        canvasCtx.fillStyle = `${color}08`;
        canvasCtx.fillRect(0, 0, width, height);
    }

    waveformAnimationId = requestAnimationFrame(drawWaveform);
}

function updateAnalyserData() {
    if (analyser) {
        analyser.getFloatTimeDomainData(waveformData);
    }
    requestAnimationFrame(updateAnalyserData);
}

// ─── STATE MACHINE ───
function setState(newState) {
    currentState = newState;
    metricState.textContent = newState;

    // Update waveform state label
    const stateLabels = {
        [STATE.IDLE]: 'AWAITING INPUT',
        [STATE.CONNECTING]: 'ESTABLISHING LINK',
        [STATE.LISTENING]: 'RECEIVING AUDIO',
        [STATE.PROCESSING]: 'LLM INFERENCE',
        [STATE.SPEAKING]: 'TTS OUTPUT',
    };
    waveformState.textContent = stateLabels[newState] || newState;

    const micRipple = document.getElementById('mic-ripple');
    if (micRipple) {
        if (newState === STATE.LISTENING || newState === STATE.SPEAKING) {
            micRipple.className = 'absolute inset-0 rounded-full bg-soul-teal/20 animate-ping opacity-100';
        } else {
            micRipple.className = 'absolute inset-0 rounded-full bg-soul-teal/20 opacity-0';
        }
    }

    // Color-code the state label
    const stateColors = {
        [STATE.IDLE]: '',
        [STATE.CONNECTING]: 'text-hud-amber',
        [STATE.LISTENING]: 'text-hud-cyan',
        [STATE.PROCESSING]: 'text-hud-amber',
        [STATE.SPEAKING]: 'text-hud-emerald',
    };
    waveformState.className = `font-hud text-[10px] tracking-[0.3em] uppercase mt-1 transition-colors duration-300 ${stateColors[newState] || 'text-text-muted'}`;

    // Update metric state color
    metricState.className = `font-hud text-sm tracking-widest uppercase ${stateColors[newState] || 'text-text-muted'}`;

    // Update system status dots
    updateSystemStatus(newState);
}

function updateSystemStatus(state) {
    const isActive = state !== STATE.IDLE;

    // STT
    sttDot.className = `status-dot w-2 h-2 rounded-full ${state === STATE.LISTENING ? 'active' :
        isActive ? 'active' : ''
        }`;
    sttDot.style.backgroundColor = state === STATE.LISTENING ? '#00FFFF' :
        isActive ? '#00E676' : '';
    sttStatus.textContent = state === STATE.LISTENING ? 'CAPTURING' : isActive ? 'READY' : 'OFFLINE';
    sttStatus.style.color = state === STATE.LISTENING ? '#00FFFF' :
        isActive ? '#00E676' : '';

    // LLM
    llmDot.className = `status-dot w-2 h-2 rounded-full ${state === STATE.PROCESSING ? 'warning' :
        isActive ? 'active' : ''
        }`;
    llmDot.style.backgroundColor = state === STATE.PROCESSING ? '#FFB300' :
        isActive ? '#00E676' : '';
    llmStatus.textContent = state === STATE.PROCESSING ? 'INFERRING' : isActive ? 'READY' : 'OFFLINE';
    llmStatus.style.color = state === STATE.PROCESSING ? '#FFB300' :
        isActive ? '#00E676' : '';

    // TTS
    ttsDot.className = `status-dot w-2 h-2 rounded-full ${state === STATE.SPEAKING ? 'active' :
        isActive ? 'active' : ''
        }`;
    ttsDot.style.backgroundColor = state === STATE.SPEAKING ? '#00E676' :
        isActive ? '#00E676' : '';
    ttsStatus.textContent = state === STATE.SPEAKING ? 'STREAMING' : isActive ? 'READY' : 'OFFLINE';
    ttsStatus.style.color = state === STATE.SPEAKING ? '#00E676' :
        isActive ? '#00E676' : '';

    // DB (always active when connected)
    dbDot.className = `status-dot w-2 h-2 rounded-full ${isActive ? 'active' : ''}`;
    dbDot.style.backgroundColor = isActive ? '#00E676' : '';
    dbStatus.textContent = isActive ? 'CONNECTED' : 'OFFLINE';
    dbStatus.style.color = isActive ? '#00E676' : '';
}

// ─── TRANSCRIPT ───
function addTranscript(type, text) {
    const now = new Date();
    const time = now.toTimeString().slice(0, 8);

    const tags = {
        user: { label: 'USR', color: 'text-hud-cyan' },
        agent: { label: 'AGT', color: 'text-hud-emerald' },
        system: { label: 'SYS', color: 'text-hud-amber' },
        error: { label: 'ERR', color: 'text-hud-rose' },
    };
    const tag = tags[type] || tags.system;

    const line = document.createElement('div');
    line.className = 'transcript-line';
    line.setAttribute('data-type', type);

    const timeSpan = document.createElement('span');
    timeSpan.className = 'font-code text-[11px] text-text-muted tabular-nums mr-3 flex-shrink-0';
    timeSpan.textContent = time;

    const tagSpan = document.createElement('span');
    tagSpan.className = `font-hud text-[10px] tracking-widest ${tag.color} mr-2 flex-shrink-0`;
    tagSpan.textContent = `[${tag.label}]`;

    const textSpan = document.createElement('span');
    textSpan.className = 'font-body text-sm text-text-primary';
    textSpan.textContent = text;

    line.appendChild(timeSpan);
    line.appendChild(tagSpan);
    line.appendChild(textSpan);

    // Make user transcript lines editable on click
    if (type === 'user') {
        function makeEditable(span) {
            span.style.cursor = 'pointer';
            span.title = 'Click to edit — press Enter to submit';
            span.classList.add('hover:underline', 'hover:decoration-hud-cyan/40');

            span.addEventListener('click', () => {
                if (line.querySelector('input')) return;

                const input = document.createElement('input');
                input.type = 'text';
                input.value = span.textContent;
                input.className = 'bg-transparent border border-hud-cyan/40 text-text-primary font-body text-sm px-1 py-0.5 rounded w-full outline-none focus:border-hud-cyan';
                input.style.minWidth = '120px';

                const originalText = span.textContent;
                span.replaceWith(input);
                input.focus();
                input.select();

                let handled = false;

                const finishEdit = (submit) => {
                    if (handled) return;
                    handled = true;

                    const newText = input.value.trim();
                    const finalText = submit && newText ? newText : originalText;

                    const newSpan = document.createElement('span');
                    newSpan.className = 'font-body text-sm text-text-primary';
                    newSpan.textContent = finalText;
                    input.replaceWith(newSpan);

                    // Re-attach editing to the new span
                    makeEditable(newSpan);

                    // If text changed, send correction to server
                    if (submit && newText && newText !== originalText && ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({
                            type: 'correction',
                            original: originalText,
                            corrected: newText
                        }));
                        addTranscript('system', `✏️ Correction sent: "${newText}"`);
                    }
                };

                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') { e.preventDefault(); finishEdit(true); }
                    if (e.key === 'Escape') { e.preventDefault(); finishEdit(false); }
                });
                input.addEventListener('blur', () => finishEdit(false));
            });
        }
        makeEditable(textSpan);
    }

    transcriptContainer.appendChild(line);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;

    if (type === 'user' || type === 'agent') {
        messageCount++;
        metricMessages.textContent = messageCount;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ─── TICKET CARDS ───
function addOrUpdateTicket(data) {
    console.log('[TICKET] addOrUpdateTicket called with:', JSON.stringify(data));

    // Remove "no tickets" placeholder if present (without nuking existing cards)
    const placeholder = ticketsContainer.querySelector('.text-center');
    if (placeholder) {
        placeholder.remove();
    }

    const ticketId = data.id || (ticketCount + 1);
    const cardId = `ticket-card-${ticketId}`;
    let existingCard = document.getElementById(cardId);

    const urgencyClass = `urgency-${data.urgency || 'medium'}`;
    const contentHTML = `
        <div class="flex justify-between items-center mb-1">
            <span class="text-xs font-bold text-soul-teal">#${String(ticketId).padStart(3, '0')}</span>
            <span class="text-[10px] text-text-muted bg-gray-100 px-1.5 py-0.5 rounded">${data.inquiry_type || 'Inquiry'}</span>
        </div>
        <div class="font-medium text-sm text-text-primary truncate">${escapeHtml(data.name || 'Unknown')}</div>
        <div class="text-xs text-text-muted truncate mt-1">${escapeHtml(data.notes || 'No description')}</div>
    `;

    if (existingCard) {
        console.log('[TICKET] Updating existing card:', cardId);
        existingCard.className = `ticket-card ${urgencyClass}`;
        existingCard.innerHTML = contentHTML;
    } else {
        console.log('[TICKET] Creating new card:', cardId);
        ticketCount++;
        metricTickets.textContent = ticketCount;

        const card = document.createElement('div');
        card.id = cardId;
        card.className = `ticket-card ${urgencyClass}`;
        card.innerHTML = contentHTML;
        ticketsContainer.prepend(card);
    }
}

// ─── SESSION TIMER ───
function startSessionTimer() {
    sessionStartTime = Date.now();
    sessionTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
        const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const secs = String(elapsed % 60).padStart(2, '0');
        metricDuration.textContent = `${mins}:${secs}`;
    }, 1000);
}
function stopSessionTimer() {
    if (sessionTimer) clearInterval(sessionTimer);
    sessionTimer = null;
}

// ─── AUDIO PLAYBACK (RAW PCM16 @ 24kHz) ───
let playbackAudioContext = null;
let nextStartTime = 0;
let playingSources = [];
let ttsGeneration = 0;

function processPCMChunk(pcmData) {
    if (!playbackAudioContext) {
        playbackAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        nextStartTime = 0;
    }

    // Convert raw PCM16 bytes to Float32 samples
    const int16 = new Int16Array(pcmData.buffer, pcmData.byteOffset, pcmData.byteLength / 2);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
    }

    // Create AudioBuffer
    const audioBuffer = playbackAudioContext.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    // Schedule playback
    const source = playbackAudioContext.createBufferSource();
    source.buffer = audioBuffer;

    // Connect through analyser for waveform visualization
    const playAnalyser = playbackAudioContext.createAnalyser();
    playAnalyser.fftSize = 256;
    source.connect(playAnalyser);
    playAnalyser.connect(playbackAudioContext.destination);

    // Use this analyser for waveform
    analyser = playAnalyser;
    waveformData = new Float32Array(playAnalyser.fftSize);

    const now = playbackAudioContext.currentTime;
    if (nextStartTime < now) {
        nextStartTime = now;
    }
    source.start(nextStartTime);
    playingSources.push(source);
    source.onended = () => {
        playingSources = playingSources.filter(s => s !== source);
    };
    nextStartTime += audioBuffer.duration;
}

function killAudio() {
    playingSources.forEach(source => {
        try { source.stop(); } catch (e) {}
    });
    playingSources = [];
    nextStartTime = 0;
    if (playbackAudioContext && playbackAudioContext.state === 'running') {
        playbackAudioContext.suspend();
    }
}

function resumeAudio() {
    if (playbackAudioContext && playbackAudioContext.state === 'suspended') {
        playbackAudioContext.resume();
    }
}

// ─── WEBSOCKET ───
async function startCall() {
    setState(STATE.CONNECTING);
    callButton.classList.add('connecting');
    callButtonText.textContent = 'Connecting...';
    addTranscript('system', 'Establishing WebSocket connection...');

    try {
        // Get microphone access
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        // Setup audio context for microphone visualization
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        waveformData = new Float32Array(analyser.fftSize);
        source.connect(analyser);

        // Setup script processor for sending audio data
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        // Open WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onopen = () => {
            callButton.classList.remove('connecting');
            callButton.classList.add('active');
            callButtonText.textContent = 'End Call';
            callButton.setAttribute('aria-label', 'End voice call');

            connectionDot.classList.add('connected');
            connectionLabel.textContent = 'Connected';

            setState(STATE.LISTENING);
            startSessionTimer();
            addTranscript('system', 'Connection established. Agent is listening...');

            isPaused = false;
            pauseButton.classList.remove('hidden');
            pauseButton.classList.add('flex');
            pauseButtonText.textContent = 'Pause Agent';

            stopButton.classList.remove('hidden');
            stopButton.classList.add('flex');

            // Send greeting to trigger initial agent response
            ws.send(JSON.stringify({ type: 'greeting' }));
            setState(STATE.PROCESSING);
            addTranscript('system', '▶ Sending greeting signal...');

            // Start sending audio data
            scriptProcessor.onaudioprocess = (e) => {
                if (!ws || ws.readyState !== WebSocket.OPEN) return;
                const inputData = e.inputBuffer.getChannelData(0);

                // RMS energy for barge-in detection
                let rms = 0;
                for (let i = 0; i < inputData.length; i++) rms += inputData[i] ** 2;
                rms = Math.sqrt(rms / inputData.length);

                if (isPaused) {
                    return; // drop all mic chunks
                }

                if (currentState === STATE.SPEAKING) {
                    // Do NOT send audio bytes (prevents echo reaching server STT)
                    // But if user is clearly speaking over agent (loud), signal barge-in
                    if (rms > 0.25) { // Raised from 0.05 to 0.25 to prevent acoustic echo cancellation loops!
                        ws.send(JSON.stringify({ type: 'barge_in' }));
                        ttsGeneration++;
                        killAudio();
                        setState(STATE.LISTENING);
                    } else {
                        return; // don't send bytes
                    }
                }

                // Normal mode: send PCM bytes for STT
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                }
                ws.send(pcm16.buffer);
            };
        };

        ws.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                const myGen = ttsGeneration;
                const arrayBuffer = await event.data.arrayBuffer();
                if (myGen !== ttsGeneration) return; // stale - discard
                resumeAudio();
                setState(STATE.SPEAKING);
                processPCMChunk(new Uint8Array(arrayBuffer));
            } else {
                // JSON control messages
                try {
                    const msg = JSON.parse(event.data);

                    if (msg.type === 'tts_complete') {
                        setState(STATE.LISTENING);
                    } else if (msg.type === 'clear_audio') {
                        killAudio();
                        setState(STATE.LISTENING);
                    } else if (msg.type === 'transcript') {
                        addTranscript('user', msg.text);
                        setState(STATE.PROCESSING);
                    } else if (msg.type === 'response') {
                        addTranscript('agent', msg.text);
                    } else if (msg.type === 'tool_call') {
                        addTranscript('system', `▶ Tool called: ${msg.name}`);
                        if (msg.name === 'log_inquiry' && msg.result && msg.result.id) {
                            addOrUpdateTicket(msg.result);
                        }
                    }
                } catch (e) {
                    // Not JSON — might be a text response
                }
            }
        };

        ws.onclose = () => {
            endCall();
            addTranscript('system', 'WebSocket connection closed.');
        };

        ws.onerror = (err) => {
            addTranscript('error', 'WebSocket error occurred.');
            endCall();
        };

    } catch (err) {
        addTranscript('error', `Failed to start: ${err.message}`);
        endCall();
    }
}

function endCall() {
    // Cleanup WebSocket
    if (ws) {
        ws.close();
        ws = null;
    }

    // Cleanup audio
    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }

    analyser = null;
    killAudio();
    stopSessionTimer();

    // Reset UI
    setState(STATE.IDLE);
    callButton.classList.remove('active', 'connecting');
    callButtonText.textContent = 'Initialize Call';
    callButton.setAttribute('aria-label', 'Start voice call');

    pauseButton.classList.remove('flex');
    pauseButton.classList.add('hidden');
    stopButton.classList.remove('flex');
    stopButton.classList.add('hidden');
    isPaused = false;

    connectionDot.classList.remove('connected');
    connectionLabel.textContent = 'Disconnected';
    latencyValue.textContent = '—ms';
}

// ─── EVENT LISTENERS ───
callButton.addEventListener('click', () => {
    if (currentState === STATE.IDLE) {
        startCall();
    } else {
        addTranscript('system', 'Terminating session...');
        endCall();
    }
});

pauseButton.addEventListener('click', () => {
    isPaused = !isPaused;
    if (isPaused) {
        pauseButtonText.textContent = 'Resume Agent';
        pauseButton.classList.add('bg-soul-teal/30');
        waveformState.textContent = 'AGENT PAUSED';
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'barge_in' }));
        }
        addTranscript('system', 'Agent paused.');
    } else {
        pauseButtonText.textContent = 'Pause Agent';
        pauseButton.classList.remove('bg-soul-teal/30');
        setState(currentState); // refresh status text
        addTranscript('system', 'Microphone resumed.');
    }
});

stopButton.addEventListener('click', () => {
    addTranscript('system', 'Saving session and resetting workspace...');
    endCall();
    
    // Clear live view elements
    if (transcriptContainer) {
        transcriptContainer.innerHTML = `
            <div class="flex items-start gap-3 bg-soul-light-teal/50 p-3 rounded-lg">
                <span class="font-code text-xs text-text-muted mt-0.5">--:--</span>
                <div class="flex-1">
                    <span class="block text-xs font-bold text-soul-teal uppercase">System</span>
                    <p class="text-sm text-text-primary mt-0.5">Workspace Reset. Press start to speak with a fresh session.</p>
                </div>
            </div>
        `;
    }
    if (ticketsContainer) {
        ticketsContainer.innerHTML = `<div class="text-center py-10"><span class="text-xs text-text-muted">No inquiries logged yet</span></div>`;
    }
    
    // Reset stats
    messageCount = 0;
    document.getElementById('metric-duration').textContent = "00:00";
    document.getElementById('metric-messages').textContent = "0";
});

const micContainer = document.getElementById('mic-container');
if (micContainer) {
    micContainer.addEventListener('click', (e) => {
        // Only trigger click if target is NOT callButton itself to avoid recursive loop
        if (e.target.closest('#call-button') === null) {
            callButton.click();
        }
    });
}

// ─── INIT ───
drawWaveform();
updateAnalyserData();

// Simulated latency counter (updates when connected)
setInterval(() => {
    if (currentState !== STATE.IDLE) {
        const simulatedLatency = Math.floor(80 + Math.random() * 120);
        latencyValue.textContent = `${simulatedLatency}ms`;
        latencyValue.style.color = simulatedLatency > 150 ? '#FFB300' : '#00FFFF';
    }
}, 2000);

// ══════════════ KNOWLEDGE BASE (RAG) ══════════════
const kbInput = document.getElementById('kb-file-input');
const kbStatus = document.getElementById('kb-status');
const kbProgress = document.getElementById('kb-progress');
const reindexBtn = document.getElementById('reindex-button');
const uploadZone = document.getElementById('upload-zone');

if (kbInput && uploadZone) {
    // File selection via click
    kbInput.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (files.length > 0) uploadDocs(files);
    });

    // Drag and Drop visual feedback
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('border-soul-teal', 'bg-soul-light-teal/40');
    });

    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('border-soul-teal', 'bg-soul-light-teal/40');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('border-soul-teal', 'bg-soul-light-teal/40');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadDocs(files);
        }
    });
}

if (reindexBtn) {
    reindexBtn.addEventListener('click', async () => {
        setKBStatus('SYNCING...', 'amber', 50);
        try {
            const resp = await fetch('/ingest', { method: 'POST' });
            const data = await resp.json();
            setKBStatus('READY', 'teal', 100);
            addTranscript('system', `Knowledge Base synchronized: ${data.chunks} chunks found.`);
        } catch (err) {
            console.error('Re-index failed:', err);
            setKBStatus('FAILED', 'red', 0);
        }
    });
}

function setKBStatus(text, colorClass, percent) {
    if (!kbStatus || !kbProgress) return;
    kbStatus.textContent = text;
    // Map previous class colors loosely or apply colors manually
    if (colorClass === 'emerald' || colorClass === 'teal') kbStatus.className = 'text-soul-teal';
    else if (colorClass === 'amber') kbStatus.className = 'text-yellow-500';
    else kbStatus.className = 'text-red-500';
    
    kbProgress.style.width = `${percent}%`;
    if (percent === 100) {
        setTimeout(() => { kbProgress.style.width = '0%'; }, 2000);
    }
}

async function uploadDocs(files) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    setKBStatus('UPLOADING...', 'amber', 50);

    try {
        const resp = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (resp.ok) {
            const data = await resp.json();
            setKBStatus('READY', 'teal', 100);
            addTranscript('system', `Intelligence updated: ${data.message}`);
            loadKnowledgeFiles(); // Refresh file list after upload
        } else {
            throw new Error('Upload failed');
        }
    } catch (err) {
        console.error('Upload error:', err);
        setKBStatus('FAILED', 'red', 0);
        addTranscript('system', 'Knowledge Base upload failed. Check general logs.');
    }
}

// ══════════════ ADMIN DASHBOARD LOGIC ══════════════
const tabCall = document.getElementById('tab-call');
const tabAdmin = document.getElementById('tab-admin');
const viewCall = document.getElementById('view-call');
const viewAdmin = document.getElementById('view-admin');
const fileListContainer = document.getElementById('file-list-container');

const cfgName = document.getElementById('cfg-name');
const cfgVoice = document.getElementById('cfg-voice');
const cfgTemp = document.getElementById('cfg-temp');
const cfgPrompt = document.getElementById('cfg-prompt');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const agentDisplayName = document.getElementById('agent-display-name');

if (tabCall && tabAdmin && viewCall && viewAdmin) {
    tabCall.addEventListener('click', () => {
        viewCall.classList.remove('hidden');
        viewAdmin.classList.add('hidden');
        tabCall.className = 'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 bg-white text-soul-navy shadow-sm';
        tabAdmin.className = 'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 text-white/80 hover:text-white';
        if (typeof resizeCanvas === "function") resizeCanvas();
    });

    tabAdmin.addEventListener('click', () => {
        viewCall.classList.add('hidden');
        viewAdmin.classList.remove('hidden');
        tabAdmin.className = 'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 bg-white text-soul-navy shadow-sm';
        tabCall.className = 'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 text-white/80 hover:text-white';
        loadKnowledgeFiles();
        loadCallHistory();
    });
}


async function loadSettings() {
    try {
        const resp = await fetch('/api/settings');
        const settings = await resp.json();
        if (cfgName) cfgName.value = settings.agent_name || 'Aria';
        if (cfgVoice) cfgVoice.value = settings.voice || 'en-AU-NatashaNeural';
        if (cfgTemp) cfgTemp.value = settings.temperature !== undefined ? settings.temperature : 0.7;
        if (cfgPrompt) cfgPrompt.value = settings.system_prompt || '';
        if (agentDisplayName) agentDisplayName.textContent = `${settings.agent_name || 'Aria'} — AI Receptionist`;
    } catch (err) { console.error('Failed to load settings:', err); }
}

if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', async () => {
        saveSettingsBtn.textContent = 'Saving...';
        const payload = {
            agent_name: cfgName.value.trim(),
            voice: cfgVoice.value,
            temperature: parseFloat(cfgTemp.value),
            system_prompt: cfgPrompt.value.trim()
        };
        try {
            const resp = await fetch('/api/settings', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                if (agentDisplayName) agentDisplayName.textContent = `${payload.agent_name} — AI Receptionist`;
                addTranscript('system', '✅ Settings saved successfully.');
            }
        } catch (err) { alert('Failed to save settings.'); }
        finally { saveSettingsBtn.textContent = 'Save Configuration'; }
    });
}

async function loadKnowledgeFiles() {
    if (!fileListContainer) return;
    try {
        const resp = await fetch('/api/knowledge-files');
        const files = await resp.json();
        if (files.length === 0) {
            fileListContainer.innerHTML = `<div class="text-center py-10 text-text-muted text-xs">No documents uploaded yet.</div>`;
            return;
        }
        fileListContainer.innerHTML = files.map(filename => {
            const ext = filename.split('.').pop().toUpperCase();
            return `
                <div class="flex items-center justify-between bg-white/[0.03] border border-white/[0.05] p-2.5 rounded-xl hover:border-soul-teal/30 hover:bg-white/[0.05] transition-all group">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-text-muted flex items-center justify-center font-bold text-xs group-hover:text-soul-teal group-hover:border-soul-teal/20 transition-all">${ext}</div>
                        <span class="text-xs font-semibold text-white truncate max-w-[180px]">${filename}</span>
                    </div>
                    <button class="text-white/40 hover:text-red-500 p-1 delete-file-btn transition-colors" data-name="${filename}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            `;
        }).join('');
        document.querySelectorAll('.delete-file-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const name = btn.getAttribute('data-name');
                if (confirm(`Delete file "${name}"?`)) await deleteFile(name);
            });
        });
    } catch (err) { }
}

async function deleteFile(filename) {
    try {
        const resp = await fetch(`/api/knowledge-files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (resp.ok) { loadKnowledgeFiles(); addTranscript('system', `🗑️ Deleted file: ${filename}`); }
    } catch (err) { }
}

async function loadCallHistory() {
    const historyBody = document.getElementById('history-table-body');
    if (!historyBody) return;
    try {
        const resp = await fetch('/api/history');
        const result = await resp.json();
        
        if (result.status === 'success' && result.data.length > 0) {
            historyBody.innerHTML = result.data.map(session => {
                const dateObj = new Date(session.start_time);
                const dateStr = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const mins = String(Math.floor(session.duration_seconds / 60)).padStart(2, '0');
                const secs = String(session.duration_seconds % 60).padStart(2, '0');
                
                return `
                    <tr class="hover:bg-white/[0.03] border-b border-white/[0.02] transition-colors">
                        <td class="px-3 py-3 text-xs text-white font-medium">${dateStr}</td>
                        <td class="px-3 py-3 text-xs font-code tabular-nums text-text-muted">${mins}:${secs}</td>
                        <td class="px-3 py-3 text-xs text-text-muted">${session.messages_count}</td>
                        <td class="px-3 py-3"><span class="bg-soul-teal/10 text-soul-teal border border-soul-teal/20 px-2.5 py-0.5 rounded-full text-[10px] font-bold">${session.tickets_created}</span></td>
                    </tr>
                `;
            }).join('');
        } else {
            historyBody.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-xs text-text-muted">No call history available yet.</td></tr>`;
        }
    } catch (err) {
        historyBody.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-xs text-red-500">Failed to load history</td></tr>`;
    }
}

document.addEventListener('DOMContentLoaded', () => { loadSettings(); loadKnowledgeFiles(); loadCallHistory(); });

