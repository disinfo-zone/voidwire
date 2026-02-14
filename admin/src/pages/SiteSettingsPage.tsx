import { useEffect, useState } from 'react';
import { apiGet, apiPut } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

type SiteConfig = {
  site_title: string;
  tagline: string;
  site_url: string;
  timezone: string;
  favicon_url: string;
  meta_description: string;
  og_image_url: string;
  og_title_template: string;
  twitter_handle: string;
  tracking_head: string;
  tracking_body: string;
};

type BackupStorageConfig = {
  provider: 'local' | 's3';
  s3_endpoint: string;
  s3_bucket: string;
  s3_region: string;
  s3_prefix: string;
  s3_use_ssl: boolean;
  s3_access_key_masked?: string;
  s3_secret_key_masked?: string;
  s3_is_configured?: boolean;
};

const EMPTY_SITE: SiteConfig = {
  site_title: 'VOIDWIRE',
  tagline: '',
  site_url: '',
  timezone: 'UTC',
  favicon_url: '',
  meta_description: '',
  og_image_url: '',
  og_title_template: '{{title}} | {{site_title}}',
  twitter_handle: '',
  tracking_head: '',
  tracking_body: '',
};

const EMPTY_STORAGE: BackupStorageConfig = {
  provider: 'local',
  s3_endpoint: '',
  s3_bucket: '',
  s3_region: 'us-east-1',
  s3_prefix: 'voidwire-backups/',
  s3_use_ssl: true,
};

export default function SiteSettingsPage() {
  const [site, setSite] = useState<SiteConfig>(EMPTY_SITE);
  const [storage, setStorage] = useState<BackupStorageConfig>(EMPTY_STORAGE);
  const [s3AccessKey, setS3AccessKey] = useState('');
  const [s3SecretKey, setS3SecretKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingSite, setSavingSite] = useState(false);
  const [savingStorage, setSavingStorage] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [siteData, storageData] = await Promise.all([
        apiGet('/admin/site/config'),
        apiGet('/admin/backup/storage'),
      ]);
      setSite({ ...EMPTY_SITE, ...siteData });
      setStorage({ ...EMPTY_STORAGE, ...storageData });
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveSite() {
    setSavingSite(true);
    try {
      await apiPut('/admin/site/config', site);
      toast.success('Site settings saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingSite(false);
    }
  }

  async function saveStorage() {
    setSavingStorage(true);
    try {
      const payload: any = { ...storage };
      if (s3AccessKey.trim().length > 0) payload.s3_access_key = s3AccessKey.trim();
      if (s3SecretKey.trim().length > 0) payload.s3_secret_key = s3SecretKey.trim();
      const updated = await apiPut('/admin/backup/storage', payload);
      setStorage({ ...EMPTY_STORAGE, ...updated });
      setS3AccessKey('');
      setS3SecretKey('');
      toast.success('Backup storage settings saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingStorage(false);
    }
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-xl text-accent mb-6">Site Settings</h1>
        <div className="flex justify-center py-12"><Spinner /></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-xl text-accent">Site Settings</h1>
      </div>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">General + SEO</h2>
          <button
            onClick={saveSite}
            disabled={savingSite}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingSite ? 'Saving...' : 'Save Site Settings'}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">Site Title</label>
            <input value={site.site_title} onChange={(e) => setSite({ ...site, site_title: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Site URL</label>
            <input value={site.site_url} onChange={(e) => setSite({ ...site, site_url: e.target.value })} placeholder="https://example.com" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Timezone</label>
            <input value={site.timezone} onChange={(e) => setSite({ ...site, timezone: e.target.value })} placeholder="America/New_York" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Favicon URL</label>
            <input value={site.favicon_url} onChange={(e) => setSite({ ...site, favicon_url: e.target.value })} placeholder="https://cdn.example.com/favicon.ico" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
        </div>

        <div>
          <label className="text-xs text-text-muted block mb-1">Tagline</label>
          <input value={site.tagline} onChange={(e) => setSite({ ...site, tagline: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>

        <div>
          <label className="text-xs text-text-muted block mb-1">Meta Description</label>
          <textarea value={site.meta_description} onChange={(e) => setSite({ ...site, meta_description: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">OpenGraph Image URL</label>
            <input value={site.og_image_url} onChange={(e) => setSite({ ...site, og_image_url: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Twitter Handle</label>
            <input value={site.twitter_handle} onChange={(e) => setSite({ ...site, twitter_handle: e.target.value })} placeholder="@voidwire" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          </div>
        </div>

        <div>
          <label className="text-xs text-text-muted block mb-1">OG Title Template</label>
          <input value={site.og_title_template} onChange={(e) => setSite({ ...site, og_title_template: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
          <div className="text-[11px] text-text-ghost mt-1">Supports <span className="font-mono">{'{{title}}'}</span> and <span className="font-mono">{'{{site_title}}'}</span>.</div>
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <h2 className="text-sm text-text-primary">Tracking Script</h2>
        <div className="text-xs text-text-muted">
          Paste analytics or tracking embed snippets. Head script injects inside <span className="font-mono">&lt;head&gt;</span>; body script injects before <span className="font-mono">&lt;/body&gt;</span>.
        </div>
        <div>
          <label className="text-xs text-text-muted block mb-1">Head HTML</label>
          <textarea value={site.tracking_head} onChange={(e) => setSite({ ...site, tracking_head: e.target.value })} rows={4} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono" />
        </div>
        <div>
          <label className="text-xs text-text-muted block mb-1">Body HTML</label>
          <textarea value={site.tracking_body} onChange={(e) => setSite({ ...site, tracking_body: e.target.value })} rows={4} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono" />
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">Backup Storage</h2>
          <button
            onClick={saveStorage}
            disabled={savingStorage}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingStorage ? 'Saving...' : 'Save Backup Storage'}
          </button>
        </div>

        <div>
          <label className="text-xs text-text-muted block mb-1">Provider</label>
          <select value={storage.provider} onChange={(e) => setStorage({ ...storage, provider: e.target.value as 'local' | 's3' })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
            <option value="local">Local filesystem</option>
            <option value="s3">S3-compatible</option>
          </select>
        </div>

        {storage.provider === 's3' && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-muted block mb-1">S3 Endpoint</label>
                <input value={storage.s3_endpoint} onChange={(e) => setStorage({ ...storage, s3_endpoint: e.target.value })} placeholder="https://s3.us-east-1.amazonaws.com" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Bucket</label>
                <input value={storage.s3_bucket} onChange={(e) => setStorage({ ...storage, s3_bucket: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Region</label>
                <input value={storage.s3_region} onChange={(e) => setStorage({ ...storage, s3_region: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Prefix</label>
                <input value={storage.s3_prefix} onChange={(e) => setStorage({ ...storage, s3_prefix: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input type="checkbox" checked={storage.s3_use_ssl} onChange={(e) => setStorage({ ...storage, s3_use_ssl: e.target.checked })} />
              use SSL
            </label>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-muted block mb-1">Access Key {storage.s3_access_key_masked ? `(current: ${storage.s3_access_key_masked})` : ''}</label>
                <input type="password" value={s3AccessKey} onChange={(e) => setS3AccessKey(e.target.value)} placeholder="leave blank to keep current" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Secret Key {storage.s3_secret_key_masked ? `(current: ${storage.s3_secret_key_masked})` : ''}</label>
                <input type="password" value={s3SecretKey} onChange={(e) => setS3SecretKey(e.target.value)} placeholder="leave blank to keep current" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
