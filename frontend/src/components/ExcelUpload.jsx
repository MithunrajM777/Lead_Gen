import React, { useState, useRef } from 'react';
import api from '../api/client';
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react';

const ExcelUpload = ({ onJobCreated }) => {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError('File is too large (max 10MB)');
        return;
      }
      setFile(selectedFile);
      setError(null);
      setSuccess(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/upload-excel', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percentCompleted);
        },
      });

      setSuccess(true);
      setFile(null);
      if (onJobCreated) onJobCreated(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload file');
    } finally {
      setIsUploading(false);
    }
  };

  const removeFile = () => {
    setFile(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="excel-upload-container" style={{ marginTop: '1.5rem' }}>
      <label style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.75rem', display: 'block' }}>
        Bulk URL Scrape (Excel/CSV)
      </label>
      
      {!file ? (
        <div 
          className="upload-dropzone"
          onClick={() => fileInputRef.current.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const droppedFile = e.dataTransfer.files[0];
            if (droppedFile) handleFileChange({ target: { files: [droppedFile] } });
          }}
        >
          <Upload size={24} color="var(--primary)" style={{ marginBottom: '0.5rem' }} />
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Click or drag .xlsx or .csv file here
          </p>
          <span style={{ fontSize: '0.65rem', opacity: 0.6, marginTop: '0.2rem' }}>
            Requires 'website_url' column
          </span>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            accept=".xlsx, .csv" 
            style={{ display: 'none' }} 
          />
        </div>
      ) : (
        <div className="file-preview">
          <div className="flex-between">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', minWidth: 0 }}>
              <FileText size={18} color="var(--primary)" />
              <span className="truncate" style={{ fontSize: '0.82rem' }}>{file.name}</span>
            </div>
            <button 
              onClick={removeFile} 
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              disabled={isUploading}
            >
              <X size={16} />
            </button>
          </div>
          
          {isUploading ? (
            <div style={{ marginTop: '0.75rem' }}>
              <div className="progress-bar-wrapper">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
              </div>
              <div style={{ fontSize: '0.7rem', textAlign: 'right', marginTop: '0.3rem', color: 'var(--text-muted)' }}>
                Uploading... {progress}%
              </div>
            </div>
          ) : (
            <button 
              className="btn btn-primary" 
              style={{ width: '100%', marginTop: '1rem', justifyContent: 'center', fontSize: '0.82rem' }}
              onClick={handleUpload}
            >
              Start Bulk Scrape
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="scraper-status error" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {success && (
        <div className="scraper-status success" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
          <CheckCircle2 size={14} /> File uploaded! Processing in background.
        </div>
      )}
    </div>
  );
};

export default ExcelUpload;
