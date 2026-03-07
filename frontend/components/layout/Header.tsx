'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { Menu, X, User, Wallet, LogOut, ChevronDown, BookOpen } from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';

const NAV_LINKS = [
  { href: '/hotels',   label: 'Hotels',   icon: '🏨' },
  { href: '/buses',    label: 'Buses',    icon: '🚌' },
  { href: '/cabs',     label: 'Cabs',     icon: '🚕' },
  { href: '/packages', label: 'Packages', icon: '🌴' },
];

export default function Header() {
  const pathname  = usePathname();
  const router    = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  const [menuOpen,     setMenuOpen]     = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = async () => {
    setUserMenuOpen(false);
    setMenuOpen(false);
    await logout();
    toast.success('Signed out successfully');
    router.push('/');
  };

  return (
    <header className="fixed top-0 inset-x-0 z-50" style={{ background: 'var(--bg-dark)', height: 56, boxShadow: '0 2px 20px rgba(0,0,0,0.2)' }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">

        {/* Logo */}
        <Link href="/" className="shrink-0">
          <span className="text-2xl font-black text-white font-heading tracking-tight">
            Zygo<span style={{ color: 'var(--primary)' }}>Trip</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-7">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-bold uppercase transition-colors duration-150"
              style={{
                letterSpacing: '0.5px',
                color: pathname.startsWith(link.href) ? '#fff' : 'rgba(255,255,255,0.7)',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#fff'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = pathname.startsWith(link.href) ? '#fff' : 'rgba(255,255,255,0.7)'; }}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* List Your Property CTA */}
        <Link
          href="/list-property"
          className="hidden md:flex items-center gap-1.5 text-sm font-bold px-3 py-1.5 rounded-full transition-colors shrink-0"
          style={{ border: '1.5px solid rgba(255,255,255,0.35)', color: 'rgba(255,255,255,0.85)' }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.12)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          🏨 List Property
        </Link>

        {/* Desktop auth */}
        <div className="hidden md:flex items-center gap-3">
          {isLoading ? (
            <div className="w-24 h-8 rounded-full animate-pulse" style={{ background: 'rgba(255,255,255,0.1)' }} />
          ) : isAuthenticated && user ? (
            <>
              <Link href="/wallet" className="flex items-center gap-1.5 text-sm font-bold transition-colors"
                style={{ color: 'rgba(255,255,255,0.7)' }}
                onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = '#fff')}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)')}>
                <Wallet size={15} /> Wallet
              </Link>

              <div ref={userMenuRef} className="relative">
                <button
                  onClick={() => setUserMenuOpen(v => !v)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full font-bold text-white transition-colors"
                  style={{ border: '1.5px solid rgba(255,255,255,0.3)', background: userMenuOpen ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.05)' }}
                >
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-black shrink-0"
                    style={{ background: 'var(--primary)' }}>
                    {user.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
                  </div>
                  <span className="text-sm max-w-[90px] truncate">{user.full_name?.split(' ')[0]}</span>
                  <ChevronDown size={13} className={clsx('text-white/60 transition-transform', userMenuOpen && 'rotate-180')} />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-52 bg-white rounded-2xl shadow-modal border border-neutral-100 py-1.5 z-50 animate-slide-down">
                    <div className="px-4 py-3 border-b border-neutral-100">
                      <p className="text-sm font-black text-neutral-900 truncate">{user.full_name}</p>
                      <p className="text-xs text-neutral-400 truncate mt-0.5">{user.email}</p>
                    </div>
                    <Link href="/account" onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors">
                      <User size={15} className="text-neutral-400" /> My Account
                    </Link>
                    <Link href="/account" onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors">
                      <BookOpen size={15} className="text-neutral-400" /> My Bookings
                    </Link>
                    <Link href="/wallet" onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors">
                      <Wallet size={15} className="text-neutral-400" /> Wallet
                    </Link>
                    <div className="border-t border-neutral-100 mt-1 pt-1">
                      <button onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm font-bold hover:bg-red-50 transition-colors"
                        style={{ color: 'var(--primary)' }}>
                        <LogOut size={15} /> Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <button onClick={() => router.push('/account/login')}
                className="px-4 py-1.5 rounded-full text-sm font-bold text-white transition-colors"
                style={{ border: '1.5px solid rgba(255,255,255,0.4)', background: 'transparent' }}
                onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.1)')}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}>
                Login
              </button>
              <button onClick={() => router.push('/account/register')}
                className="px-4 py-1.5 rounded-full text-sm font-black text-white transition-colors"
                style={{ background: 'var(--primary)' }}
                onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'var(--primary-dark)')}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'var(--primary)')}>
                Sign Up
              </button>
            </>
          )}
        </div>

        {/* Mobile menu button */}
        <button onClick={() => setMenuOpen(v => !v)}
          className="md:hidden p-2 rounded-xl transition-colors text-white/80 hover:text-white" aria-label="Toggle menu">
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden px-4 py-4 space-y-1 border-t"
          style={{ background: 'var(--bg-mid)', borderColor: 'rgba(255,255,255,0.1)' }}>
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} onClick={() => setMenuOpen(false)}
              className="flex items-center gap-2 py-2.5 px-3 rounded-xl text-sm font-bold transition-colors"
              style={{ color: pathname.startsWith(link.href) ? '#fff' : 'rgba(255,255,255,0.7)', background: pathname.startsWith(link.href) ? 'rgba(255,255,255,0.1)' : 'transparent' }}>
              {link.icon} {link.label}
            </Link>
          ))}
          <Link href="/list-property" onClick={() => setMenuOpen(false)}
            className="flex items-center gap-2 py-2.5 px-3 text-sm font-bold rounded-xl transition-colors"
            style={{ color: 'rgba(255,255,255,0.8)', background: 'rgba(255,255,255,0.07)' }}>
            🏨 List Your Property
          </Link>

          <div className="pt-3 space-y-1 border-t" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
            {isAuthenticated && user ? (
              <>
                <div className="flex items-center gap-3 px-3 py-2.5">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-black" style={{ background: 'var(--primary)' }}>
                    {user.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
                  </div>
                  <div>
                    <p className="text-sm font-black text-white">{user.full_name}</p>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>{user.email}</p>
                  </div>
                </div>
                <Link href="/account" onClick={() => setMenuOpen(false)} className="flex items-center gap-2 py-2.5 px-3 text-sm font-semibold rounded-xl transition-colors" style={{ color: 'rgba(255,255,255,0.7)' }}>
                  <User size={15} /> My Account
                </Link>
                <Link href="/wallet" onClick={() => setMenuOpen(false)} className="flex items-center gap-2 py-2.5 px-3 text-sm font-semibold rounded-xl transition-colors" style={{ color: 'rgba(255,255,255,0.7)' }}>
                  <Wallet size={15} /> Wallet
                </Link>
                <button onClick={handleLogout} className="w-full flex items-center gap-2 py-2.5 px-3 text-sm font-bold rounded-xl transition-colors" style={{ color: 'var(--primary-light)' }}>
                  <LogOut size={15} /> Sign Out
                </button>
              </>
            ) : (
              <>
                <Link href="/account/login" onClick={() => setMenuOpen(false)} className="flex items-center py-2.5 px-3 text-sm font-bold rounded-xl transition-colors" style={{ color: 'rgba(255,255,255,0.7)' }}>
                  Login
                </Link>
                <Link href="/account/register" onClick={() => setMenuOpen(false)} className="flex items-center justify-center py-2.5 px-3 text-sm font-black text-white rounded-xl transition-colors" style={{ background: 'var(--primary)' }}>
                  Sign Up Free
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
