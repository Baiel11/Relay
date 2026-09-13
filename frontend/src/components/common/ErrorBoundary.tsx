import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, LogOut } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Relay ErrorBoundary caught runtime exception:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleReset = () => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {
      // Ignore storage errors
    }
    window.location.href = '/login';
  };

  public override render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen w-screen items-center justify-center bg-[#050507] p-6 text-white select-none">
          <div className="w-full max-w-lg rounded-3xl cosmos-card p-8 border border-red-500/20 shadow-2xl relative animate-fade-in">
            <div className="flex items-center gap-3 mb-6 text-red-400">
              <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-sm font-bold tracking-widest uppercase text-white">
                  Application Encountered An Error
                </h2>
                <p className="text-[11px] text-[#888898] mt-0.5">
                  A client-side runtime exception occurred.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#111116] border border-[#22222a] mb-6 overflow-x-auto max-h-48">
              <p className="text-xs font-mono text-red-300 font-semibold mb-2">
                {this.state.error?.message || 'Unknown render error'}
              </p>
              {this.state.error?.stack && (
                <pre className="text-[10px] font-mono text-[#666675] whitespace-pre-wrap leading-relaxed">
                  {this.state.error.stack.slice(0, 500)}
                </pre>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={this.handleReload}
                className="flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-white hover:bg-gray-200 text-black text-xs font-bold tracking-wider uppercase transition-colors"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Reload Page</span>
              </button>
              <button
                onClick={this.handleReset}
                className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-[#181820] hover:bg-[#22222c] text-[#aaaaaa] hover:text-white text-xs font-semibold tracking-wider uppercase transition-colors border border-[#2a2a35]"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span>Reset & Log In</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
