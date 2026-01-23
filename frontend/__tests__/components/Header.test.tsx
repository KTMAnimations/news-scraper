import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from '@/components/layout/Header';

// Override the default mock for specific tests
const mockUseSession = jest.fn();
const mockSignOut = jest.fn();
const mockSetTheme = jest.fn();

jest.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signOut: (...args: unknown[]) => mockSignOut(...args),
}));

jest.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'dark',
    setTheme: mockSetTheme,
    resolvedTheme: 'dark',
  }),
}));

describe('Header', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: {
        user: {
          name: 'John Doe',
          email: 'john@example.com',
          subscriptionTier: 'professional',
        },
        accessToken: 'mock-token',
      },
      status: 'authenticated',
    });
  });

  describe('branding', () => {
    it('renders the logo and brand name', () => {
      render(<Header />);
      expect(screen.getByText('M')).toBeInTheDocument();
      expect(screen.getByText('Micro-Alpha')).toBeInTheDocument();
    });

    it('logo links to dashboard', () => {
      render(<Header />);
      const logoLink = screen.getByText('Micro-Alpha').closest('a');
      expect(logoLink).toHaveAttribute('href', '/dashboard');
    });
  });

  describe('search', () => {
    it('renders the search input', () => {
      render(<Header />);
      const searchInput = screen.getByPlaceholderText('Search events, tickers, news...');
      expect(searchInput).toBeInTheDocument();
    });

    it('displays keyboard shortcut hints', () => {
      render(<Header />);
      // Check for keyboard shortcut
      expect(screen.getByText('K')).toBeInTheDocument();
    });
  });

  describe('live indicator', () => {
    it('renders live status indicator (hidden on mobile)', () => {
      const { container } = render(<Header />);
      // The live indicator is hidden on mobile (md:flex), so we check for its existence in the DOM
      const liveIndicator = container.querySelector('.hidden.md\\:block') ||
        container.querySelector('[class*="md:flex"]');
      expect(liveIndicator).toBeInTheDocument();
    });
  });

  describe('theme toggle', () => {
    it('opens theme menu on click', () => {
      render(<Header />);

      // Theme options should not be visible initially
      expect(screen.queryByText('Light')).not.toBeInTheDocument();

      // Click theme toggle button
      const themeButton = screen.getByLabelText('Toggle theme');
      fireEvent.click(themeButton);

      // Theme options should now be visible
      expect(screen.getByText('Light')).toBeInTheDocument();
      expect(screen.getByText('Dark')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();
    });

    it('changes theme to light when light option is clicked', () => {
      render(<Header />);

      // Open theme menu
      const themeButton = screen.getByLabelText('Toggle theme');
      fireEvent.click(themeButton);

      // Click light option
      fireEvent.click(screen.getByText('Light'));

      expect(mockSetTheme).toHaveBeenCalledWith('light');
    });

    it('changes theme to dark when dark option is clicked', () => {
      render(<Header />);

      // Open theme menu
      const themeButton = screen.getByLabelText('Toggle theme');
      fireEvent.click(themeButton);

      // Click dark option
      fireEvent.click(screen.getByText('Dark'));

      expect(mockSetTheme).toHaveBeenCalledWith('dark');
    });

    it('changes theme to system when system option is clicked', () => {
      render(<Header />);

      // Open theme menu
      const themeButton = screen.getByLabelText('Toggle theme');
      fireEvent.click(themeButton);

      // Click system option
      fireEvent.click(screen.getByText('System'));

      expect(mockSetTheme).toHaveBeenCalledWith('system');
    });

    it('closes theme menu when clicking outside', () => {
      render(<Header />);

      // Open theme menu
      const themeButton = screen.getByLabelText('Toggle theme');
      fireEvent.click(themeButton);
      expect(screen.getByText('Light')).toBeInTheDocument();

      // Click the backdrop overlay
      const backdrop = document.querySelector('.fixed.inset-0');
      fireEvent.click(backdrop!);

      // Theme menu should close
      expect(screen.queryByText('Light')).not.toBeInTheDocument();
    });
  });

  describe('notifications', () => {
    it('renders notification button', () => {
      render(<Header />);
      // Bell icon is rendered (checking for parent button)
      const buttons = screen.getAllByRole('button');
      const notificationButton = buttons.find(btn => btn.querySelector('svg.lucide-bell') !== null);
      expect(notificationButton).toBeInTheDocument();
    });

    it('shows notification indicator', () => {
      const { container } = render(<Header />);
      // Check for the red dot indicator
      const notificationDot = container.querySelector('.bg-negative.rounded-full');
      expect(notificationDot).toBeInTheDocument();
    });
  });

  describe('user menu', () => {
    it('displays user initial in avatar', () => {
      render(<Header />);
      expect(screen.getByText('J')).toBeInTheDocument();
    });

    it('displays username', () => {
      render(<Header />);
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('opens user menu on click', () => {
      render(<Header />);

      // User menu options should not be visible initially
      expect(screen.queryByText('Settings')).not.toBeInTheDocument();

      // Click user button
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);

      // User menu should be visible
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Sign out')).toBeInTheDocument();
    });

    it('shows user email in expanded menu', () => {
      render(<Header />);

      // Open user menu
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);

      expect(screen.getByText('john@example.com')).toBeInTheDocument();
    });

    it('shows subscription tier in expanded menu', () => {
      render(<Header />);

      // Open user menu
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);

      expect(screen.getByText('professional Plan')).toBeInTheDocument();
    });

    it('links to settings page', () => {
      render(<Header />);

      // Open user menu
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);

      const settingsLink = screen.getByText('Settings').closest('a');
      expect(settingsLink).toHaveAttribute('href', '/dashboard/settings');
    });

    it('calls signOut when sign out button is clicked', () => {
      render(<Header />);

      // Open user menu
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);

      // Click sign out
      fireEvent.click(screen.getByText('Sign out'));

      expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: '/auth/login' });
    });

    it('closes user menu when clicking outside', () => {
      render(<Header />);

      // Open user menu
      const userButton = screen.getByText('John Doe').closest('button');
      fireEvent.click(userButton!);
      expect(screen.getByText('Settings')).toBeInTheDocument();

      // Click the backdrop
      const backdrops = document.querySelectorAll('.fixed.inset-0');
      fireEvent.click(backdrops[backdrops.length - 1]);

      // Menu should close
      expect(screen.queryByText('Settings')).not.toBeInTheDocument();
    });
  });

  describe('unauthenticated state', () => {
    beforeEach(() => {
      mockUseSession.mockReturnValue({
        data: null,
        status: 'unauthenticated',
      });
    });

    it('shows default user initial when not authenticated', () => {
      render(<Header />);
      expect(screen.getByText('U')).toBeInTheDocument();
    });

    it('shows "User" as fallback name in menu', () => {
      render(<Header />);

      // Open user menu (find the button by avatar)
      const avatarButton = screen.getByText('U').closest('button');
      fireEvent.click(avatarButton!);

      expect(screen.getByText('User')).toBeInTheDocument();
    });
  });

  describe('user with email only (no name)', () => {
    beforeEach(() => {
      mockUseSession.mockReturnValue({
        data: {
          user: {
            email: 'jane@example.com',
          },
          accessToken: 'mock-token',
        },
        status: 'authenticated',
      });
    });

    it('shows email initial in avatar', () => {
      render(<Header />);
      expect(screen.getByText('J')).toBeInTheDocument();
    });

    it('shows email prefix as display name', () => {
      render(<Header />);
      expect(screen.getByText('jane')).toBeInTheDocument();
    });
  });
});
