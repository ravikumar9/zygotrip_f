'use client';
import { useEffect, useState } from 'react';
import { RefreshCw, WifiOff, ServerCrash, AlertTriangle } from 'lucide-react';

interface ApiErrorStateProps {
  /** Error object from the failed request */
  error?: Error | null;
  /** Retry function (e.g., refetch from react-query) */
  onRetry?: () => void;
  /** Number of seconds to auto-retry (0 = no auto-retry) */
  autoRetrySeconds?: number;
  /** Title override */
  title?: string;
  /** Compact mode for inline use */
  compact?: boolean;
  className?: string;
}

/** Maps common error patterns to user-friendly messages + icons */
function getErrorInfo(error?: Error | null) {
  const msg = error?.message?.toLowerCase() || '';

  if (msg.includes('network') || msg.includes('fetch') || msg.includes('econnrefused')) {
    return {
      icon: WifiOff,
      title: 'No internet connection',
      description: 'Please check your network and try again.',
      color: 'text-amber-600',
      bg: 'bg-amber-50',
    };
  }
  if (msg.includes('500') || msg.includes('server')) {
    return {
      icon: ServerCrash,
      title: 'Server issue',
      description: 'Our servers are having a moment. We\'re on it!',
      color: 'text-red-500',
      bg: 'bg-red-50',
    };
  }
  if (msg.includes('timeout') || msg.includes('timed out')) {
    return {
      icon: RefreshCw,
      title: 'Request timed out',
      description: 'It\'s taking longer than expected. Try again.',
      color: 'text-blue-500',
      bg: 'bg-blue-50',
    };
  }
  return {
    icon: AlertTriangle,
    title: 'Something went wrong',
    description: 'We couldn\'t load this content. This is usually temporary.',
    color: 'text-neutral-500',
    bg: 'bg-page',
  };
}

/**
 * Friendly API error state with auto-retry countdown.
 *
 * Usage:
 *   <ApiErrorState error={error} onRetry={refetch} autoRetrySeconds={10} />
 */
export default function ApiErrorState({
  error,
  onRetry,
  autoRetrySeconds = 10,
  title,
  compact = false,
  className = '',
}: ApiErrorStateProps) {
  const info = getErrorInfo(error);
  const Icon = info.icon;
  const [countdown, setCountdown] = useState(autoRetrySeconds);

  useEffect(() => {
    if (!onRetry || autoRetrySeconds <= 0) return;
    setCountdown(autoRetrySeconds);

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          onRetry();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [onRetry, autoRetrySeconds]);

  if (compact) {
    return (
      <div className={`flex items-center gap-3 p-3 rounded-xl ${info.bg} ${className}`}>
        <Icon size={16} className={info.color} />
        <p className="text-xs text-neutral-600 flex-1">{title || info.title}</p>
        {onRetry && (
          <button onClick={onRetry} className="text-xs font-bold text-primary-600 hover:text-primary-700 shrink-0">
            Retry {countdown > 0 && `(${countdown}s)`}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`text-center py-12 ${className}`}>
      <div className={`w-16 h-16 mx-auto rounded-2xl ${info.bg} flex items-center justify-center mb-4`}>
        <Icon size={28} className={info.color} />
      </div>
      <h2 className="text-lg font-semibold text-neutral-900 mb-2">{title || info.title}</h2>
      <p className="text-sm text-neutral-400 mb-5 max-w-xs mx-auto">{info.description}</p>
      <div className="flex items-center justify-center gap-3">
        {onRetry && (
          <button
            onClick={() => { setCountdown(autoRetrySeconds); onRetry(); }}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <RefreshCw size={14} />
            Retry Now
          </button>
        )}
        <button
          onClick={() => typeof window !== 'undefined' && window.location.reload()}
          className="btn-secondary text-sm"
        >
          Reload Page
        </button>
      </div>
      {countdown > 0 && onRetry && (
        <p className="text-xs text-neutral-400 mt-3">Auto-retrying in {countdown}s…</p>
      )}
    </div>
  );
}
