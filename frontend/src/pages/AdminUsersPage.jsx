import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { 
  UserCheck, UserX, Search, Shield, 
  ArrowLeft, Mail, Calendar, Clock,
  Filter, CheckCircle, XCircle
} from 'lucide-react';

const AdminUsersPage = () => {
    const navigate = useNavigate();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all'); // all, pending, approved
    const [searchTerm, setSearchTerm] = useState('');
    const [actionLoading, setActionLoading] = useState(null);

    const fetchUsers = useCallback(async () => {
        try {
            setLoading(true);
            const res = await api.get('/admin/users');
            setUsers(res.data);
        } catch (err) {
            console.error('Failed to fetch users:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchUsers();
    }, [fetchUsers]);

    const handleAction = async (userId, action) => {
        setActionLoading(userId);
        try {
            await api.post(`/admin/users/${userId}/${action}`);
            await fetchUsers();
        } catch (err) {
            alert(`Failed to ${action} user: ` + (err.userMessage || err.message));
        } finally {
            setActionLoading(null);
        }
    };

    const filteredUsers = users.filter(u => {
        const matchesFilter = 
            filter === 'all' ? true :
            filter === 'pending' ? !u.is_approved :
            u.is_approved;
        
        const matchesSearch = 
            u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (u.email && u.email.toLowerCase().includes(searchTerm.toLowerCase()));
        
        return matchesFilter && matchesSearch;
    });

    return (
        <div className="container animate-fade-in">
            <div className="flex-between" style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button className="btn btn-secondary" onClick={() => navigate('/')}>
                        <ArrowLeft size={16} /> Dashboard
                    </button>
                    <div>
                        <h1 style={{ fontSize: '1.5rem', fontWeight: '800' }}>User Management</h1>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            Approve or restrict application access
                        </p>
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <div className="glass-card" style={{ padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.6rem', border: '1px solid var(--primary)' }}>
                        <Shield size={16} color="var(--primary)" />
                        <span style={{ fontWeight: '700', fontSize: '0.85rem' }}>Admin Control</span>
                    </div>
                </div>
            </div>

            <div className="glass-card" style={{ marginBottom: '2rem', padding: '1.25rem' }}>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '250px', position: 'relative' }}>
                        <Search size={18} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                        <input 
                            type="text" 
                            placeholder="Search by username or email..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            style={{ paddingLeft: '2.8rem' }}
                        />
                    </div>
                    
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button 
                            className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-outline'}`}
                            onClick={() => setFilter('all')}
                            style={{ fontSize: '0.82rem' }}
                        >
                            All Users
                        </button>
                        <button 
                            className={`btn ${filter === 'pending' ? 'btn-primary' : 'btn-outline'}`}
                            onClick={() => setFilter('pending')}
                            style={{ fontSize: '0.82rem' }}
                        >
                            Pending
                        </button>
                        <button 
                            className={`btn ${filter === 'approved' ? 'btn-primary' : 'btn-outline'}`}
                            onClick={() => setFilter('approved')}
                            style={{ fontSize: '0.82rem' }}
                        >
                            Approved
                        </button>
                    </div>
                </div>
            </div>

            <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
                <table className="lead_table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ background: 'rgba(0,0,0,0.02)', borderBottom: '1px solid var(--glass-border)' }}>
                            <th style={{ padding: '1.25rem', textAlign: 'left', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>User Details</th>
                            <th style={{ padding: '1.25rem', textAlign: 'left', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Status</th>
                            <th style={{ padding: '1.25rem', textAlign: 'left', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Platform Info</th>
                            <th style={{ padding: '1.25rem', textAlign: 'center', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan="4" style={{ padding: '4rem', textAlign: 'center' }}>
                                    <div className="spinner-lg" style={{ margin: '0 auto 1rem' }} />
                                    <p style={{ color: 'var(--text-muted)' }}>Loading users...</p>
                                </td>
                            </tr>
                        ) : filteredUsers.length === 0 ? (
                            <tr>
                                <td colSpan="4" style={{ padding: '4rem', textAlign: 'center' }}>
                                    <XCircle size={40} style={{ margin: '0 auto 1rem', opacity: 0.2 }} />
                                    <p style={{ color: 'var(--text-muted)' }}>No users found matching your criteria.</p>
                                </td>
                            </tr>
                        ) : filteredUsers.map(u => (
                            <tr key={u.id} style={{ borderBottom: '1px solid var(--glass-border)' }}>
                                <td style={{ padding: '1.25rem' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                        <div style={{ width: '40px', height: '40px', background: 'var(--primary)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: '800' }}>
                                            {u.username[0].toUpperCase()}
                                        </div>
                                        <div>
                                            <div style={{ fontWeight: '700' }}>{u.username}</div>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                                <Mail size={12} /> {u.email || 'No email provided'}
                                            </div>
                                        </div>
                                    </div>
                                </td>
                                <td style={{ padding: '1.25rem' }}>
                                    {u.is_approved ? (
                                        <span className="status-badge status-valid">
                                            <CheckCircle size={10} style={{ marginRight: '0.3rem' }} /> Approved
                                        </span>
                                    ) : (
                                        <span className="status-badge status-unverified">
                                            <Clock size={10} style={{ marginRight: '0.3rem' }} /> Pending
                                        </span>
                                    )}
                                </td>
                                <td style={{ padding: '1.25rem' }}>
                                    <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                                        <strong style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>Plan:</strong> {u.plan}
                                    </div>
                                    <div style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--primary)' }}>
                                        {u.credits.toLocaleString()} Credits
                                    </div>
                                </td>
                                <td style={{ padding: '1.25rem' }}>
                                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                                        {!u.is_approved ? (
                                            <button 
                                                className="btn btn-primary"
                                                onClick={() => handleAction(u.id, 'approve')}
                                                disabled={actionLoading === u.id}
                                                style={{ padding: '0.5rem 0.85rem', fontSize: '0.75rem' }}
                                            >
                                                {actionLoading === u.id ? <div className="spinner" style={{ width: '12px', height: '12px' }} /> : <><UserCheck size={14} /> Approve</>}
                                            </button>
                                        ) : (
                                            <button 
                                                className="btn btn-outline"
                                                onClick={() => handleAction(u.id, 'reject')}
                                                disabled={actionLoading === u.id}
                                                style={{ padding: '0.5rem 0.85rem', fontSize: '0.75rem', color: 'var(--error)', borderColor: 'rgba(220,38,38,0.2)' }}
                                            >
                                                {actionLoading === u.id ? <div className="spinner" style={{ width: '12px', height: '12px' }} /> : <><UserX size={14} /> Restrict</>}
                                            </button>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default AdminUsersPage;
