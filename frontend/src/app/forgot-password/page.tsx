'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, ArrowRight, ArrowLeft, Mail, Check } from 'lucide-react';

const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

export default function ForgotPasswordPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState<string>('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setError(null);

    try {
      // In mock mode, always succeed
      if (MOCK_MODE) {
        setSubmittedEmail(data.email);
        setSuccess(true);
        return;
      }

      const response = await fetch(`${API_URL}/api/v1/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: data.email }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send reset email');
      }

      setSubmittedEmail(data.email);
      setSuccess(true);
    } catch (err) {
      // Even if there's an error, we don't want to reveal if the email exists or not
      // So we show success regardless for security
      setSubmittedEmail(data.email);
      setSuccess(true);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="w-full max-w-md animate-scale-in">
          <div className="card p-8 text-center rounded-2xl">
            <div className="w-16 h-16 rounded-full bg-accent-subtle mx-auto mb-5 flex items-center justify-center">
              <Mail className="h-8 w-8 text-accent" strokeWidth={2} />
            </div>
            <h2 className="text-2xl font-bold text-text-primary mb-2">Check your email</h2>
            <p className="text-text-secondary mb-6">
              We sent a password reset link to{' '}
              <span className="font-medium text-text-primary">{submittedEmail}</span>
            </p>
            <div className="bg-bg-secondary rounded-xl p-4 text-left mb-6">
              <p className="text-sm text-text-tertiary">
                Didn&apos;t receive the email? Check your spam folder, or{' '}
                <button
                  onClick={() => setSuccess(false)}
                  className="text-accent hover:text-accent-hover font-medium transition-colors"
                >
                  try again
                </button>
                .
              </p>
            </div>
            <Link href="/login" className="btn btn-secondary w-full py-3 flex items-center justify-center gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-primary flex">
      {/* Left panel - Branding (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] bg-text-primary relative overflow-hidden">
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
              <h2 className="text-4xl xl:text-5xl font-bold text-bg-primary leading-[1.15] mb-5 tracking-tight">
                Reset your
                <br />
                <span className="text-bg-primary/60">password</span>
              </h2>
              <p className="text-bg-primary/60 text-lg leading-relaxed max-w-md">
                No worries, it happens to the best of us. We&apos;ll help you get back into your account.
              </p>
            </div>

            {/* Security info */}
            <div className="space-y-4">
              {[
                'We\'ll send a secure link to your email',
                'Link expires after 1 hour for security',
                'You can request a new link anytime',
              ].map((info) => (
                <div key={info} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                    <Check className="h-3 w-3 text-accent" strokeWidth={3} />
                  </div>
                  <span className="text-bg-primary/80">{info}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="pt-8 border-t border-bg-primary/10">
            <p className="text-bg-primary/60 text-sm">
              Having trouble? Contact our support team at{' '}
              <a href="mailto:support@micro-alpha.com" className="text-accent hover:text-accent-hover transition-colors">
                support@micro-alpha.com
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* Right panel - Forgot password form */}
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
          <div className="w-full max-w-md animate-fade-up">
            {/* Back link */}
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors mb-8"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to sign in
            </Link>

            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-text-primary mb-2 tracking-tight">
                Forgot password?
              </h1>
              <p className="text-text-secondary">
                Enter your email address and we&apos;ll send you a link to reset your password.
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              {error && (
                <div className="bg-negative-subtle border border-negative/20 text-negative px-4 py-3 rounded-xl text-sm flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-negative flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-text-primary"
                >
                  Email address
                </label>
                <input
                  {...register('email')}
                  type="email"
                  id="email"
                  autoComplete="email"
                  className="input py-3"
                  placeholder="you@example.com"
                />
                {errors.email && (
                  <p className="text-sm text-negative">{errors.email.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary w-full py-3 flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="animate-spin h-4 w-4" />
                    Sending reset link...
                  </>
                ) : (
                  <>
                    Send reset link
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            {/* Additional help */}
            <div className="mt-8 p-4 bg-bg-secondary rounded-xl">
              <p className="text-sm text-text-tertiary">
                Remember your password?{' '}
                <Link
                  href="/login"
                  className="text-accent hover:text-accent-hover font-medium transition-colors"
                >
                  Sign in instead
                </Link>
              </p>
            </div>
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
