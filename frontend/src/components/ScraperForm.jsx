import React, { useState, useRef, useEffect } from 'react';
import api from '../api/client';
import { Search, Globe, Loader2, MapPin, Zap, CheckCircle2, AlertCircle, Clock, XCircle, FileSpreadsheet } from 'lucide-react';
import ExcelUpload from './ExcelUpload';

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
  stopped:    { label: 'Job Stopped', cls: 'error',   Icon: XCircle },
};

const POLL_INTERVAL_MS = 3000;

const ScraperForm = ({ onJobCreated, onLeadReceived, onScrapingStarted, lastClearedAt }) => {
  const [input, setInput]       = useState('');
  const [location, setLocation] = useState('');
  const [pincodes, setPincodes] = useState('');
  const [type, setType]         = useState('maps');
  const [isScraping, setIsScraping]   = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobId, setJobId]       = useState(null);
  const [error, setError]       = useState(null);
  const [inputError, setInputError]   = useState(null);
  const [locationError, setLocationError] = useState(null);
  const [pincodeError, setPincodeError]   = useState(null);
  const pollRef = useRef(null);

  // Reset state when results are cleared from parent
  useEffect(() => {
    if (lastClearedAt > 0) {
      setJobStatus(null);
      setError(null);
      setIsScraping(false);
      setJobId(null);
      setInputError(null);
      setLocationError(null);
      setPincodeError(null);
    }
  }, [lastClearedAt]);

  // Stop polling on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleTypeChange = (newType) => {
    setType(newType);
    setInputError(null);
    setLocationError(null);
    setPincodeError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const iErr = type === 'url' ? validateUrl(input) : validateKeyword(input);
    setInputError(iErr);
    if (iErr) return;

    setIsScraping(true);
    setError(null);
    setJobStatus('processing');
    setJobId(null);
    if (onScrapingStarted) onScrapingStarted();

    // Parse pincodes
    const pincodeArray = pincodes.trim() 
      ? pincodes.split(',').map(p => p.trim()).filter(p => p.length > 0)
      : [];

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/jobs/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
          input, 
          location: pincodeArray.length > 0 ? "" : location, 
          pincodes: pincodeArray, 
          type 
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to start streaming');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamDone = false;  // flag to exit the outer while loop

      console.log('[Stream] Reader started, waiting for data...');

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          console.log('[Stream] Reader done (stream closed by server).');
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.replace('data: ', '').trim();
          if (!jsonStr) continue;

          console.log('[Stream] Raw SSE line received:', jsonStr.slice(0, 120));

          try {
            const data = JSON.parse(jsonStr);

            if (data.job_id) {
              console.log('[Stream] Job ID received:', data.job_id);
              setJobId(data.job_id);
              continue;
            }

            if (data.done) {
              console.log('[Stream] Scraping DONE signal received.');
              setJobStatus('completed');
              setIsScraping(false);
              streamDone = true;
              break;  // break inner for loop
            }

            if (data.stopped) {
              console.log('[Stream] Scraping STOPPED signal received.');
              setJobStatus('stopped');
              setIsScraping(false);
              setError('Scraping stopped by user');
              streamDone = true;
              break;
            }

            if (Object.prototype.hasOwnProperty.call(data, 'error')) {
              // Use hasOwnProperty so {"error": ""} (empty msg) is also caught
              const errMsg = data.error || 'Scraping failed — check server logs for details.';
              console.error('[Stream] Error from backend:', errMsg);
              setError(errMsg);
              setJobStatus('failed');
              setIsScraping(false);
              streamDone = true;
              break;
            }

            // It's a lead!
            console.log('[Stream] Lead received:', data.company_name);
            if (onLeadReceived) onLeadReceived(data);
          } catch (err) {
            console.error('[Stream] Error parsing SSE chunk:', err, '| Raw:', jsonStr);
          }
        }

        if (streamDone) break;  // break outer while loop
      }

      setInput('');
      setLocation('');
      setPincodes('');
      if (onJobCreated) onJobCreated();
    } catch (err) {
      if (err.name === 'AbortError') {
        setJobStatus('stopped');
        setError("Scraping stopped by user");
      } else {
        setError(err.message || 'Failed to start scraping job.');
        setJobStatus(null);
      }
      setIsScraping(false);
    }
  };

  const handleStop = async () => {
    if (!jobId) return;
    try {
      await api.post(`/jobs/${jobId}/stop`);
      setIsScraping(false);
      setJobStatus('stopped');
      setError("Scraping stopped by user");
    } catch (err) {
      console.error("Failed to stop job:", err);
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
          <label htmlFor="scraper-input">{type === 'maps' ? 'Search Keyword' : 'Website URL'}</label>
          <div style={{ position: 'relative' }}>
            {type === 'maps'
              ? <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              : <Globe  size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            }
            <input
              id="scraper-input"
              name="scraper-input"
              style={{ paddingLeft: '2.4rem', borderColor: inputError ? 'var(--error)' : undefined }}
              value={input}
              onChange={(e) => { setInput(e.target.value); setInputError(null); }}
              placeholder={type === 'maps' ? 'e.g., IT companies in Chennai' : 'https://example.com'}
              required
              disabled={isScraping}
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
            <label htmlFor="location">Location</label>
            <div style={{ position: 'relative' }}>
              <MapPin size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                id="location"
                name="location"
                style={{ paddingLeft: '2.4rem', opacity: pincodes.trim() ? 0.5 : 1 }}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g., Chennai, Tamil Nadu"
                required={!pincodes.trim()}
                disabled={isScraping || !!pincodes.trim()}
              />
            </div>
          </div>
        )}

        {/* Pincodes (maps only) */}
        {type === 'maps' && (
          <div className="input-group" style={{ marginTop: '1rem' }}>
            <label htmlFor="pincodes">Pincode(s) <span style={{ fontSize: '0.7rem', fontWeight: 'normal', opacity: 0.7 }}>(Optional, comma-separated)</span></label>
            <div style={{ position: 'relative' }}>
              <MapPin size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                id="pincodes"
                name="pincodes"
                style={{ paddingLeft: '2.4rem' }}
                value={pincodes}
                onChange={(e) => setPincodes(e.target.value)}
                placeholder="e.g., 638001, 638002"
                disabled={isScraping}
              />
            </div>
            {pincodes.trim() && (
              <div style={{ fontSize: '0.7rem', color: 'var(--primary)', marginTop: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <CheckCircle2 size={12} /> Location disabled (Pincode search active)
              </div>
            )}
          </div>
        )}

        {/* Submit button */}
         <div style={{ marginTop: '0.5rem' }}>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={isScraping}
          >
            {isScraping ? (
              <><div className="spinner" /> Scraping...</>
            ) : (
              <>{type === 'maps' ? <><Search size={16}/> Search & Scrape</> : <><Globe size={16}/> Crawl Website</>}</>
            )}
          </button>

          <button
            type="button"
            className="btn btn-danger"
            onClick={handleStop}
            disabled={!isScraping}
            style={{ width: "100%", marginTop: "10px", justifyContent: 'center' }}
          >
            <XCircle size={18} /> Stop
          </button>
        </div>
      </form>

      {/* Progress indicator */}
      {isScraping && (
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
          {isScraping && jobStatus === 'processing'
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

      {/* Excel Upload Section */}
      <ExcelUpload onJobCreated={onJobCreated} />
    </div>
  );
};

export default ScraperForm;
