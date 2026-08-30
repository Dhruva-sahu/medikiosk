import React from 'react';
import { Outlet } from 'react-router-dom';

export const KioskLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 font-sans">
      <div className="w-full max-w-4xl bg-white rounded-3xl shadow-xl border-4 border-slate-200 overflow-hidden">
        <header className="bg-slate-800 text-white p-6 text-center">
          <h1 className="text-3xl font-bold tracking-tight">Swasthya Setu</h1>
          <p className="text-slate-300 text-lg">AI-Powered Patient Intake</p>
        </header>
        <main className="p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
