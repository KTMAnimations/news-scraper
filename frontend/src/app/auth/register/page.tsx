'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Mail, Lock, User, ArrowRight, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';

const registerSchema = z
  .object({
    full_name: z.string().min(2, 'Name must be at least 2 characters'),
    email: z.string().email('Invalid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
        'Password must contain uppercase, lowercase, and a number'
      ),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterForm) => {
    setError(null);

    try {
      await api.register(data.email, data.password, data.full_name);
      setSuccess(true);
      setTimeout(() => {
        router.push('/auth/login');
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    }
  };

  if (success) {
    return (
      <div className="opacity-0 animate-fade-up">
        <div className="card-elevated rounded-xl p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-bullish-bg mx-auto mb-4 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-bullish" />
          </div>
          <h2 className="font-serif text-2xl text-ink mb-2">Account created!</h2>
          <p className="text-ink-muted">
            Redirecting you to sign in...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="opacity-0 animate-fade-up">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ink mb-2">Create your account</h1>
        <p className="text-ink-muted">
          Start your 14-day free trial. No credit card required.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {error && (
          <div className="bg-bearish-bg border border-bearish/20 text-bearish px-4 py-3 rounded-lg text-sm flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-bearish mt-1.5 flex-shrink-0" />
            {error}
          </div>
        )}

        <div>
          <label
            htmlFor="full_name"
            className="block text-sm font-medium text-ink mb-2"
          >
            Full Name
          </label>
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
            <input
              {...register('full_name')}
              type="text"
              id="full_name"
              autoComplete="name"
              className="input w-full pl-11 pr-4 py-3 rounded-lg text-ink placeholder-ink-faint"
              placeholder="John Doe"
            />
          </div>
          {errors.full_name && (
            <p className="mt-1.5 text-sm text-bearish">
              {errors.full_name.message}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-ink mb-2"
          >
            Email
          </label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
            <input
              {...register('email')}
              type="email"
              id="email"
              autoComplete="email"
              className="input w-full pl-11 pr-4 py-3 rounded-lg text-ink placeholder-ink-faint"
              placeholder="you@example.com"
            />
          </div>
          {errors.email && (
            <p className="mt-1.5 text-sm text-bearish">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-sm font-medium text-ink mb-2"
          >
            Password
          </label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
            <input
              {...register('password')}
              type="password"
              id="password"
              autoComplete="new-password"
              className="input w-full pl-11 pr-4 py-3 rounded-lg text-ink placeholder-ink-faint"
              placeholder="Create a strong password"
            />
          </div>
          {errors.password && (
            <p className="mt-1.5 text-sm text-bearish">
              {errors.password.message}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="confirmPassword"
            className="block text-sm font-medium text-ink mb-2"
          >
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
            <input
              {...register('confirmPassword')}
              type="password"
              id="confirmPassword"
              autoComplete="new-password"
              className="input w-full pl-11 pr-4 py-3 rounded-lg text-ink placeholder-ink-faint"
              placeholder="Confirm your password"
            />
          </div>
          {errors.confirmPassword && (
            <p className="mt-1.5 text-sm text-bearish">
              {errors.confirmPassword.message}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="btn btn-primary w-full py-3 rounded-lg flex items-center justify-center gap-2 mt-6"
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
      <p className="mt-8 text-center text-sm text-ink-muted">
        Already have an account?{' '}
        <Link
          href="/auth/login"
          className="text-accent hover:text-accent-dark font-medium transition-colors editorial-underline pb-0.5"
        >
          Sign in
        </Link>
      </p>

      <p className="mt-4 text-xs text-ink-faint text-center leading-relaxed">
        By creating an account, you agree to our{' '}
        <Link href="/terms" className="underline hover:text-ink-muted">
          Terms of Service
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="underline hover:text-ink-muted">
          Privacy Policy
        </Link>
        .
      </p>
    </div>
  );
}
