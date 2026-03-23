'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { confirmWalletTopup } from '@/services/wallet';
import toast from 'react-hot-toast';

function TopupReturnContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Verifying your payment...');

  useEffect(() => {
    const orderId = searchParams.get('order_id');
    const amount = searchParams.get('amount');
    if (!orderId || !amount) {
      setStatus('error');
      setMessage('Invalid return URL.');
      return;
    }
    confirmWalletTopup(parseFloat(amount), orderId)
      .then((data) => {
        setStatus('success');
        setMessage(data.message || `₹${amount} added to your ZygoWallet!`);
        setTimeout(() => router.push('/wallet'), 2000);
      })
      .catch((err) => {
        setStatus('error');
        setMessage(err.message || 'Verification failed. Contact support.');
      });
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-page">
      <div className="text-center max-w-sm px-4 bg-white/80 rounded-2xl p-8 shadow-lg">
        {status === 'loading' && <><Loader2 className="w-16 h-16 animate-spin text-red-500 mx-auto mb-4" /><h2 className="text-xl font-bold">Verifying Payment</h2><p className="text-neutral-500 mt-2">{message}</p></>}
        {status === 'success' && <><CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" /><h2 className="text-xl font-bold text-green-700">Wallet Topped Up!</h2><p className="text-neutral-500 mt-2">{message}</p></>}
        {status === 'error' && <><XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" /><h2 className="text-xl font-bold">Verification Failed</h2><p className="text-neutral-500 mt-2 text-sm">{message}</p><button onClick={() => router.push('/wallet')} className="mt-4 px-6 py-2 bg-red-500 text-white rounded-lg">Back to Wallet</button></>}
      </div>
    </div>
  );
}

export default function TopupReturnPage() {
  return <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="w-16 h-16 animate-spin text-red-500" /></div>}><TopupReturnContent /></Suspense>;
}
