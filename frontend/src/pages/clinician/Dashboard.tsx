import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { api } from '../../api/client';
import type { QueueItem, DashboardCounts } from '../../types';
import {
  AlertCircle, User, Clock, ChevronRight, Activity, Users, AlertTriangle,
  CheckCircle, BarChart3, RefreshCw, LogOut, Stethoscope, FileText
} from 'lucide-react';

export default function ClinicianDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [counts, setCounts] = useState<DashboardCounts | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [priorityOnly, setPriorityOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [countsRes, queueRes] = await Promise.all([
        api.dashboard(),
        api.queue(priorityOnly),
      ]);
      setCounts(countsRes.data || countsRes);
      setQueue(queueRes.data || queueRes);
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [priorityOnly]);

  // Auto-refresh every 30s
  useEffect(() => {
    const timer = setInterval(() => loadData(), 30000);
    return () => clearInterval(timer);
  }, [priorityOnly]);

  const timeAgo = (dateStr?: string) => {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-600 rounded-lg">
              <Activity size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Swasthya Setu Clinician</h1>
              <p className="text-sm text-slate-500">Clinical Dashboard</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => loadData(true)}
              disabled={refreshing}
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <RefreshCw size={20} className={refreshing ? 'animate-spin' : ''} />
            </button>
            <div className="flex items-center gap-2">
              <div className="p-2 bg-green-100 rounded-lg text-green-600">
                <Stethoscope size={20} />
              </div>
              <span className="text-sm font-medium text-slate-700">{user?.full_name}</span>
            </div>
            <button onClick={logout} className="p-2 text-slate-400 hover:text-slate-600 transition-colors">
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Stats Cards */}
        {counts && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              label="New Cases"
              value={counts.new_cases}
              icon={<FileText size={20} />}
              color="blue"
            />
            <StatCard
              label="Pending Review"
              value={counts.pending_review}
              icon={<Clock size={20} />}
              color="amber"
            />
            <StatCard
              label="Priority"
              value={counts.priority_cases}
              icon={<AlertTriangle size={20} />}
              color="red"
            />
            <StatCard
              label="Completed"
              value={counts.completed_cases}
              icon={<CheckCircle size={20} />}
              color="green"
            />
            <StatCard
              label="Today's Queue"
              value={counts.today_queue}
              icon={<Users size={20} />}
              color="slate"
            />
          </div>
        )}

        {/* Queue */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Clock size={20} className="text-slate-400" />
                Patient Queue
              </h2>
              <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-sm font-medium rounded-full">
                {queue.length} patients
              </span>
            </div>
            <button
              onClick={() => setPriorityOnly(!priorityOnly)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                priorityOnly
                  ? 'bg-red-100 text-red-700 border border-red-200'
                  : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
              }`}
            >
              <AlertTriangle size={14} className="inline mr-1" />
              {priorityOnly ? 'Showing Priority' : 'Priority Only'}
            </button>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-500">Loading queue...</div>
          ) : queue.length === 0 ? (
            <div className="p-12 text-center">
              <Users size={48} className="text-slate-300 mx-auto mb-3" />
              <p className="text-lg text-slate-500">No patients in queue</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {queue.map((item) => (
                <Link
                  key={item.session_id}
                  to={`/clinician/case/${item.session_id}`}
                  className={`p-5 flex items-center gap-4 hover:bg-slate-50 transition-colors group ${
                    item.priority === 'PRIORITY' ? 'border-l-4 border-l-red-500' : ''
                  }`}
                >
                  <div className={`p-3 rounded-full ${
                    item.priority === 'PRIORITY' ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'
                  }`}>
                    <User size={22} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 truncate">{item.patient_name}</span>
                      {item.patient_age && (
                        <span className="text-sm text-slate-400">
                          {item.patient_age}{item.patient_gender ? `/${item.patient_gender}` : ''}
                        </span>
                      )}
                      {item.priority === 'PRIORITY' && (
                        <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs font-bold rounded uppercase">
                          Urgent
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-600 truncate">{item.chief_complaint || 'No chief complaint recorded'}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm text-slate-400">{timeAgo(item.submitted_at)}</p>
                    {item.red_flag_count > 0 && (
                      <p className="text-sm font-bold text-red-500 flex items-center justify-end gap-1">
                        <AlertCircle size={14} /> {item.red_flag_count} red flag{item.red_flag_count > 1 ? 's' : ''}
                      </p>
                    )}
                  </div>
                  <ChevronRight size={20} className="text-slate-300 group-hover:text-brand-500 transition-colors shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function StatCard({ label, value, icon, color }: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  const colors: Record<string, { bg: string; icon: string; value: string }> = {
    blue: { bg: 'bg-blue-50', icon: 'text-blue-500', value: 'text-blue-700' },
    amber: { bg: 'bg-amber-50', icon: 'text-amber-500', value: 'text-amber-700' },
    red: { bg: 'bg-red-50', icon: 'text-red-500', value: 'text-red-700' },
    green: { bg: 'bg-green-50', icon: 'text-green-500', value: 'text-green-700' },
    slate: { bg: 'bg-slate-50', icon: 'text-slate-500', value: 'text-slate-700' },
  };
  const c = colors[color] || colors.slate;

  return (
    <div className={`p-4 rounded-xl border border-slate-200 ${c.bg}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={c.icon}>{icon}</span>
        <span className="text-sm font-medium text-slate-600">{label}</span>
      </div>
      <p className={`text-3xl font-bold ${c.value}`}>{value}</p>
    </div>
  );
}
