import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Volume2, Mic, Check, ArrowRight, Upload, AlertCircle } from 'lucide-react';

// Mock API calls - these should be replaced by actual services in a real app
const api = {
  async startSession(lang: string, mode: string) {
    const res = await fetch('/api/v1/intake/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: lang, mode }),
    });
    return res.json();
  },
  async getNextQuestion(sessionId: string) {
    const res = await fetch(`/api/v1/intake/next?session_id=${sessionId}`);
    return res.json();
  },
  async submitAnswer(sessionId: string, questionCode: string, answerText: string) {
    const res = await fetch('/api/v1/intake/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question_code: questionCode, answer_text: answerText }),
    });
    return res.json();
  },
  async synthesizeSpeech(text: string, lang: string) {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('language', lang);
    const res = await fetch('/api/v1/speech/synthesize', {
      method: 'POST',
      body: formData,
    });
    return res.blob();
  },
};

type Step = 'LANGUAGE' | 'CONSENT' | 'INTAKE' | 'DOCUMENTS' | 'REVIEW';

export const IntakeFlow: React.FC = () => {
  const [step, setStep] = useState<Step>('LANGUAGE');
  const [language, setLanguage] = useState('en');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [currentAnswer, setCurrentAnswer] = useState('');

  const handleLanguageSelect = async (lang: string) => {
    setLanguage(lang);
    const data = await api.startSession(lang, 'STANDARD');
    setSessionId(data.session_id);
    setStep('CONSENT');
  };

  const playGuidance = async (text: string) => {
    const blob = await api.synthesizeSpeech(text, language);
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-8">
      {step === 'LANGUAGE' && (
        <div className="text-center space-y-8 w-full max-w-md">
          <h2 className="text-4xl font-bold text-slate-800">Select Language / भाषा चुनें</h2>
          <div className="grid grid-cols-1 gap-6">
            <button
              onClick={() => handleLanguageSelect('en')}
              className="py-8 px-6 text-3xl font-semibold bg-white border-4 border-slate-200 rounded-2xl hover:border-blue-500 hover:bg-blue-50 transition-all shadow-sm"
            >
              English
            </button>
            <button
              onClick={() => handleLanguageSelect('hi')}
              className="py-8 px-6 text-3xl font-semibold bg-white border-4 border-slate-200 rounded-2xl hover:border-blue-500 hover:bg-blue-50 transition-all shadow-sm"
            >
              हिन्दी
            </button>
          </div>
        </div>
      )}

      {step === 'CONSENT' && (
        <div className="text-center space-y-8 w-full max-w-2xl">
          <h2 className="text-4xl font-bold text-slate-800">Consent / सहमति</h2>
          <p className="text-2xl text-slate-600 leading-relaxed">
            We will collect your medical history to help the doctor treat you better. Your data is secure.
            <br />
            हम आपकी बेहतर चिकित्सा के लिए आपका स्वास्थ्य विवरण एकत्र करेंगे। आपका डेटा सुरक्षित है।
          </p>
          <div className="flex justify-center">
            <button
              onClick={() => playGuidance("Consent text in selected language")}
              className="p-4 bg-slate-100 rounded-full text-slate-600 hover:bg-slate-200 transition-colors"
            >
              <Volume2 size={48} />
            </button>
          </div>
          <button
            onClick={() => setStep('INTAKE')}
            className="w-full py-8 px-6 text-3xl font-bold bg-blue-600 text-white rounded-2xl hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-4"
          >
            I Agree / मैं सहमत हूँ <Check size={32} />
          </button>
        </div>
      )}

      {step === 'INTAKE' && (
        <div className="w-full space-y-8">
          <IntakeQuestion
            sessionId={sessionId!}
            language={language}
            onComplete={() => setStep('DOCUMENTS')}
            playGuidance={playGuidance}
          />
        </div>
      )}

      {step === 'DOCUMENTS' && (
        <div className="text-center space-y-8 w-full max-w-2xl">
          <h2 className="text-4xl font-bold text-slate-800">Upload Records / दस्तावेज़ अपलोड करें</h2>
          <p className="text-2xl text-slate-600">Upload prescriptions or lab reports</p>
          <div className="border-4 border-dashed border-slate-300 rounded-3xl p-12 flex flex-col items-center justify-center gap-6 bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer">
            <Upload size={80} className="text-slate-400" />
            <span className="text-2xl font-medium text-slate-600">Tap to upload photos or PDFs</span>
          </div>
          <button
            onClick={() => setStep('REVIEW')}
            className="w-full py-8 px-6 text-3xl font-bold bg-blue-600 text-white rounded-2xl hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-4"
          >
            Finish / समाप्त करें <ArrowRight size={32} />
          </button>
        </div>
      )}

      {step === 'REVIEW' && (
        <div className="text-center space-y-8 w-full max-w-2xl">
          <h2 className="text-4xl font-bold text-slate-800">All Done! / सब हो गया!</h2>
          <p className="text-2xl text-slate-600">Your information has been sent to the doctor. Please wait for your turn.</p>
          <div className="p-8 bg-green-50 border-2 border-green-200 rounded-3xl flex items-center justify-center gap-4 text-green-700 text-2xl font-bold">
            <Check size={32} /> Submitted Successfully
          </div>
        </div>
      )}
    </div>
  );
};

