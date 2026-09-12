import React from 'react';
import { Outlet } from 'react-router-dom';
import { MatrixBackground } from '../components/common/MatrixBackground';

export const AuthLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen items-center justify-center space-bg px-4 py-8 relative overflow-hidden">
      {/* Single persistent canvas background across login & register route transitions */}
      <MatrixBackground />
      
      {/* Nested Route View (LoginPage or RegisterPage) */}
      <div className="w-full max-w-[420px] relative z-10">
        <Outlet />
      </div>
    </div>
  );
};
