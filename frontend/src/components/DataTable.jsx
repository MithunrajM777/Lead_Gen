import React from 'react';
import {
  Mail, Phone, MapPin, ExternalLink, Filter,
  Star, Globe, Search as SearchIcon, ChevronLeft, ChevronRight,
  AlertCircle, CheckCircle2,
} from 'lucide-react';

/**
 * DataTable — displays scraped lead results.
 * Matches the CSV column order: Company | Email | Phone | Website | Address | Rating | Status
 */
const DataTable = ({
  data, total, limit, offset,
  onPageChange, onFilterChange, filter,
  searchTerm, onSearchChange,
}) => {
  const currentPage  = Math.floor(offset / limit) + 1;
  const totalPages   = Math.ceil(total / limit);
  const startIndex   = offset + 1;
  const endIndex     = Math.min(offset + limit, total);

  return (
    <div
      className="glass-card"
      style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: '480px' }}
    >
      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.02)' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search */}
          <div style={{ position: 'relative', flex: '1 1 220px', minWidth: '180px' }}>
            <SearchIcon size={16} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              style={{ paddingLeft: '2.2rem', background: 'rgba(0,0,0,0.25)', fontSize: '0.85rem' }}
              placeholder="Search by name, email, category…"
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </div>

          {/* Status filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flex: '0 0 auto' }}>
            <Filter size={14} color="var(--text-muted)" />
            <select
              style={{ width: 'auto', background: 'rgba(0,0,0,0.25)', padding: '0.55rem 2rem 0.55rem 0.85rem', fontSize: '0.85rem' }}
              value={filter}
              onChange={(e) => onFilterChange(e.target.value)}
            >
              <option value="all">All Leads</option>
              <option value="valid">Valid Only</option>
              <option value="invalid">Invalid</option>
              <option value="unverified">Unverified</option>
            </select>
          </div>

          {/* Record count */}
          {total > 0 && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
              {total.toLocaleString()} lead{total !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {/* ── Table ────────────────────────────────────────────────────── */}
      <div style={{ overflowX: 'auto', flex: 1 }}>
        <table className="lead-table">
          <thead>
            <tr>
              <th style={{ minWidth: '160px' }}>Company</th>
              <th style={{ minWidth: '200px' }}>Email</th>
              <th style={{ minWidth: '140px' }}>Phone</th>
              <th style={{ minWidth: '130px' }}>Website</th>
              <th style={{ minWidth: '180px' }}>Address</th>
              <th style={{ minWidth: '80px'  }}>Rating</th>
              <th style={{ minWidth: '100px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '5rem 2rem', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                    <SearchIcon size={40} style={{ opacity: 0.18 }} />
                    <span style={{ fontSize: '0.9rem' }}>No leads found. Start a scraping job to see results here.</span>
                  </div>
                </td>
              </tr>
            ) : data.map((item) => (
              <tr key={item.id} className="animate-fade-in">
                {/* Company */}
                <td>
                  <div style={{ fontWeight: '600', color: 'var(--text)', fontSize: '0.88rem' }} title={item.company_name}>
                    {item.company_name || '—'}
                  </div>
                  {item.category && (
                    <div style={{ fontSize: '0.73rem', color: 'var(--primary)', marginTop: '0.2rem' }}>
                      {item.category}
                    </div>
                  )}
                </td>

                {/* Email */}
                <td>
                  {item.email ? (
                    <a
                      href={`mailto:${item.email}`}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.83rem', color: 'var(--text)', textDecoration: 'none' }}
                      title={item.email}
                    >
                      <Mail size={13} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                      <span className="cell-text">{item.email}</span>
                    </a>
                  ) : (
                    <NoData />
                  )}
                </td>

                {/* Phone */}
                <td>
                  {item.phone ? (
                    <a
                      href={`tel:${item.phone}`}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.83rem', color: 'var(--text)', textDecoration: 'none' }}
                    >
                      <Phone size={13} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                      {item.phone}
                    </a>
                  ) : (
                    <NoData />
                  )}
                </td>

                {/* Website */}
                <td>
                  {item.website ? (
                    <a
                      href={item.website.startsWith('http') ? item.website : `https://${item.website}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.83rem', color: 'var(--primary)', textDecoration: 'none' }}
                    >
                      <Globe size={13} style={{ flexShrink: 0 }} />
                      <span className="cell-text">Visit</span>
                      <ExternalLink size={11} />
                    </a>
                  ) : (
                    <NoData />
                  )}
                </td>

                {/* Address */}
                <td>
                  {item.address ? (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', fontSize: '0.82rem', color: 'var(--text)' }}>
                      <MapPin size={13} color="var(--text-muted)" style={{ marginTop: '2px', flexShrink: 0 }} />
                      <span style={{ lineHeight: 1.4 }}>{item.address}</span>
                    </div>
                  ) : (
                    <NoData />
                  )}
                </td>

                {/* Rating */}
                <td>
                  {item.rating != null ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.83rem' }}>
                      <Star size={13} fill="var(--warning)" color="var(--warning)" />
                      <span>{Number(item.rating).toFixed(1)}</span>
                      {item.reviews_count > 0 && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>({item.reviews_count})</span>
                      )}
                    </div>
                  ) : (
                    <NoData />
                  )}
                </td>

                {/* Status */}
                <td>
                  <span className={`status-badge status-${item.validation_status ?? 'unverified'}`}>
                    {item.validation_status === 'valid'
                      ? <><CheckCircle2 size={11} style={{ display: 'inline', marginRight: '3px' }} />Valid</>
                      : item.validation_status === 'invalid'
                        ? <><AlertCircle size={11} style={{ display: 'inline', marginRight: '3px' }} />Invalid</>
                        : item.validation_status ?? 'unverified'
                    }
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ───────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div style={{
          padding: '0.85rem 1.25rem',
          borderTop: '1px solid var(--glass-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(255,255,255,0.01)',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Showing {startIndex}–{endIndex} of {total.toLocaleString()} leads
          </span>
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button
              className="btn btn-secondary"
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              style={{ padding: '0.35rem 0.7rem' }}
            >
              <ChevronLeft size={15} />
            </button>
            <span style={{ fontSize: '0.82rem', padding: '0 0.4rem', color: 'var(--text-muted)' }}>
              {currentPage} / {totalPages}
            </span>
            <button
              className="btn btn-secondary"
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              style={{ padding: '0.35rem 0.7rem' }}
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

/* Small helper for empty cells */
const NoData = () => (
  <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem', fontStyle: 'italic' }}>—</span>
);

export default DataTable;
