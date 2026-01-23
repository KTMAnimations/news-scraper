'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, ArrowRight, Check } from 'lucide-react';
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

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    setError(null);

    try {
      await api.register(data.email, data.password, data.full_name);
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
      setError(err instanceof Error ? err.message : 'Registration failed');
    }
  };

  if (success) {
    return (
      <div className="animate-scale-in opacity-0">
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
    );
  }

  return (
    <div className="animate-fade-up opacity-0">
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
            htmlFor="full_name"
            className="block text-sm font-medium text-text-primary"
          >
            Full Name
          </label>
          <input
            {...register('full_name')}
            type="text"
            id="full_name"
            autoComplete="name"
            className="input py-3"
            placeholder="John Doe"
          />
          {errors.full_name && (
            <p className="text-sm text-negative">{errors.full_name.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <label
            htmlFor="email"
            className="block text-sm font-medium text-text-primary"
          >
            Email
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
          <input
            {...register('password')}
            type="password"
            id="password"
            autoComplete="new-password"
            className="input py-3"
            placeholder="Create a strong password"
          />
          {errors.password && (
            <p className="text-sm text-negative">{errors.password.message}</p>
          )}
          <p className="text-xs text-text-tertiary">
            Must be at least 8 characters with uppercase, lowercase, and number
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="confirmPassword"
            className="block text-sm font-medium text-text-primary"
          >
            Confirm Password
          </label>
          <input
            {...register('confirmPassword')}
            type="password"
            id="confirmPassword"
            autoComplete="new-password"
            className="input py-3"
            placeholder="Confirm your password"
          />
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
  );
}
