<script lang="ts">
  import { onDestroy } from 'svelte';
  import { authFetch } from '../utils/auth';

  export let onSave: (() => void) | undefined = undefined;

  let birthDate = '';
  let birthTime = '';
  let birthTimeKnown = false;
  let birthCity = '';
  let birthLatitude = 0;
  let birthLongitude = 0;
  let birthTimezone = '';
  let houseSystem = 'placidus';

  let locationResults: any[] = [];
  let locationQuery = '';
  let locationSearchTimer: number | undefined;
  let locationSearchAbort: AbortController | null = null;
  let searching = false;
  let saving = false;
  let error = '';
  let success = '';

  function searchLocation() {
    const query = locationQuery.trim();
    if (query.length < 3) {
      locationResults = [];
      searching = false;
      if (locationSearchTimer) {
        window.clearTimeout(locationSearchTimer);
        locationSearchTimer = undefined;
      }
      if (locationSearchAbort) {
        locationSearchAbort.abort();
        locationSearchAbort = null;
      }
      return;
    }

    if (locationSearchTimer) {
      window.clearTimeout(locationSearchTimer);
    }
    locationSearchTimer = window.setTimeout(() => {
      void runLocationSearch(query);
    }, 250);
  }

  async function runLocationSearch(query: string) {
    if (locationSearchAbort) {
      locationSearchAbort.abort();
    }
    locationSearchAbort = new AbortController();
    searching = true;
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`,
        {
          headers: { 'Accept': 'application/json' },
          signal: locationSearchAbort.signal,
        }
      );
      if (!res.ok) {
        locationResults = [];
        return;
      }
      locationResults = await res.json();
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      locationResults = [];
    } finally {
      searching = false;
      locationSearchAbort = null;
    }
  }

  function selectLocation(result: any) {
    birthCity = result.display_name.split(',').slice(0, 2).join(',').trim();
    birthLatitude = parseFloat(result.lat);
    birthLongitude = parseFloat(result.lon);

    birthTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    locationQuery = birthCity;
    locationResults = [];
  }

  async function handleSubmit() {
    error = '';
    success = '';
    saving = true;

    try {
      const res = await authFetch('/v1/user/profile/birth-data', {
        method: 'PUT',
        body: JSON.stringify({
          birth_date: birthDate,
          birth_time: birthTimeKnown ? birthTime : null,
          birth_time_known: birthTimeKnown,
          birth_city: birthCity.trim(),
          birth_latitude: birthLatitude,
          birth_longitude: birthLongitude,
          birth_timezone: birthTimezone.trim(),
          house_system: houseSystem,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save');
      }

      success = 'Birth data saved and natal chart computed.';
      if (onSave) onSave();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save';
    }
    saving = false;
  }

  onDestroy(() => {
    if (locationSearchTimer) {
      window.clearTimeout(locationSearchTimer);
    }
    if (locationSearchAbort) {
      locationSearchAbort.abort();
    }
  });
</script>

<form class="birth-form" on:submit|preventDefault={handleSubmit}>
  <div class="form-group">
    <label for="birth-date">Birth Date</label>
    <input type="date" id="birth-date" bind:value={birthDate} required />
  </div>

  <div class="form-group">
    <label class="checkbox-label">
      <input type="checkbox" bind:checked={birthTimeKnown} />
      <span>I know my birth time</span>
    </label>
  </div>

  {#if birthTimeKnown}
    <div class="form-group">
      <label for="birth-time">Birth Time</label>
      <input type="time" id="birth-time" bind:value={birthTime} required />
    </div>
  {/if}

  <div class="form-group">
    <label for="location">Birth Location</label>
    <input
      type="text"
      id="location"
      bind:value={locationQuery}
      on:input={searchLocation}
      placeholder="Search city..."
      autocomplete="off"
    />
    {#if searching}
      <span class="search-hint">Searching...</span>
    {/if}
    {#if locationResults.length > 0}
      <ul class="location-results">
        {#each locationResults as result}
          <li>
            <button type="button" on:click={() => selectLocation(result)}>
              {result.display_name}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  {#if birthCity}
    <div class="resolved-location">
      <span class="location-label">Selected:</span> {birthCity}
      <br />
      <span class="location-coords">{birthLatitude.toFixed(4)}, {birthLongitude.toFixed(4)}</span>
      {#if birthTimezone}
        <br /><span class="location-tz">Timezone: {birthTimezone}</span>
      {/if}
    </div>
  {/if}

  <div class="form-group">
    <label for="timezone-override">Timezone (IANA)</label>
    <input type="text" id="timezone-override" bind:value={birthTimezone} placeholder="e.g. America/New_York" required />
  </div>

  <div class="form-group">
    <label for="house-system">House System</label>
    <select id="house-system" bind:value={houseSystem}>
      <option value="placidus">Placidus</option>
      <option value="whole_sign">Whole Sign</option>
      <option value="koch">Koch</option>
      <option value="equal">Equal</option>
      <option value="porphyry">Porphyry</option>
    </select>
  </div>

  {#if error}
    <div class="error">{error}</div>
  {/if}
  {#if success}
    <div class="success">{success}</div>
  {/if}

  <button type="submit" class="save-button" disabled={saving || !birthDate || !birthCity}>
    {saving ? 'Saving...' : 'Save Birth Data'}
  </button>
</form>

<style>
  .birth-form {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .form-group label {
    font-family: var(--font-sans);
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .form-group input,
  .form-group select {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--text-ghost);
    color: var(--text-primary);
    padding: 0.65rem 0.75rem;
    font-family: var(--font-sans);
    font-size: 0.8rem;
    border-radius: 2px;
  }

  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-size: 0.8rem !important;
    color: var(--text-secondary) !important;
  }

  .checkbox-label input[type="checkbox"] {
    width: auto;
    padding: 0;
  }

  .search-hint {
    font-family: var(--font-sans);
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .location-results {
    list-style: none;
    border: 1px solid var(--text-ghost);
    max-height: 200px;
    overflow-y: auto;
  }

  .location-results li button {
    width: 100%;
    text-align: left;
    background: var(--surface);
    border: none;
    border-bottom: 1px solid var(--text-ghost);
    color: var(--text-secondary);
    padding: 0.5rem 0.75rem;
    font-family: var(--font-sans);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .location-results li button:hover {
    background: var(--accent-glow);
    color: var(--text-primary);
  }

  .resolved-location {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    color: var(--text-secondary);
    padding: 0.75rem;
    border: 1px solid var(--text-ghost);
    background: rgba(255, 255, 255, 0.02);
  }

  .location-label {
    color: var(--accent);
  }

  .location-coords,
  .location-tz {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    color: var(--text-muted);
  }

  .error {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    color: #c45;
    text-align: center;
  }

  .success {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    color: var(--accent);
    text-align: center;
  }

  .save-button {
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 0.75rem;
    font-family: var(--font-sans);
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.3s ease;
  }

  .save-button:hover:not(:disabled) {
    background: var(--accent-glow);
  }

  .save-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
