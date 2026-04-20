import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../AuthContext';
import { LogIn, UserPlus, Lock, User as UserIcon, Mail, AlertCircle, Loader2 } from 'lucide-react';

// ── Shared inline field component ────────────────────────────────────────────
const Field = ({ label, icon: Icon, error, children }) => (
  <div className="input-group">
    <label>{label}</label>
    <div style={{ position: 'relative' }}>
      {Icon && (
        <Icon
          size={16}
          style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }}
        />
      )}
      {children}
    </div>
    {error && (
      <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
        <AlertCircle size={12} /> {error}
      </div>
    )}
  </div>
);

// ── Shared auth card wrapper ─────────────────────────────────────────────────
const AuthCard = ({ icon: CardIcon, title, subtitle, children }) => (
  <div className="auth-container animate-fade-in">
    <div className="glass-card auth-card">
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div style={{
          background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
          width: '48px', height: '48px', borderRadius: '12px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 1rem',
          boxShadow: '0 4px 14px rgba(99,102,241,0.35)',
        }}>
          <CardIcon size={22} color="white" />
        </div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: '700', marginBottom: '0.3rem' }}>{title}</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{subtitle}</p>
      </div>
      {children}
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Login Page
// ─────────────────────────────────────────────────────────────────────────────
export const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const { login } = useAuth();
  const navigate  = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);
      const res = await api.post('/token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      login(res.data.access_token);
      navigate('/');
    } catch (err) {
      setError(err.userMessage || 'Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard icon={LogIn} title="Welcome Back" subtitle="Sign in to continue scraping leads">
      {error && (
        <div className="scraper-status error" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <Field label="Username" icon={UserIcon}>
          <input
            type="text"
            style={{ paddingLeft: '2.4rem' }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="your_username"
            autoComplete="username"
            required
            disabled={loading}
          />
        </Field>
        <Field label="Password" icon={Lock}>
          <input
            type="password"
            style={{ paddingLeft: '2.4rem' }}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
            disabled={loading}
          />
        </Field>
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
          disabled={loading}
        >
          {loading ? <><div className="spinner" style={{ width: '15px', height: '15px', borderWidth: '2px' }} /> Signing in…</> : 'Sign In'}
        </button>
      </form>
      <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        Don't have an account?{' '}
        <Link to="/signup" style={{ color: 'var(--primary)', fontWeight: '600' }}>Create one</Link>
      </p>
    </AuthCard>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Signup Page
// ─────────────────────────────────────────────────────────────────────────────
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export const SignupPage = () => {
  const [form, setForm]     = useState({ username: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');
  const navigate = useNavigate();

  const set = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const validate = () => {
    const e = {};
    if (!form.username.trim())            e.username = 'Username is required';
    if (!EMAIL_RE.test(form.email))        e.email    = 'Enter a valid email address';
    if (form.password.length < 6)          e.password = 'Minimum 6 characters';
    if (form.password !== form.confirm)    e.confirm  = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setApiError('');
    setLoading(true);
    try {
      await api.post('/signup', {
        username: form.username.trim(),
        email:    form.email.trim(),
        password: form.password,
      });
      navigate('/login', { state: { message: 'Account created! Please sign in.' } });
    } catch (err) {
      setApiError(err.userMessage || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard icon={UserPlus} title="Create Account" subtitle="Start extracting business leads today">
      {apiError && (
        <div className="scraper-status error" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={15} /> {apiError}
        </div>
      )}
      <form onSubmit={handleSubmit} noValidate>
        <Field label="Username" icon={UserIcon} error={errors.username}>
          <input
            type="text"
            style={{ paddingLeft: '2.4rem', borderColor: errors.username ? 'var(--error)' : undefined }}
            value={form.username}
            onChange={set('username')}
            placeholder="your_username"
            autoComplete="username"
            required
            disabled={loading}
          />
        </Field>
        <Field label="Email Address" icon={Mail} error={errors.email}>
          <input
            type="email"
            style={{ paddingLeft: '2.4rem', borderColor: errors.email ? 'var(--error)' : undefined }}
            value={form.email}
            onChange={set('email')}
            placeholder="you@company.com"
            autoComplete="email"
            required
            disabled={loading}
          />
        </Field>
        <Field label="Password" icon={Lock} error={errors.password}>
          <input
            type="password"
            style={{ paddingLeft: '2.4rem', borderColor: errors.password ? 'var(--error)' : undefined }}
            value={form.password}
            onChange={set('password')}
            placeholder="Min. 6 characters"
            autoComplete="new-password"
            required
            disabled={loading}
          />
        </Field>
        <Field label="Confirm Password" icon={Lock} error={errors.confirm}>
          <input
            type="password"
            style={{ paddingLeft: '2.4rem', borderColor: errors.confirm ? 'var(--error)' : undefined }}
            value={form.confirm}
            onChange={set('confirm')}
            placeholder="Repeat password"
            autoComplete="new-password"
            required
            disabled={loading}
          />
        </Field>
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
          disabled={loading}
        >
          {loading ? <><div className="spinner" style={{ width: '15px', height: '15px', borderWidth: '2px' }} /> Creating account…</> : 'Create Account'}
        </button>
      </form>
      <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        Already have an account?{' '}
        <Link to="/login" style={{ color: 'var(--primary)', fontWeight: '600' }}>Sign in</Link>
      </p>
    </AuthCard>
  );
};
