<script lang="ts">
  import { authFetch } from '../utils/auth';
  import { onMount } from 'svelte';

  let tier = 'free';
  let subscription: any = null;
  let prices: any[] = [];
  let discountCode = '';
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      const [subRes, priceRes] = await Promise.all([
        authFetch('/v1/user/subscription/'),
        fetch('/v1/user/subscription/prices'),
      ]);

      if (subRes.ok) {
        const data = await subRes.json();
        tier = data.tier;
        subscription = data.subscription;
      }

      if (priceRes.ok) {
        const data = await priceRes.json();
        prices = data.prices || [];
      }
    } catch {
      error = 'Failed to load subscription info';
    }
    loading = false;
  });

  async function handleUpgrade(priceId: string) {
    try {
      const currentUrl = window.location.origin;
      const normalizedDiscountCode = discountCode.trim().toUpperCase();
      const res = await authFetch('/v1/user/subscription/checkout', {
        method: 'POST',
        body: JSON.stringify({
          price_id: priceId,
          success_url: `${currentUrl}/dashboard?upgraded=true`,
          cancel_url: `${currentUrl}/dashboard`,
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
    }
  }

  async function handleManageBilling() {
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
    }
  }

  function formatPrice(amount: number, currency: string): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount / 100);
  }

  function handleDiscountInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement | null;
    discountCode = input?.value ?? '';
  }
</script>

<div class="subscription-manager">
  {#if loading}
    <p class="loading">Loading...</p>
  {:else}
    <div class="current-plan">
      <span class="plan-label">Current Plan</span>
      <span class="plan-tier">{tier === 'pro' ? 'Pro' : 'Free'}</span>
    </div>

    {#if subscription}
      <div class="subscription-details">
        <div class="detail-row">
          <span class="detail-label">Status</span>
          <span class="detail-value">{subscription.status}</span>
        </div>
        {#if subscription.billing_interval}
          <div class="detail-row">
            <span class="detail-label">Billing</span>
            <span class="detail-value">{subscription.billing_interval === 'month' ? 'Monthly' : 'Yearly'}</span>
          </div>
        {/if}
        {#if subscription.current_period_end}
          <div class="detail-row">
            <span class="detail-label">Renews</span>
            <span class="detail-value">{new Date(subscription.current_period_end).toLocaleDateString()}</span>
          </div>
        {/if}
        {#if subscription.cancel_at_period_end}
          <div class="cancel-notice">Cancels at end of period</div>
        {/if}
        <button class="manage-button" on:click={handleManageBilling}>Manage Billing</button>
      </div>
    {:else if prices.length > 0 && tier !== 'pro'}
      <div class="upgrade-section">
        <p class="upgrade-text">Upgrade to Pro for daily personalized readings with deeper analysis.</p>
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
            <button class="price-button" on:click={() => handleUpgrade(price.id)}>
              {formatPrice(price.unit_amount, price.currency)} / {price.interval}
            </button>
          {/each}
        </div>
      </div>
    {:else if tier === 'pro'}
      <div class="upgrade-section">
        <p class="upgrade-text">Pro access is active on this account.</p>
      </div>
    {/if}

    {#if error}
      <div class="error">{error}</div>
    {/if}
  {/if}
</div>

<style>
  .subscription-manager {
    border: 1px solid var(--text-ghost);
    padding: 1.5rem;
    background: rgba(255, 255, 255, 0.02);
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
    margin-bottom: 1rem;
  }

  .plan-label {
    font-family: var(--font-sans);
    font-size: 0.6rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .plan-tier {
    font-family: var(--font-sans);
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 500;
  }

  .subscription-details {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    font-family: var(--font-sans);
    font-size: 0.75rem;
  }

  .detail-label {
    color: var(--text-muted);
  }

  .detail-value {
    color: var(--text-secondary);
  }

  .cancel-notice {
    font-family: var(--font-sans);
    font-size: 0.7rem;
    color: #c45;
    text-align: center;
    padding: 0.5rem;
  }

  .manage-button {
    background: transparent;
    border: 1px solid var(--text-ghost);
    color: var(--text-secondary);
    padding: 0.6rem;
    font-family: var(--font-sans);
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    cursor: pointer;
    margin-top: 0.5rem;
    transition: all 0.3s ease;
  }

  .manage-button:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .upgrade-section {
    margin-top: 0.5rem;
  }

  .upgrade-text {
    font-family: var(--font-sans);
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 1rem;
    line-height: 1.5;
  }

  .price-options {
    display: flex;
    gap: 0.75rem;
    margin-top: 0.75rem;
  }

  .discount-input {
    width: 100%;
    background: transparent;
    border: 1px solid var(--text-ghost);
    color: var(--text-secondary);
    padding: 0.6rem 0.7rem;
    font-family: var(--font-sans);
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .discount-input:focus {
    outline: none;
    border-color: var(--accent);
    color: var(--accent);
  }

  .price-button {
    flex: 1;
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 0.75rem;
    font-family: var(--font-sans);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.3s ease;
  }

  .price-button:hover {
    background: var(--accent-glow);
  }

  .error {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    color: #c45;
    text-align: center;
    margin-top: 1rem;
  }
</style>
