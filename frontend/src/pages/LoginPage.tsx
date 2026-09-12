import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/useAuthStore';
import { authService } from '../services/auth.service';
import { AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authService.login({ email, password });
      useAuthStore.getState().setAccessToken(response.access_token);
      const user = await authService.getCurrentUser();
      login(response.access_token, user);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password.');
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
            AUTHENTICATION PORTAL
          </p>
        </div>

        {/* Tab Switcher: Sign In vs Sign Up */}
        <div className="flex border-b border-[#1c1c24] mb-7 text-xs font-semibold tracking-widest uppercase">
          <div className="flex-1 pb-3 text-center text-white border-b-2 border-white cursor-pointer">
            SIGN IN
          </div>
          <Link
            to="/register"
            className="flex-1 pb-3 text-center text-[#555565] hover:text-gray-300 cursor-pointer transition-colors"
          >
            SIGN UP
          </Link>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 rounded-xl bg-red-500/10 border border-red-500/20 p-3.5 mb-6 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
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
                autoComplete="current-password"
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

          {/* Remember Me & Forgot Password */}
          <div className="flex items-center justify-between text-xs pt-1">
            <label className="flex items-center gap-2 text-[#888898] cursor-pointer hover:text-gray-300">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 rounded bg-[#141417] border-[#222228] checked:bg-white checked:border-white transition-colors cursor-pointer accent-white"
              />
              <span>Remember me</span>
            </label>
            <a href="#" onClick={(e) => e.preventDefault()} className="text-[#666675] hover:text-gray-300 transition-colors">
              Forgot password?
            </a>
          </div>

          {/* Launch Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 rounded-xl bg-white hover:bg-gray-200 text-black py-3.5 text-xs font-bold tracking-[0.15em] uppercase transition-all shadow-lg active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin text-black" /> : 'LAUNCH SIGN IN'}
          </button>
        </form>

        {/* Footer link */}
        <div className="mt-8 text-center text-xs text-[#666675]">
          Don't have an account?{' '}
          <Link to="/register" className="font-semibold text-white hover:underline">
            Sign up
          </Link>
        </div>
      </div>
  );
};

