import { useEffect, useState } from 'react';
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

type StripeConfig = {
  enabled: boolean;
  publishable_key: string;
  secret_key_masked?: string;
  webhook_secret_masked?: string;
  is_configured?: boolean;
  webhook_is_configured?: boolean;
};

type StripeCheckResult = {
  status: 'ok' | 'warning' | 'error';
  message: string;
  enabled: boolean;
  account_id?: string;
  api_mode?: string;
  secret_key_mode?: string | null;
  publishable_key_mode?: string | null;
  key_mode_match: boolean;
  webhook_ready: boolean;
  active_price_count: number;
  sample_prices: Array<{
    id: string | null;
    unit_amount: number | null;
    currency: string | null;
    interval: string | null;
    product?: string | null;
    nickname?: string | null;
  }>;
  warnings: string[];
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

type BillingSnapshot = {
  activeOrTrialing: number;
  trialing: number;
  pastDue: number;
  canceled: number;
  checkoutSuccess24h: number;
  checkoutFailure24h: number;
  checkoutFailureRate24h: number;
  webhookLagMinutes: number | null;
};

const EMPTY_STRIPE: StripeConfig = {
  enabled: false,
  publishable_key: '',
  secret_key_masked: '',
  webhook_secret_masked: '',
  is_configured: false,
  webhook_is_configured: false,
};

const EMPTY_BILLING_SNAPSHOT: BillingSnapshot = {
  activeOrTrialing: 0,
  trialing: 0,
  pastDue: 0,
  canceled: 0,
  checkoutSuccess24h: 0,
  checkoutFailure24h: 0,
  checkoutFailureRate24h: 0,
  webhookLagMinutes: null,
};

function fromInputDateTime(value: string): string | null {
  if (!value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

function formatPrice(amount: number | null, currency: string | null): string {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) return '-';
  const code = (currency || 'USD').toUpperCase();
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: code }).format(amount / 100);
  } catch {
    return `${amount / 100} ${code}`;
  }
}

function formatDiscountLabel(code: DiscountCode): string {
  if (code.percent_off != null) {
    return `${code.percent_off}% off`;
  }
  if (code.amount_off_cents != null && code.currency) {
    return `${(code.amount_off_cents / 100).toFixed(2)} ${code.currency.toUpperCase()} off`;
  }
  return 'discount';
}

