import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api/client';
import {
  ArrowLeft, CheckCircle2, CreditCard,
  AlertCircle, QrCode as QrIcon, User, Hash,
  Zap, Crown, Rocket
} from 'lucide-react';
import { QRCode } from 'react-qr-code';

const PLANS = {
  starter: { name: 'Starter', price: 199, credits: 100, icon: Zap, color: 'var(--primary)' },
  pro: { name: 'Professional', price: 499, credits: 500, icon: Crown, color: '#f59e0b' },
  enterprise: { name: 'Enterprise', price: 999, credits: 2500, icon: Rocket, color: 'var(--secondary)' }
};

const PaymentPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  
  const query = new URLSearchParams(location.search);
  const planId = query.get('plan') || 'starter';
  const plan = PLANS[planId] || PLANS.starter;

  const [formData, setFormData] = useState({
    accountName: '',
    upiId: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.post('/payments', {
        plan_name: planId,
        amount: plan.price,
        account_name: formData.accountName,
        upi_id: formData.upiId
      });
      setSuccess(true);
    } catch (err) {
      setError(err.userMessage || 'Failed to submit payment request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="container animate-fade-in" style={{ maxWidth: '600px', textAlign: 'center', padding: '4rem 1rem' }}>
        <div className="glass-card" style={{ padding: '3rem 2rem' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(34, 197, 94, 0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem'
          }}>
            <CheckCircle2 size={32} color="#22c55e" />
          </div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: '800', marginBottom: '1rem' }}>Request Submitted!</h1>
          <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
            Your payment request for the <strong>{plan.name}</strong> plan is being reviewed. 
            Credits will be added once the admin confirms the transaction.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/')} style={{ width: '100%' }}>
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const PlanIcon = plan.icon;

  return (
    <div className="container animate-fade-in" style={{ maxWidth: '900px' }}>
      <button
        className="btn btn-outline"
        onClick={() => navigate('/pricing')}
        style={{ marginBottom: '2rem', fontSize: '0.82rem' }}
      >
        <ArrowLeft size={15} /> Back to Pricing
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '2rem' }}>
        
        {/* Left Side: QR Code & Instructions */}
        <div className="glass-card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: '700', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <QrIcon size={20} color="var(--primary)" /> Scan to Pay
          </h2>
          
          <div style={{ 
            background: 'white', padding: '1.5rem', borderRadius: '12px', 
            width: '240px', height: '240px', margin: '0 auto 2rem',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)'
          }}>
            <div style={{ height: "auto", margin: "0 auto", maxWidth: 200, width: "100%" }}>
              <QRCode
                size={256}
                style={{ height: "auto", maxWidth: "100%", width: "100%" }}
                value={`upi://pay?pa=mithunrajm777-2@okaxis&pn=Mithun&am=${plan.price}&cu=INR`}
                viewBox={`0 0 256 256`}
              />
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Scan the QR code using any UPI app (GPay, PhonePe, Paytm) and pay the exact amount.
            </p>
            <div style={{ 
              background: 'rgba(255,255,255,0.05)', padding: '1rem', borderRadius: '8px',
              border: '1px dashed rgba(255,255,255,0.1)', fontSize: '0.85rem'
            }}>
              Payable Amount: <span style={{ color: plan.color, fontWeight: '800', fontSize: '1.1rem' }}>₹{plan.price}</span>
            </div>
          </div>
        </div>

        {/* Right Side: Form */}
        <div className="glass-card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: '700', marginBottom: '0.5rem' }}>Confirm Details</h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '2rem' }}>
            Enter the details of the account used for payment.
          </p>

          {error && (
            <div className="scraper-status error" style={{ marginBottom: '1.5rem' }}>
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>
                SELECTED PLAN
              </label>
              <div style={{ 
                display: 'flex', alignItems: 'center', gap: '0.75rem', 
                padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '10px',
                border: `1px solid ${plan.color}33`
              }}>
                <div style={{ 
                  width: '36px', height: '36px', borderRadius: '8px', background: `${plan.color}22`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <PlanIcon size={18} color={plan.color} />
                </div>
                <div>
                  <div style={{ fontSize: '0.9rem', fontWeight: '700' }}>{plan.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{plan.credits} Credits</div>
                </div>
              </div>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                ACCOUNT HOLDER NAME
              </label>
              <div className="input-with-icon">
                <User size={16} />
                <input
                  type="text"
                  placeholder="e.g. John Doe"
                  required
                  value={formData.accountName}
                  onChange={(e) => setFormData({ ...formData, accountName: e.target.value })}
                  style={{ paddingLeft: '2.8rem' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                YOUR UPI ID
              </label>
              <div className="input-with-icon">
                <Hash size={16} />
                <input
                  type="text"
                  placeholder="e.g. john@okaxis"
                  required
                  value={formData.upiId}
                  onChange={(e) => setFormData({ ...formData, upiId: e.target.value })}
                  style={{ paddingLeft: '2.8rem' }}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', padding: '1rem' }}
            >
              {loading ? (
                <><div className="spinner" style={{ width: '16px', height: '16px' }} /> Submitting...</>
              ) : (
                <><CreditCard size={18} /> Submit Payment Request</>
              )}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '1.5rem' }}>
            <span style={{ color: 'var(--secondary)' }}>Note:</span> Admin will verify your transaction manually. This usually takes 1-4 hours.
          </p>
        </div>

      </div>
    </div>
  );
};

export default PaymentPage;
