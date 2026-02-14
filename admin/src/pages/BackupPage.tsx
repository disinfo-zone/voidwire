import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiDelete } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

interface Backup {
  filename: string;
  size_bytes: number;
  created_at: string;
}

export default function BackupPage() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoreFile, setRestoreFile] = useState<string | null>(null);
  const [deleteFile, setDeleteFile] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { loadBackups(); }, []);

  async function loadBackups() {
    setLoading(true);
    try {
      const data = await apiGet('/admin/backup/');
      setBackups(data.backups || []);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleCreate() {
    setCreating(true);
    try {
      await apiPost('/admin/backup/create');
      toast.success('Backup created');
      loadBackups();
    } catch (e: any) {
      toast.error(e.message);
    }
    setCreating(false);
  }

  async function handleRestore() {
    if (!restoreFile) return;
    try {
      await apiPost(`/admin/backup/${encodeURIComponent(restoreFile)}/restore`);
      toast.success('Backup restored');
    } catch (e: any) {
      toast.error(e.message);
    }
    setRestoreFile(null);
  }

  async function handleDelete() {
    if (!deleteFile) return;
    try {
      await apiDelete(`/admin/backup/${encodeURIComponent(deleteFile)}`);
      setBackups(backups.filter((b) => b.filename !== deleteFile));
      toast.success('Backup deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteFile(null);
  }

  function handleDownload(filename: string) {
    const token = localStorage.getItem('voidwire_admin_token');
    const base = (import.meta as any).env?.VITE_API_URL || '';
    const url = `${base}/admin/backup/${encodeURIComponent(filename)}/download`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    // For auth, open in new tab (cookie-based) or use fetch+blob
    window.open(`${url}?token=${token}`, '_blank');
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Backups</h1>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="text-xs px-4 py-2 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
        >
          {creating ? 'Creating...' : 'Create Backup'}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : backups.length === 0 ? (
        <div className="bg-surface-raised border border-text-ghost rounded p-6 text-center">
          <p className="text-text-muted text-sm">No backups yet. Create your first backup above.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted uppercase tracking-wider border-b border-text-ghost">
                <th className="text-left py-2 px-3">Filename</th>
                <th className="text-left py-2 px-3">Size</th>
                <th className="text-left py-2 px-3">Created</th>
                <th className="text-right py-2 px-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.filename} className="border-b border-text-ghost hover:bg-surface">
                  <td className="py-2 px-3 text-text-primary font-mono text-xs">{b.filename}</td>
                  <td className="py-2 px-3 text-text-secondary">{formatSize(b.size_bytes)}</td>
                  <td className="py-2 px-3 text-text-secondary">{b.created_at ? new Date(b.created_at).toLocaleString() : '-'}</td>
                  <td className="py-2 px-3 text-right">
                    <div className="flex gap-2 justify-end">
                      <button onClick={() => handleDownload(b.filename)} className="text-xs text-text-muted hover:text-accent">download</button>
                      <button onClick={() => setRestoreFile(b.filename)} className="text-xs text-accent hover:underline">restore</button>
                      <button onClick={() => setDeleteFile(b.filename)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!restoreFile}
        title="Restore Backup"
        message={`This will restore the database from "${restoreFile}". Current data will be overwritten. Continue?`}
        onConfirm={handleRestore}
        onCancel={() => setRestoreFile(null)}
        destructive
      />

      <ConfirmDialog
        open={!!deleteFile}
        title="Delete Backup"
        message={`Are you sure you want to delete "${deleteFile}"?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteFile(null)}
        destructive
      />
    </div>
  );
}