export default function BillingPage() {
  const [stripe, setStripe] = useState<StripeConfig>(EMPTY_STRIPE);
  const [stripeSecretKey, setStripeSecretKey] = useState('');
  const [stripeWebhookSecret, setStripeWebhookSecret] = useState('');
  const [savingStripe, setSavingStripe] = useState(false);
  const [testingStripe, setTestingStripe] = useState(false);
  const [stripeCheckResult, setStripeCheckResult] = useState<StripeCheckResult | null>(null);
  const [discountCodes, setDiscountCodes] = useState<DiscountCode[]>([]);
  const [loadingDiscountCodes, setLoadingDiscountCodes] = useState(true);
  const [showInactiveCodes, setShowInactiveCodes] = useState(true);
  const [deleteCodeId, setDeleteCodeId] = useState<string | null>(null);
  const [reconcilingBilling, setReconcilingBilling] = useState(false);
  const [loadingBillingSnapshot, setLoadingBillingSnapshot] = useState(true);
  const [billingSnapshot, setBillingSnapshot] = useState<BillingSnapshot>(EMPTY_BILLING_SNAPSHOT);
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
  const [loadingStripe, setLoadingStripe] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    void Promise.all([loadStripeConfig(), loadDiscountCodes(), loadBillingSnapshot()]);
  }, []);

  async function loadStripeConfig() {
    setLoadingStripe(true);
    try {
      const data = await apiGet('/admin/site/billing/stripe');
      setStripe({ ...EMPTY_STRIPE, ...(data || {}) });
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingStripe(false);
    }
  }

  async function loadDiscountCodes() {
    setLoadingDiscountCodes(true);
    try {
      const data = await apiGet('/admin/accounts/discount-codes');
      setDiscountCodes(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingDiscountCodes(false);
    }
  }

  async function loadBillingSnapshot() {
    setLoadingBillingSnapshot(true);
    try {
      const [kpis, operational] = await Promise.all([
        apiGet('/admin/analytics/kpis'),
        apiGet('/admin/analytics/operational-health'),
      ]);
      setBillingSnapshot({
        activeOrTrialing: Number(kpis?.subscriptions?.active_or_trialing || 0),
        trialing: Number(kpis?.subscriptions?.trialing || 0),
        pastDue: Number(kpis?.subscriptions?.past_due || 0),
        canceled: Number(kpis?.subscriptions?.canceled || 0),
        checkoutSuccess24h: Number(operational?.slo?.checkout_failure_rate_10pct_24h?.success_count || 0),
        checkoutFailure24h: Number(operational?.slo?.checkout_failure_rate_10pct_24h?.failure_count || 0),
        checkoutFailureRate24h: Number(
          operational?.slo?.checkout_failure_rate_10pct_24h?.failure_rate_percent || 0,
        ),
        webhookLagMinutes:
          typeof operational?.slo?.webhook_freshness_30m?.lag_minutes === 'number'
            ? Number(operational.slo.webhook_freshness_30m.lag_minutes)
            : null,
      });
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingBillingSnapshot(false);
    }
  }

  async function saveStripe() {
    setSavingStripe(true);
    try {
      const payload: any = {
        enabled: stripe.enabled,
        publishable_key: stripe.publishable_key || '',
      };
      if (stripeSecretKey.trim().length > 0) {
        payload.secret_key = stripeSecretKey.trim();
      }
      if (stripeWebhookSecret.trim().length > 0) {
        payload.webhook_secret = stripeWebhookSecret.trim();
      }
      const updated = await apiPut('/admin/site/billing/stripe', payload);
      setStripe({ ...EMPTY_STRIPE, ...(updated || {}) });
      setStripeSecretKey('');
      setStripeWebhookSecret('');
      toast.success('Stripe settings saved');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingStripe(false);
    }
  }

  async function runStripeCheck() {
    setTestingStripe(true);
    setStripeCheckResult(null);
    try {
      const result = await apiPost('/admin/site/billing/stripe/test', {});
      setStripeCheckResult(result as StripeCheckResult);
      if (result?.status === 'ok') {
        toast.success('Stripe check passed');
      } else if (result?.status === 'warning') {
        toast.info('Stripe check completed with warnings');
      } else {
        toast.error(result?.message || 'Stripe check failed');
      }
      await loadBillingSnapshot();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setTestingStripe(false);
    }
  }

  async function reconcileBilling() {
    setReconcilingBilling(true);
    try {
      const data = await apiPost('/admin/accounts/billing/reconcile');
      const updated = typeof data?.updated === 'number' ? data.updated : 0;
      const scanned = typeof data?.scanned === 'number' ? data.scanned : 0;
      toast.success(`Billing reconciliation complete (${updated}/${scanned} updated)`);
      await loadBillingSnapshot();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setReconcilingBilling(false);
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

  async function createDiscountCode() {
    const payload: Record<string, unknown> = {
      code: createCodeForm.code,
      duration: createCodeForm.duration,
      duration_in_months:
        createCodeForm.duration === 'repeating' && createCodeForm.durationInMonths
          ? Number(createCodeForm.durationInMonths)
          : null,
      max_redemptions: createCodeForm.maxRedemptions ? Number(createCodeForm.maxRedemptions) : null,
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

  const loading = loadingStripe || loadingDiscountCodes || loadingBillingSnapshot;

  if (loading) {
    return (
      <div>
        <h1 className="text-xl text-accent mb-6">Billing</h1>
        <div className="flex justify-center py-12"><Spinner /></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl text-accent">Billing</h1>
        <div className="text-xs text-text-muted mt-1">
          Stripe credentials, pricing visibility, discount codes, and billing health in one place.
        </div>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs uppercase tracking-wider text-text-muted mb-1">Subscriptions</div>
          <div className="text-sm text-text-primary">
            {billingSnapshot.activeOrTrialing} active/trialing
          </div>
          <div className="text-xs text-text-muted mt-1">
            {billingSnapshot.trialing} trialing · {billingSnapshot.pastDue} past due · {billingSnapshot.canceled} canceled
          </div>
        </div>
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs uppercase tracking-wider text-text-muted mb-1">Checkout Health (24h)</div>
          <div className="text-sm text-text-primary">
            {billingSnapshot.checkoutSuccess24h} success · {billingSnapshot.checkoutFailure24h} failed
          </div>
          <div className="text-xs text-text-muted mt-1">
            Failure rate {billingSnapshot.checkoutFailureRate24h.toFixed(2)}%
            {billingSnapshot.webhookLagMinutes != null ? ` · webhook lag ${billingSnapshot.webhookLagMinutes}m` : ''}
          </div>
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm text-text-primary">Stripe Credentials</h2>
          <button
            onClick={saveStripe}
            disabled={savingStripe}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {savingStripe ? 'Saving...' : 'Save Stripe Settings'}
          </button>
        </div>
        <div className="text-xs text-text-muted">
          Configure publishable/secret keys and webhook secret. Enable only when checkout is ready for users.
        </div>

        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input
            type="checkbox"
            checked={stripe.enabled}
            onChange={(e) => setStripe((prev) => ({ ...prev, enabled: e.target.checked }))}
          />
          Enable Stripe checkout and billing portal
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">Publishable Key</label>
            <input
              value={stripe.publishable_key}
              onChange={(e) => setStripe((prev) => ({ ...prev, publishable_key: e.target.value }))}
              placeholder="pk_live_..."
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Secret Key {stripe.secret_key_masked ? `(current: ${stripe.secret_key_masked})` : ''}
            </label>
            <input
              type="password"
              value={stripeSecretKey}
              onChange={(e) => setStripeSecretKey(e.target.value)}
              placeholder="leave blank to keep current"
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
          <div className="md:col-span-2">
            <label className="text-xs text-text-muted block mb-1">
              Webhook Secret {stripe.webhook_secret_masked ? `(current: ${stripe.webhook_secret_masked})` : ''}
            </label>
            <input
              type="password"
              value={stripeWebhookSecret}
              onChange={(e) => setStripeWebhookSecret(e.target.value)}
              placeholder="whsec_... (leave blank to keep current)"
              className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
            />
          </div>
        </div>

        <div className="text-xs text-text-muted">
          Status: {stripe.is_configured ? 'configured' : 'incomplete'} {stripe.enabled ? '(enabled)' : '(disabled)'}
          {' · '}Webhook: {stripe.webhook_is_configured ? 'configured' : 'missing'}
        </div>

        <div className="border-t border-text-ghost/40 pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs text-text-muted">Run live connectivity check (keys + account + prices + webhook readiness)</div>
            <button
              onClick={runStripeCheck}
              disabled={testingStripe}
              className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary disabled:opacity-50"
            >
              {testingStripe ? 'Checking...' : 'Run Stripe Check'}
            </button>
          </div>
          {stripeCheckResult && (
            <div className="border border-text-ghost rounded p-3 space-y-2 text-xs text-text-muted">
              <div className="text-text-primary">
                Check status: <span className="text-accent">{stripeCheckResult.status}</span> · {stripeCheckResult.message}
              </div>
              <div>
                Account: <span className="text-text-secondary">{stripeCheckResult.account_id || 'n/a'}</span>
                {' · '}API mode: <span className="text-text-secondary">{stripeCheckResult.api_mode || 'unknown'}</span>
                {' · '}Key mode match: <span className="text-text-secondary">{stripeCheckResult.key_mode_match ? 'yes' : 'no'}</span>
                {' · '}Webhook ready: <span className="text-text-secondary">{stripeCheckResult.webhook_ready ? 'yes' : 'no'}</span>
              </div>
              <div>
                Active recurring prices: <span className="text-text-secondary">{stripeCheckResult.active_price_count}</span>
              </div>
              {stripeCheckResult.warnings?.length > 0 && (
                <div className="space-y-1">
                  {stripeCheckResult.warnings.map((warning, idx) => (
                    <div key={`stripe-warning-${idx}`} className="text-amber-300">- {warning}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm text-text-primary">Pricing + Discount Codes</h2>
          <button
            onClick={reconcileBilling}
            disabled={reconcilingBilling}
            className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary disabled:opacity-50"
          >
            {reconcilingBilling ? 'Reconciling...' : 'Reconcile Billing'}
          </button>
        </div>
        <div className="text-xs text-text-muted">
          Active prices come from Stripe. Create and manage promo/discount codes here.
        </div>
        {stripeCheckResult?.sample_prices?.length ? (
          <div className="border border-text-ghost rounded p-3">
            <div className="text-xs text-text-muted mb-2">Sample active recurring prices</div>
            <div className="space-y-1">
              {stripeCheckResult.sample_prices.map((price, idx) => (
                <div key={`stripe-price-${price.id || idx}`} className="text-xs text-text-secondary">
                  {price.nickname || price.product || price.id || `price_${idx + 1}`} · {formatPrice(price.unit_amount, price.currency)}
                  {' / '}{price.interval || 'recurring'}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-xs text-text-muted">
            Run Stripe check to fetch current active price samples.
          </div>
        )}

        <div className="border border-text-ghost rounded p-4 space-y-3">
          <div className="text-xs text-text-muted">Create discount code</div>
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

        {loadingDiscountCodes ? (
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
              <div key={code.id} className="bg-surface border border-text-ghost rounded p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">
                      {code.code}
                      <span className="text-text-muted ml-2">
                        {formatDiscountLabel(code)}
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

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <h2 className="text-sm text-text-primary mb-2">Credits Ledger</h2>
          <div className="text-xs text-text-muted">
            Coming soon: credit balances, usage history, adjustments, and refill rules.
          </div>
        </div>
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <h2 className="text-sm text-text-primary mb-2">Billing Analytics</h2>
          <div className="text-xs text-text-muted">
            Coming soon: revenue trendlines, plan conversion funnels, churn/cohort drilldowns.
          </div>
        </div>
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
