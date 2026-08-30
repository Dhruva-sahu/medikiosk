import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { api } from '../../api/client';
import type { CaseDetail as CaseDetailType, DoctorNote, TimelineEventOut } from '../../types';
import {
  ArrowLeft, Check, X, Edit3, AlertTriangle, FileText, Activity, Clock,
  User, Pill, Beaker, Heart, Brain, Calendar, Shield, Stethoscope,
  MessageSquare, CheckCircle, XCircle, ChevronDown, ChevronUp, Loader2,
  ExternalLink, Send, Eye, Link2
} from 'lucide-react';

export default function CaseDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [caseData, setCaseData] = useState<CaseDetailType | null>(null);
  const [timeline, setTimeline] = useState<TimelineEventOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'summary' | 'history' | 'documents' | 'timeline' | 'notes'>('summary');
  const [noteContent, setNoteContent] = useState('');
  const [noteType, setNoteType] = useState('CONSULTATION');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);

  const loadCase = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const [caseRes, timelineRes] = await Promise.all([
        api.getCase(sessionId),
        api.timeline(caseData?.patient?.id || '').catch(() => ({ data: [] })),
      ]);
      setCaseData(caseRes.data || caseRes);
      setTimeline(timelineRes.data || timelineRes);
    } catch (err) {
      console.error('Failed to load case:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  const handleStatusChange = async (status: string) => {
    if (!sessionId) return;
    setStatusLoading(true);
    try {
      await api.updateCaseStatus(sessionId, status);
      await loadCase();
    } catch (err) {
      console.error(err);
    } finally {
      setStatusLoading(false);
    }
  };

  const handleAddNote = async () => {
    if (!sessionId || !noteContent.trim()) return;
    setSubmittingNote(true);
    try {
      await api.addNote(sessionId, {
        note_type: noteType,
        content: noteContent.trim(),
      });
      setNoteContent('');
      await loadCase();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleVerify = async (targetType: string, targetId: string, status: string) => {
    try {
      await api.verifyField({ target_type: targetType, target_id: targetId, status });
      await loadCase();
    } catch (err) {
      console.error(err);
    }
  };

  const handleHisPush = async () => {
    if (!sessionId) return;
    try {
      await api.hisPush(sessionId);
      alert('Case pushed to HIS successfully (mock)');
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={48} className="animate-spin text-brand-500 mx-auto" />
          <p className="text-slate-500 mt-4 text-lg">Loading case...</p>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-500 text-lg">Case not found</p>
      </div>
    );
  }

  const { session, patient, summary, red_flags, documents, notes, answers, abdm } = caseData;
  const structured = summary?.structured || {};

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/clinician')}
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-slate-900">{patient.full_name}</h1>
                {session.priority === 'PRIORITY' && (
                  <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs font-bold rounded uppercase">
                    Urgent
                  </span>
                )}
                {session.mode === 'AYUSH' && (
                  <span className="px-2 py-0.5 bg-purple-100 text-purple-600 text-xs font-bold rounded uppercase">
                    AYUSH
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-500">{session.chief_complaint || 'No chief complaint'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={session.status}
              onChange={(e) => handleStatusChange(e.target.value)}
              disabled={statusLoading}
              className="px-3 py-2 text-sm font-medium border border-slate-200 rounded-lg bg-white text-slate-700 focus:ring-2 focus:ring-brand-500 outline-none"
            >
              <option value="REVIEW_REQUIRED">Review Required</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="WAITING">Waiting</option>
              <option value="COMPLETED">Completed</option>
            </select>
            <button
              onClick={handleHisPush}
              className="px-4 py-2 text-sm font-medium bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors flex items-center gap-2"
            >
              <Send size={14} /> Push to HIS
            </button>
          </div>
        </div>
      </header>

      {/* Red flags banner */}
      {red_flags.length > 0 && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-3">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className="text-red-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-bold text-red-700 text-sm uppercase tracking-wide">
                  Clinical Priority Alert — {red_flags.length} flag{red_flags.length > 1 ? 's' : ''}
                </p>
                {red_flags.map((f, i) => (
                  <p key={i} className="text-red-600 text-sm mt-1">{f.message}</p>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Tabs */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
              <div className="flex border-b border-slate-200 overflow-x-auto">
                {[
                  { id: 'summary', label: 'Summary', icon: <Activity size={16} /> },
                  { id: 'history', label: 'History', icon: <FileText size={16} /> },
                  { id: 'documents', label: 'Documents', icon: <Beaker size={16} /> },
                  { id: 'timeline', label: 'Timeline', icon: <Calendar size={16} /> },
                  { id: 'notes', label: 'Notes', icon: <MessageSquare size={16} /> },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`px-5 py-3 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${
                      activeTab === tab.id
                        ? 'text-brand-600 border-b-2 border-brand-600 bg-brand-50/50'
                        : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="p-6">
                {/* SUMMARY TAB */}
                {activeTab === 'summary' && (
                  <div className="space-y-6">
                    {/* AI Summary */}
                    {summary && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="font-bold text-slate-900 flex items-center gap-2">
                            <Activity size={18} className="text-brand-500" />
                            AI-Generated Clinical Summary
                          </h3>
                          <div className="flex items-center gap-2">
                            {summary.is_ai_generated && (
                              <span className="px-2 py-0.5 bg-blue-100 text-blue-600 text-xs font-bold rounded">
                                AI: {summary.ai_provider}
                              </span>
                            )}
                            <span className={`px-2 py-0.5 text-xs font-bold rounded ${
                              summary.verification_status === 'CLINICIAN_VERIFIED'
                                ? 'bg-green-100 text-green-700'
                                : summary.verification_status === 'EDITED'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-slate-100 text-slate-600'
                            }`}>
                              {summary.verification_status}
                            </span>
                          </div>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                          <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                            {summary.prose}
                          </pre>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleVerify('clinical_summary', session.id, 'VERIFIED')}
                            className="px-3 py-1.5 bg-green-100 text-green-700 text-sm font-medium rounded-lg hover:bg-green-200 transition-colors flex items-center gap-1"
                          >
                            <Check size={14} /> Verify
                          </button>
                          <button
                            onClick={() => handleVerify('clinical_summary', session.id, 'EDITED')}
                            className="px-3 py-1.5 bg-amber-100 text-amber-700 text-sm font-medium rounded-lg hover:bg-amber-200 transition-colors flex items-center gap-1"
                          >
                            <Edit3 size={14} /> Needs Edit
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Structured data sections */}
                    {structured.chief_complaint && (
                      <SummarySection title="Chief Complaint" icon={<Stethoscope size={18} />}>
                        <p className="text-slate-800">{structured.chief_complaint}</p>
                      </SummarySection>
                    )}

                    {structured.hpi && Object.keys(structured.hpi).length > 0 && (
                      <SummarySection title="History of Present Illness" icon={<Activity size={18} />}>
                        <div className="grid grid-cols-2 gap-3">
                          {Object.entries(structured.hpi).map(([k, v]) => (
                            <div key={k} className="p-3 bg-slate-50 rounded-lg">
                              <span className="text-xs font-bold text-slate-500 uppercase">{k.replace(/_/g, ' ')}</span>
                              <p className="text-sm font-medium text-slate-800 mt-1">{String(v)}</p>
                            </div>
                          ))}
                        </div>
                      </SummarySection>
                    )}

                    {structured.past_medical_history?.length > 0 && (
                      <SummarySection title="Past Medical History" icon={<Heart size={18} />}>
                        <ul className="list-disc list-inside space-y-1 text-slate-700">
                          {structured.past_medical_history.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </SummarySection>
                    )}

                    {structured.past_surgical_history?.length > 0 && (
                      <SummarySection title="Past Surgical History" icon={<Shield size={18} />}>
                        <ul className="list-disc list-inside space-y-1 text-slate-700">
                          {structured.past_surgical_history.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </SummarySection>
                    )}

                    {(structured.drug_history?.length > 0 || structured.current_medications?.length > 0) && (
                      <SummarySection title="Medications" icon={<Pill size={18} />}>
                        <ul className="list-disc list-inside space-y-1 text-slate-700">
                          {(structured.drug_history || structured.current_medications || []).map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </SummarySection>
                    )}

                    {structured.allergies?.length > 0 && (
                      <SummarySection title="Allergies" icon={<AlertTriangle size={18} />}>
                        <ul className="list-disc list-inside space-y-1 text-slate-700">
                          {structured.allergies.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </SummarySection>
                    )}

                    {structured.family_history?.length > 0 && (
                      <SummarySection title="Family History" icon={<Users size={18} />}>
                        <ul className="list-disc list-inside space-y-1 text-slate-700">
                          {structured.family_history.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </SummarySection>
                    )}

                    {structured.personal_history && Object.keys(structured.personal_history).length > 0 && (
                      <SummarySection title="Personal History" icon={<User size={18} />}>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(structured.personal_history).map(([k, v]) => (
                            <div key={k} className="p-2 bg-slate-50 rounded">
                              <span className="text-xs text-slate-500 uppercase">{k.replace(/_/g, ' ')}</span>
                              <p className="text-sm font-medium text-slate-800">{String(v)}</p>
                            </div>
                          ))}
                        </div>
                      </SummarySection>
                    )}

                    {structured.ayush && Object.keys(structured.ayush).length > 0 && (
                      <SummarySection title="AYUSH / Dashavidha Pariksha" icon={<Brain size={18} />}>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(structured.ayush).map(([k, v]) => (
                            <div key={k} className="p-2 bg-purple-50 rounded">
                              <span className="text-xs text-purple-600 uppercase">{k.replace(/_/g, ' ')}</span>
                              <p className="text-sm font-medium text-slate-800">{String(v)}</p>
                            </div>
                          ))}
                        </div>
                      </SummarySection>
                    )}
                  </div>
                )}

                {/* HISTORY TAB */}
                {activeTab === 'history' && (
                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-900">All Intake Answers ({answers.length})</h3>
                    {answers.length === 0 ? (
                      <p className="text-slate-500">No answers recorded.</p>
                    ) : (
                      <div className="space-y-2">
                        {answers.map((a) => (
                          <div key={a.id} className="p-4 bg-slate-50 rounded-lg border border-slate-100">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-brand-600 uppercase">{a.question_code.replace(/_/g, ' ')}</span>
                              <span className="text-xs text-slate-400 flex items-center gap-1">
                                {a.source === 'VOICE_TRANSCRIBED' ? '🎤 Voice' : '👆 Touch'}
                              </span>
                            </div>
                            <p className="text-slate-800">{a.answer_text}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* DOCUMENTS TAB */}
                {activeTab === 'documents' && (
                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-900">Medical Documents ({documents.length})</h3>
                    {documents.length === 0 ? (
                      <p className="text-slate-500">No documents uploaded.</p>
                    ) : (
                      <div className="space-y-4">
                        {documents.map((doc) => (
                          <DocumentCard key={doc.id} doc={doc} onVerify={handleVerify} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* TIMELINE TAB */}
                {activeTab === 'timeline' && (
                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-900">Medical Timeline</h3>
                    {timeline.length === 0 ? (
                      <p className="text-slate-500">No timeline events.</p>
                    ) : (
                      <div className="space-y-3">
                        {timeline.map((event) => (
                          <div key={event.id} className="flex gap-4">
                            <div className="flex flex-col items-center">
                              <div className={`w-3 h-3 rounded-full ${
                                event.event_type === 'INTAKE' ? 'bg-blue-500' :
                                event.event_type === 'DOCUMENT' ? 'bg-green-500' :
                                'bg-slate-400'
                              }`} />
                              <div className="flex-1 w-px bg-slate-200" />
                            </div>
                            <div className="pb-4">
                              <p className="text-xs text-slate-400">{event.event_date || 'Unknown date'}</p>
                              <p className="font-medium text-slate-900">{event.title}</p>
                              {event.detail && <p className="text-sm text-slate-600">{event.detail}</p>}
                              <span className="text-xs text-slate-400">{event.source}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* NOTES TAB */}
                {activeTab === 'notes' && (
                  <div className="space-y-6">
                    {/* Add note form */}
                    <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                      <div className="flex items-center gap-3">
                        <select
                          value={noteType}
                          onChange={(e) => setNoteType(e.target.value)}
                          className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white"
                        >
                          <option value="CONSULTATION">Consultation Note</option>
                          <option value="ASSESSMENT">Assessment</option>
                          <option value="PLAN">Plan</option>
                          <option value="FOLLOW_UP">Follow-up</option>
                        </select>
                      </div>
                      <textarea
                        value={noteContent}
                        onChange={(e) => setNoteContent(e.target.value)}
                        placeholder="Add clinical notes..."
                        rows={3}
                        className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none resize-none"
                      />
                      <button
                        onClick={handleAddNote}
                        disabled={!noteContent.trim() || submittingNote}
                        className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-40 flex items-center gap-2"
                      >
                        {submittingNote ? <Loader2 size={14} className="animate-spin" /> : <MessageSquare size={14} />}
                        Add Note
                      </button>
                    </div>

                    {/* Existing notes */}
                    <div className="space-y-3">
                      {notes.length === 0 ? (
                        <p className="text-slate-500">No notes yet.</p>
                      ) : (
                        notes.map((note) => (
                          <div key={note.id} className="p-4 bg-white border border-slate-200 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs font-bold text-slate-500 uppercase">{note.note_type}</span>
                              <span className="text-xs text-slate-400">
                                {new Date(note.created_at).toLocaleString()}
                              </span>
                            </div>
                            <p className="text-sm text-slate-700">{note.content}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Patient info */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h3 className="font-bold text-slate-900 flex items-center gap-2">
                <User size={18} /> Patient Information
              </h3>
              <InfoRow label="Name" value={patient.full_name} />
              <InfoRow label="Gender" value={patient.gender || '—'} />
              <InfoRow label="Blood Group" value={patient.blood_group || '—'} />
              <InfoRow label="Phone" value={patient.phone || '—'} />
              <InfoRow label="ABHA ID" value={patient.abha_id || '—'} />
              <InfoRow label="Language" value={patient.preferred_language === 'hi' ? 'Hindi' : 'English'} />
              {abdm && (
                <div className="pt-2 border-t border-slate-100">
                  <InfoRow label="ABDM" value={abdm.status} />
                </div>
              )}
            </div>

            {/* Red flags */}
            {red_flags.length > 0 && (
              <div className="bg-red-50 rounded-xl border border-red-200 shadow-sm p-5 space-y-3">
                <h3 className="font-bold text-red-700 flex items-center gap-2">
                  <AlertTriangle size={18} /> Red Flags
                </h3>
                {red_flags.map((flag, i) => (
                  <div key={i} className="p-3 bg-white border border-red-100 rounded-lg">
                    <p className="text-sm font-medium text-red-600">{flag.message}</p>
                    <span className="text-xs text-red-400 uppercase">{flag.severity}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Lab results from documents */}
            {documents.some(d => d.extractions?.some(e => e.entity_type === 'LAB')) && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <Beaker size={18} /> Lab Results
                </h3>
                <div className="space-y-2">
                  {documents.flatMap(d => d.extractions || [])
                    .filter(e => e.entity_type === 'LAB')
                    .map((e, i) => (
                      <div key={i} className={`p-2 rounded text-sm ${
                        e.payload.abnormal_flag ? 'bg-red-50' : 'bg-slate-50'
                      }`}>
                        <span className="font-medium text-slate-800">{e.payload.test_name}</span>
                        <span className="text-slate-500 mx-1">:</span>
                        <span className={`font-bold ${
                          e.payload.abnormal_flag?.startsWith('H') ? 'text-red-600' :
                          e.payload.abnormal_flag?.startsWith('L') ? 'text-amber-600' :
                          'text-slate-800'
                        }`}>
                          {e.payload.value} {e.payload.unit}
                        </span>
                        {e.payload.reference_range && (
                          <span className="text-xs text-slate-400 ml-1">({e.payload.reference_range})</span>
                        )}
                        {e.payload.abnormal_flag && (
                          <span className="text-xs font-bold text-red-500 ml-1">{e.payload.abnormal_flag}</span>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Medications from documents */}
            {documents.some(d => d.extractions?.some(e => e.entity_type === 'MEDICATION')) && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                  <Pill size={18} /> Extracted Medications
                </h3>
                <div className="space-y-2">
                  {documents.flatMap(d => d.extractions || [])
                    .filter(e => e.entity_type === 'MEDICATION')
                    .map((e, i) => (
                      <div key={i} className="p-2 bg-slate-50 rounded text-sm">
                        <span className="font-medium text-slate-800">{e.payload.name}</span>
                        {e.payload.dose && (
                          <span className="text-slate-500 ml-2">{e.payload.dose}</span>
                        )}
                        {e.payload.unit && (
                          <span className="text-slate-400 ml-1">{e.payload.unit}</span>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Quick actions */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
              <h3 className="font-bold text-slate-900">Quick Actions</h3>
              <button
                onClick={() => handleStatusChange('COMPLETED')}
                disabled={statusLoading}
                className="w-full py-2.5 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
              >
                <CheckCircle size={16} /> Mark Completed
              </button>
              <button
                onClick={() => handleHisPush()}
                className="w-full py-2.5 bg-slate-100 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-200 transition-colors flex items-center justify-center gap-2"
              >
                <Send size={16} /> Push to HIS
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummarySection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h4 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
        {icon} {title}
      </h4>
      <div className="pl-6">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}

function Users({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function DocumentCard({ doc, onVerify }: { doc: any; onVerify: (type: string, id: string, status: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <div className="p-4 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-3">
          <FileText size={20} className="text-slate-400" />
          <div>
            <p className="font-medium text-slate-900">{doc.filename}</p>
            <p className="text-xs text-slate-500">
              {doc.document_type?.replace(/_/g, ' ')} • {doc.document_date || 'No date'}
              {doc.ocr_confidence && ` • OCR: ${(doc.ocr_confidence * 100).toFixed(0)}%`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onVerify('document', doc.id, 'VERIFIED')}
            className="p-1.5 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
            title="Verify"
          >
            <Check size={16} />
          </button>
          <button
            onClick={() => onVerify('document', doc.id, 'REJECTED')}
            className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="Reject"
          >
            <X size={16} />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="p-4 border-t border-slate-200 space-y-4">
          {/* OCR text */}
          {doc.ocr_text && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase mb-1">OCR Text</p>
              <pre className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg whitespace-pre-wrap max-h-60 overflow-y-auto font-mono">
                {doc.ocr_text}
              </pre>
            </div>
          )}

          {/* Extractions */}
          {doc.extractions && doc.extractions.length > 0 && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase mb-2">
                Extracted Entities ({doc.extractions.length})
              </p>
              <div className="space-y-2">
                {doc.extractions.map((ext: any) => (
                  <div key={ext.id} className="p-2 bg-slate-50 rounded-lg flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-brand-600 uppercase">{ext.entity_type}</span>
                      <p className="text-sm text-slate-700">{JSON.stringify(ext.payload)}</p>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => onVerify('extraction', ext.id, 'VERIFIED')}
                        className="p-1 text-green-600 hover:bg-green-50 rounded"
                      >
                        <Check size={12} />
                      </button>
                      <button
                        onClick={() => onVerify('extraction', ext.id, 'REJECTED')}
                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
