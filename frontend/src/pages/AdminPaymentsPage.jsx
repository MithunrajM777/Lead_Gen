import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api/client';
import {
  ArrowLeft, CheckCircle2, XCircle, Clock,
  User, CreditCard, RefreshCw, Search,
  Filter, AlertCircle
} from 'lucide-react';

const AdminPaymentsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('pending');
  const [actionLoading, setActionLoading] = useState(null); // ID of payment being processed

  const fetchPayments = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/admin/payments${filter !== 'all' ? `?status=${filter}` : ''}`);
      setPayments(res.data);
    } catch (err) {
      setError(err.userMessage || 'Failed to fetch payments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, [filter]);

  const handleAction = async (id, action) => {
    setActionLoading(id);
    try {
      await api.post(`/admin/payments/${id}/${action}`);
      // Refresh list
      fetchPayments();
    } catch (err) {
      alert(err.userMessage || `Failed to ${action} payment`);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'approved': return '#22c55e';
      case 'rejected': return '#ef4444';
      default: return '#f59e0b';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'approved': return <CheckCircle2 size={14} color="#22c55e" />;
      case 'rejected': return <XCircle size={14} color="#ef4444" />;
      default: return <Clock size={14} color="#f59e0b" />;
    }
  };

  return (
    <div className="container animate-fade-in" style={{ maxWidth: '1200px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2.5rem' }}>
        <div>
          <button
            className="btn btn-outline"
            onClick={() => navigate('/')}
            style={{ marginBottom: '1rem', fontSize: '0.82rem' }}
          >
            <ArrowLeft size={15} /> Back to Dashboard
          </button>
          <h1 style={{ fontSize: '1.8rem', fontWeight: '800' }}>Payment Management</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Verify and approve manual payment requests.</p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <select 
            className="input-field" 
            style={{ width: '160px', marginBottom: 0 }}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="pending">Pending Only</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="all">All Payments</option>
          </select>
          <button className="btn btn-outline" onClick={fetchPayments} style={{ padding: '0.75rem' }}>
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <div className="scraper-status error" style={{ marginBottom: '2rem' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <div className="glass-card" style={{ padding: '1rem', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '800px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>USER</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>PLAN</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>AMOUNT</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>UPI / NAME</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>DATE</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>STATUS</th>
              <th style={{ padding: '1.25rem 1rem', fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="7" style={{ padding: '4rem', textAlign: 'center' }}>
                  <div className="spinner" style={{ margin: '0 auto' }} />
                  <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>Loading payments...</p>
                </td>
              </tr>
            ) : payments.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ padding: '4rem', textAlign: 'center' }}>
                  <CreditCard size={48} color="var(--text-muted)" style={{ opacity: 0.3, marginBottom: '1rem' }} />
                  <p style={{ color: 'var(--text-muted)' }}>No payment requests found.</p>
                </td>
              </tr>
            ) : (
              payments.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', transition: 'background 0.2s' }} className="hover-row">
                  <td style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{ 
                        width: '32px', height: '32px', borderRadius: '50%', background: 'rgba(255,255,255,0.05)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        <User size={14} color="var(--primary)" />
                      </div>
                      <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>{p.username}</span>
                    </div>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ 
                      fontSize: '0.7rem', fontWeight: '800', textTransform: 'uppercase',
                      padding: '0.2rem 0.6rem', borderRadius: '999px', background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.1)'
                    }}>
                      {p.plan_name}
                    </span>
                  </td>
                  <td style={{ padding: '1rem', fontWeight: '700', color: 'var(--primary)' }}>₹{p.amount}</td>
                  <td style={{ padding: '1rem' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: '600' }}>{p.account_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{p.upi_id}</div>
                  </td>
                  <td style={{ padding: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {new Date(p.created_at).toLocaleDateString()} <br />
                    {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <div style={{ 
                      display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.3rem 0.75rem', borderRadius: '6px', 
                      background: `${getStatusColor(p.status)}15`,
                      color: getStatusColor(p.status),
                      fontSize: '0.75rem', fontWeight: '700', textTransform: 'capitalize'
                    }}>
                      {getStatusIcon(p.status)} {p.status}
                    </div>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    {p.status === 'pending' ? (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button 
                          className="btn btn-primary" 
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem', background: '#22c55e', borderColor: '#22c55e' }}
                          onClick={() => handleAction(p.id, 'approve')}
                          disabled={actionLoading === p.id}
                        >
                          {actionLoading === p.id ? '...' : 'Approve'}
                        </button>
                        <button 
                          className="btn btn-outline" 
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem', color: '#ef4444', borderColor: '#ef4444' }}
                          onClick={() => handleAction(p.id, 'reject')}
                          disabled={actionLoading === p.id}
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No actions</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <style>{`
        .hover-row:hover { background: rgba(255,255,255,0.02); }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default AdminPaymentsPage;
