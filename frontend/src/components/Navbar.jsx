import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { 
  Zap, LogOut, CreditCard, Shield, UserCheck, RefreshCw, AlertCircle 
} from 'lucide-react';

const Navbar = () => {
  const { user, logout, fetchMe, refreshing } = useAuth();
  const navigate = useNavigate();

  return (
    <nav style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem',
    }}>
      {/* Brand */}
      <div 
        onClick={() => navigate('/')} 
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}
      >
        <div style={{
          background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
          padding: '0.6rem', borderRadius: '12px',
          boxShadow: '0 4px 14px rgba(99,102,241,0.4)',
        }}>
          <Zap size={22} color="white" fill="white" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.35rem', fontWeight: '800', letterSpacing: '-0.5px', lineHeight: 1 }}>
            LEADGEN <span style={{ color: 'var(--primary)' }}>PRO</span>
          </h1>
          <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Enterprise Dashboard
          </p>
        </div>
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        {user?.is_admin && (
          <>
            <span 
              onClick={() => navigate('/admin/users')}
              style={{
                cursor: 'pointer',
                padding: '0.28rem 0.8rem', borderRadius: '999px', fontSize: '0.68rem',
                fontWeight: '700', letterSpacing: '0.06em', color: 'var(--primary)',
                background: 'rgba(79,70,229,0.08)', border: '1px solid rgba(79,70,229,0.2)',
                display: 'flex', alignItems: 'center', gap: '0.4rem'
              }}
            >
              <UserCheck size={12} /> USERS
            </span>

            <span 
              onClick={() => navigate('/admin/payments')}
              style={{
                cursor: 'pointer',
                padding: '0.28rem 0.8rem', borderRadius: '999px', fontSize: '0.68rem',
                fontWeight: '700', letterSpacing: '0.06em', color: '#fbbf24',
                background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.4)',
                display: 'flex', alignItems: 'center', gap: '0.4rem'
              }}
            >
              <Shield size={12} /> PAYMENTS
            </span>
          </>
        )}

        <div className="glass-card" style={{ 
          padding: '0.5rem 1rem', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.6rem', 
          border: '1px solid rgba(99,102,241,0.4)',
          position: 'relative'
        }}>
          <CreditCard size={16} color="var(--primary)" />
          <span style={{ fontWeight: '700', fontSize: '0.9rem' }}>
            {user?.is_admin ? '∞' : user?.credits ?? 0}
            <span style={{ fontSize: '0.75rem', opacity: 0.65, marginLeft: '0.3rem' }}>Credits</span>
          </span>
          
          <button 
            onClick={fetchMe}
            disabled={refreshing}
            style={{
              background: 'none',
              border: 'none',
              cursor: refreshing ? 'default' : 'pointer',
              display: 'flex',
              padding: '2px',
              marginLeft: '4px',
              color: 'var(--text-muted)'
            }}
            title="Refresh Credits"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} style={{ 
              animation: refreshing ? 'spin 1s linear infinite' : 'none' 
            }} />
          </button>
        </div>

        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          {user?.username}
        </span>

        <button className="btn btn-outline" onClick={logout} style={{ padding: '0.5rem 1rem', fontSize: '0.82rem' }}>
          <LogOut size={15} /> Logout
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
