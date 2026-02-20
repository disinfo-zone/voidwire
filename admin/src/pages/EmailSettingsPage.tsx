import { useEffect, useState } from 'react';
import { apiGet, apiPost, apiPut } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

type EmailProvider = 'smtp' | 'resend';

type SMTPConfig = {
  enabled: boolean;
  provider: EmailProvider;
  host: string;
  port: number;
  username: string;
  from_email: string;
  from_name: string;
  reply_to: string;
  use_ssl: boolean;
  use_starttls: boolean;
  password_masked?: string;
  resend_api_key_masked?: string;
  resend_api_base_url: string;
  is_configured?: boolean;
};

type EmailTemplateContent = {
  subject: string;
  text_body: string;
  html_body: string;
};

type EmailTemplatesConfig = {
  verification: EmailTemplateContent;
  password_reset: EmailTemplateContent;
  test_email: EmailTemplateContent;
  updated_at?: string | null;
};

type TemplateKey = keyof Pick<EmailTemplatesConfig, 'verification' | 'password_reset' | 'test_email'>;

const EMPTY_SMTP: SMTPConfig = {
  enabled: false,
  provider: 'smtp',
  host: '',
  port: 587,
  username: '',
  from_email: '',
  from_name: 'Voidwire',
  reply_to: '',
  use_ssl: false,
  use_starttls: true,
  password_masked: '',
  resend_api_key_masked: '',
  resend_api_base_url: 'https://api.resend.com',
  is_configured: false,
};

const EMPTY_TEMPLATES: EmailTemplatesConfig = {
  verification: {
    subject: '',
    text_body: '',
    html_body: '',
  },
  password_reset: {
    subject: '',
    text_body: '',
    html_body: '',
  },
  test_email: {
    subject: '',
    text_body: '',
    html_body: '',
  },
  updated_at: null,
};

const TEMPLATE_LABELS: Record<TemplateKey, string> = {
  verification: 'Verification',
  password_reset: 'Password Reset',
  test_email: 'Test Email',
};

