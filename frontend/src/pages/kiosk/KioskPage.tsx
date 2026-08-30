import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { api } from '../../api/client';
import type { IntakeQuestion, IntakeSession, MedicalDocument } from '../../types';
import {
  Volume2, Mic, MicOff, Check, ArrowRight, ArrowLeft, Upload, AlertCircle,
  Loader2, FileText, X, Activity, Stethoscope, ChevronRight, Languages
} from 'lucide-react';

type Step = 'MODE_SELECT' | 'CONSENT' | 'INTAKE' | 'DOCUMENTS' | 'REVIEW' | 'COMPLETE';

export default function KioskPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('MODE_SELECT');
  const [language, setLanguage] = useState('en');
  const [mode, setMode] = useState('STANDARD');
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleLanguageSelect = async (lang: string) => {
    setLanguage(lang);
    setStep('CONSENT');
  };

  const handleModeSelect = async (m: string) => {
    setMode(m);
    try {
      const res = await api.startIntake({ language, mode: m });
      const sess = res.data || res;
      setSession(sess);
    } catch (err) {
      console.error('Failed to start session', err);
    }
  };

  const handleConsent = async () => {
    if (!session) {
      try {
        const res = await api.startIntake({ language, mode });
        setSession(res.data || res);
      } catch (err) {
        console.error(err);
        return;
      }
    }
    try {
      await api.grantConsent({
        scope: ['history', 'documents', 'ai_processing', 'summary', 'his_share', 'abdm_share'],
        purpose: 'Clinical intake',
        language,
      });
    } catch (err) {
      console.error('Consent error:', err);
    }
    setStep('INTAKE');
  };

  const handleIntakeComplete = () => {
    setStep('DOCUMENTS');
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const res = await api.uploadDocument(file, session?.id);
      const doc = res.data || res;
      setDocuments(prev => [...prev, doc]);
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (!session) return;
    try {
      const res = await api.submitSession(session.id, {
        final_chief_complaint: undefined,
      });
      setSummary(res.data || res);
      setStep('COMPLETE');
    } catch (err) {
      console.error('Submit error:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex flex-col">
      {/* Header */}
      <header className="bg-brand-800 text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/10 rounded-lg">
            <Activity size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold">Swasthya Setu</h1>
            <p className="text-blue-200 text-sm">AI-Powered Patient Intake</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <span className="text-sm text-blue-200">{user.full_name}</span>
          )}
          <button onClick={logout} className="text-sm text-blue-200 hover:text-white transition-colors">
            Sign Out
          </button>
        </div>
      </header>

      {/* Progress bar */}
      {step !== 'MODE_SELECT' && step !== 'COMPLETE' && (
        <div className="bg-white border-b border-slate-200 px-6 py-3">
          <div className="max-w-4xl mx-auto flex items-center gap-4">
            {(['MODE_SELECT', 'CONSENT', 'INTAKE', 'DOCUMENTS', 'REVIEW'].map((s, i) => {
              const stepOrder = ['MODE_SELECT', 'CONSENT', 'INTAKE', 'DOCUMENTS', 'REVIEW'];
              const currentIdx = stepOrder.indexOf(step);
              const isActive = s === step;
              const isDone = i < currentIdx;
              const labels = ['Mode', 'Consent', 'History', 'Documents', 'Review'];
              return (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                    isDone ? 'bg-green-500 text-white' : isActive ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'
                  }`}>
                    {isDone ? <Check size={14} /> : i + 1}
                  </div>
                  <span className={`text-sm font-medium hidden sm:inline ${isActive ? 'text-brand-700' : isDone ? 'text-green-600' : 'text-slate-400'}`}>
                    {labels[i]}
                  </span>
                  {i < 4 && <div className={`flex-1 h-0.5 ${isDone ? 'bg-green-300' : 'bg-slate-200'}`} />}
                </div>
              );
            }))}
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-3xl">
          {step === 'MODE_SELECT' && (
            <ModeSelect onSelect={handleModeSelect} onLanguageChange={handleLanguageSelect} language={language} onNext={() => setStep('CONSENT')} />
          )}
          {step === 'CONSENT' && (
            <ConsentStep onAgree={handleConsent} language={language} />
          )}
          {step === 'INTAKE' && session && (
            <IntakeStep
              sessionId={session.id}
              language={language}
              mode={mode}
              onComplete={handleIntakeComplete}
            />
          )}
          {step === 'DOCUMENTS' && (
            <DocumentStep
              sessionId={session?.id}
              documents={documents}
              onUpload={handleUpload}
              uploading={uploading}
              onFinish={() => handleSubmit()}
              onSkip={() => handleSubmit()}
            />
          )}
          {step === 'COMPLETE' && (
            <CompleteStep summary={summary} onLogout={logout} />
          )}
        </div>
      </main>
    </div>
  );
}

// ---- MODE SELECT ----
function ModeSelect({ onSelect, onLanguageChange, language, onNext }: {
  onSelect: (mode: string) => void;
  onLanguageChange: (lang: string) => void;
  language: string;
  onNext: () => void;
}) {
  const [selectedLang, setSelectedLang] = useState(language);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);

  const handleContinue = () => {
    onLanguageChange(selectedLang);
    onSelect(selectedMode || 'STANDARD');
    onNext();
  };

  return (
    <div className="space-y-8 text-center">
      <div className="space-y-2">
        <h2 className="text-4xl font-bold text-slate-900">Welcome to Swasthya Setu</h2>
        <p className="text-xl text-slate-500">This will help prepare your case for the doctor</p>
      </div>

      {/* Language Selection */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-4">
        <div className="flex items-center justify-center gap-2 text-slate-700">
          <Languages size={24} />
          <h3 className="text-xl font-bold">Select Language / भाषा चुनें</h3>
        </div>
        <div className="grid grid-cols-2 gap-4 max-w-md mx-auto">
          {[
            { code: 'en', label: 'English', sub: 'English' },
            { code: 'hi', label: 'हिन्दी', sub: 'Hindi' },
          ].map((l) => (
            <button
              key={l.code}
              onClick={() => setSelectedLang(l.code)}
              className={`py-6 px-4 text-2xl font-bold rounded-xl border-2 transition-all ${
                selectedLang === l.code
                  ? 'border-brand-500 bg-brand-50 text-brand-700'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Mode Selection */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-4">
        <div className="flex items-center justify-center gap-2 text-slate-700">
          <Stethoscope size={24} />
          <h3 className="text-xl font-bold">Intake Mode</h3>
        </div>
        <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto">
          <button
            onClick={() => setSelectedMode('STANDARD')}
            className={`py-6 px-4 rounded-xl border-2 transition-all text-left ${
              selectedMode === 'STANDARD'
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-200 hover:border-slate-300'
            }`}
          >
            <div className="text-lg font-bold text-slate-900">Standard</div>
            <div className="text-sm text-slate-500 mt-1">General clinical history (SOCRATES + standard history)</div>
          </button>
          <button
            onClick={() => setSelectedMode('AYUSH')}
            className={`py-6 px-4 rounded-xl border-2 transition-all text-left ${
              selectedMode === 'AYUSH'
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-200 hover:border-slate-300'
            }`}
          >
            <div className="text-lg font-bold text-slate-900">AYUSH</div>
            <div className="text-sm text-slate-500 mt-1">Ayurvedic intake with Dashavidha Pariksha</div>
          </button>
        </div>
      </div>

      <button
        onClick={handleContinue}
        disabled={!selectedMode}
        className="w-full py-5 text-2xl font-bold bg-brand-600 text-white rounded-2xl hover:bg-brand-700 transition-all shadow-lg disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-3"
      >
        Begin Intake / शुरू करें <ArrowRight size={28} />
      </button>
    </div>
  );
}

// ---- CONSENT ----
function ConsentStep({ onAgree, language }: { onAgree: () => void; language: string }) {
  const [audioGuidance, setAudioGuidance] = useState(false);

  const playGuidance = () => {
    setAudioGuidance(true);
    const text = language === 'hi'
      ? 'हम आपका स्वास्थ्य विवरण एकत्र करेंगे। आपका डेटा सुरक्षित है और केवल आपके डॉक्टर को दिखाया जाएगा।'
      : 'We will collect your medical history to help the doctor treat you better. Your data is secure and will only be shown to your treating doctor.';
    api.synthesizeSpeech(text, language)
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
        audio.onended = () => setAudioGuidance(false);
      })
      .catch(() => setAudioGuidance(false));
  };

  return (
    <div className="space-y-8 text-center">
      <h2 className="text-4xl font-bold text-slate-900">
        {language === 'hi' ? 'सहमति' : 'Consent'}
      </h2>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-6 text-left">
        <div className="space-y-4 text-lg text-slate-700 leading-relaxed">
          <p>
            {language === 'hi'
              ? 'Swasthya Setu आपका स्वास्थ्य इतिहास एकत्र करेगा और आपके डॉक्टर के लिए एक संरचित सारांश तैयार करेगा।'
              : 'Swasthya Setu will collect your medical history and prepare a structured summary for your doctor.'}
          </p>
          <ul className="space-y-2 list-disc list-inside">
            <li>{language === 'hi' ? 'आपका डेटा एन्क्रिप्ट और सुरक्षित है' : 'Your data is encrypted and secure'}</li>
            <li>{language === 'hi' ? 'केवल आपका इलाज करने वाला डॉक्टर देखेगा' : 'Only your treating doctor will see it'}</li>
            <li>{language === 'hi' ? 'AI जानकारी इकट्ठा करता है और संरचित करता है — निदान नहीं करता' : 'AI collects and structures information — it does not diagnose'}</li>
            <li>{language === 'hi' ? 'आप कभी भी सहमति वापस ले सकते हैं' : 'You can revoke consent at any time'}</li>
          </ul>
          <p className="text-sm text-slate-500 italic">
            {language === 'hi'
              ? 'यह सहमति DPDP Act 2023 और ABDM सहमति अवधारणाओं के सिद्धांतों के अनुसार है।'
              : 'This consent follows DPDP Act 2023 and ABDM consent principles.'}
          </p>
        </div>

        <div className="flex justify-center">
          <button
            onClick={playGuidance}
            disabled={audioGuidance}
            className="p-4 bg-slate-100 rounded-full text-slate-600 hover:bg-slate-200 transition-colors"
          >
            {audioGuidance ? <Loader2 size={32} className="animate-spin" /> : <Volume2 size={32} />}
          </button>
        </div>
      </div>

      <button
        onClick={onAgree}
        className="w-full py-5 text-2xl font-bold bg-brand-600 text-white rounded-2xl hover:bg-brand-700 transition-all shadow-lg flex items-center justify-center gap-3"
      >
        {language === 'hi' ? 'मैं सहमत हूँ' : 'I Agree'} <Check size={28} />
      </button>
    </div>
  );
}

// ---- INTAKE ----
function IntakeStep({ sessionId, language, mode, onComplete }: {
  sessionId: string;
  language: string;
  mode: string;
  onComplete: () => void;
}) {
  const [question, setQuestion] = useState<IntakeQuestion | null>(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [progress, setProgress] = useState(0);
  const [totalQ, setTotalQ] = useState(0);
  const [currentNum, setCurrentNum] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const loadingRef = useRef(false);

  const loadQuestion = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const res = await api.getNextQuestion(sessionId);
      const data = res.data || res;
      if (data.is_complete || !data.next_question) {
        onComplete();
        return;
      }
      setQuestion(data.next_question);
      setProgress(data.next_question.progress || 0);
      setTotalQ(data.next_question.total || 0);
      setCurrentNum(prev => prev + 1);
    } catch (err) {
      console.error(err);
      onComplete();
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [sessionId, onComplete]);

  useEffect(() => {
    loadQuestion();
  }, [loadQuestion]);

  const handleSubmitAnswer = async () => {
    if (!question || (!answer.trim() && question.answer_type === 'text')) return;
    setSubmitting(true);
    try {
      await api.submitAnswer(sessionId, {
        question_code: question.code,
        answer_text: answer || undefined,
        source: isRecording ? 'VOICE_TRANSCRIBED' : 'PATIENT_TOUCH',
      });
      setAnswer('');
      loadQuestion();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleChoiceSelect = async (value: string) => {
    if (!question) return;
    setSubmitting(true);
    try {
      await api.submitAnswer(sessionId, {
        question_code: question.code,
        answer_text: value,
        source: 'PATIENT_TOUCH',
      });
      setAnswer('');
      loadQuestion();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        try {
          const res = await api.transcribe(blob, language);
          const data = res.data || res;
          setAnswer(data.text || '');
          setIsRecording(false);
        } catch (err) {
          console.error('Transcription error', err);
          setIsRecording(false);
        }
      };
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone error', err);
      alert('Could not access microphone. Please allow microphone access or type your answer.');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const playGuidance = (text: string) => {
    api.synthesizeSpeech(text, language)
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
      })
      .catch(() => {});
  };

  if (loading) {
    return (
      <div className="text-center py-20">
        <Loader2 size={48} className="animate-spin text-brand-500 mx-auto" />
        <p className="text-xl text-slate-500 mt-4">Loading question...</p>
      </div>
    );
  }

  if (!question) return null;

  return (
    <div className="space-y-8">
      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm font-medium text-slate-500">
          <span>{language === 'hi' ? 'प्रश्न' : 'Question'} {currentNum}/{totalQ}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
          <div className="h-full bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* Domain badge */}
      <div className="flex items-center gap-2">
        <span className="px-3 py-1 bg-brand-100 text-brand-700 text-sm font-bold rounded-full uppercase">
          {question.domain.replace('_', ' ')}
        </span>
        {question.required && (
          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full">
            {language === 'hi' ? 'आवश्यक' : 'Required'}
          </span>
        )}
      </div>

      {/* Question */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-3xl font-bold text-slate-900 leading-tight flex-1">
            {question.prompt}
          </h2>
          <button
            onClick={() => playGuidance(question.prompt)}
            className="p-3 bg-slate-100 rounded-full text-slate-500 hover:bg-slate-200 transition-colors shrink-0"
            title="Listen to question"
          >
            <Volume2 size={24} />
          </button>
        </div>

        {/* Answer input */}
        {question.answer_type === 'text' || question.answer_type === 'number' ? (
          <div className="space-y-4">
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={language === 'hi' ? 'यहाँ अपना उत्तर लिखें...' : 'Type your answer here...'}
              className="w-full p-6 text-xl border-2 border-slate-200 rounded-xl focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none min-h-[160px] resize-none transition-all"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmitAnswer();
                }
              }}
            />
          </div>
        ) : question.answer_type === 'scale' ? (
          <div className="grid grid-cols-5 gap-3">
            {[1,2,3,4,5,6,7,8,9,10].map(n => (
              <button
                key={n}
                onClick={() => { setAnswer(String(n)); }}
                className={`py-4 text-2xl font-bold rounded-xl border-2 transition-all ${
                  answer === String(n)
                    ? n <= 3 ? 'border-green-500 bg-green-50 text-green-700'
                      : n <= 6 ? 'border-amber-500 bg-amber-50 text-amber-700'
                      : 'border-red-500 bg-red-50 text-red-700'
                    : 'border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        ) : question.answer_type === 'choice' || question.answer_type === 'multiselect' ? (
          <div className="space-y-3">
            {question.options?.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleChoiceSelect(opt.value)}
                className="w-full py-5 px-6 text-xl font-semibold bg-white border-2 border-slate-200 rounded-xl hover:border-brand-500 hover:bg-brand-50 transition-all text-left flex justify-between items-center group"
              >
                <span>{opt.label}</span>
                <ChevronRight size={22} className="text-slate-300 group-hover:text-brand-500 transition-colors" />
              </button>
            ))}
          </div>
        ) : null}

        {/* Voice + Submit buttons */}
        {(question.answer_type === 'text' || question.answer_type === 'number') && (
          <div className="flex gap-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`flex-1 py-5 text-xl font-bold rounded-xl flex items-center justify-center gap-3 transition-all ${
                isRecording
                  ? 'bg-red-500 text-white animate-pulse'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {isRecording ? <><MicOff size={24} /> {language === 'hi' ? 'रोकें' : 'Stop Recording'}</> : <><Mic size={24} /> {language === 'hi' ? 'बोलें' : 'Speak Answer'}</>}
            </button>
            <button
              onClick={handleSubmitAnswer}
              disabled={!answer.trim() || submitting}
              className="flex-1 py-5 text-xl font-bold bg-brand-600 text-white rounded-xl hover:bg-brand-700 transition-all disabled:opacity-40 flex items-center justify-center gap-3"
            >
              {submitting ? <Loader2 size={24} className="animate-spin" /> : <>{language === 'hi' ? 'अगला' : 'Next'} <ArrowRight size={24} /></>}
            </button>
          </div>
        )}

        {/* Scale submit */}
        {question.answer_type === 'scale' && answer && (
          <button
            onClick={handleSubmitAnswer}
            disabled={submitting}
            className="w-full py-5 text-xl font-bold bg-brand-600 text-white rounded-xl hover:bg-brand-700 transition-all flex items-center justify-center gap-3"
          >
            {submitting ? <Loader2 size={24} className="animate-spin" /> : <>{language === 'hi' ? 'अगला' : 'Next'} <ArrowRight size={24} /></>}
          </button>
        )}
      </div>

      {/* Skip button for non-required */}
      {!question.required && (
        <button
          onClick={() => { setAnswer(''); loadQuestion(); }}
          className="w-full py-3 text-slate-500 hover:text-slate-700 transition-colors text-lg"
        >
          {language === 'hi' ? 'छोड़ें / Skip' : 'Skip this question'}
        </button>
      )}
    </div>
  );
}

// ---- DOCUMENTS ----
function DocumentStep({ sessionId, documents, onUpload, uploading, onFinish, onSkip }: {
  sessionId?: string;
  documents: MedicalDocument[];
  onUpload: (file: File) => void;
  uploading: boolean;
  onFinish: () => void;
  onSkip: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-8 text-center">
      <h2 className="text-4xl font-bold text-slate-900">Upload Medical Records</h2>
      <p className="text-xl text-slate-500">Upload prescriptions, lab reports, or discharge summaries (optional)</p>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/jpg,image/png,application/pdf"
        onChange={handleFileChange}
        className="hidden"
      />

      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="w-full border-4 border-dashed border-slate-300 rounded-2xl p-12 flex flex-col items-center justify-center gap-4 bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer disabled:opacity-50"
      >
        {uploading ? (
          <Loader2 size={60} className="animate-spin text-brand-500" />
        ) : (
          <Upload size={60} className="text-slate-400" />
        )}
        <span className="text-xl font-medium text-slate-600">
          {uploading ? 'Processing with OCR...' : 'Tap to upload photos or PDFs'}
        </span>
      </button>

      {/* Uploaded documents */}
      {documents.length > 0 && (
        <div className="space-y-3 text-left">
          <h3 className="text-lg font-bold text-slate-700">Uploaded Documents</h3>
          {documents.map((doc, i) => (
            <div key={doc.id || i} className="p-4 bg-white border border-slate-200 rounded-xl flex items-center gap-3">
              <FileText size={20} className="text-slate-400" />
              <div className="flex-1">
                <p className="font-medium text-slate-900">{doc.filename}</p>
                <p className="text-sm text-slate-500">
                  {doc.document_type?.replace('_', ' ')} • OCR confidence: {((doc.ocr_confidence || 0) * 100).toFixed(0)}%
                  {doc.extractions && doc.extractions.length > 0 && ` • ${doc.extractions.length} entities extracted`}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-4">
        <button
          onClick={onSkip}
          className="flex-1 py-5 text-xl font-bold bg-slate-100 text-slate-700 rounded-2xl hover:bg-slate-200 transition-all"
        >
          Skip / No Documents
        </button>
        <button
          onClick={onFinish}
          className="flex-1 py-5 text-xl font-bold bg-brand-600 text-white rounded-2xl hover:bg-brand-700 transition-all shadow-lg flex items-center justify-center gap-3"
        >
          Submit Case <Check size={24} />
        </button>
      </div>
    </div>
  );
}

// ---- COMPLETE ----
function CompleteStep({ summary, onLogout }: { summary: any; onLogout: () => void }) {
  return (
    <div className="space-y-8 text-center">
      <div className="flex justify-center">
        <div className="p-6 bg-green-100 rounded-full">
          <Check size={64} className="text-green-600" />
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="text-4xl font-bold text-slate-900">Case Submitted Successfully!</h2>
        <p className="text-xl text-slate-500">
          Your information has been sent to the doctor. Please wait for your turn.
        </p>
      </div>

      {summary?.red_flags?.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-left space-y-3">
          <div className="flex items-center gap-2 text-red-700 font-bold">
            <AlertCircle size={24} />
            <span>Clinical Priority Alert</span>
          </div>
          {summary.red_flags.map((f: any, i: number) => (
            <p key={i} className="text-red-600">{f.message}</p>
          ))}
          <p className="text-sm text-red-500 italic">
            A staff member has been notified. You will be attended to shortly.
          </p>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-left space-y-3">
        <h3 className="font-bold text-slate-900">What happens next?</h3>
        <ol className="list-decimal list-inside space-y-2 text-slate-600">
          <li>Your case has been sent to the clinician queue</li>
          <li>The AI has prepared a structured clinical summary</li>
          <li>Red flags (if any) have been flagged for priority review</li>
          <li>The doctor will review your history before calling you</li>
        </ol>
      </div>

      <button
        onClick={onLogout}
        className="w-full py-5 text-xl font-bold bg-brand-600 text-white rounded-2xl hover:bg-brand-700 transition-all"
      >
        Done — Sign Out
      </button>
    </div>
  );
}
