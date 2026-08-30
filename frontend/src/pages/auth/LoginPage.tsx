import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Activity, User, Stethoscope, ArrowRight, ChevronLeft } from 'lucide-react';

type Mode = 'ROLE_SELECT' | 'LOGIN' | 'REGISTER';

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('ROLE_SELECT');
  const [role, setRole] = useState<'PATIENT' | 'CLINICIAN'>('PATIENT');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(email, password);
      navigate(user.role === 'CLINICIAN' || user.role === 'ADMIN' ? '/clinician' : '/kiosk');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await register({
        email,
        password,
        full_name: fullName,
        phone: phone || undefined,
        role,
        preferred_language: 'en',
      });
      navigate(user.role === 'CLINICIAN' ? '/clinician' : '/kiosk');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const demoLogin = async (email: string) => {
    setError('');
    setLoading(true);
    try {
      const user = await login(email, 'demo1234');
      navigate(user.role === 'CLINICIAN' || user.role === 'ADMIN' ? '/clinician' : '/kiosk');
    } catch (err: any) {
      setError(err.message || 'Demo login failed');
    } finally {
      setLoading(false);
    }
  };

  if (mode === 'ROLE_SELECT') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
        <div className="w-full max-w-lg space-y-8">
          <div className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="p-4 bg-brand-600 rounded-2xl">
                <Activity size={48} className="text-white" />
              </div>
            </div>
            <h1 className="text-4xl font-bold text-slate-900">Swasthya Setu</h1>
            <p className="text-lg text-slate-500">AI-Powered Clinical History & Patient Case-Taking</p>
          </div>

          <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8 space-y-6">
            <h2 className="text-xl font-bold text-slate-800 text-center">I am a...</h2>

            <button
              onClick={() => { setRole('PATIENT'); setMode('LOGIN'); }}
              className="w-full p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-brand-500 hover:bg-brand-50 transition-all flex items-center gap-4 group"
            >
              <div className="p-3 bg-blue-100 rounded-xl text-blue-600 group-hover:bg-blue-200 transition-colors">
                <User size={28} />
              </div>
              <div className="text-left flex-1">
                <div className="text-xl font-bold text-slate-900">Patient</div>
                <div className="text-sm text-slate-500">Complete your clinical history before seeing the doctor</div>
              </div>
              <ArrowRight size={20} className="text-slate-300 group-hover:text-brand-500 transition-colors" />
            </button>

            <button
              onClick={() => { setRole('CLINICIAN'); setMode('LOGIN'); }}
              className="w-full p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-brand-500 hover:bg-brand-50 transition-all flex items-center gap-4 group"
            >
              <div className="p-3 bg-green-100 rounded-xl text-green-600 group-hover:bg-green-200 transition-colors">
                <Stethoscope size={28} />
              </div>
              <div className="text-left flex-1">
                <div className="text-xl font-bold text-slate-900">Clinician</div>
                <div className="text-sm text-slate-500">Review patient cases and clinical summaries</div>
              </div>
              <ArrowRight size={20} className="text-slate-300 group-hover:text-brand-500 transition-colors" />
            </button>

            <div className="pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500 text-center mb-3">Quick demo access (no registration needed)</p>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => demoLogin('ananya@demo.medikiosk')}
                  className="py-3 px-4 bg-slate-100 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  🩺 Demo Patient
                </button>
                <button
                  onClick={() => demoLogin('doctor@demo.medikiosk')}
                  className="py-3 px-4 bg-slate-100 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  👨‍⚕️ Demo Clinician
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <button onClick={() => setMode('ROLE_SELECT')} className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-700 transition-colors mb-2">
            <ChevronLeft size={16} /> Back
          </button>
          <div className="flex justify-center">
            <div className={`p-3 rounded-xl ${role === 'PATIENT' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'}`}>
              {role === 'PATIENT' ? <User size={32} /> : <Stethoscope size={32} />}
            </div>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">
            {role === 'PATIENT' ? 'Patient' : 'Clinician'} {mode === 'LOGIN' ? 'Login' : 'Registration'}
          </h1>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {mode === 'LOGIN' ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                  placeholder="••••••••"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-brand-600 text-white font-bold text-lg rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? 'Signing in...' : 'Sign In'}
                {!loading && <ArrowRight size={20} />}
              </button>
              <p className="text-center text-sm text-slate-500">
                Don't have an account?{' '}
                <button type="button" onClick={() => setMode('REGISTER')} className="text-brand-600 font-medium hover:underline">
                  Register
                </button>
              </p>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Phone (optional)</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none text-lg"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-brand-600 text-white font-bold text-lg rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? 'Creating account...' : 'Create Account'}
                {!loading && <ArrowRight size={20} />}
              </button>
              <p className="text-center text-sm text-slate-500">
                Already have an account?{' '}
                <button type="button" onClick={() => setMode('LOGIN')} className="text-brand-600 font-medium hover:underline">
                  Sign in
                </button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
