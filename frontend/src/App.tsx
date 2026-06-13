import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  Sparkles,
  Send,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  Check,
  MessageSquare,
  Briefcase,
  AlertCircle,
  Info,
  Award,
  Volume2,
  Mic,
  MicOff
} from 'lucide-react';
import Tesseract from 'tesseract.js';

const API_BASE = "http://localhost:8000";

interface ChatMessage {
  sender: 'ai' | 'user';
  message: string;
  evaluation?: string;
}

interface QABreakdown {
  question: string;
  answer: string;
  feedback: string;
}

interface FinalFeedback {
  overall_score: number;
  verdict: string;
  summary: string;
  strengths: string[];
  improvements: string[];
  technical_skills_rating: number;
  technical_skills_comments: string;
  communication_skills_rating: number;
  communication_skills_comments: string;
  qa_breakdown: QABreakdown[];
}

interface SessionReport {
  candidate_name: string;
  candidate_email: string;
  target_role: string;
  status: string;
  created_at: string;
  final_feedback: FinalFeedback;
  transcript: {
    sender: 'ai' | 'user';
    message: string;
    evaluation?: string;
    timestamp: string;
  }[];
}

export default function App() {
  // Navigation states
  const [step, setStep] = useState<'upload' | 'chat' | 'report'>('upload');

  // App config states
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [targetRole, setTargetRole] = useState<string>('Software Engineer');
  const [experienceYears, setExperienceYears] = useState<number>(3);
  const [totalQuestions] = useState<number>(5);

  // Upload states
  const [candidateName, setCandidateName] = useState<string>('');
  const [candidateEmail, setCandidateEmail] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState<string>('');
  const [isPasteMode] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string>('');

  // Client-side OCR states
  const [isOcrLoading, setIsOcrLoading] = useState<boolean>(false);
  const [ocrProgress, setOcrProgress] = useState<number>(0);
  const [ocrStatus, setOcrStatus] = useState<string>('');

  // Chat states
  const [sessionId, setSessionId] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<string>('');
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);
  const [userAnswer, setUserAnswer] = useState<string>('');
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState<boolean>(false);
  const [lastAnswerEvaluation, setLastAnswerEvaluation] = useState<string>('');

  // Voice & Timer states
  const [isVoiceMode, setIsVoiceMode] = useState<boolean>(true);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(0);
  const [timerType, setTimerType] = useState<'idle' | 'speech' | null>(null);

  const countdownIntervalRef = useRef<any>(null);
  const recognitionRef = useRef<any>(null);
  const userAnswerRef = useRef<string>('');
  const candidateNameRef = useRef<string>('');
  const activeUtteranceRef = useRef<any>(null);
  const nudgeTriggeredRef = useRef<boolean>(false);

  // Update ref whenever candidateName changes to avoid stale closures in timers
  useEffect(() => {
    candidateNameRef.current = candidateName;
  }, [candidateName]);

  // Update ref whenever userAnswer changes to avoid stale closures in timers
  useEffect(() => {
    userAnswerRef.current = userAnswer;
  }, [userAnswer]);

  // Clean up all voice activities on component unmount
  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
    };
  }, []);

  // Initialize browser Speech Recognition
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-US';

      rec.onresult = (event: any) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setUserAnswer(prev => {
            const trimmed = prev.trim();
            return trimmed ? `${trimmed} ${finalTranscript.trim()}` : finalTranscript.trim();
          });
        }
      };

      rec.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        if (event.error === 'not-allowed') {
          setUploadError("Microphone permission denied. Please allow mic access.");
          setIsListening(false);
        }
      };

      rec.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = rec;
    }
  }, []);

  // Report states
  const [report, setReport] = useState<SessionReport | null>(null);
  const [isReportLoading, setIsReportLoading] = useState<boolean>(false);

  // History states
  const [pastSessions, setPastSessions] = useState<any[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState<boolean>(false);

  // Chat scroll anchor
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Drag over state
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fetchPastSessions = async () => {
    setIsHistoryLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/sessions`);
      if (res.ok) {
        const data = await res.json();
        setPastSessions(data);
      }
    } catch (err) {
      console.error("Failed to fetch past sessions:", err);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  // Check backend status and demo mode on mount
  useEffect(() => {
    fetch(`${API_BASE}/`)
      .then(res => res.json())
      .then(data => {
        setIsDemoMode(data.demo_mode);
      })
      .catch(err => {
        console.error("Failed to connect to backend:", err);
        setIsDemoMode(true); // default to demo mode if backend is down
      });
    fetchPastSessions();
  }, [step]);

  const handleViewReport = async (sid: string) => {
    setIsReportLoading(true);
    setStep('report');
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sid}/report`);
      if (res.ok) {
        const data = await res.json();
        setReport(data);
      }
    } catch (err) {
      console.error("Error loading report:", err);
    } finally {
      setIsReportLoading(false);
    }
  };

  // Scroll to bottom of chat messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, currentQuestion]);

  // Voice & TTS / STT helper methods
  const startCountdown = (duration: number, type: 'idle' | 'speech', onComplete: () => void) => {
    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    
    setSecondsRemaining(duration);
    setTimerType(type);

    countdownIntervalRef.current = setInterval(() => {
      setSecondsRemaining(prev => {
        if (prev <= 1) {
          clearInterval(countdownIntervalRef.current!);
          countdownIntervalRef.current = null;
          setTimerType(null);
          onComplete();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const stopCountdown = () => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    setTimerType(null);
    setSecondsRemaining(0);
  };

  const speakText = (text: string, onEndCallback?: () => void) => {
    if (!isVoiceMode) {
      if (onEndCallback) onEndCallback();
      return;
    }

    // Safely detach callback references on previous utterance to prevent duplicate trigger bugs
    if (activeUtteranceRef.current) {
      activeUtteranceRef.current.onend = null;
      activeUtteranceRef.current.onerror = null;
    }
    window.speechSynthesis.cancel();
    setIsSpeaking(true);

    const cleanText = text.replace(/[*#_`]/g, '').trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    activeUtteranceRef.current = utterance;

    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => v.lang.startsWith('en'));
    if (englishVoice) {
      utterance.voice = englishVoice;
    }

    utterance.onend = () => {
      setIsSpeaking(false);
      activeUtteranceRef.current = null;
      if (onEndCallback) onEndCallback();
    };

    utterance.onerror = (e) => {
      console.error("Speech synthesis error:", e);
      setIsSpeaking(false);
      activeUtteranceRef.current = null;
      if (onEndCallback) onEndCallback();
    };

    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if (activeUtteranceRef.current) {
      activeUtteranceRef.current.onend = null;
      activeUtteranceRef.current.onerror = null;
    }
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    activeUtteranceRef.current = null;
  };

  const startListening = () => {
    stopSpeaking();
    stopCountdown();

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        
        startCountdown(15, 'speech', () => {
          if (recognitionRef.current) {
            try {
              recognitionRef.current.stop();
            } catch (e) {}
          }
          setIsListening(false);
          
          const finalAnswer = userAnswerRef.current.trim() || "Candidate did not respond.";
          setUserAnswer('');
          fetchNextQuestion(sessionId, finalAnswer);
        });
      } catch (err) {
        console.error("Failed to start Speech Recognition:", err);
      }
    } else {
      setUploadError("Speech recognition is not supported in this browser. Please use Google Chrome.");
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
    setIsListening(false);
    stopCountdown();
  };

  const toggleMic = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleAiSpeakingFinished = (questionIdx: number) => {
    if (!isVoiceMode) return;

    startCountdown(10, 'idle', () => {
      if (questionIdx === 0) {
        if (!nudgeTriggeredRef.current) {
          nudgeTriggeredRef.current = true;
          const nudgeMessage = `Are you there, ${candidateNameRef.current || 'Candidate'}?`;
          
          setChatHistory(prev => [
            ...prev,
            { sender: 'ai', message: nudgeMessage }
          ]);
          
          speakText(nudgeMessage);
        }
      } else {
        const skipMessage = "Okay, let's leave that question. Let's move on.";
        
        setChatHistory(prev => [
          ...prev,
          { sender: 'ai', message: skipMessage }
        ]);

        speakText(skipMessage, () => {
          setUserAnswer('');
          fetchNextQuestion(sessionId, "Candidate did not respond.");
        });
      }
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      validateAndSetFile(droppedFile);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    const allowed = ['pdf', 'png', 'jpg', 'jpeg', 'webp'];

    if (ext && allowed.includes(ext)) {
      setFile(selectedFile);
      setUploadError('');
    } else {
      setUploadError('Invalid file format. Please upload a PDF or an image (PNG, JPG, JPEG, WEBP).');
    }
  };

  // Run Tesseract.js client side OCR
  const runClientSideOcr = async (imageFile: File): Promise<string> => {
    setIsOcrLoading(true);
    setOcrStatus('Initializing OCR engine...');
    setOcrProgress(0);

    try {
      const result = await Tesseract.recognize(
        imageFile,
        'eng',
        {
          logger: m => {
            if (m.status === 'recognizing') {
              setOcrProgress(Math.round(m.progress * 100));
              setOcrStatus(`Reading resume: ${Math.round(m.progress * 100)}%`);
            }
          }
        }
      );

      setIsOcrLoading(false);
      return result.data.text;
    } catch (err: any) {
      setIsOcrLoading(false);
      throw new Error(`OCR processing failed: ${err.message || err}`);
    }
  };

  const startInterviewWithText = async (extractedText: string) => {
    setIsUploading(true);
    try {
      const response = await fetch(`${API_BASE}/api/start-interview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          candidate_name: candidateName || 'Candidate',
          candidate_email: candidateEmail || '',
          target_role: `${targetRole} (${experienceYears === 15 ? '15+' : experienceYears} Years Experience)`,
          resume_text: extractedText,
          total_questions: totalQuestions,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start interview session.');
      }

      const data = await response.json();
      setSessionId(data.session_id);

      // Successfully started session, now trigger the first question
      await fetchNextQuestion(data.session_id, null);
      setStep('chat');
    } catch (err: any) {
      setUploadError(err.message || 'An error occurred.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadError('Please select a resume file to proceed.');
      return;
    }

    setUploadError('');

    // 1. Text Paste Mode
    if (isPasteMode && pasteText) {
      await startInterviewWithText(pasteText);
      return;
    }

    // 2. File Upload Mode
    if (file) {
      setIsUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      formData.append('target_role', `${targetRole} (${experienceYears === 15 ? '15+' : experienceYears} Years Experience)`);
      formData.append('total_questions', totalQuestions.toString());

      try {
        const response = await fetch(`${API_BASE}/api/upload-resume`, {
          method: 'POST',
          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Failed to upload resume.');
        }

        // Handle case where backend requests client side OCR (e.g. image or scanned PDF)
        if (data.status === 'client_ocr_required') {
          // If it's an image, we can run OCR immediately
          const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name);
          if (isImage) {
            setIsUploading(false);
            const ocrText = await runClientSideOcr(file);
            if (!ocrText || ocrText.trim().length < 50) {
              throw new Error("OCR extracted too little text. Please try copy-pasting your resume text directly.");
            }
            await startInterviewWithText(ocrText);
          } else {
            // It's a scanned PDF
            setIsUploading(false);
            setUploadError("This PDF appears to be scanned. Please upload your resume as an image (PNG/JPG) to run automatic in-browser OCR scanning, or upload a text-based PDF.");
          }
          return;
        }

        // Standard upload succeeded
        setSessionId(data.session_id);
        if (data.details && data.details.candidate_name && data.details.candidate_name !== 'Candidate') {
          setCandidateName(data.details.candidate_name);
        }
        if (data.details && data.details.candidate_email) {
          setCandidateEmail(data.details.candidate_email);
        }

        // Fetch the first question
        await fetchNextQuestion(data.session_id, null);
        setStep('chat');

      } catch (err: any) {
        setUploadError(err.message || 'An error occurred during upload.');
      } finally {
        setIsUploading(false);
      }
    }
  };

  const fetchNextQuestion = async (sessId: string, answer: string | null) => {
    setIsSubmittingAnswer(true);
    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessId}/next-question`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: answer !== null ? JSON.stringify({ answer }) : undefined,
      });

      if (!response.ok) {
        throw new Error('Failed to fetch next question.');
      }

      const data = await response.json();

      if (data.status === 'completed') {
        // Show report
        setStep('report');
        await fetchReport(sessId);
      } else {
        // Ongoing chat
        if (answer !== null) {
          // Candidate answered, update conversation history with user message + evaluation
          setChatHistory(prev => [
            ...prev,
            { sender: 'user', message: answer }
          ]);
        }

        // Add AI question
        setCurrentQuestion(data.question);
        setCurrentQuestionIndex(data.question_index);
        setLastAnswerEvaluation(data.evaluation || '');

        setChatHistory(prev => [
          ...prev,
          { sender: 'ai', message: data.question, evaluation: data.evaluation }
        ]);

        nudgeTriggeredRef.current = false;

        if (isVoiceMode) {
          stopCountdown();
          speakText(data.question, () => {
            handleAiSpeakingFinished(data.question_index);
          });
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleSendAnswer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userAnswer.trim() || isSubmittingAnswer) return;

    stopSpeaking();
    stopListening();
    stopCountdown();

    const answerToSend = userAnswer.trim();
    setUserAnswer('');
    fetchNextQuestion(sessionId, answerToSend);
  };

  const fetchReport = async (sessId: string) => {
    setIsReportLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessId}/report`);
      if (!response.ok) throw new Error("Failed to load evaluation report.");

      const data = await response.json();
      setReport(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsReportLoading(false);
    }
  };

  const resetInterview = () => {
    stopSpeaking();
    stopListening();
    stopCountdown();

    setStep('upload');
    setFile(null);
    setPasteText('');
    setCandidateName('');
    setCandidateEmail('');
    setSessionId('');
    setChatHistory([]);
    setCurrentQuestion('');
    setCurrentQuestionIndex(0);
    setUserAnswer('');
    setReport(null);
    setUploadError('');
    setOcrProgress(0);
    setOcrStatus('');
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-icon">
            <Sparkles size={20} />
          </div>
          <span className="logo-text">AI Interviewer</span>
        </div>

        <div className={`api-badge ${isDemoMode ? 'demo' : ''}`}>
          <span className="dot"></span>
          <span>{isDemoMode ? 'Demo Mode (Mock AI)' : 'Gemini AI Active'}</span>
        </div>
      </header>

      {/* Main Container */}
      <main className="main-content">

        {/* STEP 1: UPLOAD & SETUP */}
        {step === 'upload' && (
          <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
            <div className="hero-section">
              <h1 className="hero-title">Practice Interviews, Led by AI</h1>
              <p className="hero-subtitle">
                Upload your resume, select a target role, and conduct a simulated,
                high-fidelity technical interview with detailed feedback reports.
              </p>
            </div>

            <div className="glass-card">
              <form onSubmit={handleUploadSubmit}>

                {/* Meta details */}
                <div className="grid-2 mb-2">
                  <div className="form-group">
                    <label className="form-label flex-gap-2">
                      <Briefcase size={16} /> Target Job Role
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Software Engineer, React Developer"
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      Years of Experience: <strong style={{ color: 'var(--primary)' }}>{experienceYears === 15 ? '15+ Years' : `${experienceYears} Years`}</strong>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="15"
                      value={experienceYears}
                      onChange={(e) => setExperienceYears(Number(e.target.value))}
                      className="form-input"
                      style={{ padding: '0.25rem', height: 'auto', background: 'transparent' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                      <span>0 Years</span>
                      <span>5 Years</span>
                      <span>10 Years</span>
                      <span>15+ Years</span>
                    </div>
                  </div>
                </div>

                <div
                  className={`upload-zone ${isDragOver ? 'dragover' : ''}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => document.getElementById('resume-file-input')?.click()}
                  style={{ marginTop: '1.5rem' }}
                >
                  <input
                    type="file"
                    id="resume-file-input"
                    style={{ display: 'none' }}
                    accept=".pdf,.png,.jpg,.jpeg,.webp"
                    onChange={handleFileChange}
                  />

                  <div className="upload-icon">
                    <Upload size={32} />
                  </div>
                  {file ? (
                    <div>
                      <p style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{file.name}</p>
                      <p style={{ fontSize: '0.85rem' }}>{(file.size / (1024 * 1024)).toFixed(2)} MB • Click to replace</p>
                    </div>
                  ) : (
                    <div>
                      <p style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Drag and drop your resume here</p>
                      <p style={{ fontSize: '0.85rem' }}>Supports PDF, PNG, JPG, JPEG, WEBP</p>
                    </div>
                  )}
                </div>

                {/* Error message */}
                {uploadError && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.5rem',
                    color: 'var(--danger)',
                    background: 'var(--danger-bg)',
                    padding: '1rem',
                    borderRadius: '8px',
                    marginTop: '1.5rem',
                    fontSize: '0.9rem',
                    textAlign: 'left'
                  }}>
                    <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                    <span>{uploadError}</span>
                  </div>
                )}

                {/* Client Side OCR Progress */}
                {isOcrLoading && (
                  <div className="ocr-progress-container">
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', fontWeight: 500 }}>
                      <span className="flex-gap-2">
                        <RefreshCw size={14} className="loader" /> {ocrStatus}
                      </span>
                      <span>{ocrProgress}%</span>
                    </div>
                    <div className="progress-bar-bg">
                      <div className="progress-bar-fill" style={{ width: `${ocrProgress}%` }}></div>
                    </div>
                  </div>
                )}

                {/* Submit button */}
                <button
                  type="submit"
                  className="btn btn-primary mt-3"
                  style={{ width: '100%', padding: '0.9rem' }}
                  disabled={isUploading || isOcrLoading || !file}
                >
                  {isUploading ? (
                    <>
                      <RefreshCw size={18} className="loader" />
                      <span>Analyzing Resume & Launching Session...</span>
                    </>
                  ) : isOcrLoading ? (
                    <span>Running In-Browser OCR scanning...</span>
                  ) : (
                    <>
                      <Sparkles size={18} />
                      <span>Start Mock Interview</span>
                    </>
                  )}
                </button>

              </form>
            </div>

            <div style={{ marginTop: '2rem', textAlign: 'left', opacity: 0.75, fontSize: '0.85rem' }} className="glass-card">
              <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem' }} className="flex-gap-2">
                <Info size={14} /> Technology Architecture Notes
              </h4>
              <p className="mb-1">
                <strong>Digital PDF Text Extraction:</strong> Performed instantly on the backend using python's <code>pypdf</code> library.
              </p>
              <p>
                <strong>Scanned Document OCR:</strong> If you upload a scanned image or image-only PDF, the application triggers <code>tesseract.js</code> to run OCR directly in your browser. This bypasses the need for local system-level Tesseract binaries!
              </p>
            </div>

            {/* Past Interviews History (Always visible on start/front page) */}
            <div className="glass-card" style={{ textAlign: 'left', marginTop: '1.5rem' }}>
              <h3 style={{ fontSize: '1.2rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)' }}>
                <Award size={20} /> Past Interview Reports
              </h3>
              {isHistoryLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                  <RefreshCw size={14} className="loader" />
                  <span>Loading history...</span>
                </div>
              ) : pastSessions.length === 0 ? (
                <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic', margin: 0 }}>
                  No past interview reports found. Start an interview above to generate your first report!
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {pastSessions.map((s) => (
                    <div
                      key={s.session_id}
                      onClick={() => handleViewReport(s.session_id)}
                      style={{
                        padding: '1rem',
                        borderRadius: '8px',
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--border-color)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                        e.currentTarget.style.borderColor = 'var(--primary)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                        e.currentTarget.style.borderColor = 'var(--border-color)';
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div>
                          <h4 style={{ fontSize: '1rem', margin: 0, color: 'var(--text-primary)' }}>{s.target_role}</h4>
                          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                            Candidate: {s.candidate_name || 'Candidate'} {s.candidate_email ? `(${s.candidate_email})` : ''}
                          </p>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{
                            fontSize: '1.1rem',
                            fontWeight: 700,
                            color: s.final_feedback?.overall_score >= 80 ? '#10B981' : s.final_feedback?.overall_score >= 70 ? '#F59E0B' : '#EF4444'
                          }}>
                            Score: {s.final_feedback?.overall_score || '70'}
                          </span>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0.1rem 0 0 0' }}>
                            {new Date(s.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      {s.final_feedback?.verdict && (
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                          <span style={{
                            padding: '0.1rem 0.4rem',
                            borderRadius: '4px',
                            background: 'rgba(255,255,255,0.06)',
                            color: 'var(--text-secondary)'
                          }}>
                            Verdict: <strong style={{ color: 'var(--text-primary)' }}>{s.final_feedback.verdict}</strong>
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 2: INTERVIEW CHAT */}
        {step === 'chat' && (
          <div className="interview-layout">

            {/* Sidebar info */}
            <div className="sidebar-panel">
              <div className="glass-card interview-stats-card">
                <div className="ai-avatar-container">
                  <div className="ai-orb pulse">
                    <div className="ai-orb-inner">
                      <MessageSquare size={28} style={{ color: 'var(--primary)' }} />
                    </div>
                  </div>
                  <div>
                    <h3 style={{ marginBottom: '0.25rem' }}>AI Interviewer</h3>
                    <div className="status-label">Active Session</div>
                  </div>
                </div>

                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.25rem', textAlign: 'left' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.9rem' }}>
                    <div>
                      <span style={{ color: 'var(--text-tertiary)' }}>Role: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{targetRole}</strong>
                    </div>
                    {candidateName && (
                      <div>
                        <span style={{ color: 'var(--text-tertiary)' }}>Candidate: </span>
                        <strong style={{ color: 'var(--text-primary)' }}>{candidateName}</strong>
                      </div>
                    )}
                    <div>
                      <span style={{ color: 'var(--text-tertiary)' }}>Total Questions: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{totalQuestions}</strong>
                    </div>
                  </div>
                </div>

                {/* Feedback Indicator of Last Response */}
                {lastAnswerEvaluation && (
                  <div style={{
                    marginTop: '1.5rem',
                    paddingTop: '1.25rem',
                    borderTop: '1px solid var(--border-color)',
                    textAlign: 'left'
                  }}>
                    <h5 className="flex-gap-2 mb-1" style={{ color: 'var(--accent-pink)', fontSize: '0.85rem', textTransform: 'uppercase' }}>
                      <TrendingUp size={14} /> Real-time Evaluation
                    </h5>
                    <p style={{ fontSize: '0.8rem', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                      "{lastAnswerEvaluation}"
                    </p>
                  </div>
                )}
              </div>

              <button
                onClick={resetInterview}
                className="btn btn-secondary"
                style={{ width: '100%' }}
              >
                End Session Early
              </button>
            </div>

            {/* Chat Screen */}
            <div className="glass-card chat-panel">
              <div className="chat-header">
                <div>
                  <h3>Technical Interview Screen</h3>
                  <p style={{ fontSize: '0.8rem' }}>Answer each question thoroughly. Take your time.</p>
                </div>
                <div className="progress-indicator">
                  <span>Question {Math.min(currentQuestionIndex + 1, totalQuestions)} of {totalQuestions}</span>
                  <div style={{ width: '80px', height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      background: 'var(--grad-primary)',
                      width: `${((currentQuestionIndex) / totalQuestions) * 100}%`,
                      transition: 'width 0.3s ease'
                    }}></div>
                  </div>
                </div>
              </div>

              {/* Voice controls panel */}
              <div className="voice-controls-bar" style={{ margin: '0.75rem 1.5rem 0 1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', width: '100%' }}>
                  <button 
                    type="button" 
                    onClick={() => setIsVoiceMode(prev => {
                      const next = !prev;
                      if (!next) {
                        stopSpeaking();
                        stopListening();
                        stopCountdown();
                      } else {
                        if (currentQuestion) {
                          speakText(currentQuestion, () => {
                            handleAiSpeakingFinished(currentQuestionIndex);
                          });
                        }
                      }
                      return next;
                    })}
                    className={`voice-mode-toggle ${isVoiceMode ? 'active' : ''}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.4rem 0.8rem',
                      borderRadius: '20px',
                      border: '1px solid var(--border-color)',
                      background: isVoiceMode ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
                      color: isVoiceMode ? '#c084fc' : 'var(--text-secondary)',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <Volume2 size={14} />
                    <span>{isVoiceMode ? 'Voice Mode: ON' : 'Voice Mode: OFF'}</span>
                  </button>

                  {isVoiceMode && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.8rem', flexGrow: 1, justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {isSpeaking ? (
                          <span style={{ color: 'var(--accent-pink)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span className="dot pulse" style={{ backgroundColor: 'var(--accent-pink)' }}></span>
                            AI is speaking...
                            <button 
                              type="button" 
                              onClick={stopSpeaking} 
                              style={{ 
                                background: 'rgba(255,255,255,0.1)', 
                                border: 'none', 
                                color: 'var(--text-primary)', 
                                padding: '0.15rem 0.4rem', 
                                borderRadius: '4px',
                                fontSize: '0.7rem',
                                cursor: 'pointer',
                                marginLeft: '0.5rem'
                              }}
                            >
                              Skip
                            </button>
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-tertiary)' }}>AI Finished Speaking</span>
                        )}
                      </div>

                      {timerType && (
                        <span style={{ 
                          color: timerType === 'idle' ? 'var(--warning)' : '#10b981', 
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem'
                        }}>
                          <span className="dot pulse" style={{ backgroundColor: timerType === 'idle' ? 'var(--warning)' : '#10b981' }}></span>
                          {timerType === 'idle' ? `Idle Nudge in: ${secondsRemaining}s` : `Recording... Time left: ${secondsRemaining}s`}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Chat Transcript Area */}
              <div className="chat-messages">
                {chatHistory.map((msg, index) => {
                  // Only display user messages and AI questions, don't show the initial prompt evaluations as standard chat bubbles.
                  // Except the actual questions.
                  const isUser = msg.sender === 'user';

                  return (
                    <div
                      key={index}
                      className={`message-bubble ${isUser ? 'candidate' : 'ai'}`}
                    >
                      {msg.message}
                    </div>
                  );
                })}

                {/* Submitting indicator */}
                {isSubmittingAnswer && (
                  <div className="message-bubble ai flex-gap-2">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>AI is evaluating and preparing question...</span>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Chat Input */}
              <div className="chat-input-area">
                <form onSubmit={handleSendAnswer} className="chat-input-form" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  {isVoiceMode && (
                    <button
                      type="button"
                      onClick={toggleMic}
                      className={`mic-btn ${isListening ? 'active' : ''}`}
                      disabled={isSpeaking || isSubmittingAnswer}
                      title={isListening ? "Stop listening" : "Start speaking"}
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        flexShrink: 0
                      }}
                    >
                      {isListening ? <MicOff size={20} /> : <Mic size={20} />}
                    </button>
                  )}
                  <textarea
                    className="chat-textarea"
                    placeholder={isListening ? "Listening... Speak your answer now." : "Type your response here..."}
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendAnswer(e);
                      }
                    }}
                    disabled={isSubmittingAnswer}
                  />
                  <button
                    type="submit"
                    className="chat-send-btn"
                    disabled={isSubmittingAnswer || !userAnswer.trim()}
                  >
                    <Send size={18} />
                  </button>
                </form>
              </div>

            </div>

          </div>
        )}

        {/* STEP 3: FINAL REPORT */}
        {step === 'report' && (
          <div style={{ maxWidth: '900px', margin: '0 auto', width: '100%' }}>

            {isReportLoading ? (
              <div className="glass-card text-center" style={{ padding: '5rem 2rem' }}>
                <RefreshCw size={48} className="loader" style={{ margin: '0 auto 1.5rem auto' }} />
                <h2>Compiling Your Interview Evaluation Report...</h2>
                <p className="mt-2">Generating scores, reviewing communication metrics, and structuring suggestions.</p>
              </div>
            ) : report && report.final_feedback ? (
              <div>

                <div className="report-header">
                  <h1 className="hero-title">Interview Summary Report</h1>
                  <p className="hero-subtitle">Candidate: {report.candidate_name || 'Candidate'} • Role: {report.target_role}</p>
                </div>

                {/* Score & Summary */}
                <div className="glass-card mb-3 text-center">
                  <div className="score-circle-container">
                    <div className="score-circle" style={{ '--score': report.final_feedback.overall_score } as any}>
                      <div className="score-value">
                        <span className="score-num">{report.final_feedback.overall_score}</span>
                        <span className="score-label">Overall Score</span>
                      </div>
                    </div>
                  </div>

                  <div className={`verdict-badge ${report.final_feedback.verdict.toLowerCase().replace(' ', '-')}`}>
                    Verdict: {report.final_feedback.verdict}
                  </div>

                  <p className="report-summary-text mt-3">
                    {report.final_feedback.summary}
                  </p>
                </div>

                {/* Strengths & Improvements */}
                <div className="grid-2 mb-3">
                  <div className="glass-card" style={{ height: '100%' }}>
                    <h3 className="mb-3 flex-gap-2" style={{ color: 'var(--success)' }}>
                      <CheckCircle2 size={20} /> Key Strengths
                    </h3>
                    <ul className="bullet-list">
                      {report.final_feedback.strengths.map((str, idx) => (
                        <li key={idx} className="bullet-item strength">
                          <Check size={16} className="bullet-icon" />
                          <span>{str}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="glass-card" style={{ height: '100%' }}>
                    <h3 className="mb-3 flex-gap-2" style={{ color: 'var(--warning)' }}>
                      <AlertTriangle size={20} /> Areas for Improvement
                    </h3>
                    <ul className="bullet-list">
                      {report.final_feedback.improvements.map((imp, idx) => (
                        <li key={idx} className="bullet-item improvement">
                          <AlertTriangle size={16} className="bullet-icon" />
                          <span>{imp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Technical & Communication Metrics */}
                <div className="glass-card mb-3">
                  <h3 className="mb-3">Skills Assessment</h3>

                  <div className="rating-bar-container">
                    <div className="rating-header">
                      <span>Technical Competence</span>
                      <span>{report.final_feedback.technical_skills_rating} / 10</span>
                    </div>
                    <div className="rating-bar-bg">
                      <div className="rating-bar-fill" style={{ width: `${report.final_feedback.technical_skills_rating * 10}%` }}></div>
                    </div>
                    <p style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>{report.final_feedback.technical_skills_comments}</p>
                  </div>

                  <div className="rating-bar-container" style={{ marginTop: '1.5rem' }}>
                    <div className="rating-header">
                      <span>Communication & Clarity</span>
                      <span>{report.final_feedback.communication_skills_rating} / 10</span>
                    </div>
                    <div className="rating-bar-bg">
                      <div className="rating-bar-fill" style={{ width: `${report.final_feedback.communication_skills_rating * 10}%` }}></div>
                    </div>
                    <p style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>{report.final_feedback.communication_skills_comments}</p>
                  </div>
                </div>

                {/* Q&A Breakdown */}
                <div className="qa-section">
                  <h3 className="mb-3 flex-gap-2"><FileText size={20} /> Question-by-Question Evaluation</h3>

                  {report.final_feedback.qa_breakdown.map((qa, index) => (
                    <div key={index} className="qa-card">
                      <div className="qa-question-header">
                        <span>Q{index + 1}:</span>
                        <span>{qa.question}</span>
                      </div>
                      <div className="qa-body">
                        <div className="qa-item">
                          <span className="qa-label">Your Response</span>
                          <span className="qa-text" style={{ fontStyle: 'italic', borderLeft: '2px solid rgba(255,255,255,0.1)', paddingLeft: '0.75rem' }}>
                            "{qa.answer}"
                          </span>
                        </div>
                        <div className="qa-item qa-feedback-box">
                          <span className="qa-label" style={{ color: 'var(--primary)', fontWeight: 700 }}>AI Evaluator Feedback</span>
                          <span className="qa-text" style={{ color: 'var(--text-primary)' }}>{qa.feedback}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="text-center mt-3" style={{ marginBottom: '3rem' }}>
                  <button
                    onClick={resetInterview}
                    className="btn btn-primary"
                    style={{ padding: '0.8rem 2.5rem' }}
                  >
                    <RefreshCw size={18} />
                    <span>Practice Another Interview</span>
                  </button>
                </div>

              </div>
            ) : (
              <div className="glass-card text-center" style={{ padding: '4rem 2rem' }}>
                <AlertCircle size={48} style={{ color: 'var(--danger)', margin: '0 auto 1rem auto' }} />
                <h2>Failed to Load Report</h2>
                <p>There was an issue loading your feedback. You can retry or return to start page.</p>
                <button onClick={resetInterview} className="btn btn-primary mt-2">Go to Start</button>
              </div>
            )}

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>© 2026 AI Interviewer Mock Screening Suite. Created for candidate screening simulation.</p>
      </footer>
    </div>
  );
}