const IntakeQuestion: React.FC<{ sessionId: string, language: string, onComplete: () => void, playGuidance: (t: string) => void }> = ({ sessionId, language, onComplete, playGuidance }) => {
  const [question, setQuestion] = useState<any>(null);
  const [answer, setAnswer] = useState('');
  const [isRecording, setIsRecording] = useState(false);

  useEffect(() => {
    loadNext();
  }, []);

  const loadNext = async () => {
    const data = await api.getNextQuestion(sessionId);
    if (data.next_question) {
      setQuestion(data.next_question);
      // Auto-play guidance
      playGuidance(data.next_question.prompt);
    } else {
      onComplete();
    }
  };

  const handleAnswer = async () => {
    await api.submitAnswer(sessionId, question.code, answer);
    setAnswer('');
    loadNext();
  };

  if (!question) return <div className="text-center text-2xl">Loading...</div>;

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div className="flex justify-between items-center">
        <span className="text-xl font-medium text-slate-500">Question {question.progress}%</span>
        <button
          onClick={() => playGuidance(question.prompt)}
          className="p-3 bg-slate-100 rounded-full text-slate-600 hover:bg-slate-200 transition-colors"
        >
          <Volume2 size={24} />
        </button>
      </div>

      <h2 className="text-4xl font-bold text-slate-800 leading-tight">
        {question.prompt}
      </h2>

      {question.answer_type === 'text' ? (
        <div className="space-y-6">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your answer here..."
            className="w-full p-6 text-2xl border-4 border-slate-200 rounded-2xl focus:border-blue-500 outline-none min-h-[200px]"
          />
          <div className="flex gap-4">
            <button
              onClick={() => setIsRecording(!isRecording)}
              className={`flex-1 py-6 px-6 text-2xl font-bold rounded-2xl flex items-center justify-center gap-3 transition-all ${isRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}`}
            >
              <Mic size={28} /> {isRecording ? 'Recording...' : 'Speak Answer'}
            </button>
            <button
              onClick={handleAnswer}
              className="flex-1 py-6 px-6 text-2xl font-bold bg-blue-600 text-white rounded-2xl hover:bg-blue-700 transition-all shadow-md flex items-center justify-center gap-3"
            >
              Next <ArrowRight size={28} />
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {question.options?.map((opt: any) => (
            <button
              key={opt.value}
              onClick={() => {
                setAnswer(opt.label);
                handleAnswer();
              }}
              className="py-6 px-6 text-2xl font-semibold bg-white border-4 border-slate-200 rounded-2xl hover:border-blue-500 hover:bg-blue-50 transition-all text-left flex justify-between items-center"
            >
              {opt.label}
              <Check size={24} className="text-slate-300" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
