import Link from 'next/link';
import { ArrowRight, Activity, Shield, Zap, BarChart3, Clock, TrendingUp } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-paper">
      {/* Subtle grid background */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.015]"
        style={{
          backgroundImage: `
            linear-gradient(hsl(var(--ink)) 1px, transparent 1px),
            linear-gradient(90deg, hsl(var(--ink)) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      {/* Header */}
      <header className="relative border-b border-border">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 bg-ink rounded-md flex items-center justify-center group-hover:scale-105 transition-transform">
              <Activity className="h-5 w-5 text-paper" strokeWidth={2.5} />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-xl text-ink tracking-tight">Micro-Alpha</span>
              <span className="text-2xs text-ink-faint uppercase tracking-widest">Sentiment Intelligence</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-8">
            <Link href="#features" className="text-sm text-ink-muted hover:text-ink transition-colors editorial-underline pb-0.5">
              Features
            </Link>
            <Link href="#pricing" className="text-sm text-ink-muted hover:text-ink transition-colors editorial-underline pb-0.5">
              Pricing
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/auth/login"
              className="text-sm text-ink-muted hover:text-ink transition-colors px-4 py-2"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="btn btn-primary text-sm px-5 py-2.5 rounded-md"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative max-w-6xl mx-auto px-6 pt-24 pb-32">
        <div className="max-w-3xl">
          {/* Eyebrow */}
          <div className="flex items-center gap-2 mb-6 opacity-0 animate-fade-up">
            <div className="w-2 h-2 rounded-full bg-accent live-indicator" />
            <span className="text-sm font-medium text-accent">Live Sentiment Feed</span>
          </div>

          {/* Headline */}
          <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl text-ink leading-[1.1] tracking-tight mb-6 opacity-0 animate-fade-up stagger-1">
            Alpha signals for
            <br />
            <span className="italic text-ink-muted">micro-cap</span> securities
          </h1>

          {/* Subhead */}
          <p className="text-lg md:text-xl text-ink-muted leading-relaxed max-w-xl mb-10 opacity-0 animate-fade-up stagger-2">
            Real-time sentiment analysis on SEC filings, news, and social data.
            Get actionable signals before mainstream providers.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4 opacity-0 animate-fade-up stagger-3">
            <Link
              href="/auth/register"
              className="btn btn-primary inline-flex items-center justify-center gap-2 text-base px-7 py-3.5 rounded-md"
            >
              Start Free Trial
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#features"
              className="btn btn-secondary inline-flex items-center justify-center gap-2 text-base px-7 py-3.5 rounded-md"
            >
              See How It Works
            </Link>
          </div>
        </div>

        {/* Stats strip */}
        <div className="mt-20 pt-10 border-t border-border opacity-0 animate-fade-up stagger-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
            {[
              { value: '<2s', label: 'Filing Latency' },
              { value: '97%', label: 'FinBERT Accuracy' },
              { value: '50+', label: 'Data Sources' },
              { value: '24/7', label: 'Live Monitoring' },
            ].map((stat) => (
              <div key={stat.label}>
                <div className="font-mono text-3xl md:text-4xl font-semibold text-ink tracking-tight">
                  {stat.value}
                </div>
                <div className="text-sm text-ink-faint mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative bg-paper-warm border-y border-border py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="max-w-xl mb-16">
            <h2 className="font-serif text-3xl md:text-4xl text-ink mb-4">
              Your information edge
            </h2>
            <p className="text-ink-muted leading-relaxed">
              We process SEC filings, news, and social sentiment 24/7 to surface
              trading signals that matter.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Clock,
                title: 'Sub-second Latency',
                description: 'Process SEC filings and breaking news within seconds of publication. Beat the market.',
              },
              {
                icon: Zap,
                title: 'FinBERT Sentiment',
                description: 'Financial-domain NLP trained on millions of documents for accurate sentiment scoring.',
              },
              {
                icon: BarChart3,
                title: 'Alpha Scoring',
                description: 'Proprietary algorithm ranks events by trading potential, accounting for liquidity and timing.',
              },
              {
                icon: TrendingUp,
                title: 'Direction Signals',
                description: 'Clear bullish/bearish indicators with confidence scores. No ambiguity.',
              },
              {
                icon: Activity,
                title: 'Real-time Feed',
                description: 'WebSocket streaming delivers events instantly. Never miss a market-moving headline.',
              },
              {
                icon: Shield,
                title: 'Limited Seats',
                description: 'Capped subscriptions preserve edge for serious traders. Exclusivity by design.',
              },
            ].map((feature) => (
              <div
                key={feature.title}
                className="card p-6 rounded-lg group hover:shadow-card-hover transition-shadow"
              >
                <div className="w-10 h-10 rounded-md bg-accent-light flex items-center justify-center mb-4 group-hover:bg-accent group-hover:text-paper transition-colors">
                  <feature.icon className="h-5 w-5 text-accent group-hover:text-paper transition-colors" />
                </div>
                <h3 className="font-serif text-lg text-ink mb-2">{feature.title}</h3>
                <p className="text-sm text-ink-muted leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="card-elevated rounded-xl p-10 md:p-14 text-center">
            <h2 className="font-serif text-3xl md:text-4xl text-ink mb-4">
              Ready for an edge?
            </h2>
            <p className="text-ink-muted max-w-lg mx-auto mb-8">
              Join traders who identify opportunities in illiquid markets
              before the crowd. Limited seats available.
            </p>
            <Link
              href="/auth/register"
              className="btn btn-primary inline-flex items-center gap-2 text-base px-8 py-4 rounded-md"
            >
              Start Your Free Trial
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-ink-faint" />
            <span className="text-sm text-ink-faint">Micro-Alpha</span>
          </div>
          <p className="text-sm text-ink-faint">
            &copy; {new Date().getFullYear()} Micro-Alpha. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
