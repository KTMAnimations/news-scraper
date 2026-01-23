'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

// Animated data ticker for visual interest
function DataTicker() {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setOffset((prev) => (prev + 1) % 100);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden opacity-10">
      <div
        className="flex flex-col gap-4 font-mono text-xs text-bg-primary whitespace-nowrap"
        style={{ transform: `translateY(-${offset * 0.5}px)` }}
      >
        {Array.from({ length: 30 }).map((_, i) => (
          <div key={i} className="flex gap-8">
            <span>ABCD +2.4%</span>
            <span>EFGH -1.2%</span>
            <span>IJKL +5.8%</span>
            <span>MNOP -0.3%</span>
            <span>QRST +1.9%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg-primary flex">
      {/* Left panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] bg-text-primary relative overflow-hidden">
        {/* Animated background */}
        <DataTicker />

        {/* Gradient overlays */}
        <div className="absolute inset-0 bg-gradient-to-br from-accent/20 via-transparent to-positive/10 pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-text-primary to-transparent pointer-events-none" />

        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16 w-full">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 bg-bg-primary rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform">
              <span className="text-text-primary font-mono font-bold text-sm">M</span>
            </div>
            <span className="font-semibold text-lg text-bg-primary tracking-tight">Micro-Alpha</span>
          </Link>

          {/* Main content */}
          <div className="space-y-10">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-primary/10 border border-bg-primary/20 mb-6">
                <div className="w-2 h-2 rounded-full bg-positive animate-pulse" />
                <span className="text-sm font-medium text-bg-primary/90">Live Feed Active</span>
              </div>

              <h2 className="text-4xl xl:text-5xl font-bold text-bg-primary leading-[1.15] mb-5 tracking-tight">
                Trade micro-caps
                <br />
                <span className="text-bg-primary/60">with conviction</span>
              </h2>
              <p className="text-bg-primary/60 text-lg leading-relaxed max-w-md">
                AI-powered sentiment analysis on SEC filings, breaking news, and social signals.
              </p>
            </div>

            {/* Stats */}
            <div className="flex gap-10">
              {[
                { value: '<2s', label: 'Latency' },
                { value: '97%', label: 'Accuracy' },
                { value: '50+', label: 'Sources' },
              ].map((stat) => (
                <div key={stat.label}>
                  <div className="font-mono text-3xl text-bg-primary font-semibold tracking-tight">
                    {stat.value}
                  </div>
                  <div className="text-sm text-bg-primary/50 mt-1">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Testimonial */}
          <div className="pt-8 border-t border-bg-primary/10">
            <blockquote className="text-bg-primary/80 text-lg mb-4 leading-relaxed">
              &ldquo;The only platform that consistently surfaces alpha before Bloomberg terminals.&rdquo;
            </blockquote>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
                <span className="font-mono font-semibold text-sm text-accent">JR</span>
              </div>
              <div>
                <div className="text-bg-primary text-sm font-medium">James Rodriguez</div>
                <div className="text-bg-primary/50 text-sm">PM, Apex Capital</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel - Auth form */}
      <div className="flex-1 flex flex-col relative">
        {/* Subtle background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-bg-secondary/30 via-transparent to-accent/5 pointer-events-none" />

        {/* Mobile header */}
        <div className="lg:hidden border-b border-border p-4 relative z-10">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-text-primary rounded-lg flex items-center justify-center">
              <span className="text-bg-primary font-mono font-bold text-xs">M</span>
            </div>
            <span className="font-semibold text-lg text-text-primary">Micro-Alpha</span>
          </Link>
        </div>

        {/* Form container */}
        <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10">
          <div className="w-full max-w-md">
            {children}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border p-6 text-center relative z-10">
          <p className="text-sm text-text-quaternary">
            &copy; {new Date().getFullYear()} Micro-Alpha. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}
