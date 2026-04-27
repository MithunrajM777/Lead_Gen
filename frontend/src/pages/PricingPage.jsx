import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api/client';
import {
  ArrowLeft, CheckCircle2, Zap, Crown, Rocket,
  CreditCard, AlertCircle, Sparkles,
} from 'lucide-react';

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 199,
    credits: 100,
    color: 'var(--primary)',
    icon: Zap,
    features: [
      '100 Scraping Credits',
      'Google Maps Extraction',
      'Direct URL Crawling',
      'CSV Export',
      'Email Enrichment',
      'Email Support',
    ],
  },
  {
    id: 'pro',
    name: 'Professional',
    price: 499,
    credits: 500,
    color: '#f59e0b',
    icon: Crown,
    popular: true,
    features: [
      '500 Scraping Credits',
      'Everything in Starter',
      'Priority Scraping Queue',
      'Phone & Email Validation',
      'Advanced Data Enrichment',
      'Priority Support',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 999,
    credits: 2500,
    color: 'var(--secondary)',
    icon: Rocket,
    features: [
      '2,500 Scraping Credits',
      'Everything in Professional',
      'API Access',
      'Custom Export Formats',
      'Dedicated Account Manager',
      'SLA Guarantee',
    ],
  },
];

const PricingPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [purchasing, setPurchasing] = useState(null); // plan id
  const [success, setSuccess]     = useState(null);
  const [error, setError]         = useState(null);

  const handlePurchase = (plan) => {
    navigate(`/payment?plan=${plan.id}`);
  };

  return (
    <div className="container animate-fade-in" style={{ maxWidth: '1100px' }}>

      {/* Back button */}
      <button
        className="btn btn-outline"
        onClick={() => navigate('/')}
        style={{ marginBottom: '2rem', fontSize: '0.82rem' }}
      >
        <ArrowLeft size={15} /> Back to Dashboard
      </button>

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.35rem 1rem', borderRadius: '999px', fontSize: '0.75rem',
          fontWeight: '700', color: 'var(--primary)', background: 'rgba(99,102,241,0.1)',
          border: '1px solid rgba(99,102,241,0.3)', marginBottom: '1.25rem',
        }}>
          <Sparkles size={13} /> PRICING PLANS
        </div>
        <h1 style={{ fontSize: '2.2rem', fontWeight: '800', marginBottom: '0.75rem' }}>
          Choose Your <span style={{ color: 'var(--primary)' }}>Plan</span>
        </h1>
        <p style={{ fontSize: '1rem', color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto' }}>
          Scale your lead generation with more credits and advanced features.
        </p>
      </div>

      {/* Banners */}
      {success && (
        <div className="scraper-status success animate-fade-in" style={{ marginBottom: '1.5rem', justifyContent: 'center' }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}
      {error && (
        <div className="scraper-status error animate-fade-in" style={{ marginBottom: '1.5rem', justifyContent: 'center' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Plan cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '1.5rem',
        marginBottom: '3rem',
      }}>
        {PLANS.map((plan) => {
          const Icon = plan.icon;
          return (
            <div
              key={plan.id}
              className="glass-card"
              style={{
                padding: '2rem 1.5rem',
                position: 'relative',
                border: plan.popular ? `2px solid ${plan.color}` : undefined,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div style={{
                  position: 'absolute', top: '-12px', left: '50%', transform: 'translateX(-50%)',
                  background: plan.color, color: '#0f172a', padding: '0.2rem 1rem',
                  borderRadius: '999px', fontSize: '0.7rem', fontWeight: '800',
                  letterSpacing: '0.04em', whiteSpace: 'nowrap',
                }}>
                  MOST POPULAR
                </div>
              )}

              {/* Plan header */}
              <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
                <div style={{
                  width: '48px', height: '48px', borderRadius: '14px',
                  background: `${plan.color}22`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 1rem',
                }}>
                  <Icon size={22} color={plan.color} />
                </div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '0.5rem' }}>
                  {plan.name}
                </h3>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: '0.2rem' }}>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>₹</span>
                  <span style={{ fontSize: '2.4rem', fontWeight: '800', fontFamily: 'Outfit, sans-serif', color: plan.color }}>
                    {plan.price.toLocaleString('en-IN')}
                  </span>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>/mo</span>
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                  {plan.credits.toLocaleString()} credits included
                </p>
              </div>

              {/* Feature list */}
              <ul style={{ listStyle: 'none', padding: 0, flex: 1, marginBottom: '1.5rem' }}>
                {plan.features.map((f, i) => (
                  <li key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    fontSize: '0.82rem', color: 'var(--text)', padding: '0.35rem 0',
                  }}>
                    <CheckCircle2 size={14} color={plan.color} style={{ flexShrink: 0 }} />
                    {f}
                  </li>
                ))}
              </ul>

              {/* Buy button */}
              <button
                className={`btn ${plan.popular ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => handlePurchase(plan)}
                disabled={purchasing === plan.id}
                style={{
                  width: '100%', justifyContent: 'center', fontSize: '0.85rem',
                  ...(plan.popular ? {} : { borderColor: `${plan.color}55`, color: plan.color }),
                }}
              >
                {purchasing === plan.id ? (
                  <><div className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} /> Processing…</>
                ) : (
                  <><CreditCard size={15} /> Get {plan.name}</>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Footer note */}
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          All plans include a 30-day money-back guarantee. Need custom volumes?{' '}
          <a href="mailto:support@leadgenpro.com" style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: '600' }}>
            Contact Sales
          </a>
        </p>
      </div>
    </div>
  );
};

export default PricingPage;