export default function EmailSettingsPage() {
  const [delivery, setDelivery] = useState<SMTPConfig>(EMPTY_SMTP);
  const [smtpPassword, setSmtpPassword] = useState('');
  const [resendApiKey, setResendApiKey] = useState('');
  const [testRecipient, setTestRecipient] = useState('');
  const [templates, setTemplates] = useState<EmailTemplatesConfig>(EMPTY_TEMPLATES);
  const [activeTemplate, setActiveTemplate] = useState<TemplateKey>('verification');
  const [loading, setLoading] = useState(true);
  const [savingDelivery, setSavingDelivery] = useState(false);
  const [savingTemplates, setSavingTemplates] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [smtpData, templatesData] = await Promise.all([
        apiGet('/admin/site/email/smtp'),
        apiGet('/admin/site/email/templates'),
      ]);
      setDelivery({ ...EMPTY_SMTP, ...(smtpData || {}) });
      setTemplates({
        ...EMPTY_TEMPLATES,
        ...(templatesData || {}),
        verification: { ...EMPTY_TEMPLATES.verification, ...(templatesData?.verification || {}) },
        password_reset: { ...EMPTY_TEMPLATES.password_reset, ...(templatesData?.password_reset || {}) },
        test_email: { ...EMPTY_TEMPLATES.test_email, ...(templatesData?.test_email || {}) },
      });
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveDelivery() {
    setSavingDelivery(true);
    try {
      const payload: any = { ...delivery };
      if (smtpPassword.trim().length > 0) {
        payload.password = smtpPassword.trim();
      }
      if (resendApiKey.trim().length > 0) {
        payload.resend_api_key = resendApiKey.trim();
      }
      const updated = await apiPut('/admin/site/email/smtp', payload);
      setDelivery({ ...EMPTY_SMTP, ...(updated || {}) });
      setSmtpPassword('');
      setResendApiKey('');
      toast.success('Email delivery settings saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingDelivery(false);
    }
  }

  async function saveEmailTemplates() {
    setSavingTemplates(true);
    try {
      const payload = {
        verification: templates.verification,
        password_reset: templates.password_reset,
        test_email: templates.test_email,
      };
      const updated = await apiPut('/admin/site/email/templates', payload);
      setTemplates({
        ...EMPTY_TEMPLATES,
        ...(updated || {}),
        verification: { ...EMPTY_TEMPLATES.verification, ...(updated?.verification || {}) },
        password_reset: { ...EMPTY_TEMPLATES.password_reset, ...(updated?.password_reset || {}) },
        test_email: { ...EMPTY_TEMPLATES.test_email, ...(updated?.test_email || {}) },
      });
      toast.success('Email templates saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingTemplates(false);
    }
  }

  async function sendTestEmail() {
    const to = testRecipient.trim();
    if (!to) {
      toast.error('Enter a test recipient email');
      return;
    }
    setSendingTest(true);
    try {
      await apiPost('/admin/site/email/smtp/test', { to_email: to });
      toast.success('Test email sent');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSendingTest(false);
    }
  }

  function updateActiveTemplateField(field: keyof EmailTemplateContent, value: string) {
    setTemplates((prev) => ({
      ...prev,
      [activeTemplate]: {
        ...prev[activeTemplate],
        [field]: value,
      },
    }));
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-xl text-accent mb-6">Email Settings</h1>
        <div className="flex justify-center py-12"><Spinner /></div>
      </div>
    );
  }

  const smtpProvider = delivery.provider === 'smtp';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl text-accent">Email Settings</h1>
        <div className="text-xs text-text-muted mt-1">
          Configure delivery provider and edit transactional email templates.
        </div>
      </div>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">Delivery Provider</h2>
          <button
            onClick={saveDelivery}
            disabled={savingDelivery}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingDelivery ? 'Saving...' : 'Save Delivery Settings'}
          </button>
        </div>

        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input
            type="checkbox"
            checked={delivery.enabled}
            onChange={(e) => setDelivery((prev) => ({ ...prev, enabled: e.target.checked }))}
          />
          Enable transactional email delivery
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">Provider</label>
            <select
              value={delivery.provider}
              onChange={(e) => setDelivery((prev) => ({ ...prev, provider: e.target.value as EmailProvider }))}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            >
              <option value="resend">Resend API (Recommended)</option>
              <option value="smtp">SMTP</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">From Email</label>
            <input
              value={delivery.from_email}
              onChange={(e) => setDelivery((prev) => ({ ...prev, from_email: e.target.value }))}
              placeholder="noreply@voidwire.com"
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">From Name</label>
            <input
              value={delivery.from_name}
              onChange={(e) => setDelivery((prev) => ({ ...prev, from_name: e.target.value }))}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Reply-To (optional)</label>
            <input
              value={delivery.reply_to}
              onChange={(e) => setDelivery((prev) => ({ ...prev, reply_to: e.target.value }))}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
        </div>

        {smtpProvider ? (
          <div className="border border-text-ghost rounded p-3 space-y-3">
            <div className="text-xs text-text-muted">SMTP transport settings</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-muted block mb-1">SMTP Host</label>
                <input
                  value={delivery.host}
                  onChange={(e) => setDelivery((prev) => ({ ...prev, host: e.target.value }))}
                  placeholder="smtp.resend.com"
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">SMTP Port</label>
                <input
                  type="number"
                  value={delivery.port}
                  onChange={(e) => setDelivery((prev) => ({ ...prev, port: Number(e.target.value) || 587 }))}
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">SMTP Username</label>
                <input
                  value={delivery.username}
                  onChange={(e) => setDelivery((prev) => ({ ...prev, username: e.target.value }))}
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">
                  SMTP Password {delivery.password_masked ? `(current: ${delivery.password_masked})` : ''}
                </label>
                <input
                  type="password"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  placeholder="leave blank to keep current"
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-xs text-text-muted">
                <input
                  type="checkbox"
                  checked={delivery.use_ssl}
                  onChange={(e) =>
                    setDelivery((prev) => ({
                      ...prev,
                      use_ssl: e.target.checked,
                      use_starttls: e.target.checked ? false : prev.use_starttls,
                    }))
                  }
                />
                Use implicit SSL (465)
              </label>
              <label className="flex items-center gap-2 text-xs text-text-muted">
                <input
                  type="checkbox"
                  checked={delivery.use_starttls}
                  disabled={delivery.use_ssl}
                  onChange={(e) => setDelivery((prev) => ({ ...prev, use_starttls: e.target.checked }))}
                />
                Use STARTTLS (587)
              </label>
            </div>
          </div>
        ) : (
          <div className="border border-text-ghost rounded p-3 space-y-3">
            <div className="text-xs text-text-muted">
              Resend API transport (recommended). No SMTP relay required.
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-muted block mb-1">
                  Resend API Key {delivery.resend_api_key_masked ? `(current: ${delivery.resend_api_key_masked})` : ''}
                </label>
                <input
                  type="password"
                  value={resendApiKey}
                  onChange={(e) => setResendApiKey(e.target.value)}
                  placeholder="re_..."
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Resend API Base URL</label>
                <input
                  value={delivery.resend_api_base_url}
                  onChange={(e) => setDelivery((prev) => ({ ...prev, resend_api_base_url: e.target.value }))}
                  placeholder="https://api.resend.com"
                  className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                />
              </div>
            </div>
          </div>
        )}

        <div className="border-t border-text-ghost/40 pt-3 space-y-2">
          <div className="text-xs text-text-muted">
            Status: {delivery.is_configured ? 'configured' : 'incomplete'} {delivery.enabled ? '(enabled)' : '(disabled)'}
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              value={testRecipient}
              onChange={(e) => setTestRecipient(e.target.value)}
              placeholder="test recipient email"
              className="flex-1 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
            <button
              onClick={sendTestEmail}
              disabled={sendingTest}
              className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary disabled:opacity-50"
            >
              {sendingTest ? 'Sending...' : 'Send Test Email'}
            </button>
          </div>
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">Email Templates</h2>
          <button
            onClick={saveEmailTemplates}
            disabled={savingTemplates}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingTemplates ? 'Saving...' : 'Save Templates'}
          </button>
        </div>
        <div className="text-xs text-text-muted">
          Placeholders available: <span className="font-mono">{'{{site_name}}'}</span>, <span className="font-mono">{'{{verify_link}}'}</span>, <span className="font-mono">{'{{reset_link}}'}</span>, <span className="font-mono">{'{{token}}'}</span>.
        </div>

        <div className="flex gap-2 flex-wrap">
          {(Object.keys(TEMPLATE_LABELS) as TemplateKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setActiveTemplate(key)}
              className={`text-xs px-3 py-1 rounded border ${
                activeTemplate === key
                  ? 'border-accent text-accent bg-accent/10'
                  : 'border-text-ghost text-text-muted hover:text-text-primary'
              }`}
            >
              {TEMPLATE_LABELS[key]}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">Subject</label>
            <input
              value={templates[activeTemplate].subject}
              onChange={(e) => updateActiveTemplateField('subject', e.target.value)}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Text Body</label>
            <textarea
              value={templates[activeTemplate].text_body}
              onChange={(e) => updateActiveTemplateField('text_body', e.target.value)}
              rows={8}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">HTML Body</label>
            <textarea
              value={templates[activeTemplate].html_body}
              onChange={(e) => updateActiveTemplateField('html_body', e.target.value)}
              rows={8}
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
