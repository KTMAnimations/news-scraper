'use client';

import { useState, Suspense } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormData = z.infer<typeof loginSchema>;

function LoginFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard';
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setError(null);

    const result = await signIn('credentials', {
      email: data.email,
      password: data.password,
      redirect: false,
    });

    if (result?.error) {
      setError('Invalid email or password. Please try again.');
    } else {
      router.push(callbackUrl);
    }
  };

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
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-primary/10 border border-bg-primary/20 mb-6">
                <div className="w-2 h-2 rounded-full bg-positive animate-pulse" />
                <span className="text-sm font-medium text-bg-primary/90">Live Feed Active</span>
              </div>

              <h2 className="text-4xl xl:text-5xl font-bold text-bg-primary leading-[1.15] mb-5 tracking-tight">
                Welcome back
                <br />
                <span className="text-bg-primary/60">to your dashboard</span>
              </h2>
              <p className="text-bg-primary/60 text-lg leading-relaxed max-w-md">
                Access real-time sentiment signals and alpha opportunities for micro-cap securities.
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

          {/* Footer quote */}
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

      {/* Right panel - Login form */}
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
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-text-primary mb-2 tracking-tight">
                Sign in
              </h1>
              <p className="text-text-secondary">
                Enter your credentials to access your account
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

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-text-primary"
                  >
                    Password
                  </label>
                  <Link
                    href="/forgot-password"
                    className="text-sm text-accent hover:text-accent-hover transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    {...register('password')}
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    autoComplete="current-password"
                    className="input py-3 pr-12"
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary transition-colors"
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-sm text-negative">{errors.password.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary w-full py-3 mt-2 flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="animate-spin h-4 w-4" />
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="relative my-8">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center">
                <span className="bg-bg-primary px-4 text-sm text-text-tertiary">or continue with</span>
              </div>
            </div>

            {/* OAuth buttons */}
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => signIn('google', { callbackUrl })}
                className="btn btn-secondary py-3 flex items-center justify-center gap-2 text-sm"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Google
              </button>
              <button
                type="button"
                onClick={() => signIn('github', { callbackUrl })}
                className="btn btn-secondary py-3 flex items-center justify-center gap-2 text-sm"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"/>
                </svg>
                GitHub
              </button>
            </div>

            {/* Footer */}
            <p className="mt-8 text-center text-sm text-text-secondary">
              Don&apos;t have an account?{' '}
              <Link
                href="/register"
                className="text-accent hover:text-accent-hover font-medium transition-colors link-underline"
              >
                Create one
              </Link>
            </p>
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

function LoginFormFallback() {
  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center">
      <div className="w-full max-w-md p-6 space-y-5">
        <div className="space-y-2">
          <div className="h-8 skeleton w-1/2" />
          <div className="h-5 skeleton w-3/4" />
        </div>
        <div className="space-y-4 pt-4">
          <div className="h-12 skeleton" />
          <div className="h-12 skeleton" />
          <div className="h-12 skeleton" />
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFormFallback />}>
      <LoginFormContent />
    </Suspense>
  );
}
