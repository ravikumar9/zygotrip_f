import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="bg-neutral-900 text-neutral-300 mt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="col-span-2 md:col-span-1">
            <p className="text-2xl font-bold text-white mb-2">
              Zygo<span className="text-accent-500">Trip</span>
            </p>
            <p className="text-sm text-neutral-400 leading-relaxed">
              Your trusted travel companion — hotels, buses, cabs, and holiday packages.
            </p>
          </div>

          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Travel</h4>
            <ul className="space-y-2 text-sm">
              {['Hotels', 'Buses', 'Cabs', 'Packages'].map(item => (
                <li key={item}>
                  <Link href={`/${item.toLowerCase()}`} className="hover:text-white transition-colors">
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Company</h4>
            <ul className="space-y-2 text-sm">
              {['About', 'Careers', 'Blog', 'Press'].map(item => (
                <li key={item}>
                  <Link href="#" className="hover:text-white transition-colors">{item}</Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white text-sm font-semibold mb-4 uppercase tracking-wide">Support</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="#" className="hover:text-white transition-colors">Help Centre</Link></li>
              <li><Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link></li>
              <li><a href="mailto:support@zygotrip.com" className="hover:text-white transition-colors">Contact Us</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-neutral-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-neutral-500">
          <p>© {new Date().getFullYear()} ZygoTrip. All rights reserved.</p>
          <p>Made with ❤️ in India 🇮🇳</p>
        </div>
      </div>
    </footer>
  );
}
