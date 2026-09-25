import { useState } from 'react'
import { API_BASE_URL } from './services/api'
import './App.css'

function App() {
  const [message, setMessage] = useState('')

  const handleSetupCheck = () => {
    setMessage('MatchGrid frontend is working correctly!')
  }

  return (
    <main className="app">
      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div className="brand">
            <div className="brand-mark">M</div>

            <div>
              <h1>MatchGrid</h1>
              <p>Sports management platform</p>
            </div>
          </div>

          <span className="status">Frontend Ready</span>
        </header>

        {/* Hero Section */}
        <section className="hero">
          <div className="hero-card">
            <p className="eyebrow">Welcome to MatchGrid</p>

            <h2>
              Manage matches.
              <br />
              Track the game.
            </h2>

            <p className="description">
              A modern frontend foundation for managing matches, teams,
              tournaments, live updates, and more.
            </p>

            <button
              type="button"
              className="hero-action"
              onClick={handleSetupCheck}
            >
              Check Frontend
            </button>

            {message && (
              <p className="success-message">
                {message}
              </p>
            )}
          </div>

          {/* Frontend Information */}
          <div className="info-card">
            <h3>Frontend Foundation</h3>

            <p>
              The React application is configured and ready for feature
              development.
            </p>

            <div className="feature-list">
              <div className="feature">
                <div className="feature-icon">⚛</div>

                <div>
                  <strong>React</strong>
                  <span>Component-based frontend</span>
                </div>
              </div>

              <div className="feature">
                <div className="feature-icon">📁</div>

                <div>
                  <strong>Organized Structure</strong>
                  <span>Components, pages and services</span>
                </div>
              </div>

              <div className="feature">
                <div className="feature-icon">⚡</div>

                <div>
                  <strong>Vite</strong>
                  <span>Fast development environment</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SCRUM-13: Tailwind CSS Test */}
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                SCRUM-13
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-900">
                Tailwind CSS Test
              </h2>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                This sample component verifies that Tailwind CSS utility
                classes are connected correctly to the React frontend.
              </p>
            </div>

            <span className="inline-flex w-fit items-center rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-700">
              ✓ Configured
            </span>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-900">
                Utility Classes
              </p>

              <p className="mt-1 text-sm text-slate-600">
                Spacing, colors and typography are working.
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-900">
                Responsive Design
              </p>

              <p className="mt-1 text-sm text-slate-600">
                Responsive utility classes are available.
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-900">
                Reusable Styling
              </p>

              <p className="mt-1 text-sm text-slate-600">
                Tailwind can be used across frontend components.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="mt-6 rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
          >
            Tailwind Button
          </button>
        </section>

        {/* SCRUM-15: Frontend Environment */}
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                SCRUM-15
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-900">
                Frontend Environment
              </h2>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                The backend API URL is loaded from the frontend environment
                configuration instead of being hard-coded in the application.
              </p>
            </div>

            <span className="inline-flex w-fit items-center rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-700">
              ✓ Configured
            </span>
          </div>

          <div className="mt-5 rounded-xl bg-slate-100 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              API Base URL
            </p>

            <code className="mt-2 block break-all text-sm font-semibold text-slate-800">
              {API_BASE_URL}
            </code>
          </div>
        </section>

        {/* Development Status */}
        <section className="section">
          <div className="section-header">
            <div>
              <h3>Development Status</h3>
              <p>Initial frontend configuration is complete.</p>
            </div>

            <span className="ready">Ready for development</span>
          </div>

          <p>
            MatchGrid frontend is successfully configured with React, Vite,
            Tailwind CSS, and frontend environment variables. Feature-specific
            screens and components can now be added.
          </p>
        </section>

        {/* Footer */}
        <footer className="footer">
          MatchGrid © 2026
        </footer>
      </div>
    </main>
  )
}

export default App