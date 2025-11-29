import React, { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

function VoiceButton() {
    const [backendConnected, setBackendConnected] = useState(false);
    const [greeted, setGreeted] = useState(false);

    // Check backend status
    const checkStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (res.ok) {
                setBackendConnected(true);
            }
        } catch {
            setBackendConnected(false);
        }
    }, []);

    useEffect(() => {
        checkStatus();
        const interval = setInterval(checkStatus, 5000);
        return () => clearInterval(interval);
    }, [checkStatus]);

    const playAudio = async (url) => {
        if (url) {
            const audio = new Audio(`${API_BASE}${url}`);
            await audio.play();
        }
    };

    const playGreeting = async () => {
        try {
            const res = await fetch(`${API_BASE}/start-conversation`);
            const data = await res.json();
            await playAudio(data.audio_url);
            setGreeted(true);
        } catch (e) {
            console.error('Greeting error:', e);
        }
    };

    const recordAudio = async () => {
        if (!greeted){
            playGreeting()
        }
    }

    return (
        <div className="voice-assistant">
            <h1>📅 Calendar Voice Assistant</h1>
            
            <div className="status-panel">
                <div className={`status-item ${backendConnected ? 'connected' : 'disconnected'}`}>
                    {backendConnected ? '✅' : '❌'} Backend
                </div>
            </div>

            <div className="controls">
                <button
                    onClick={recordAudio}
                    disabled={!backendConnected}
                >
                    <span>Press to speak</span>
                </button>
            </div>
        </div>
    );
}

export default VoiceButton;
