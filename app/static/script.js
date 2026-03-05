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

// ─── DOM REFS ───
const callButton = document.getElementById('call-button');
const callButtonText = document.getElementById('call-button-text');
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
        case STATE.LISTENING: return '#00FFFF';
        case STATE.SPEAKING: return '#00E676';
        case STATE.PROCESSING: return '#FFB300';
        default: return 'rgba(224, 224, 255, 0.15)';
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
    line.innerHTML = `
        <span class="font-code text-[11px] text-text-muted tabular-nums mr-3 flex-shrink-0">${time}</span>
        <span class="font-hud text-[10px] tracking-widest ${tag.color} mr-2 flex-shrink-0">[${tag.label}]</span>
        <span class="font-body text-sm text-text-primary">${escapeHtml(text)}</span>
    `;

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
function addTicket(data) {
    ticketCount++;
    metricTickets.textContent = ticketCount;

    // Remove "no tickets" placeholder
    if (ticketsContainer.querySelector('.text-center')) {
        ticketsContainer.innerHTML = '';
    }

    const urgencyClass = `urgency-${data.urgency || 'medium'}`;
    const card = document.createElement('div');
    card.className = `ticket-card ${urgencyClass}`;
    card.innerHTML = `
        <div class="flex justify-between items-center mb-1">
            <span class="font-hud text-[10px] tracking-widest text-hud-cyan uppercase">#${String(data.id || ticketCount).padStart(4, '0')}</span>
            <span class="font-code text-[10px] text-text-muted">${data.urgency || 'medium'}</span>
        </div>
        <div class="font-body text-sm text-text-primary truncate">${escapeHtml(data.name || 'Unknown')}</div>
        <div class="font-body text-xs text-text-muted truncate mt-1">${escapeHtml(data.issue || 'No description')}</div>
    `;

    ticketsContainer.prepend(card);
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
    nextStartTime += audioBuffer.duration;
}

function clearAudioQueue() {
    nextStartTime = 0;
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

            // Send greeting to trigger initial agent response
            ws.send(JSON.stringify({ type: 'greeting' }));
            setState(STATE.PROCESSING);
            addTranscript('system', '▶ Sending greeting signal...');

            // Start sending audio data
            scriptProcessor.onaudioprocess = (e) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const pcm16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                    }
                    ws.send(pcm16.buffer);
                }
            };
        };

        ws.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                // Raw PCM16 audio data from TTS
                setState(STATE.SPEAKING);
                const arrayBuffer = await event.data.arrayBuffer();
                processPCMChunk(new Uint8Array(arrayBuffer));
            } else {
                // JSON control messages
                try {
                    const msg = JSON.parse(event.data);

                    if (msg.type === 'tts_complete') {
                        setState(STATE.LISTENING);
                    } else if (msg.type === 'clear_audio') {
                        clearAudioQueue();
                        addTranscript('system', '⚡ Barge-in detected — audio cleared');
                        setState(STATE.LISTENING);
                    } else if (msg.type === 'transcript') {
                        addTranscript('user', msg.text);
                        setState(STATE.PROCESSING);
                    } else if (msg.type === 'response') {
                        addTranscript('agent', msg.text);
                    } else if (msg.type === 'tool_call') {
                        addTranscript('system', `▶ Tool called: ${msg.name}`);
                        if (msg.name === 'create_ticket' && msg.result) {
                            addTicket(msg.result);
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
    clearAudioQueue();
    stopSessionTimer();

    // Reset UI
    setState(STATE.IDLE);
    callButton.classList.remove('active', 'connecting');
    callButtonText.textContent = 'Initialize Call';
    callButton.setAttribute('aria-label', 'Start voice call');

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
