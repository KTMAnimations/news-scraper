'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, ArrowRight, Check, Eye, EyeOff } from 'lucide-react';
import { api } from '@/lib/api';

const registerSchema = z
  .object({
    username: z
      .string()
      .min(3, 'Username must be at least 3 characters')
      .max(30, 'Username must be at most 30 characters')
      .regex(/^[a-zA-Z0-9_-]+$/, 'Username can only contain letters, numbers, underscores, and hyphens'),
    email: z.string().email('Please enter a valid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
        'Password must contain at least one uppercase letter, one lowercase letter, and one number'
      ),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: 'onChange',
  });

  const password = watch('password', '');

  // Password strength indicator
  const getPasswordStrength = (pwd: string) => {
    let strength = 0;
    if (pwd.length >= 8) strength++;
    if (pwd.length >= 12) strength++;
    if (/[a-z]/.test(pwd)) strength++;
    if (/[A-Z]/.test(pwd)) strength++;
    if (/\d/.test(pwd)) strength++;
    if (/[^a-zA-Z\d]/.test(pwd)) strength++;
    return Math.min(strength, 5);
  };

  const passwordStrength = getPasswordStrength(password);
  const strengthLabels = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'];
  const strengthColors = ['bg-negative', 'bg-warning', 'bg-warning', 'bg-positive', 'bg-positive'];

  const onSubmit = async (data: RegisterFormData) => {
    setError(null);

    try {
      await api.register(data.email, data.password, data.username);
      setSuccess(true);
      setTimeout(() => {
        router.push('/login');
      }, 2000);
    } catch (err) {
      // In mock mode, registration always succeeds
      if (process.env.NEXT_PUBLIC_MOCK_MODE === 'true') {
        setSuccess(true);
        setTimeout(() => {
          router.push('/login');
        }, 2000);
        return;
      }
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="animate-scale-in w-full max-w-md">
          <div className="card p-8 text-center rounded-2xl">
            <div className="w-16 h-16 rounded-full bg-positive-subtle mx-auto mb-5 flex items-center justify-center">
              <Check className="h-8 w-8 text-positive" strokeWidth={2.5} />
            </div>
            <h2 className="text-2xl font-bold text-text-primary mb-2">Account created!</h2>
            <p className="text-text-secondary">
              Redirecting you to sign in...
            </p>
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
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-primary/10 border border-bg-primary/20 mb-6">
                <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                <span className="text-sm font-medium text-bg-primary/90">14-Day Free Trial</span>
              </div>

              <h2 className="text-4xl xl:text-5xl font-bold text-bg-primary leading-[1.15] mb-5 tracking-tight">
                Start trading
                <br />
                <span className="text-bg-primary/60">with conviction</span>
              </h2>
              <p className="text-bg-primary/60 text-lg leading-relaxed max-w-md">
                Get instant access to AI-powered sentiment signals on micro-cap securities.
              </p>
            </div>

            {/* Features */}
            <div className="space-y-4">
              {[
                'Real-time SEC filing alerts',
                'AI sentiment analysis on news',
                'Custom watchlist with notifications',
                'High-alpha signal detection',
              ].map((feature) => (
                <div key={feature} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-positive/20 flex items-center justify-center flex-shrink-0">
                    <Check className="h-3 w-3 text-positive" strokeWidth={3} />
                  </div>
                  <span className="text-bg-primary/80">{feature}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="pt-8 border-t border-bg-primary/10">
            <div className="flex items-center gap-4">
              <div className="flex -space-x-2">
                {['JR', 'AK', 'MR', 'SC'].map((initials, i) => (
                  <div
                    key={initials}
                    className="w-8 h-8 rounded-full bg-accent/20 border-2 border-text-primary flex items-center justify-center"
                    style={{ zIndex: 4 - i }}
                  >
                    <span className="font-mono font-semibold text-xs text-accent">{initials}</span>
                  </div>
                ))}
              </div>
              <div className="text-bg-primary/70 text-sm">
                <span className="font-semibold text-bg-primary">2,500+</span> traders already onboard
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel - Registration form */}
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
        <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10 overflow-y-auto">
          <div className="w-full max-w-md animate-fade-up py-8">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-text-primary mb-2 tracking-tight">
                Create your account
              </h1>
              <p className="text-text-secondary">
                Start your 14-day free trial. No credit card required.
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
                  htmlFor="username"
                  className="block text-sm font-medium text-text-primary"
                >
                  Username
                </label>
                <input
                  {...register('username')}
                  type="text"
                  id="username"
                  autoComplete="username"
                  className="input py-3"
                  placeholder="johndoe"
                />
                {errors.username && (
                  <p className="text-sm text-negative">{errors.username.message}</p>
                )}
              </div>

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
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-text-primary"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    {...register('password')}
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    autoComplete="new-password"
                    className="input py-3 pr-12"
                    placeholder="Create a strong password"
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

                {/* Password strength indicator */}
                {password && (
                  <div className="space-y-2 mt-2">
                    <div className="flex gap-1">
                      {[...Array(5)].map((_, i) => (
                        <div
                          key={i}
                          className={`h-1 flex-1 rounded-full transition-colors ${
                            i < passwordStrength
                              ? strengthColors[passwordStrength - 1]
                              : 'bg-border'
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-xs text-text-tertiary">
                      Password strength: {passwordStrength > 0 ? strengthLabels[passwordStrength - 1] : 'Too short'}
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="confirmPassword"
                  className="block text-sm font-medium text-text-primary"
                >
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    {...register('confirmPassword')}
                    type={showConfirmPassword ? 'text' : 'password'}
                    id="confirmPassword"
                    autoComplete="new-password"
                    className="input py-3 pr-12"
                    placeholder="Confirm your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary transition-colors"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-sm text-negative">{errors.confirmPassword.message}</p>
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
                    Creating account...
                  </>
                ) : (
                  <>
                    Create account
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            {/* Footer */}
            <p className="mt-8 text-center text-sm text-text-secondary">
              Already have an account?{' '}
              <Link
                href="/login"
                className="text-accent hover:text-accent-hover font-medium transition-colors link-underline"
              >
                Sign in
              </Link>
            </p>

            <p className="mt-4 text-xs text-text-quaternary text-center leading-relaxed">
              By creating an account, you agree to our{' '}
              <Link href="/terms" className="text-text-tertiary hover:text-text-secondary transition-colors">
                Terms of Service
              </Link>{' '}
              and{' '}
              <Link href="/privacy" className="text-text-tertiary hover:text-text-secondary transition-colors">
                Privacy Policy
              </Link>
              .
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
