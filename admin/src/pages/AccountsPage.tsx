import { useEffect, useState } from 'react';
import { apiDelete, apiGet, apiPatch, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

type AccountUser = {
  id: string;
  email: string;
  display_name: string | null;
  tier: 'free' | 'pro';
  has_active_subscription: boolean;
  pro_override: boolean;
  pro_override_reason: string | null;
  pro_override_until: string | null;
  created_at: string | null;
  last_login_at: string | null;
};

type DiscountCode = {
  id: string;
  code: string;
  description: string | null;
  percent_off: number | null;
  amount_off_cents: number | null;
  currency: string | null;
  duration: string;
  duration_in_months: number | null;
  max_redemptions: number | null;
  starts_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  is_usable_now: boolean;
};

type AdminUserAccount = {
  id: string;
  email: string;
  role: 'owner' | 'admin' | 'support' | 'readonly';
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

function toInputDateTime(value: string | null): string {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function fromInputDateTime(value: string): string | null {
  if (!value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

export default function AccountsPage() {
  const [users, setUsers] = useState<AccountUser[]>([]);
  const [adminUsers, setAdminUsers] = useState<AdminUserAccount[]>([]);
  const [discountCodes, setDiscountCodes] = useState<DiscountCode[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(true);
  const [loadingCodes, setLoadingCodes] = useState(true);
  const [reconcilingBilling, setReconcilingBilling] = useState(false);
  const [runningRetentionCleanup, setRunningRetentionCleanup] = useState(false);
  const [query, setQuery] = useState('');
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [overrideEnabled, setOverrideEnabled] = useState(true);
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideExpiresAt, setOverrideExpiresAt] = useState('');
  const [showInactiveCodes, setShowInactiveCodes] = useState(true);
  const [deleteCodeId, setDeleteCodeId] = useState<string | null>(null);
  const [createCodeForm, setCreateCodeForm] = useState({
    code: '',
    discountType: 'percent',
    percentOff: '20',
    amountOffCents: '',
    currency: 'usd',
    duration: 'once',
    durationInMonths: '',
    maxRedemptions: '',
    startsAt: '',
    expiresAt: '',
    description: '',
  });
  const [creatingCode, setCreatingCode] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    void Promise.all([loadUsers(), loadAdminUsers(), loadDiscountCodes()]);
  }, []);

  async function loadUsers() {
    setLoadingUsers(true);
    try {
      const params = new URLSearchParams();
      params.set('limit', '100');
      if (query.trim()) params.set('q', query.trim());
      const data = await apiGet(`/admin/accounts/users?${params.toString()}`);
      setUsers(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingUsers(false);
    }
  }

  async function loadDiscountCodes() {
    setLoadingCodes(true);
    try {
      const data = await apiGet('/admin/accounts/discount-codes');
      setDiscountCodes(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingCodes(false);
    }
  }

  async function loadAdminUsers() {
    setLoadingAdminUsers(true);
    try {
      const data = await apiGet('/admin/accounts/admin-users');
      setAdminUsers(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingAdminUsers(false);
    }
  }

  async function updateAdminUser(adminUserId: string, payload: Record<string, unknown>) {
    try {
      await apiPatch(`/admin/accounts/admin-users/${adminUserId}`, payload);
      toast.success('Admin account updated');
      await loadAdminUsers();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function reconcileBilling() {
    setReconcilingBilling(true);
    try {
      const data = await apiPost('/admin/accounts/billing/reconcile');
      const updated = typeof data?.updated === 'number' ? data.updated : 0;
      const scanned = typeof data?.scanned === 'number' ? data.scanned : 0;
      toast.success(`Billing reconciliation complete (${updated}/${scanned} updated)`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setReconcilingBilling(false);
    }
  }

  async function cleanupRetentionData() {
    setRunningRetentionCleanup(true);
    try {
      const data = await apiPost('/admin/accounts/retention/cleanup');
      const jobRows = typeof data?.async_jobs_deleted === 'number' ? data.async_jobs_deleted : 0;
      const analyticsRows = typeof data?.analytics_deleted === 'number' ? data.analytics_deleted : 0;
      toast.success(`Retention cleanup complete (${jobRows} jobs, ${analyticsRows} analytics rows)`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setRunningRetentionCleanup(false);
    }
  }

  function startEditOverride(user: AccountUser) {
    setEditingUserId(user.id);
    setOverrideEnabled(user.pro_override);
    setOverrideReason(user.pro_override_reason || '');
    setOverrideExpiresAt(toInputDateTime(user.pro_override_until));
  }

  async function saveOverride(userId: string) {
    try {
      await apiPatch(`/admin/accounts/users/${userId}/pro-override`, {
        enabled: overrideEnabled,
        reason: overrideEnabled ? (overrideReason.trim() || null) : null,
        expires_at: overrideEnabled ? fromInputDateTime(overrideExpiresAt) : null,
      });
      toast.success('Pro override updated');
      setEditingUserId(null);
      await loadUsers();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function toggleDiscountCode(code: DiscountCode, nextActive: boolean) {
    try {
      await apiPatch(`/admin/accounts/discount-codes/${code.id}`, {
        is_active: nextActive,
      });
      toast.success(nextActive ? 'Discount code enabled' : 'Discount code disabled');
      await loadDiscountCodes();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  function discountLabel(code: DiscountCode): string {
    if (code.percent_off != null) {
      return `${code.percent_off}% off`;
    }
    if (code.amount_off_cents != null && code.currency) {
      return `${(code.amount_off_cents / 100).toFixed(2)} ${code.currency.toUpperCase()} off`;
    }
    return 'discount';
  }

  async function createDiscountCode() {
    const payload: Record<string, unknown> = {
      code: createCodeForm.code,
      duration: createCodeForm.duration,
      duration_in_months:
        createCodeForm.duration === 'repeating' && createCodeForm.durationInMonths
          ? Number(createCodeForm.durationInMonths)
          : null,
      max_redemptions: createCodeForm.maxRedemptions
        ? Number(createCodeForm.maxRedemptions)
        : null,
      starts_at: fromInputDateTime(createCodeForm.startsAt),
      expires_at: fromInputDateTime(createCodeForm.expiresAt),
      description: createCodeForm.description.trim() || null,
    };

    if (createCodeForm.discountType === 'percent') {
      const percentOff = Number(createCodeForm.percentOff);
      if (!Number.isFinite(percentOff) || percentOff <= 0 || percentOff > 100) {
        toast.error('Percent off must be between 0 and 100');
        return;
      }
      payload.percent_off = percentOff;
    } else {
      const amountOffCents = Number(createCodeForm.amountOffCents);
      if (!Number.isFinite(amountOffCents) || amountOffCents < 1) {
        toast.error('Amount off must be at least 1 cent');
        return;
      }
      payload.amount_off_cents = amountOffCents;
      payload.currency = createCodeForm.currency.trim().toLowerCase();
    }

    setCreatingCode(true);
    try {
      await apiPost('/admin/accounts/discount-codes', payload);
      toast.success('Discount code created');
      setCreateCodeForm({
        code: '',
        discountType: 'percent',
        percentOff: '20',
        amountOffCents: '',
        currency: 'usd',
        duration: 'once',
        durationInMonths: '',
        maxRedemptions: '',
        startsAt: '',
        expiresAt: '',
        description: '',
      });
      await loadDiscountCodes();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setCreatingCode(false);
    }
  }

  async function deleteDiscountCode() {
    if (!deleteCodeId) return;
    try {
      await apiDelete(`/admin/accounts/discount-codes/${deleteCodeId}`);
      toast.success('Discount code deleted');
      await loadDiscountCodes();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setDeleteCodeId(null);
    }
  }

  const visibleCodes = showInactiveCodes
    ? discountCodes
    : discountCodes.filter((code) => code.is_active);

  return (
    <div className="space-y-8">
      <section>
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-xl text-accent">Admin Access</h1>
          <div className="flex gap-2">
            <button
              onClick={reconcileBilling}
              disabled={reconcilingBilling}
              className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary disabled:opacity-50"
            >
              {reconcilingBilling ? 'Reconciling...' : 'Reconcile Billing'}
            </button>
            <button
              onClick={cleanupRetentionData}
              disabled={runningRetentionCleanup}
              className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary disabled:opacity-50"
            >
              {runningRetentionCleanup ? 'Cleaning...' : 'Run Retention Cleanup'}
            </button>
          </div>
        </div>
        {loadingAdminUsers ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <div className="space-y-2">
            {adminUsers.map((adminUser) => (
              <div key={adminUser.id} className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">{adminUser.email}</div>
                    <div className="text-xs text-text-muted">
                      Last login {adminUser.last_login_at ? new Date(adminUser.last_login_at).toLocaleString() : 'never'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={adminUser.role}
                      onChange={(event) => {
                        void updateAdminUser(adminUser.id, { role: event.target.value });
                      }}
                      className="bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary"
                    >
                      <option value="owner">owner</option>
                      <option value="admin">admin</option>
                      <option value="support">support</option>
                      <option value="readonly">readonly</option>
                    </select>
                    <label className="flex items-center gap-2 text-xs text-text-muted">
                      <input
                        type="checkbox"
                        checked={adminUser.is_active}
                        onChange={(event) => {
                          void updateAdminUser(adminUser.id, { is_active: event.target.checked });
                        }}
                      />
                      active
                    </label>
                  </div>
                </div>
              </div>
            ))}
            {adminUsers.length === 0 && (
              <div className="text-sm text-text-muted">No admin users found.</div>
            )}
          </div>
        )}
      </section>

      <section>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h1 className="text-xl text-accent">Accounts</h1>
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by email"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <button
              onClick={loadUsers}
              className="px-3 py-1 text-xs bg-surface-raised border border-text-ghost rounded text-text-secondary hover:text-text-primary"
            >
              Search
            </button>
          </div>
        </div>

        {loadingUsers ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <div className="space-y-2">
            {users.map((user) => (
              <div key={user.id} className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">{user.email}</div>
                    <div className="text-xs text-text-muted">
                      {user.display_name || 'No display name'} | Created {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                    </div>
                    <div className="text-xs mt-1">
                      <span className={user.tier === 'pro' ? 'text-accent' : 'text-text-muted'}>
                        Tier: {user.tier.toUpperCase()}
                      </span>
                      {user.has_active_subscription && (
                        <span className="text-green-400 ml-2">subscription active</span>
                      )}
                      {user.pro_override && (
                        <span className="text-yellow-300 ml-2">manual override</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => startEditOverride(user)}
                    className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
                  >
                    Manage Pro Override
                  </button>
                </div>

                {editingUserId === user.id && (
                  <div className="mt-3 bg-surface border border-text-ghost rounded p-3 space-y-2">
                    <label className="flex items-center gap-2 text-xs text-text-secondary">
                      <input
                        type="checkbox"
                        checked={overrideEnabled}
                        onChange={(event) => setOverrideEnabled(event.target.checked)}
                      />
                      Enable manual pro access
                    </label>
                    <input
                      value={overrideReason}
                      onChange={(event) => setOverrideReason(event.target.value)}
                      placeholder="Reason (optional)"
                      className="w-full bg-surface-raised border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                    />
                    <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
                      <label className="text-xs text-text-muted">Expires at (optional):</label>
                      <input
                        type="datetime-local"
                        value={overrideExpiresAt}
                        onChange={(event) => setOverrideExpiresAt(event.target.value)}
                        className="bg-surface-raised border border-text-ghost rounded px-2 py-1 text-xs text-text-primary"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => saveOverride(user.id)}
                        className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingUserId(null)}
                        className="text-xs px-3 py-1 text-text-muted hover:text-text-primary"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {users.length === 0 && (
              <div className="text-sm text-text-muted">No users found.</div>
            )}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-xl text-accent mb-4">Discount Codes</h2>
        <div className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              value={createCodeForm.code}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, code: event.target.value.toUpperCase() }))}
              placeholder="Code (e.g. TEST50)"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary uppercase"
              maxLength={32}
            />
            <select
              value={createCodeForm.discountType}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, discountType: event.target.value }))}
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            >
              <option value="percent">Percent Off</option>
              <option value="amount">Fixed Amount</option>
            </select>
            {createCodeForm.discountType === 'percent' ? (
              <input
                type="number"
                value={createCodeForm.percentOff}
                onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, percentOff: event.target.value }))}
                placeholder="Percent off"
                className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                min={1}
                max={100}
              />
            ) : (
              <input
                type="number"
                value={createCodeForm.amountOffCents}
                onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, amountOffCents: event.target.value }))}
                placeholder="Amount off (cents)"
                className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                min={1}
              />
            )}
            <input
              value={createCodeForm.currency}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, currency: event.target.value.toLowerCase() }))}
              placeholder="Currency (usd)"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary uppercase"
              maxLength={3}
              disabled={createCodeForm.discountType !== 'amount'}
            />
            <select
              value={createCodeForm.duration}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, duration: event.target.value }))}
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            >
              <option value="once">Once</option>
              <option value="forever">Forever</option>
              <option value="repeating">Repeating</option>
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              type="number"
              value={createCodeForm.durationInMonths}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, durationInMonths: event.target.value }))}
              placeholder="Duration months"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
              min={1}
              max={36}
              disabled={createCodeForm.duration !== 'repeating'}
            />
            <input
              type="number"
              value={createCodeForm.maxRedemptions}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, maxRedemptions: event.target.value }))}
              placeholder="Max redemptions"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
              min={1}
            />
            <input
              type="datetime-local"
              value={createCodeForm.startsAt}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, startsAt: event.target.value }))}
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <input
              type="datetime-local"
              value={createCodeForm.expiresAt}
              onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, expiresAt: event.target.value }))}
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
          </div>
          <input
            value={createCodeForm.description}
            onChange={(event) => setCreateCodeForm((prev) => ({ ...prev, description: event.target.value }))}
            placeholder="Description (optional)"
            className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
          />
          <button
            onClick={createDiscountCode}
            disabled={creatingCode}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {creatingCode ? 'Creating...' : 'Create Discount Code'}
          </button>
        </div>

        {loadingCodes ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs text-text-muted flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showInactiveCodes}
                  onChange={(event) => setShowInactiveCodes(event.target.checked)}
                />
                Show archived/disabled codes
              </label>
            </div>
            {visibleCodes.map((code) => (
              <div key={code.id} className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">
                      {code.code}
                      <span className="text-text-muted ml-2">
                        {discountLabel(code)}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted">
                      {code.description || 'No description'} | {code.duration}
                      {code.duration_in_months ? ` (${code.duration_in_months} months)` : ''}
                    </div>
                    <div className="text-xs mt-1">
                      {code.is_active ? (
                        <span className="text-green-400">active</span>
                      ) : (
                        <span className="text-red-400">disabled</span>
                      )}
                      {!code.is_usable_now && code.is_active && (
                        <span className="text-yellow-300 ml-2">outside active window</span>
                      )}
                      {code.expires_at && (
                        <span className="text-text-muted ml-2">
                          expires {new Date(code.expires_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleDiscountCode(code, !code.is_active)}
                      className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary"
                    >
                      {code.is_active ? 'Archive' : 'Restore'}
                    </button>
                    <button
                      onClick={() => setDeleteCodeId(code.id)}
                      className="text-xs px-3 py-1 bg-red-900/30 border border-red-700 rounded text-red-300 hover:bg-red-900/50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
            {visibleCodes.length === 0 && (
              <div className="text-sm text-text-muted">No discount codes yet.</div>
            )}
          </div>
        )}
      </section>
      <ConfirmDialog
        open={!!deleteCodeId}
        title="Delete Discount Code"
        message="This permanently deletes the local code entry. The Stripe promotion code will be deactivated first."
        onConfirm={deleteDiscountCode}
        onCancel={() => setDeleteCodeId(null)}
        confirmLabel="Delete"
        destructive
      />
    </div>
  );
}
