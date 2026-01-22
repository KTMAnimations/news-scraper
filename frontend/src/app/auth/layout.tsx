import Link from 'next/link';
import { Activity } from 'lucide-react';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-paper flex">
      {/* Left panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-2/5 bg-ink relative overflow-hidden">
        {/* Subtle pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(hsl(var(--paper)) 1px, transparent 1px),
              linear-gradient(90deg, hsl(var(--paper)) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
          }}
        />

        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 bg-paper rounded-md flex items-center justify-center group-hover:scale-105 transition-transform">
              <Activity className="h-5 w-5 text-ink" strokeWidth={2.5} />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-xl text-paper tracking-tight">Micro-Alpha</span>
              <span className="text-2xs text-paper/50 uppercase tracking-widest">Sentiment Intelligence</span>
            </div>
          </Link>

          {/* Feature highlights */}
          <div className="space-y-8">
            <div>
              <div className="font-mono text-accent text-sm mb-2">&lt;2s latency</div>
              <h2 className="font-serif text-3xl text-paper leading-tight mb-3">
                Alpha signals for<br />
                <span className="italic text-paper/70">micro-cap</span> securities
              </h2>
              <p className="text-paper/60 leading-relaxed max-w-md">
                Real-time sentiment analysis on SEC filings, news, and social data.
                Get actionable signals before mainstream providers.
              </p>
            </div>

            <div className="flex gap-8">
              <div>
                <div className="font-mono text-2xl text-paper font-semibold">97%</div>
                <div className="text-sm text-paper/50">FinBERT Accuracy</div>
              </div>
              <div>
                <div className="font-mono text-2xl text-paper font-semibold">50+</div>
                <div className="text-sm text-paper/50">Data Sources</div>
              </div>
              <div>
                <div className="font-mono text-2xl text-paper font-semibold">24/7</div>
                <div className="text-sm text-paper/50">Monitoring</div>
              </div>
            </div>
          </div>

          {/* Testimonial */}
          <div className="border-t border-paper/10 pt-8">
            <blockquote className="text-paper/80 italic font-serif text-lg mb-4">
              &ldquo;The only platform that consistently surfaces alpha before Bloomberg terminals.&rdquo;
            </blockquote>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-paper/10 flex items-center justify-center text-paper/60 font-medium">
                JR
              </div>
              <div>
                <div className="text-paper text-sm font-medium">James Rodriguez</div>
                <div className="text-paper/50 text-sm">PM, Apex Capital</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel - Auth form */}
      <div className="flex-1 flex flex-col">
        {/* Mobile header */}
        <div className="lg:hidden border-b border-border p-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-ink rounded-md flex items-center justify-center">
              <Activity className="h-4 w-4 text-paper" strokeWidth={2.5} />
            </div>
            <span className="font-serif text-lg text-ink">Micro-Alpha</span>
          </Link>
        </div>

        {/* Form container */}
        <div className="flex-1 flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            {children}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border p-6 text-center">
          <p className="text-sm text-ink-faint">
            &copy; {new Date().getFullYear()} Micro-Alpha. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}
