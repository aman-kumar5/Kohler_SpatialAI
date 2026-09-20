import React from 'react';
import { useDesignStore } from './store';
import OnboardingWizard from './components/wizard/OnboardingWizard';
import Dashboard from './components/dashboard/Dashboard';
import LandingPage from './components/LandingPage';
// CSS is handled by the bundler; TypeScript has no declaration for this side-effect import.
// @ts-ignore
import './styles.css';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = {
      hasError: false,
      message: '',
    };
  }

  static getDerivedStateFromError(error: Error) {
    return {
      hasError: true,
      message: error.message,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('UI Error caught by boundary:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({
      hasError: false,
      message: '',
    });

    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-screen">
          <div className="error-card">
            <h2>Something went wrong in the display</h2>

            <p className="error-msg">
              {this.state.message ||
                'An unexpected rendering error occurred.'}
            </p>

            <p className="suggested-fix">
              Suggested fix: Check browser console logs or reload the
              application.
            </p>

            <button
              type="button"
              className="btn-primary"
              onClick={this.handleReload}
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  const wizardDone = useDesignStore((s) => s.wizardDone);
  const [showLanding, setShowLanding] = React.useState(true);

  const handleEnterApp = React.useCallback(() => {
    setShowLanding(false);
  }, []);

  return (
    <ErrorBoundary>
      <div
        className={`app-container${
          showLanding ? ' landing-container' : ''
        }`}
      >
        {!showLanding && (
          <header className="app-header">
            <div className="header-brand">
              <span className="brand-kohler">KOHLER</span>
              <span className="brand-sub">SpatialAI</span>
            </div>

            <div className="header-right">

              <button
                type="button"
                className="header-user-icon"
                aria-label="User Account"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  aria-hidden="true"
                >
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </button>
            </div>
          </header>
        )}

        <main className="app-main">
          {showLanding ? (
            <LandingPage onEnter={handleEnterApp} />
          ) : !wizardDone ? (
            <OnboardingWizard />
          ) : (
            <Dashboard />
          )}
        </main>
      </div>
    </ErrorBoundary>
  );
}
