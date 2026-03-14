'use client';

import Link from 'next/link';
import { ChevronRight, Home } from 'lucide-react';
import { BreadcrumbJsonLd } from '@/components/seo/JsonLd';

interface BreadcrumbItem {
  label: string;
  href: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

/**
 * Breadcrumbs — visible navigation + schema.org BreadcrumbList JSON-LD.
 *
 * Usage:
 *   <Breadcrumbs items={[
 *     { label: 'Hotels', href: '/hotels' },
 *     { label: 'Goa', href: '/hotels/goa' },
 *     { label: 'Taj Fort Aguada', href: '/hotels/taj-fort-aguada' },
 *   ]} />
 */
export default function Breadcrumbs({ items, className = '' }: BreadcrumbsProps) {
  const allItems = [{ label: 'Home', href: '/' }, ...items];

  return (
    <>
      <BreadcrumbJsonLd
        items={allItems.map((item) => ({ name: item.label, url: item.href }))}
      />
      <nav
        aria-label="Breadcrumb"
        className={`flex items-center gap-1.5 text-xs text-neutral-500 overflow-x-auto ${className}`}
      >
        {allItems.map((item, index) => {
          const isLast = index === allItems.length - 1;
          return (
            <span key={item.href} className="flex items-center gap-1.5 whitespace-nowrap">
              {index === 0 && <Home size={12} className="shrink-0" />}
              {index > 0 && <ChevronRight size={10} className="text-neutral-300 shrink-0" />}
              {isLast ? (
                <span className="font-semibold text-neutral-700 truncate max-w-[200px]">
                  {item.label}
                </span>
              ) : (
                <Link
                  href={item.href}
                  className="hover:text-primary-600 transition-colors truncate max-w-[200px]"
                >
                  {item.label}
                </Link>
              )}
            </span>
          );
        })}
      </nav>
    </>
  );
}
