'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { Plane, Hotel, Wallet, User, Menu, X, ChevronDown } from 'lucide-react';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? 'rgba(255,255,255,0.97)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        boxShadow: scrolled ? '0 2px 20px rgba(0,0,0,0.08)' : 'none',
      }}
    >
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #eb5757, #f97316)' }}>
              <span className="text-white font-bold text-sm">Z</span>
            </div>
            <span
              className="font-bold text-xl font-heading"
              style={{
                color: scrolled ? '#1a1a2e' : 'white',
              }}
            >
              ZygoTrip
            </span>
          </Link>

          {/* Center nav links */}
          <div className="hidden md:flex items-center gap-1">
            {[
              { icon: Hotel, label: 'Hotels', href: '/hotels' },
            ].map(({ icon: Icon, label, href }) => (
              <Link
                key={label}
                href={href}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all"
                style={{
                  color: scrolled ? '#374151' : 'rgba(255,255,255,0.9)',
                }}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}
          </div>

          {/* Right side */}
          <div className="hidden md:flex items-center gap-2">
            <Link
              href="/wallet"
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all"
              style={{ color: scrolled ? '#374151' : 'rgba(255,255,255,0.9)' }}
            >
              <Wallet size={16} />
              Wallet
            </Link>
            <Link
              href="/account"
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold"
              style={{
                background: scrolled ? 'linear-gradient(135deg, #eb5757, #c0392b)' : 'rgba(255,255,255,0.2)',
                color: 'white',
                backdropFilter: 'blur(8px)',
              }}
            >
              <User size={15} />
              My Account
            </Link>
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2"
            onClick={() => setMobileOpen(!mobileOpen)}
            style={{ color: scrolled ? '#1a1a2e' : 'white' }}
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden bg-white border-t border-gray-100 shadow-lg">
          <div className="p-4 space-y-1">
            <Link href="/hotels" className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-700 font-semibold hover:bg-gray-50">
              <Hotel size={18} /> Hotels
            </Link>
            <Link href="/wallet" className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-700 font-semibold hover:bg-gray-50">
              <Wallet size={18} /> Wallet
            </Link>
            <Link href="/account" className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-700 font-semibold hover:bg-gray-50">
              <User size={18} /> My Account
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
