import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createUser } from '../api/userApi'
import { Eye, EyeOff, Code2 } from 'lucide-react'

const RegisterPage = () => {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    confirm_password: '',
  })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const validate = () => {
    const errs = {}
    if (!form.first_name.trim()) errs.first_name = 'First name is required.'
    else if (form.first_name.trim().length < 3) errs.first_name = 'At least 3 characters.'
    if (!form.last_name.trim()) errs.last_name = 'Last name is required.'
    else if (form.last_name.trim().length < 3) errs.last_name = 'At least 3 characters.'
    if (!form.email.trim()) errs.email = 'Email is required.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = 'Enter a valid email.'
    if (!form.password) errs.password = 'Password is required.'
    else {
      if (form.password.length < 8) errs.password = 'At least 8 characters.'
      else if (!/[A-Z]/.test(form.password)) errs.password = 'Must contain an uppercase letter.'
      else if (!/[a-z]/.test(form.password)) errs.password = 'Must contain a lowercase letter.'
      else if (!/[0-9]/.test(form.password)) errs.password = 'Must contain a digit.'
      else if (!/[!@#$%^&*]/.test(form.password)) errs.password = 'Must contain a special character (!@#$%^&*).'
    }
    if (!form.confirm_password) errs.confirm_password = 'Please confirm your password.'
    else if (form.password !== form.confirm_password) errs.confirm_password = 'Passwords do not match.'
    return errs
  }

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setErrors((prev) => ({ ...prev, [e.target.name]: '' }))
    setServerError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setLoading(true)
    try {
      await createUser(form)
      navigate('/login', { state: { registered: true } })
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (Array.isArray(detail)) {
        setServerError(detail.map((d) => d.msg).join(' '))
      } else {
        setServerError(typeof detail === 'string' ? detail : 'Registration failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-card--wide">
        <div className="auth-logo">
          <Code2 size={32} strokeWidth={1.5} />
          <span>CodeCompletion</span>
        </div>

        <h1 className="auth-title">Create account</h1>
        <p className="auth-subtitle">Start coding smarter today</p>

        {serverError && <div className="auth-error-banner">{serverError}</div>}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">First Name</label>
              <input
                id="first_name"
                name="first_name"
                type="text"
                autoComplete="given-name"
                value={form.first_name}
                onChange={handleChange}
                className={errors.first_name ? 'input-error' : ''}
                placeholder="John"
              />
              {errors.first_name && <span className="field-error">{errors.first_name}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="last_name">Last Name</label>
              <input
                id="last_name"
                name="last_name"
                type="text"
                autoComplete="family-name"
                value={form.last_name}
                onChange={handleChange}
                className={errors.last_name ? 'input-error' : ''}
                placeholder="Doe"
              />
              {errors.last_name && <span className="field-error">{errors.last_name}</span>}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={handleChange}
              className={errors.email ? 'input-error' : ''}
              placeholder="you@example.com"
            />
            {errors.email && <span className="field-error">{errors.email}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-wrapper">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.password}
                onChange={handleChange}
                className={errors.password ? 'input-error' : ''}
                placeholder="Min 8 chars, upper, lower, digit, symbol"
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.password && <span className="field-error">{errors.password}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="confirm_password">Confirm Password</label>
            <div className="input-wrapper">
              <input
                id="confirm_password"
                name="confirm_password"
                type={showConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.confirm_password}
                onChange={handleChange}
                className={errors.confirm_password ? 'input-error' : ''}
                placeholder="••••••••"
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowConfirm((v) => !v)}
                tabIndex={-1}
                aria-label={showConfirm ? 'Hide password' : 'Show password'}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.confirm_password && <span className="field-error">{errors.confirm_password}</span>}
          </div>

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? <span className="btn-spinner" /> : 'Create Account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" className="auth-link">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

export default RegisterPage
