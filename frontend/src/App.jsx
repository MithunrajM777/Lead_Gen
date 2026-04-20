import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import api from './api/client';
import {
  Download, CheckCircle, XCircle,
  Database, LogOut, CreditCard,
  Layers, Zap, TrendingUp, Shield, Trash2, UserCheck
} from 'lucide-react';

import { AuthProvider, useAuth } from './AuthContext';
import { LoginPage, SignupPage } from './pages/AuthPages';
import PricingPage from './pages/PricingPage';
import ScraperForm from './components/ScraperForm';
import DataTable from './components/DataTable';
import Navbar from './components/Navbar';
import PaymentPage from './pages/PaymentPage';
import AdminPaymentsPage from './pages/AdminPaymentsPage';
import AdminUsersPage from './pages/AdminUsersPage';
import { AlertCircle } from 'lucide-react';

// ── Error Boundary ──────────────────────────────────────────────────────────
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="container" style={{ textAlign: 'center', padding: '5rem 2rem' }}>
          <div className="glass-card" style={{ padding: '3rem' }}>
            <XCircle size={48} color="var(--error)" style={{ marginBottom: '1.5rem' }} />
            <h1 style={{ marginBottom: '1rem' }}>Something went wrong.</h1>
            <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
              We encountered an unexpected error. Please try refreshing the page.
            </p>
            <button className="btn btn-primary" onClick={() => window.location.reload()}>
              Refresh Application
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Stat Card ───────────────────────────────────────────────────────────────
const StatCard = ({ label, value, icon: Icon, color, gradient }) => (
  <div
    className="glass-card stat-card"
    style={gradient ? { background: gradient, border: 'none' } : {}}
  >
    <div className="flex-between" style={{ marginBottom: '0.75rem' }}>
      <span style={{ color: gradient ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
      <Icon size={18} color={gradient ? 'white' : color} />
    </div>
    <div style={{ fontSize: '2rem', fontWeight: '800', color: gradient ? 'white' : color ?? 'var(--text)', fontFamily: 'Outfit, sans-serif' }}>
      {value}
    </div>
  </div>
);

// ── Dashboard ───────────────────────────────────────────────────────────────
const Dashboard = () => {
  const { user, logout, fetchMe } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats]     = useState({ total_leads: 0, valid_leads: 0, credits: 0, jobs_count: 0 });
  const [results, setResults] = useState([]);
  const [total, setTotal]     = useState(0);
  const [limit]               = useState(20);
  const [offset, setOffset]   = useState(0);
  const [filter, setFilter]   = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [exporting, setExporting]   = useState(false);
  const [clearing,  setClearing]    = useState(false);

  // ── Data fetching ─────────────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Stats fetch error:', err);
    }
  }, []);

  const fetchLeads = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit, offset });
      if (filter !== 'all') params.set('status', filter);
      if (searchTerm)       params.set('search', searchTerm);

      const res = await api.get(`/results?${params}`);
      setResults(res.data.items ?? []);
      setTotal(res.data.total ?? 0);
    } catch (err) {
      console.error('Leads fetch error:', err);
    }
  }, [limit, offset, filter, searchTerm]);

  useEffect(() => {
    fetchStats();
    fetchLeads();
    const id = setInterval(() => { fetchStats(); fetchLeads(); }, 15000);
    return () => clearInterval(id);
  }, [fetchStats, fetchLeads]);

  // ── CSV Export (server-side — clean encoding) ─────────────────────
  const handleExport = async () => {
    if (total === 0) return;
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (filter !== 'all') params.set('status', filter);

      // Stream the CSV via Blob so the JWT header is sent properly
      const res = await api.get(`/results/export?${params}`, {
        responseType: 'blob',
      });

      const url  = window.URL.createObjectURL(new Blob([res.data], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href  = url;
      link.setAttribute('download', `leads_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed: ' + (err.userMessage || err.message));
    } finally {
      setExporting(false);
    }
  };

  // ── Clear all results ─────────────────────────────────────────────
  const handleClear = async () => {
    if (!window.confirm(
      `This will permanently delete all ${total.toLocaleString()} leads and job history.\n\nAre you sure?`
    )) return;

    setClearing(true);
    try {
      await api.delete('/results/clear');
      // Reset local UI state immediately
      setResults([]);
      setTotal(0);
      setOffset(0);
      setFilter('all');
      setSearchTerm('');
      // Refresh stats from server
      await fetchStats();
    } catch (err) {
      alert('Clear failed: ' + (err.userMessage || err.message));
    } finally {
      setClearing(false);
    }
  };

  const accuracy = stats.total_leads > 0
    ? Math.round((stats.valid_leads / stats.total_leads) * 100)
    : 0;

  return (
    <div className="container animate-fade-in">

      <Navbar />

      {!user?.is_admin && user?.credits === 0 && (
        <div className="warning-banner">
          <AlertCircle size={20} />
          <span>No credits remaining. Please upgrade your plan to continue scraping.</span>
        </div>
      )}

      {/* ── Stats Grid ─────────────────────────────────────────────── */}
      <div className="stats-grid">
        <StatCard label="Total Leads"   value={stats.total_leads.toLocaleString()} icon={Layers}     color="var(--primary)" />
        <StatCard label="Verified Valid" value={stats.valid_leads.toLocaleString()} icon={CheckCircle} color="var(--success)" />
        <StatCard label="Jobs Run"       value={stats.jobs_count}                   icon={TrendingUp}  color="var(--warning)" />
        <StatCard
          label="Accuracy Rate"
          value={`${accuracy}%`}
          icon={Shield}
          gradient="linear-gradient(135deg, var(--primary), var(--secondary))"
        />
      </div>

      {/* ── Main content: Sidebar + Results ────────────────────────── */}
      <div className="dashboard-grid">

        {/* Left column: form + subscription */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <ScraperForm onJobCreated={() => { fetchStats(); fetchLeads(); fetchMe(); }} />

          {/* Subscription card */}
          <div className="glass-card" style={{ padding: '1.25rem' }}>
            <h4 style={{ marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.95rem' }}>
              <CreditCard size={16} color="var(--primary)" /> Subscription
            </h4>
            <div style={{ padding: '0.85rem', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
              <p style={{ fontSize: '0.82rem', marginBottom: '0.85rem', color: 'var(--text-muted)' }}>
                Currently on <strong style={{ color: 'var(--text)' }}>
                  {user?.tier || 'Free'}
                </strong>
              </p>
              {!user?.is_admin && (
                <button
                  className="btn btn-primary"
                  onClick={() => navigate('/pricing')}
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.82rem' }}
                >
                  Upgrade to PRO
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right column: results table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 }}>
          <div className="flex-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: '700' }}>Extraction Results</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                Real-time verified leads from your campaigns
              </p>
            </div>
            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {/* Clear button — only shown when there is data */}
              {total > 0 && (
                <button
                  className="btn btn-outline"
                  onClick={handleClear}
                  disabled={clearing}
                  style={{
                    fontSize: '0.82rem',
                    borderColor: 'rgba(239,68,68,0.4)',
                    color: clearing ? 'var(--text-muted)' : 'var(--error)',
                  }}
                  title="Delete all scraped leads"
                >
                  {clearing
                    ? <><div className="spinner" style={{ width: '13px', height: '13px', borderWidth: '2px', borderTopColor: 'var(--error)', borderColor: 'rgba(239,68,68,0.2)' }} /> Clearing…</>
                    : <><Trash2 size={14} /> Clear Results</>
                  }
                </button>
              )}

              {/* Export button */}
              <button
                className="btn btn-primary"
                onClick={handleExport}
                disabled={total === 0 || exporting}
                style={{ fontSize: '0.82rem' }}
              >
                {exporting
                  ? <><div className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} /> Exporting…</>
                  : <><Download size={15} /> Export CSV ({total.toLocaleString()})</>
                }
              </button>
            </div>
          </div>

          <DataTable
            data={results}
            total={total}
            limit={limit}
            offset={offset}
            filter={filter}
            searchTerm={searchTerm}
            onPageChange={(page) => setOffset((page - 1) * limit)}
            onFilterChange={(f) => { setFilter(f); setOffset(0); }}
            onSearchChange={(s) => { setSearchTerm(s); setOffset(0); }}
          />
        </div>
      </div>
    </div>
  );
};

// ── Private Route ────────────────────────────────────────────────────────────
const PrivateRoute = ({ children }) => {
  const { token, loading } = useAuth();
  if (loading) return (
    <div className="loading-screen">
      <div className="spinner spinner-lg" />
      Preparing LeadGen Pro…
    </div>
  );
  return token ? children : <Navigate to="/login" />;
};

// ── App ──────────────────────────────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <Router>
          <Routes>
            <Route path="/login"  element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/pricing" element={
              <PrivateRoute>
                <PricingPage />
              </PrivateRoute>
            } />
            <Route path="/payment" element={
              <PrivateRoute>
                <PaymentPage />
              </PrivateRoute>
            } />
            <Route path="/admin/payments" element={
              <AdminPaymentsPageWrapper />
            } />
            <Route path="/admin/users" element={
              <AdminUsersPageWrapper />
            } />
            <Route path="/" element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            } />
          </Routes>
        </Router>
      </ErrorBoundary>
    </AuthProvider>
  );
}

// Helper to handle admin redirects safely inside router
const AdminPaymentsPageWrapper = () => {
  const { user } = useAuth();
  return (
    <PrivateRoute>
      {user?.is_admin ? <AdminPaymentsPage /> : <Navigate to="/" />}
    </PrivateRoute>
  );
};

const AdminUsersPageWrapper = () => {
  const { user } = useAuth();
  return (
    <PrivateRoute>
      {user?.is_admin ? <AdminUsersPage /> : <Navigate to="/" />}
    </PrivateRoute>
  );
};

export default App;
