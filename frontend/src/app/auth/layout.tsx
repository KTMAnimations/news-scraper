export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="w-full max-w-md px-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Micro-Alpha
          </h1>
          <p className="text-slate-400">
            Real-time sentiment signals for micro-cap securities
          </p>
        </div>
        {children}
      </div>
    </div>
  );
}
