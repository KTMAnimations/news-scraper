'use client';

import Link from 'next/link';
import { ArrowRight, ArrowUpRight } from 'lucide-react';

// Animated counter component
function AnimatedNumber({ value, suffix = '' }: { value: string; suffix?: string }) {
  return (
    <span className="font-mono text-4xl md:text-5xl font-semibold tracking-tight">
      {value}
      <span className="text-accent">{suffix}</span>
    </span>
  );
}

// Live data visualization component
function LiveDataViz() {
  return (
    <div className="relative w-full h-full min-h-[400px]">
      {/* Floating cards with mock data */}
      <div className="absolute top-8 left-8 card-glass p-4 rounded-xl animate-fade-up opacity-0 stagger-2 hover-lift">
        <div className="flex items-center gap-3 mb-3">
          <div className="live-dot" />
          <span className="text-xs font-medium text-text-secondary">Live Feed</span>
        </div>
        <div className="space-y-2">
          {[
            { ticker: 'ABCD', signal: '+', color: 'positive' },
            { ticker: 'EFGH', signal: '-', color: 'negative' },
            { ticker: 'IJKL', signal: '+', color: 'positive' },
          ].map((item, i) => (
            <div key={i} className="flex items-center justify-between gap-8 py-1.5 border-b border-border last:border-0">
              <span className="ticker-chip">{item.ticker}</span>
              <span className={`font-mono text-sm font-semibold text-${item.color}`}>
                {item.signal}82
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="absolute top-16 right-12 card-glass p-4 rounded-xl animate-fade-up opacity-0 stagger-3 hover-lift">
        <div className="data-label mb-2">Alpha Score</div>
        <div className="font-mono text-3xl font-bold text-accent">94</div>
        <div className="text-xs text-text-tertiary mt-1">High confidence</div>
      </div>

      <div className="absolute bottom-24 left-16 card-glass p-4 rounded-xl animate-fade-up opacity-0 stagger-4 hover-lift">
        <div className="data-label mb-2">SEC Filing</div>
        <div className="text-sm font-medium text-text-primary">Form 4 - Insider Buy</div>
        <div className="text-xs text-text-tertiary mt-1">2s ago</div>
      </div>

      <div className="absolute bottom-12 right-8 card-glass p-4 rounded-xl animate-fade-up opacity-0 stagger-5 hover-lift">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-positive" />
          <span className="data-label">Bullish</span>
        </div>
        <div className="font-mono text-2xl font-semibold text-positive">+127</div>
        <div className="text-xs text-text-tertiary">signals today</div>
      </div>

      {/* Decorative elements */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 400 400" fill="none">
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(var(--accent))" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(var(--accent))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M50,200 Q100,100 200,150 T350,100"
          stroke="url(#lineGradient)"
          strokeWidth="2"
          fill="none"
          className="animate-[draw-line_3s_ease-out_forwards]"
          style={{ strokeDasharray: 1000, strokeDashoffset: 1000 }}
        />
        <path
          d="M50,300 Q150,200 250,250 T400,200"
          stroke="url(#lineGradient)"
          strokeWidth="2"
          fill="none"
          className="animate-[draw-line_3s_ease-out_0.5s_forwards]"
          style={{ strokeDasharray: 1000, strokeDashoffset: 1000 }}
        />
      </svg>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen bg-bg-primary relative overflow-hidden">
      {/* Gradient orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-float" />
        <div className="absolute top-1/2 -left-40 w-80 h-80 bg-accent/5 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
        <div className="absolute -bottom-40 right-1/4 w-72 h-72 bg-positive/5 rounded-full blur-3xl animate-float" style={{ animationDelay: '4s' }} />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-border/50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-text-primary rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform">
              <span className="text-bg-primary font-mono font-bold text-sm">M</span>
            </div>
            <span className="font-semibold text-lg tracking-tight text-text-primary">Micro-Alpha</span>
          </Link>

          <nav className="hidden md:flex items-center gap-8">
            <Link href="#features" className="text-sm text-text-secondary hover:text-text-primary transition-colors link-underline">
              Features
            </Link>
            <Link href="#pricing" className="text-sm text-text-secondary hover:text-text-primary transition-colors link-underline">
              Pricing
            </Link>
            <Link href="#about" className="text-sm text-text-secondary hover:text-text-primary transition-colors link-underline">
              About
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/auth/login"
              className="btn btn-ghost text-sm"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="btn btn-primary text-sm px-5 py-2.5"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left column - Copy */}
          <div>
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-subtle border border-accent/20 mb-8 animate-fade-down opacity-0">
              <div className="live-dot" />
              <span className="text-sm font-medium text-accent">Real-time Sentiment Analysis</span>
            </div>

            {/* Headline */}
            <h1 className="text-5xl md:text-6xl lg:text-[4rem] font-bold text-text-primary leading-[1.1] tracking-tight mb-6 animate-fade-up opacity-0 stagger-1">
              Trade micro-caps
              <br />
              <span className="gradient-text">with conviction</span>
            </h1>

            {/* Subhead */}
            <p className="text-lg text-text-secondary leading-relaxed max-w-lg mb-10 animate-fade-up opacity-0 stagger-2">
              AI-powered sentiment analysis on SEC filings, breaking news, and social signals.
              Get alpha before the market moves.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 animate-fade-up opacity-0 stagger-3">
              <Link
                href="/auth/register"
                className="btn btn-primary inline-flex items-center justify-center gap-2 text-base px-7 py-3.5"
              >
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="#features"
                className="btn btn-secondary inline-flex items-center justify-center gap-2 text-base px-7 py-3.5"
              >
                Learn More
              </Link>
            </div>

            {/* Trust indicators */}
            <div className="flex items-center gap-8 mt-12 pt-8 border-t border-border animate-fade-up opacity-0 stagger-4">
              <div>
                <div className="font-mono text-2xl font-semibold text-text-primary">50+</div>
                <div className="text-sm text-text-tertiary">Data sources</div>
              </div>
              <div className="w-px h-10 bg-border" />
              <div>
                <div className="font-mono text-2xl font-semibold text-text-primary">&lt;2s</div>
                <div className="text-sm text-text-tertiary">Latency</div>
              </div>
              <div className="w-px h-10 bg-border" />
              <div>
                <div className="font-mono text-2xl font-semibold text-text-primary">97%</div>
                <div className="text-sm text-text-tertiary">Accuracy</div>
              </div>
            </div>
          </div>

          {/* Right column - Visualization */}
          <div className="relative hidden lg:block animate-blur-in opacity-0 stagger-2">
            <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent rounded-3xl" />
            <LiveDataViz />
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="relative z-10 border-y border-border bg-bg-secondary/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
            {[
              { value: '247', suffix: 'K', label: 'Events Processed' },
              { value: '12', suffix: 'ms', label: 'Avg Response Time' },
              { value: '99.9', suffix: '%', label: 'Uptime SLA' },
              { value: '24', suffix: '/7', label: 'Live Monitoring' },
            ].map((stat, i) => (
              <div
                key={stat.label}
                className={`text-center animate-fade-up opacity-0 stagger-${i + 1}`}
              >
                <AnimatedNumber value={stat.value} suffix={stat.suffix} />
                <div className="text-sm text-text-tertiary mt-2">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative z-10 py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-text-primary mb-4 animate-fade-up opacity-0">
              Your information edge
            </h2>
            <p className="text-text-secondary text-lg animate-fade-up opacity-0 stagger-1">
              Purpose-built for traders who need speed, accuracy, and actionable signals.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                title: 'Sub-second Processing',
                description: 'SEC filings and breaking news processed instantly. Get signals while others wait.',
                metric: '<2s',
                metricLabel: 'latency',
              },
              {
                title: 'FinBERT Analysis',
                description: 'Domain-specific NLP trained on financial documents for accurate sentiment scoring.',
                metric: '97%',
                metricLabel: 'accuracy',
              },
              {
                title: 'Alpha Scoring',
                description: 'Proprietary algorithm ranks events by trading potential, adjusted for liquidity.',
                metric: '±100',
                metricLabel: 'score range',
              },
              {
                title: 'Direction Signals',
                description: 'Clear bullish/bearish indicators with confidence scores. Zero ambiguity.',
                metric: '3x',
                metricLabel: 'signal types',
              },
              {
                title: 'Real-time Streaming',
                description: 'WebSocket delivery ensures you never miss a market-moving event.',
                metric: '24/7',
                metricLabel: 'live feed',
              },
              {
                title: 'Limited Access',
                description: 'Capped subscriptions to preserve alpha. Exclusivity by design.',
                metric: '100',
                metricLabel: 'seats only',
              },
            ].map((feature, i) => (
              <div
                key={feature.title}
                className={`card-interactive p-6 group animate-fade-up opacity-0 stagger-${(i % 3) + 1}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <h3 className="text-lg font-semibold text-text-primary group-hover:text-accent transition-colors">
                    {feature.title}
                  </h3>
                  <ArrowUpRight className="h-5 w-5 text-text-quaternary group-hover:text-accent transition-all group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
                <p className="text-sm text-text-secondary leading-relaxed mb-6">
                  {feature.description}
                </p>
                <div className="pt-4 border-t border-border">
                  <span className="font-mono text-2xl font-semibold text-text-primary">{feature.metric}</span>
                  <span className="text-sm text-text-tertiary ml-2">{feature.metricLabel}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="relative z-10 py-24 bg-bg-secondary/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="card p-8 md:p-12 rounded-2xl overflow-hidden relative">
            {/* Decorative gradient */}
            <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-accent/5 to-transparent pointer-events-none" />

            <div className="relative grid md:grid-cols-2 gap-12 items-center">
              <div>
                <blockquote className="text-xl md:text-2xl font-medium text-text-primary leading-relaxed mb-6">
                  &ldquo;Finally, a sentiment feed that understands micro-cap dynamics.
                  The Form 4 alerts alone have paid for our subscription.&rdquo;
                </blockquote>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-accent-subtle flex items-center justify-center">
                    <span className="font-mono font-semibold text-accent">JM</span>
                  </div>
                  <div>
                    <div className="font-medium text-text-primary">James Mitchell</div>
                    <div className="text-sm text-text-tertiary">Portfolio Manager, Apex Capital</div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="bg-bg-elevated rounded-xl p-5 border border-border">
                  <div className="font-mono text-3xl font-bold text-accent mb-1">+340%</div>
                  <div className="text-sm text-text-tertiary">Signal accuracy improvement</div>
                </div>
                <div className="bg-bg-elevated rounded-xl p-5 border border-border">
                  <div className="font-mono text-3xl font-bold text-positive mb-1">4.8x</div>
                  <div className="text-sm text-text-tertiary">ROI on subscription</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="relative overflow-hidden rounded-3xl bg-text-primary p-12 md:p-16">
            {/* Background effects */}
            <div className="absolute inset-0 opacity-20">
              <div className="absolute top-0 left-1/4 w-64 h-64 bg-accent rounded-full blur-3xl" />
              <div className="absolute bottom-0 right-1/4 w-48 h-48 bg-positive rounded-full blur-3xl" />
            </div>

            <div className="relative text-center">
              <h2 className="text-3xl md:text-4xl font-bold text-bg-primary mb-4">
                Ready to gain an edge?
              </h2>
              <p className="text-bg-primary/70 max-w-lg mx-auto mb-8 text-lg">
                Join traders who identify opportunities before the crowd.
                Limited seats available.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link
                  href="/auth/register"
                  className="btn bg-bg-primary text-text-primary hover:bg-bg-secondary inline-flex items-center justify-center gap-2 text-base px-8 py-4 rounded-xl font-medium transition-all"
                >
                  Start Free Trial
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/auth/login"
                  className="btn bg-transparent text-bg-primary border border-bg-primary/30 hover:bg-bg-primary/10 inline-flex items-center justify-center gap-2 text-base px-8 py-4 rounded-xl font-medium transition-all"
                >
                  Sign In
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 bg-text-primary rounded-md flex items-center justify-center">
                <span className="text-bg-primary font-mono font-bold text-xs">M</span>
              </div>
              <span className="text-sm text-text-secondary">Micro-Alpha</span>
            </div>

            <nav className="flex items-center gap-6">
              <Link href="#" className="text-sm text-text-tertiary hover:text-text-primary transition-colors">
                Terms
              </Link>
              <Link href="#" className="text-sm text-text-tertiary hover:text-text-primary transition-colors">
                Privacy
              </Link>
              <Link href="#" className="text-sm text-text-tertiary hover:text-text-primary transition-colors">
                Contact
              </Link>
            </nav>

            <p className="text-sm text-text-quaternary">
              &copy; {new Date().getFullYear()} Micro-Alpha. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
