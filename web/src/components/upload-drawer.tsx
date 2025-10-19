'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { DevFlagsControl } from './dev-flags-control';
import { useI18n } from '../i18n/context';

type UploadContextValue = {
  open: () => void;
  close: () => void;
};

const UploadDrawerContext = createContext<UploadContextValue | null>(null);

export function UploadDrawerProvider({ children }: { children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);

  const open = useCallback(() => setVisible(true), []);
  const close = useCallback(() => setVisible(false), []);

  const value = useMemo(() => ({ open, close }), [open, close]);

  return (
    <UploadDrawerContext.Provider value={value}>
      {children}
      {visible ? <UploadDrawer onClose={close} /> : null}
      <DevFlagsControl />
    </UploadDrawerContext.Provider>
  );
}

export function useUploadDrawer() {
  const ctx = useContext(UploadDrawerContext);
  if (!ctx) {
    throw new Error('useUploadDrawer must be used within UploadDrawerProvider');
  }
  return ctx;
}

function UploadDrawer({ onClose }: { onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<Element | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string; batchId?: string } | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    previouslyFocused.current = document.activeElement;
    panelRef.current?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
      }
    }
    window.addEventListener('keydown', handleKey, true);
    return () => {
      window.removeEventListener('keydown', handleKey, true);
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
  }, [onClose]);

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    // Get user ID from URL or session
    const params = new URLSearchParams(window.location.search);
    const userId = params.get('user') || 'default_user';

    setUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });

      const response = await fetchWithRetry(`/api/hc/photo/ingest?userId=${userId}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      setUploadResult({
        success: true,
        message: `Successfully uploaded ${result.count} photo(s)`,
        batchId: result.batch_id,
      });
    } catch (error) {
      setUploadResult({
        success: false,
        message: error instanceof Error ? error.message : 'Upload failed',
      });
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  }, [handleFiles]);

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="hc-upload-title">
      <div
        ref={panelRef}
        tabIndex={-1}
        id="hc-upload-drawer"
        className="w-full max-w-2xl rounded-t-2xl bg-slate-900 p-6 shadow-xl"
      >
        <div className="flex items-center justify-between">
          <h2 id="hc-upload-title" className="text-lg font-semibold">
            {t('uploadDrawer.title')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300 hover:bg-slate-700"
          >
            {t('uploadDrawer.close')}
          </button>
        </div>
        <p className="mt-3 text-sm text-slate-400">{t('uploadDrawer.dropHint')}</p>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileInputChange}
          className="hidden"
        />

        {/* Drag and drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`mt-5 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
            isDragging
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-700 hover:border-slate-600'
          }`}
        >
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-700 border-t-blue-500"></div>
              <p className="font-medium text-slate-200">Uploading photos...</p>
            </div>
          ) : uploadResult ? (
            <div className="flex flex-col items-center gap-3">
              {uploadResult.success ? (
                <>
                  <div className="text-4xl">✅</div>
                  <p className="font-medium text-green-400">{uploadResult.message}</p>
                  {uploadResult.batchId && (
                    <p className="text-xs text-slate-400">Batch ID: {uploadResult.batchId}</p>
                  )}
                  <button
                    onClick={() => setUploadResult(null)}
                    className="mt-2 rounded bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700"
                  >
                    Upload More
                  </button>
                </>
              ) : (
                <>
                  <div className="text-4xl">❌</div>
                  <p className="font-medium text-red-400">{uploadResult.message}</p>
                  <button
                    onClick={() => setUploadResult(null)}
                    className="mt-2 rounded bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700"
                  >
                    Try Again
                  </button>
                </>
              )}
            </div>
          ) : (
            <>
              <p className="font-medium text-slate-200">{t('uploadDrawer.dragDrop')}</p>
              <p className="mt-2 text-sm text-slate-400">{t('uploadDrawer.pickFilesHint')}</p>
              <button
                onClick={handleBrowseClick}
                className="mt-4 rounded-lg bg-blue-600 px-6 py-2 font-medium text-white hover:bg-blue-500"
              >
                Browse Files
              </button>
              <p className="mt-3 text-xs text-slate-500">Accepts JPEG, PNG, WebP</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
