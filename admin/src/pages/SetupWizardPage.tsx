import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';

const steps = ['Database', 'Admin Account', 'LLM Config', 'Sources', 'Site Settings', 'Complete'];

export default function SetupWizardPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [status, setStatus] = useState('');
  const [adminForm, setAdminForm] = useState({ email: '', password: '' });
  const [totpUri, setTotpUri] = useState('');
  const [checkingStatus, setCheckingStatus] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    async function checkSetupStatus() {
      try {
        const data = await apiGet('/setup/status');
        if (!cancelled && data?.is_complete) {
          const hasToken = Boolean(localStorage.getItem('voidwire_admin_token'));
          navigate(hasToken ? '/' : '/login', { replace: true });
          return;
        }
      } catch {
        if (!cancelled) {
          setStatus('Unable to verify setup status. Check API availability.');
        }
      } finally {
        if (!cancelled) setCheckingStatus(false);
      }
    }
    void checkSetupStatus();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (checkingStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <p className="text-xs font-mono tracking-wider text-text-muted uppercase">Verifying setup state...</p>
      </div>
    );
  }

  async function initDb() {
    await apiPost('/setup/init-db');
    setStatus('Database initialized');
    setCurrentStep(1);
  }

  async function createAdmin() {
    const data = await apiPost('/setup/create-admin', adminForm);
    setTotpUri(data.totp_uri || '');
    setStatus('Admin created. Save your TOTP secret!');
    setCurrentStep(2);
  }

  async function skipToComplete() {
    setCurrentStep(5);
  }

  async function completeSetup() {
    await apiPost('/setup/complete');
    navigate('/login');
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-void">
      <div className="w-96 space-y-6">
        <h1 className="text-xs font-mono tracking-widest text-accent uppercase text-center">
          VOIDWIRE SETUP
        </h1>

        <div className="flex gap-1 mb-4">
          {steps.map((s, i) => (
            <div key={s} className={`flex-1 h-1 rounded ${i <= currentStep ? 'bg-accent' : 'bg-text-ghost'}`} />
          ))}
        </div>

        <h2 className="text-sm text-text-primary">{steps[currentStep]}</h2>

        {status && <p className="text-xs text-green-400">{status}</p>}

        {currentStep === 0 && (
          <button onClick={initDb} className="w-full bg-surface-raised border border-text-ghost rounded px-3 py-2 text-sm text-accent hover:border-accent">
            Initialize Database
          </button>
        )}

        {currentStep === 1 && (
          <div className="space-y-2">
            <input placeholder="Email" value={adminForm.email} onChange={e => setAdminForm({...adminForm, email: e.target.value})} className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
            <input type="password" placeholder="Password" value={adminForm.password} onChange={e => setAdminForm({...adminForm, password: e.target.value})} className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
            <button onClick={createAdmin} className="w-full bg-surface-raised border border-text-ghost rounded px-3 py-2 text-sm text-accent hover:border-accent">Create Admin</button>
          </div>
        )}

        {currentStep >= 2 && currentStep < 5 && (
          <div className="space-y-2">
            <p className="text-xs text-text-muted">Configure this step via the admin panel after setup.</p>
            <button onClick={skipToComplete} className="w-full bg-surface-raised border border-text-ghost rounded px-3 py-2 text-sm text-accent hover:border-accent">
              Skip to Complete
            </button>
          </div>
        )}

        {currentStep === 5 && (
          <button onClick={completeSetup} className="w-full bg-surface-raised border border-accent rounded px-3 py-2 text-sm text-accent hover:bg-accent/10">
            Complete Setup
          </button>
        )}

        {totpUri && (
          <div className="bg-surface border border-text-ghost rounded p-3 text-xs text-text-secondary break-all">
            <p className="text-text-muted mb-1">TOTP URI (add to authenticator app):</p>
            {totpUri}
          </div>
        )}
      </div>
    </div>
  );
}
