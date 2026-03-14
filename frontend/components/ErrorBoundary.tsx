'use client';

import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { analytics } from '@/lib/analytics';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Production Error Boundary — catches unhandled React rendering errors.
 *
 * - Reports to analytics + Sentry
 * - Shows friendly recovery UI with retry
 * - Prevents full-page crashes
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });

    // Report to analytics + Sentry
    analytics.captureError(error, {
      componentStack: errorInfo.componentStack || 'unknown',
      page: typeof window !== 'undefined' ? window.location.pathname : 'unknown',
    });

    analytics.track('error_boundary_triggered', {
      error_name: error.name,
      error_message: error.message.slice(0, 200),
      page: typeof window !== 'undefined' ? window.location.pathname : 'unknown',
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[60vh] flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center bg-white rounded-2xl shadow-card p-8">
            <div className="text-5xl mb-4">😵</div>
            <h2 className="text-xl font-bold text-neutral-900 mb-2">Something went wrong</h2>
            <p className="text-sm text-neutral-500 mb-6">
              We hit an unexpected error. Our team has been notified. You can try refreshing the page or going back.
            </p>

            <div className="flex items-center justify-center gap-3">
              <button
                onClick={this.handleReset}
                className="px-5 py-2.5 text-sm font-semibold text-primary-600 border border-primary-200 rounded-xl hover:bg-primary-50 transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={this.handleReload}
                className="px-5 py-2.5 text-sm font-semibold text-white bg-primary-600 rounded-xl hover:bg-primary-700 transition-colors"
              >
                Reload Page
              </button>
            </div>

            {/* Show error details in dev */}
            {process.env.NODE_ENV !== 'production' && this.state.error && (
              <details className="mt-6 text-left">
                <summary className="text-xs text-neutral-400 cursor-pointer hover:text-neutral-600">
                  Error Details (dev only)
                </summary>
                <pre className="mt-2 p-3 bg-neutral-50 rounded-lg text-xs text-red-600 overflow-x-auto whitespace-pre-wrap">
                  {this.state.error.message}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
