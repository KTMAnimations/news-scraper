import Link from 'next/link';
import { ArrowRight, Zap, Shield, Clock, TrendingUp } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">MA</span>
            </div>
            <span className="text-white font-semibold text-lg">Micro-Alpha</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link
              href="/auth/login"
              className="text-slate-300 hover:text-white transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center px-3 py-1 bg-brand-500/10 border border-brand-500/20 rounded-full text-brand-400 text-sm mb-6">
            <Zap className="h-4 w-4 mr-2" />
            Real-time sentiment analysis
          </div>
          <h1 className="text-4xl md:text-6xl font-bold text-white mb-6 leading-tight">
            Alpha signals for{' '}
            <span className="text-brand-400">micro-cap</span> securities
          </h1>
          <p className="text-xl text-slate-400 mb-8">
            Get actionable sentiment signals on thinly-traded assets before
            mainstream data providers. Powered by FinBERT NLP and real-time SEC
            filing analysis.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="w-full sm:w-auto px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-medium rounded-lg transition-colors flex items-center justify-center"
            >
              Start free trial
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <Link
              href="#features"
              className="w-full sm:w-auto px-6 py-3 border border-slate-600 text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              Learn more
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white mb-4">
            Your information edge
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto">
            We monitor SEC filings, news sources, and social sentiment 24/7 to
            deliver signals that matter.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="p-6 bg-slate-800/50 border border-slate-700 rounded-xl">
            <div className="w-12 h-12 bg-brand-500/10 rounded-lg flex items-center justify-center mb-4">
              <Clock className="h-6 w-6 text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Sub-second latency
            </h3>
            <p className="text-slate-400 text-sm">
              Process SEC filings and news within seconds of publication.
            </p>
          </div>

          <div className="p-6 bg-slate-800/50 border border-slate-700 rounded-xl">
            <div className="w-12 h-12 bg-brand-500/10 rounded-lg flex items-center justify-center mb-4">
              <Zap className="h-6 w-6 text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              FinBERT sentiment
            </h3>
            <p className="text-slate-400 text-sm">
              Financial-domain NLP for accurate sentiment analysis.
            </p>
          </div>

          <div className="p-6 bg-slate-800/50 border border-slate-700 rounded-xl">
            <div className="w-12 h-12 bg-brand-500/10 rounded-lg flex items-center justify-center mb-4">
              <TrendingUp className="h-6 w-6 text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Alpha scoring
            </h3>
            <p className="text-slate-400 text-sm">
              Proprietary scoring algorithm ranks events by trading potential.
            </p>
          </div>

          <div className="p-6 bg-slate-800/50 border border-slate-700 rounded-xl">
            <div className="w-12 h-12 bg-brand-500/10 rounded-lg flex items-center justify-center mb-4">
              <Shield className="h-6 w-6 text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Limited seats
            </h3>
            <p className="text-slate-400 text-sm">
              Capped subscriptions preserve edge for serious traders.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="bg-gradient-to-r from-brand-600/20 to-brand-500/10 border border-brand-500/20 rounded-2xl p-8 md:p-12 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to get started?
          </h2>
          <p className="text-slate-300 mb-8 max-w-xl mx-auto">
            Join traders who use Micro-Alpha to identify opportunities in
            illiquid markets before the crowd.
          </p>
          <Link
            href="/auth/register"
            className="inline-flex items-center px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-medium rounded-lg transition-colors"
          >
            Start your free trial
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-slate-500 text-sm">
          <p>&copy; 2024 Micro-Alpha. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
