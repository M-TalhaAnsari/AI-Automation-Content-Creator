import React from "react";
import { useState } from 'react'
import * as api from '../api/client'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function validate() {
    if (!EMAIL_RE.test(email)) return 'Enter a valid email'
    if (password.length < 8) return 'Password must be at least 8 characters'
    return ''
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    setError('')
    setSubmitting(true)
    try {
      if (mode === 'signup') await api.signup(email, password)
      else await api.login(email, password)
      onAuthenticated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h2 className="auth-title">TrendForge</h2>
        <div className="auth-tabs">
          <button
            type="button"
            className={'auth-tab' + (mode === 'login' ? ' active' : '')}
            onClick={() => setMode('login')}
          >
            Log in
          </button>
          <button
            type="button"
            className={'auth-tab' + (mode === 'signup' ? ' active' : '')}
            onClick={() => setMode('signup')}
          >
            Sign up
          </button>
        </div>
        <input
          className="auth-field"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <input
          className="auth-field"
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
        />
        {error && <p className="auth-error">{error}</p>}
        <button className="auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Working...' : mode === 'signup' ? 'Create account' : 'Log in'}
        </button>
      </form>
    </div>
  )
}