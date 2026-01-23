'use client';

import { useSession } from 'next-auth/react';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, ReactNode } from 'react';

interface ProtectedRouteProps {
  children: ReactNode;
  /**
   * URL to redirect to when user is not authenticated
   * @default '/login'
   */
  redirectTo?: string;
  /**
   * If true, shows nothing while checking authentication status
   * If false, shows a loading state
   * @default false
   */
  hideWhileLoading?: boolean;
  /**
   * Custom loading component to show while checking authentication
   */
  loadingComponent?: ReactNode;
  /**
   * Required subscription tiers to access this route
   * If provided, user must have one of these tiers
   */
  requiredTiers?: string[];
  /**
   * Component to show when user doesn't have required subscription tier
   */
  unauthorizedComponent?: ReactNode;
}

/**
 * Default loading component that matches the app's design system
 */
function DefaultLoadingComponent() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 bg-text-primary rounded-xl flex items-center justify-center animate-pulse">
          <span className="text-bg-primary font-mono font-bold text-lg">M</span>
        </div>
        <div className="flex flex-col items-center gap-2">
          <p className="text-sm text-text-tertiary">Loading...</p>
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Default unauthorized component when user lacks required subscription tier
 */
function DefaultUnauthorizedComponent() {
  const router = useRouter();

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary p-6">
      <div className="card p-8 max-w-md w-full text-center rounded-2xl">
        <div className="w-16 h-16 rounded-full bg-warning-subtle mx-auto mb-5 flex items-center justify-center">
          <svg
            className="h-8 w-8 text-warning"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-text-primary mb-2">Upgrade Required</h2>
        <p className="text-text-secondary mb-6">
          This feature requires a higher subscription tier. Upgrade your plan to access this content.
        </p>
        <div className="flex flex-col gap-3">
          <button
            onClick={() => router.push('/dashboard/settings')}
            className="btn btn-primary w-full py-3"
          >
            View Plans
          </button>
          <button
            onClick={() => router.back()}
            className="btn btn-secondary w-full py-3"
          >
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * A wrapper component that protects routes from unauthenticated users.
 *
 * Usage:
 * ```tsx
 * // Basic usage - redirects to /login if not authenticated
 * <ProtectedRoute>
 *   <MyProtectedPage />
 * </ProtectedRoute>
 *
 * // Custom redirect URL
 * <ProtectedRoute redirectTo="/auth/signin">
 *   <MyProtectedPage />
 * </ProtectedRoute>
 *
 * // With subscription tier requirements
 * <ProtectedRoute requiredTiers={['professional', 'enterprise']}>
 *   <PremiumFeature />
 * </ProtectedRoute>
 *
 * // Custom loading component
 * <ProtectedRoute loadingComponent={<MyCustomLoader />}>
 *   <MyProtectedPage />
 * </ProtectedRoute>
 * ```
 */
export function ProtectedRoute({
  children,
  redirectTo = '/login',
  hideWhileLoading = false,
  loadingComponent,
  requiredTiers,
  unauthorizedComponent,
}: ProtectedRouteProps) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === 'unauthenticated') {
      // Include the current path as a callback URL so user returns here after login
      const callbackUrl = encodeURIComponent(pathname);
      router.push(`${redirectTo}?callbackUrl=${callbackUrl}`);
    }
  }, [status, router, redirectTo, pathname]);

  // Still loading authentication status
  if (status === 'loading') {
    if (hideWhileLoading) {
      return null;
    }
    return loadingComponent ? <>{loadingComponent}</> : <DefaultLoadingComponent />;
  }

  // Not authenticated
  if (status === 'unauthenticated') {
    // Return null while redirect is happening
    return null;
  }

  // Check subscription tier requirements
  if (requiredTiers && requiredTiers.length > 0) {
    const userTier = session?.user?.subscriptionTier;

    if (!userTier || !requiredTiers.includes(userTier)) {
      return unauthorizedComponent ? <>{unauthorizedComponent}</> : <DefaultUnauthorizedComponent />;
    }
  }

  // Authenticated and authorized
  return <>{children}</>;
}

/**
 * Higher-order component version of ProtectedRoute
 *
 * Usage:
 * ```tsx
 * const ProtectedDashboard = withProtectedRoute(Dashboard);
 * // or with options
 * const ProtectedDashboard = withProtectedRoute(Dashboard, {
 *   redirectTo: '/auth/signin',
 *   requiredTiers: ['professional'],
 * });
 * ```
 */
export function withProtectedRoute<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options: Omit<ProtectedRouteProps, 'children'> = {}
) {
  const displayName = WrappedComponent.displayName || WrappedComponent.name || 'Component';

  const ComponentWithProtection = (props: P) => {
    return (
      <ProtectedRoute {...options}>
        <WrappedComponent {...props} />
      </ProtectedRoute>
    );
  };

  ComponentWithProtection.displayName = `withProtectedRoute(${displayName})`;

  return ComponentWithProtection;
}

/**
 * Hook to check if the current user is authenticated
 * Returns the session status and data
 *
 * Usage:
 * ```tsx
 * const { isAuthenticated, isLoading, session } = useAuth();
 *
 * if (isLoading) return <Loading />;
 * if (!isAuthenticated) return <LoginPrompt />;
 * return <AuthenticatedContent user={session.user} />;
 * ```
 */
export function useAuth() {
  const { data: session, status } = useSession();

  return {
    session,
    isAuthenticated: status === 'authenticated',
    isLoading: status === 'loading',
    isUnauthenticated: status === 'unauthenticated',
    user: session?.user,
  };
}

/**
 * Hook to check if the current user has the required subscription tier
 *
 * Usage:
 * ```tsx
 * const { hasAccess, currentTier } = useSubscriptionTier(['professional', 'enterprise']);
 *
 * if (!hasAccess) {
 *   return <UpgradePrompt currentTier={currentTier} />;
 * }
 * return <PremiumFeature />;
 * ```
 */
export function useSubscriptionTier(requiredTiers: string[]) {
  const { session, isLoading } = useAuth();
  const currentTier = session?.user?.subscriptionTier;

  return {
    hasAccess: currentTier ? requiredTiers.includes(currentTier) : false,
    currentTier,
    isLoading,
  };
}

export default ProtectedRoute;
