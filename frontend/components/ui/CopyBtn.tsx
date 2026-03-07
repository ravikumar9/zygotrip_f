'use client';

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export default function CopyBtn({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {
      // fallback for older browsers
      const el = document.createElement('textarea');
      el.value = code;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    });
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-black border-2 border-dashed transition-all select-none"
      style={{
        borderColor: 'var(--primary)',
        color:       copied ? 'var(--green)' : 'var(--primary)',
        background:  copied ? '#f0fdf4' : '#fff0f0',
      }}
      title="Copy coupon code"
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? 'Copied!' : code}
    </button>
  );
}
