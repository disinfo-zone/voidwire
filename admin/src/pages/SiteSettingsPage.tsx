import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiGet, apiPost, apiPut } from '../api/client';
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

type OAuthProviderConfig = {
  enabled: boolean;
  client_id: string;
  is_configured?: boolean;
  client_secret_masked?: string;
  team_id?: string;
  key_id?: string;
  private_key_masked?: string;
};

type OAuthConfig = {
  google: OAuthProviderConfig;
  apple: OAuthProviderConfig;
  any_enabled?: boolean;
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

const EMPTY_OAUTH: OAuthConfig = {
  google: {
    enabled: false,
    client_id: '',
    client_secret_masked: '',
    is_configured: false,
  },
  apple: {
    enabled: false,
    client_id: '',
    team_id: '',
    key_id: '',
    private_key_masked: '',
    is_configured: false,
  },
  any_enabled: false,
};

export default function SiteSettingsPage() {
  const [site, setSite] = useState<SiteConfig>(EMPTY_SITE);
  const [storage, setStorage] = useState<BackupStorageConfig>(EMPTY_STORAGE);
  const [oauth, setOauth] = useState<OAuthConfig>(EMPTY_OAUTH);
  const [s3AccessKey, setS3AccessKey] = useState('');
  const [s3SecretKey, setS3SecretKey] = useState('');
  const [googleClientSecret, setGoogleClientSecret] = useState('');
  const [applePrivateKey, setApplePrivateKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingSite, setSavingSite] = useState(false);
  const [savingStorage, setSavingStorage] = useState(false);
  const [savingOauth, setSavingOauth] = useState(false);
  const [uploadingFavicon, setUploadingFavicon] = useState(false);
  const [uploadingTwitterCard, setUploadingTwitterCard] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [siteData, storageData, oauthData] = await Promise.all([
        apiGet('/admin/site/config'),
        apiGet('/admin/backup/storage'),
        apiGet('/admin/site/auth/oauth'),
      ]);
      setSite({ ...EMPTY_SITE, ...siteData });
      setStorage({ ...EMPTY_STORAGE, ...storageData });
      setOauth({
        ...EMPTY_OAUTH,
        ...oauthData,
        google: { ...EMPTY_OAUTH.google, ...(oauthData?.google || {}) },
        apple: { ...EMPTY_OAUTH.apple, ...(oauthData?.apple || {}) },
      });
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

  function fileToDataUrl(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result !== 'string' || !reader.result) {
          reject(new Error('Failed to read file'));
          return;
        }
        resolve(reader.result);
      };
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
  }

  async function uploadSiteAsset(kind: 'favicon' | 'twittercard', file: File) {
    if (!file) return;
    const maxBytes = kind === 'favicon' ? 512 * 1024 : 5 * 1024 * 1024;
    if (file.size > maxBytes) {
      toast.error(`File is too large (max ${Math.round(maxBytes / 1024)}KB)`);
      return;
    }

    if (kind === 'favicon') setUploadingFavicon(true);
    if (kind === 'twittercard') setUploadingTwitterCard(true);
    try {
      const dataBase64 = await fileToDataUrl(file);
      const response = await apiPost('/admin/site/assets', {
        kind,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        data_base64: dataBase64,
      });
      const url = String(response?.url || '').trim();
      if (kind === 'favicon') {
        setSite((prev) => ({ ...prev, favicon_url: url || prev.favicon_url }));
      } else {
        setSite((prev) => ({ ...prev, og_image_url: url || prev.og_image_url }));
      }
      toast.success(kind === 'favicon' ? 'Favicon uploaded' : 'Twitter/OpenGraph image uploaded');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      if (kind === 'favicon') setUploadingFavicon(false);
      if (kind === 'twittercard') setUploadingTwitterCard(false);
    }
  }

  async function saveOauth() {
    setSavingOauth(true);
    try {
      const payload: any = {
        google: {
          enabled: oauth.google.enabled,
          client_id: oauth.google.client_id || '',
        },
        apple: {
          enabled: oauth.apple.enabled,
          client_id: oauth.apple.client_id || '',
          team_id: oauth.apple.team_id || '',
          key_id: oauth.apple.key_id || '',
        },
      };
      if (googleClientSecret.trim().length > 0) {
        payload.google.client_secret = googleClientSecret.trim();
      }
      if (applePrivateKey.trim().length > 0) {
        payload.apple.private_key = applePrivateKey;
      }
      const updated = await apiPut('/admin/site/auth/oauth', payload);
      setOauth({
        ...EMPTY_OAUTH,
        ...updated,
        google: { ...EMPTY_OAUTH.google, ...(updated?.google || {}) },
        apple: { ...EMPTY_OAUTH.apple, ...(updated?.apple || {}) },
      });
      setGoogleClientSecret('');
      setApplePrivateKey('');
      toast.success('OAuth settings saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingOauth(false);
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
            <div className="mt-2 flex flex-col gap-2">
              <input
                type="file"
                accept=".ico,image/png,image/svg+xml,image/jpeg,image/webp"
                disabled={uploadingFavicon}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.currentTarget.value = '';
                  if (!file) return;
                  void uploadSiteAsset('favicon', file);
                }}
                className="w-full text-xs text-text-muted file:mr-3 file:px-3 file:py-1 file:border file:border-text-ghost file:rounded file:bg-surface file:text-text-secondary"
              />
              <div className="text-[11px] text-text-ghost">
                {uploadingFavicon ? 'Uploading favicon...' : 'Upload favicon (ICO/PNG/SVG/JPG/WEBP). URL field still supports external CDN links.'}
              </div>
              {site.favicon_url && (
                <div className="flex items-center gap-2 text-[11px] text-text-ghost">
                  <img src={site.favicon_url} alt="Favicon preview" className="w-6 h-6 rounded border border-text-ghost object-contain bg-surface-raised" />
                  <span>Current favicon preview</span>
                </div>
              )}
            </div>
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
            <div className="mt-2 flex flex-col gap-2">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={uploadingTwitterCard}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.currentTarget.value = '';
                  if (!file) return;
                  void uploadSiteAsset('twittercard', file);
                }}
                className="w-full text-xs text-text-muted file:mr-3 file:px-3 file:py-1 file:border file:border-text-ghost file:rounded file:bg-surface file:text-text-secondary"
              />
              <div className="text-[11px] text-text-ghost">
                {uploadingTwitterCard
                  ? 'Uploading social card image...'
                  : 'Upload Twitter/OpenGraph card image (PNG/JPG/WEBP, up to 5MB).'}
              </div>
              {site.og_image_url && (
                <div className="mt-1">
                  <img
                    src={site.og_image_url}
                    alt="OpenGraph/Twitter card preview"
                    className="w-full max-w-sm rounded border border-text-ghost object-cover bg-surface-raised"
                  />
                </div>
              )}
            </div>
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

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-2">
        <h2 className="text-sm text-text-primary">Email Configuration</h2>
        <div className="text-xs text-text-muted">
          Transactional email delivery and editable email templates are managed in the dedicated Email panel.
        </div>
        <Link
          to="/email"
          className="inline-flex text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
        >
          Open Email Settings
        </Link>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">OAuth Sign-In</h2>
          <button
            onClick={saveOauth}
            disabled={savingOauth}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingOauth ? 'Saving...' : 'Save OAuth Settings'}
          </button>
        </div>
        <div className="text-xs text-text-muted">
          Configure provider credentials and enable only when ready. Disabled providers are hidden on login/register.
        </div>

        <div className="border border-text-ghost rounded p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs text-text-primary">Google OAuth</div>
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={oauth.google.enabled}
                onChange={(e) =>
                  setOauth((prev) => ({
                    ...prev,
                    google: { ...prev.google, enabled: e.target.checked },
                  }))
                }
              />
              enabled
            </label>
          </div>
          <input
            value={oauth.google.client_id}
            onChange={(e) =>
              setOauth((prev) => ({
                ...prev,
                google: { ...prev.google, client_id: e.target.value },
              }))
            }
            placeholder="Google client ID"
            className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
          />
          <input
            type="password"
            value={googleClientSecret}
            onChange={(e) => setGoogleClientSecret(e.target.value)}
            placeholder={`Client secret ${oauth.google.client_secret_masked ? `(current: ${oauth.google.client_secret_masked})` : '(optional)'}`}
            className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
          />
          <div className="text-xs text-text-muted">
            Status: {oauth.google.is_configured ? 'configured' : 'incomplete'} {oauth.google.enabled ? '(enabled)' : '(disabled)'}
          </div>
        </div>

        <div className="border border-text-ghost rounded p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs text-text-primary">Apple OAuth</div>
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={oauth.apple.enabled}
                onChange={(e) =>
                  setOauth((prev) => ({
                    ...prev,
                    apple: { ...prev.apple, enabled: e.target.checked },
                  }))
                }
              />
              enabled
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              value={oauth.apple.client_id || ''}
              onChange={(e) =>
                setOauth((prev) => ({
                  ...prev,
                  apple: { ...prev.apple, client_id: e.target.value },
                }))
              }
              placeholder="Apple client ID"
              className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
            <input
              value={oauth.apple.team_id || ''}
              onChange={(e) =>
                setOauth((prev) => ({
                  ...prev,
                  apple: { ...prev.apple, team_id: e.target.value },
                }))
              }
              placeholder="Apple team ID"
              className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
            <input
              value={oauth.apple.key_id || ''}
              onChange={(e) =>
                setOauth((prev) => ({
                  ...prev,
                  apple: { ...prev.apple, key_id: e.target.value },
                }))
              }
              placeholder="Apple key ID"
              className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <textarea
            value={applePrivateKey}
            onChange={(e) => setApplePrivateKey(e.target.value)}
            rows={4}
            placeholder={`Apple private key ${oauth.apple.private_key_masked ? `(current: ${oauth.apple.private_key_masked})` : '(optional)'}`}
            className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono"
          />
          <div className="text-xs text-text-muted">
            Status: {oauth.apple.is_configured ? 'configured' : 'incomplete'} {oauth.apple.enabled ? '(enabled)' : '(disabled)'}
          </div>
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-2">
        <h2 className="text-sm text-text-primary">Billing Configuration</h2>
        <div className="text-xs text-text-muted">
          Stripe credentials, discount codes, pricing visibility, and billing analytics now live in the dedicated Billing panel.
        </div>
        <Link
          to="/billing"
          className="inline-flex text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
        >
          Open Billing
        </Link>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-2">
        <h2 className="text-sm text-text-primary">Prompt Safety</h2>
        <div className="text-xs text-text-muted">
          Personal-reading banned phrases now use the same configuration as synthesis prompts.
          Manage this list in <span className="text-text-primary">Pipeline Settings - Synthesis - banned_phrases</span>.
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
