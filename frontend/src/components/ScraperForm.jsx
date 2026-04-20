import React, { useState, useRef, useEffect } from 'react';
import api from '../api/client';
import { Search, Globe, Loader2, MapPin, Zap, CheckCircle2, AlertCircle, Clock } from 'lucide-react';

// ── Validation helpers (frontend) ─────────────────────────────────────────

// URL: must start with http(s):// and have a valid domain
const URL_REGEX = /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z]{2,}(\/([-a-zA-Z0-9@:%_+.~#?&/=]*))?$/;

// Keyword: at least 2 printable characters
const KEYWORD_MIN = 2;

function validateUrl(value) {
  if (!value) return 'Website URL is required';
  if (!URL_REGEX.test(value.trim())) return 'Invalid URL — must start with https:// or http://';
  return null;
}

function validateKeyword(value) {
  if (!value || value.trim().length < KEYWORD_MIN) return `Search keyword must be at least ${KEYWORD_MIN} characters`;
  return null;
}

// ── Status display map ────────────────────────────────────────────────────
const STATUS_LABEL = {
  pending:    { label: 'Queued',     cls: 'queued',  Icon: Clock },
  processing: { label: 'Scraping…',  cls: 'queued',  Icon: Loader2 },
  completed:  { label: 'Completed!', cls: 'success', Icon: CheckCircle2 },
  failed:     { label: 'Failed',     cls: 'error',   Icon: AlertCircle },
};

const POLL_INTERVAL_MS = 3000;

const ScraperForm = ({ onJobCreated }) => {
  const [input, setInput]       = useState('');
  const [location, setLocation] = useState('');
  const [type, setType]         = useState('maps');
  const [loading, setLoading]   = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobId, setJobId]       = useState(null);
  const [error, setError]       = useState(null);
  const [inputError, setInputError]   = useState(null);
  const [locationError, setLocationError] = useState(null);
  const pollRef = useRef(null);

  // Clear stale validation when switching mode
  const handleTypeChange = (newType) => {
    setType(newType);
    setInput('');
    setInputError(null);
    setLocationError(null);
    setError(null);
  };

  // ── Stop polling on unmount ─────────────────────────────────────────
  useEffect(() => () => clearInterval(pollRef.current), []);

  // ── Poll job status ─────────────────────────────────────────────────
  const startPolling = (id) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/jobs/${id}`);
        const { status } = res.data;
        setJobStatus(status);

        if (status === 'completed' || status === 'failed') {
          clearInterval(pollRef.current);
          setLoading(false);
          if (status === 'completed') onJobCreated();
        }
      } catch (_) {
        clearInterval(pollRef.current);
        setLoading(false);
      }
    }, POLL_INTERVAL_MS);
  };

  // ── Submit handler ──────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Correct validation based on mode
    const iErr = type === 'url' ? validateUrl(input) : validateKeyword(input);
    setInputError(iErr);
    if (iErr) return;

    setLoading(true);
    setError(null);
    setJobStatus('pending');
    setJobId(null);

    try {
      const res = await api.post('/jobs', { input, location, type });
      const id = res.data.job_id;
      setJobId(id);
      setInput('');
      setLocation('');
      startPolling(id);
    } catch (err) {
      setError(err.userMessage || 'Failed to start scraping job.');
      setJobStatus(null);
      setLoading(false);
    }
  };

  const statusInfo = jobStatus ? STATUS_LABEL[jobStatus] ?? STATUS_LABEL.pending : null;

  return (
    <div className="glass-card">
      <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '1.05rem' }}>
        <Zap size={20} color="var(--primary)" /> Start Extraction Job
      </h3>

      <form onSubmit={handleSubmit}>
        {/* Job type selector */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', background: 'rgba(0,0,0,0.25)', padding: '0.3rem', borderRadius: '10px' }}>
          {[['maps', 'Google Maps'], ['url', 'Direct URL']].map(([val, label]) => (
            <button
              key={val}
              type="button"
              className={`btn ${type === val ? 'btn-primary' : ''}`}
              onClick={() => handleTypeChange(val)}
              style={{ flex: 1, justifyContent: 'center', padding: '0.5rem', fontSize: '0.82rem' }}
            >
              {val === 'maps' ? <Search size={14} /> : <Globe size={14} />} {label}
            </button>
          ))}
        </div>

        {/* Keyword / URL input */}
        <div className="input-group">
          <label>{type === 'maps' ? 'Search Keyword' : 'Website URL'}</label>
          <div style={{ position: 'relative' }}>
            {type === 'maps'
              ? <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              : <Globe  size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            }
            <input
              style={{ paddingLeft: '2.4rem', borderColor: inputError ? 'var(--error)' : undefined }}
              value={input}
              onChange={(e) => { setInput(e.target.value); setInputError(null); }}
              placeholder={type === 'maps' ? 'e.g., IT companies in Chennai' : 'https://example.com'}
              required
              disabled={loading}
            />
          </div>
          {inputError && (
            <div style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <AlertCircle size={13} /> {inputError}
            </div>
          )}
        </div>

        {/* Location (maps only) */}
        {type === 'maps' && (
          <div className="input-group">
            <label>Location</label>
            <div style={{ position: 'relative' }}>
              <MapPin size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                style={{ paddingLeft: '2.4rem' }}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g., Chennai, Tamil Nadu"
                required
                disabled={loading}
              />
            </div>
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
          disabled={loading}
        >
          {loading ? (
            <><div className="spinner" /> Scraping in progress…</>
          ) : (
            <>{type === 'maps' ? <><Search size={16}/> Search & Scrape</> : <><Globe size={16}/> Crawl Website</>}</>
          )}
        </button>
      </form>

      {/* Progress indicator */}
      {loading && (
        <div style={{ marginTop: '1rem' }}>
          <div className="progress-bar-wrapper">
            <div
              className="progress-bar-fill"
              style={{ width: jobStatus === 'processing' ? '65%' : jobStatus === 'pending' ? '20%' : '100%' }}
            />
          </div>
        </div>
      )}

      {/* Status banner */}
      {statusInfo && (
        <div className={`scraper-status ${statusInfo.cls} animate-fade-in`} style={{ marginTop: '0.75rem' }}>
          {loading && jobStatus === 'processing'
            ? <div className="spinner" style={{ borderTopColor: 'var(--primary)', borderColor: 'rgba(99,102,241,0.3)' }} />
            : <statusInfo.Icon size={16} />
          }
          <div>
            <strong>{statusInfo.label}</strong>
            {jobId && <span style={{ fontSize: '0.75rem', opacity: 0.7, marginLeft: '0.5rem' }}> · Job #{jobId}</span>}
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="scraper-status error animate-fade-in" style={{ marginTop: '0.75rem' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Credit cost info */}
      <div style={{ marginTop: '1.5rem', padding: '0.85rem 1rem', background: 'rgba(99,102,241,0.04)', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: '600' }}>Resource Usage</p>
        <ul style={{ fontSize: '0.75rem', color: 'var(--text-muted)', paddingLeft: '1rem', lineHeight: 1.8 }}>
          <li>Google Maps: <strong style={{ color: 'var(--text)' }}>10 Credits</strong></li>
          <li>Direct URL: <strong style={{ color: 'var(--text)' }}>5 Credits</strong></li>
        </ul>
      </div>
    </div>
  );
};

export default ScraperForm;
