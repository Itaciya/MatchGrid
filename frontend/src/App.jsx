import { useState } from 'react'
import './App.css'

function App() {
  const [message, setMessage] = useState('')

  const handleSetupCheck = () => {
    setMessage('MatchGrid frontend is working correctly!')
  }

  return (
    <main className="app">
      <div className="app-container">
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

            {message && <p className="success-message">{message}</p>}
          </div>

          <div className="info-card" id="features">
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

        <section className="section">
          <div className="section-header">
            <div>
              <h3>Development Status</h3>
              <p>Initial frontend setup is complete.</p>
            </div>

            <span className="ready">Ready for development</span>
          </div>

          <p>
            MatchGrid frontend is successfully configured with React and Vite.
            Feature-specific screens and components can now be added.
          </p>
        </section>

        <footer className="footer">
          MatchGrid © 2026
        </footer>
      </div>
    </main>
  )
}

export default App