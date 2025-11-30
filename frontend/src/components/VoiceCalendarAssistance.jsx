import React, { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

function VoiceCalendarAssistance() {
    const [backendConnected, setBackendConnected] = useState(false);
    const [greeted, setGreeted] = useState(false);
    const [conversationHistory, setConversationHistory] = useState([]);
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [calendarConnected, setCalendarConnected] = useState(false);
    const [isLoggingIn, setIsLoggingIn] = useState(false);
    const [isAudioPlaying, setIsAudioPlaying] = useState(false);


    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const currentAudioRef = useRef(null);
    const cancelRecordingRef = useRef(false);

    // Check backend status
    const checkStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (res.ok) {
                const data = await res.json();
                setBackendConnected(true);
                setCalendarConnected(data.logged_in);
            }
        } catch {
            setBackendConnected(false);
            setCalendarConnected(false);
        }
    }, []);

    useEffect(() => {
        checkStatus();
        const interval = setInterval(checkStatus, 5000);
        return () => clearInterval(interval);
    }, [checkStatus]);

    useEffect(() => {
        let interval;
        if (isLoggingIn) {
            interval = setInterval(async () => {
                try {
                    const res = await fetch(`${API_BASE}/check-login`);
                    const data = await res.json();
                    if (data.logged_in) {
                        setCalendarConnected(true);
                        setIsLoggingIn(false);
                        addToHistory('System', 'Connected to Google Calendar!');
                    }
                } catch (e) {
                    console.error('Login check error:', e);
                }
            }, 2000);
        }
        return () => interval && clearInterval(interval);
    }, [isLoggingIn]);

    const playAudio = async (url) => {
        if (url) {
            stopAudio();
            const audio = new Audio(`${API_BASE}${url}`);
            currentAudioRef.current = audio;
            
            setIsAudioPlaying(true);

            audio.onended = () => {
                currentAudioRef.current = null;
                setIsAudioPlaying(false);
            };
            await audio.play();
        }
    };

    const stopAudio = () => {
        if (currentAudioRef.current) {
            currentAudioRef.current.pause();
            currentAudioRef.current = null;
            setIsAudioPlaying(false);
        }
    };

    const playGreeting = async () => {
        try {
            const res = await fetch(`${API_BASE}/start-conversation`);
            const data = await res.json();
            addToHistory('Assistant', data.message);
            await playAudio(data.audio_url);
            setGreeted(true);
        } catch (e) {
            console.error('Greeting error:', e);
        }
    };

    const checkCalendarLogin = async () => {
        try {
            const res = await fetch(`${API_BASE}/login-status`);
            const data = await res.json();
            
            if (!data.logged_in) {
                addToHistory('Assistant', data.message);
                if (data.audio_url) {
                    await playAudio(data.audio_url);
                }
                setIsLoggingIn(true);
                return false;
            }
            return true;
        } catch (e) {
            console.error('Login check error:', e);
            return false;
        }
    };

    const addToHistory = (role, message) => {
        setConversationHistory(prev => [...prev, { role, message, time: new Date() }]);
    };

    const startRecording = async () => {
        stopAudio();

        if (!calendarConnected) {
            const isLoggedIn = await checkCalendarLogin();
            if (!isLoggedIn) {
                return;
            }
        }

        if (!greeted) {
            await playGreeting();
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    audioChunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const wasCancelled = cancelRecordingRef.current;
                cancelRecordingRef.current = false;
                if (wasCancelled) {
                    addToHistory("System", "Recording cancelled");
                    return;
                }
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                stream.getTracks().forEach(track => track.stop());
                await sendAudioToBackend(audioBlob);
            };

            mediaRecorder.start();
            setIsRecording(true);
        } catch (e) {
            console.error('Microphone error:', e);
            addToHistory('System', 'Could not access microphone');
        }
    };

    const sendAudioToBackend = async (audioBlob) => {
        setIsProcessing(true);

        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            const res = await fetch(`${API_BASE}/schedule`, {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            
            if (data.transcript) {
                addToHistory('User', data.transcript);
            }
            
            addToHistory('Assistant', data.message);
            
            if (data.audio_url) {
                await playAudio(data.audio_url);
            }
        } catch (e) {
            const msg = 'Error processing audio';
            addToHistory('System', msg);
        } finally {
            setIsProcessing(false);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    return (
        <div className="voice-assistant">
            <h1>📅 Voice Calendar Assistant</h1>
            
            <div className="status-panel">
                <div className={`status-item ${backendConnected ? 'connected' : 'disconnected'}`}>
                    {backendConnected ? '✅ Backend' : '❌ Backend'}
                </div>
                <div className={`status-item ${calendarConnected ? 'connected' : 'disconnected'}`}>
                    {calendarConnected ? '✅ Calendar' : '❌ Calendar'}
                </div>
            </div>

            <div className="controls">
                <button
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={!backendConnected || isLoggingIn}
                    className={`voice-button ${isRecording ? 'recording' : ''}`}
                >
                    {isProcessing
                        ? 'Processing...'
                        : isLoggingIn
                            ? 'Waiting for login...'
                            : isRecording
                                ? 'Stop Recording'
                                : 'Start Voice Conversation'}
                </button>

                <button
                onClick={() => {
                    if (isRecording) {
                        cancelRecordingRef.current = true;
                    }
                    stopRecording();
                    stopAudio();
                }}
                className="stop-button"
                disabled={!isRecording && !isAudioPlaying}
                >
                {isRecording
                ? "Cancel Recording"
                : isAudioPlaying
                    ? "Stop Audio"
                    : "-"}
                </button>
            </div>

            <h3>Conversation</h3>
            <div className="history-list">
                {conversationHistory.map((item, i) => (
                    <div key={i} className={`history-item ${item.role}`}>
                        <strong>{item.role}:</strong> {item.message}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default VoiceCalendarAssistance;