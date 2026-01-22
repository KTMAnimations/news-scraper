import { withAuth } from 'next-auth/middleware';
import { NextResponse } from 'next/server';

export default withAuth(
  function middleware(req) {
    // If the user is not authenticated and trying to access protected routes
    // The withAuth middleware will handle redirects automatically
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        // Check if the path requires authentication
        const protectedPaths = ['/dashboard', '/settings', '/watchlist', '/alerts'];
        const isProtected = protectedPaths.some((path) =>
          req.nextUrl.pathname.startsWith(path)
        );

        // Allow access if not protected or if user has token
        if (!isProtected) {
          return true;
        }

        return !!token;
      },
    },
    pages: {
      signIn: '/auth/login',
    },
  }
);

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/settings/:path*',
    '/watchlist/:path*',
    '/alerts/:path*',
  ],
};
