import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authService } from '../services/auth.service';
import { AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authService.register({ username, email, password });
      navigate('/login');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="cosmos-card p-8 rounded-3xl relative z-10 transition-all duration-300 ease-in-out">


        
        {/* Brand Icon Header */}
        <div className="text-center mb-8">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#16161b] border border-[#2a2a32] text-white mb-4 shadow-inner">
            <div className="h-4 w-4 rounded-full bg-white shadow-[0_0_10px_#ffffff]" />
          </div>
          <h1 className="text-xl font-bold tracking-[0.2em] text-white uppercase">RELAY</h1>
          <p className="mt-1 text-[10px] tracking-[0.15em] text-[#666675] uppercase">
            REGISTRATION PORTAL
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-[#1c1c24] mb-7 text-xs font-semibold tracking-widest uppercase">
          <Link
            to="/login"
            className="flex-1 pb-3 text-center text-[#555565] hover:text-gray-300 cursor-pointer transition-colors"
          >
            SIGN IN
          </Link>
          <div className="flex-1 pb-3 text-center text-white border-b-2 border-white cursor-pointer">
            SIGN UP
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 rounded-xl bg-red-500/10 border border-red-500/20 p-3.5 mb-6 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
          {/* Username */}
          <div>
            <label className="block text-[10px] font-bold tracking-[0.15em] text-[#777788] uppercase mb-2">
              USERNAME
            </label>
            <input
              type="text"
              required
              minLength={3}
              maxLength={50}
              autoComplete="off"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="alex_dev"
              className="w-full rounded-xl cosmos-input px-4 py-3 text-sm"
            />
          </div>

          {/* Email Address */}
          <div>
            <label className="block text-[10px] font-bold tracking-[0.15em] text-[#777788] uppercase mb-2">
              EMAIL ADDRESS
            </label>
            <input
              type="email"
              required
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@universe.com"
              className="w-full rounded-xl cosmos-input px-4 py-3 text-sm"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-[10px] font-bold tracking-[0.15em] text-[#777788] uppercase mb-2">
              PASSWORD
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl cosmos-input pl-4 pr-12 py-3 text-sm"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-3.5 text-[#666675] hover:text-white transition-colors"
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Create Account Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 rounded-xl bg-white hover:bg-gray-200 text-black py-3.5 text-xs font-bold tracking-[0.15em] uppercase transition-all shadow-lg active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin text-black" /> : 'CREATE ACCOUNT'}
          </button>
        </form>

        {/* Footer link */}
        <div className="mt-8 text-center text-xs text-[#666675]">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-white hover:underline">
            Sign in
          </Link>
        </div>
      </div>
  );
};

