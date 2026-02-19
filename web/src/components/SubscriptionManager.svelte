<script lang="ts">
  import { authFetch } from '../utils/auth';
  import { onMount } from 'svelte';

  type PriceOption = {
    id: string;
    unit_amount: number;
    currency: string;
    interval: string | null;
    product?: string | null;
    nickname?: string | null;
  };

  type SubscriptionDetails = {
    status: string;
    billing_interval: string | null;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  } | null;

  let tier = 'free';
  let subscription: SubscriptionDetails = null;
  let prices: PriceOption[] = [];
  let billingEnabled = false;
  let discountCode = '';
  let loading = true;
  let pendingAction = false;
  let error = '';
  let success = '';

  onMount(async () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('upgraded') === 'true') {
      success = 'Pro is now active on your account.';
      params.delete('upgraded');
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}${window.location.hash}`;
      window.history.replaceState({}, '', nextUrl);
    }
    await loadData();
  });

  async function loadData(): Promise<void> {
    loading = true;
    error = '';
    try {
      const [subRes, priceRes] = await Promise.all([
        authFetch('/v1/user/subscription/'),
        fetch('/v1/user/subscription/prices'),
      ]);

      if (subRes.ok) {
        const data = await subRes.json();
        tier = data.tier || 'free';
        subscription = data.subscription || null;
      }

      if (priceRes.ok) {
        const data = await priceRes.json();
        billingEnabled = data.enabled !== false;
        prices = ((data.prices || []) as PriceOption[]).sort((a, b) => sortPrices(a, b));
      } else {
        billingEnabled = false;
        prices = [];
      }
    } catch {
      error = 'Failed to load billing details';
      billingEnabled = false;
      prices = [];
    } finally {
      loading = false;
    }
  }

  function sortPrices(a: PriceOption, b: PriceOption): number {
    const rank = (interval: string | null): number => {
      if (interval === 'month') return 1;
      if (interval === 'year') return 2;
      return 3;
    };
    const intervalOrder = rank(a.interval) - rank(b.interval);
    if (intervalOrder !== 0) return intervalOrder;
    return (a.unit_amount || 0) - (b.unit_amount || 0);
  }

  function formatPrice(amount: number, currency: string): string {
    if (!Number.isFinite(amount)) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: String(currency || 'USD').toUpperCase(),
    }).format(amount / 100);
  }

  function formatInterval(interval: string | null): string {
    if (interval === 'month') return 'Monthly';
    if (interval === 'year') return 'Yearly';
    return 'Recurring';
  }

  function planName(price: PriceOption): string {
    const nickname = String(price.nickname || '').trim();
    if (nickname) return nickname;
    const product = String(price.product || '').trim();
    if (product) return product;
    return formatInterval(price.interval);
  }

  async function handleUpgrade(priceId: string) {
    pendingAction = true;
    error = '';
    try {
      const origin = window.location.origin;
      const normalizedDiscountCode = discountCode.trim().toUpperCase();
      const res = await authFetch('/v1/user/subscription/checkout', {
        method: 'POST',
        body: JSON.stringify({
          price_id: priceId,
          success_url: `${origin}/dashboard?upgraded=true`,
          cancel_url: `${origin}/dashboard`,
          discount_code: normalizedDiscountCode || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create checkout');
      }

      const data = await res.json();
      window.location.href = data.checkout_url;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to start checkout';
      pendingAction = false;
    }
  }

  async function handleManageBilling() {
    pendingAction = true;
    error = '';
    try {
      const res = await authFetch('/v1/user/subscription/portal', {
        method: 'POST',
        body: JSON.stringify({
          return_url: window.location.href,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to open portal');
      }

      const data = await res.json();
      window.location.href = data.portal_url;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to open billing portal';
      pendingAction = false;
    }
  }

  function handleDiscountInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement | null;
    discountCode = input?.value ?? '';
  }
</script>

<div class="subscription-manager">
  {#if loading}
    <p class="loading">Loading billing details...</p>
  {:else}
    <div class="current-plan">
      <span class="plan-label">Current Plan</span>
      <span class="plan-tier {tier === 'pro' ? 'pro' : ''}">{tier === 'pro' ? 'Pro' : 'Free'}</span>
    </div>

    {#if success}
      <div class="status success">{success}</div>
    {/if}

    {#if subscription}
      <div class="subscription-details">
        <div class="detail-row">
          <span class="detail-label">Status</span>
          <span class="detail-value">{subscription.status}</span>
        </div>
        {#if subscription.billing_interval}
          <div class="detail-row">
            <span class="detail-label">Billing</span>
            <span class="detail-value">{formatInterval(subscription.billing_interval)}</span>
          </div>
        {/if}
        {#if subscription.current_period_end}
          <div class="detail-row">
            <span class="detail-label">Renews</span>
            <span class="detail-value">{new Date(subscription.current_period_end).toLocaleDateString()}</span>
          </div>
        {/if}
        {#if subscription.cancel_at_period_end}
          <div class="status warning">Plan will cancel at period end.</div>
        {/if}
        <button class="manage-button" on:click={handleManageBilling} disabled={pendingAction}>
          {pendingAction ? 'Opening...' : 'Manage Billing'}
        </button>
      </div>
    {:else if tier === 'pro'}
      <div class="status success">Pro access is active on this account.</div>
    {:else if billingEnabled && prices.length > 0}
      <div class="upgrade-section">
        <p class="upgrade-title">Upgrade to Pro</p>
        <p class="upgrade-text">
          Daily personalized readings, deeper transit analysis, and priority generation.
        </p>
        <div class="value-points">
          <span>Daily pro reading</span>
          <span>Expanded interpretation</span>
          <span>Priority processing</span>
        </div>
        <input
          class="discount-input"
          placeholder="Discount code (optional)"
          value={discountCode}
          on:input={handleDiscountInput}
          maxlength="32"
          autocapitalize="characters"
          autocomplete="off"
        />
        <div class="price-options">
          {#each prices as price}
            <button class="price-card" on:click={() => handleUpgrade(price.id)} disabled={pendingAction}>
              <span class="price-name">{planName(price)}</span>
              <span class="price-amount">{formatPrice(price.unit_amount, price.currency)}</span>
              <span class="price-interval">{formatInterval(price.interval)}</span>
            </button>
          {/each}
        </div>
      </div>
    {:else}
      <div class="status muted">
        Pro subscriptions are not currently open. Check back soon.
      </div>
    {/if}

    {#if error}
      <div class="status error">{error}</div>
    {/if}
  {/if}
</div>

<style>
  .subscription-manager {
    border: 1px solid var(--text-ghost);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015));
    padding: 1rem;
  }

  .loading {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    color: var(--text-muted);
    text-align: center;
  }

  .current-plan {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.9rem;
  }

  .plan-label {
    font-family: var(--font-sans);
    font-size: 0.58rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .plan-tier {
    font-family: var(--font-sans);
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 600;
  }

  .plan-tier.pro {
    color: var(--accent);
  }

  .subscription-details {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: var(--font-sans);
    font-size: 0.73rem;
  }

  .detail-label {
    color: var(--text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-size: 0.6rem;
  }

  .detail-value {
    color: var(--text-secondary);
  }

  .manage-button {
    margin-top: 0.3rem;
    background: transparent;
    border: 1px solid var(--text-ghost);
    color: var(--text-secondary);
    padding: 0.65rem;
    font-family: var(--font-sans);
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    cursor: pointer;
    transition: border-color 0.25s ease, color 0.25s ease, background 0.25s ease;
  }

  .manage-button:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-glow);
  }

  .manage-button:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .upgrade-section {
    border: 1px solid rgba(214, 175, 114, 0.3);
    background: linear-gradient(160deg, rgba(214, 175, 114, 0.11), rgba(255, 255, 255, 0.02));
    border-radius: 0.4rem;
    padding: 0.9rem;
  }

  .upgrade-title {
    margin: 0;
    font-family: var(--font-body);
    font-size: 1.05rem;
    color: var(--text-primary);
  }

  .upgrade-text {
    margin: 0.35rem 0 0.65rem;
    font-family: var(--font-sans);
    font-size: 0.74rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .value-points {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.7rem;
  }

  .value-points span {
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    padding: 0.24rem 0.52rem;
    font-family: var(--font-sans);
    font-size: 0.59rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .discount-input {
    width: 100%;
    box-sizing: border-box;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--text-ghost);
    color: var(--text-secondary);
    border-radius: 0.35rem;
    padding: 0.62rem 0.72rem;
    font-family: var(--font-sans);
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .discount-input:focus {
    outline: none;
    border-color: var(--accent);
    color: var(--accent);
  }

  .price-options {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.6rem;
    margin-top: 0.75rem;
  }

  .price-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.2rem;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(214, 175, 114, 0.5);
    border-radius: 0.35rem;
    color: var(--text-primary);
    padding: 0.75rem 0.7rem;
    cursor: pointer;
    transition: transform 0.2s ease, border-color 0.25s ease, background 0.25s ease;
  }

  .price-card:hover:not(:disabled) {
    transform: translateY(-1px);
    border-color: var(--accent);
    background: rgba(214, 175, 114, 0.12);
  }

  .price-card:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .price-name {
    font-family: var(--font-sans);
    font-size: 0.58rem;
    color: var(--text-muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .price-amount {
    font-family: var(--font-body);
    font-size: 1.02rem;
    color: var(--accent);
  }

  .price-interval {
    font-family: var(--font-sans);
    font-size: 0.64rem;
    color: var(--text-secondary);
  }

  .status {
    margin-top: 0.7rem;
    border-radius: 0.3rem;
    padding: 0.55rem 0.65rem;
    font-family: var(--font-sans);
    font-size: 0.68rem;
    line-height: 1.4;
  }

  .status.success {
    border: 1px solid rgba(80, 168, 104, 0.4);
    background: rgba(80, 168, 104, 0.1);
    color: #9bd9ad;
  }

  .status.warning {
    border: 1px solid rgba(214, 175, 114, 0.4);
    background: rgba(214, 175, 114, 0.1);
    color: #e7c98f;
  }

  .status.error {
    border: 1px solid rgba(204, 68, 68, 0.45);
    background: rgba(204, 68, 68, 0.08);
    color: #db8080;
  }

  .status.muted {
    border: 1px solid var(--text-ghost);
    background: rgba(255, 255, 255, 0.015);
    color: var(--text-muted);
  }
</style>
