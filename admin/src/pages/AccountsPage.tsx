import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiDelete, apiGet, apiPatch, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

type AccountUser = {
  id: string;
  email: string;
  display_name: string | null;
  email_verified: boolean;
  is_active: boolean;
  is_test_user: boolean;
  is_admin_user: boolean;
  tier: 'free' | 'pro';
  has_active_subscription: boolean;
  pro_override: boolean;
  pro_override_reason: string | null;
  pro_override_until: string | null;
  created_at: string | null;
  last_login_at: string | null;
};

type AdminUserAccount = {
  id: string;
  email: string;
  role: 'owner' | 'admin' | 'support' | 'readonly';
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

type ReadingJob = {
  id: string;
  user_id: string;
  user_email: string;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  payload: Record<string, any>;
  result: Record<string, any> | null;
  error_message: string | null;
  attempts: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
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
  const [readingJobs, setReadingJobs] = useState<ReadingJob[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(true);
  const [loadingReadingJobs, setLoadingReadingJobs] = useState(true);
  const [runningRetentionCleanup, setRunningRetentionCleanup] = useState(false);
  const [readingJobStatusFilter, setReadingJobStatusFilter] = useState<'all' | 'queued' | 'running' | 'completed' | 'failed'>('all');
  const [query, setQuery] = useState('');
  const [creatingUser, setCreatingUser] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [userForm, setUserForm] = useState({
    email: '',
    password: '',
    displayName: '',
    emailVerified: false,
    isActive: true,
    isTestUser: false,
    isAdminUser: false,
  });
  const [editUserForm, setEditUserForm] = useState({
    email: '',
    password: '',
    displayName: '',
    emailVerified: false,
    isActive: true,
    isTestUser: false,
    isAdminUser: false,
  });
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [overrideEnabled, setOverrideEnabled] = useState(true);
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideExpiresAt, setOverrideExpiresAt] = useState('');
  const { toast } = useToast();

  useEffect(() => {
    void Promise.all([loadUsers(), loadAdminUsers(), loadReadingJobs()]);
  }, []);

  useEffect(() => {
    void loadReadingJobs();
  }, [readingJobStatusFilter]);

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

  async function loadReadingJobs() {
    setLoadingReadingJobs(true);
    try {
      const params = new URLSearchParams();
      params.set('limit', '100');
      if (readingJobStatusFilter !== 'all') {
        params.set('status', readingJobStatusFilter);
      }
      const data = await apiGet(`/admin/accounts/reading-jobs?${params.toString()}`);
      setReadingJobs(Array.isArray(data) ? data : []);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoadingReadingJobs(false);
    }
  }

  function startEditUser(user: AccountUser) {
    setEditingAccountId(user.id);
    setEditUserForm({
      email: user.email,
      password: '',
      displayName: user.display_name || '',
      emailVerified: !!user.email_verified,
      isActive: !!user.is_active,
      isTestUser: !!user.is_test_user,
      isAdminUser: !!user.is_admin_user,
    });
  }

  async function createUser() {
    if (!userForm.email.trim()) {
      toast.error('Email is required');
      return;
    }
    if (userForm.password.trim().length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setCreatingUser(true);
    try {
      await apiPost('/admin/accounts/users', {
        email: userForm.email.trim(),
        password: userForm.password,
        display_name: userForm.displayName.trim() || null,
        email_verified: userForm.emailVerified,
        is_active: userForm.isActive,
        is_test_user: userForm.isTestUser,
        is_admin_user: userForm.isAdminUser,
      });
      toast.success('User created');
      setUserForm({
        email: '',
        password: '',
        displayName: '',
        emailVerified: false,
        isActive: true,
        isTestUser: false,
        isAdminUser: false,
      });
      await loadUsers();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setCreatingUser(false);
    }
  }

  async function saveUserEdit(userId: string) {
    try {
      const payload: Record<string, unknown> = {
        email: editUserForm.email.trim(),
        display_name: editUserForm.displayName.trim() || null,
        email_verified: editUserForm.emailVerified,
        is_active: editUserForm.isActive,
        is_test_user: editUserForm.isTestUser,
        is_admin_user: editUserForm.isAdminUser,
      };
      if (editUserForm.password.trim().length > 0) {
        if (editUserForm.password.trim().length < 8) {
          toast.error('Password must be at least 8 characters');
          return;
        }
        payload.password = editUserForm.password;
      }
      await apiPatch(`/admin/accounts/users/${userId}`, payload);
      toast.success('User updated');
      setEditingAccountId(null);
      await loadUsers();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function deleteUser() {
    if (!deleteUserId) return;
    try {
      await apiDelete(`/admin/accounts/users/${deleteUserId}`);
      toast.success('User deleted');
      await loadUsers();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setDeleteUserId(null);
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

  return (
    <div className="space-y-8">
      <section>
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-xl text-accent">Admin Access</h1>
          <div className="flex gap-2">
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

      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <h1 className="text-xl text-accent">Accounts</h1>
          <div className="flex gap-2">
            <Link
              to="/billing"
              className="px-3 py-1 text-xs bg-accent/20 text-accent rounded hover:bg-accent/30"
            >
              Open Billing
            </Link>
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

        <div className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
          <h3 className="text-sm text-text-primary">Create User</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              value={userForm.email}
              onChange={(event) => setUserForm((prev) => ({ ...prev, email: event.target.value }))}
              placeholder="Email"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <input
              value={userForm.password}
              onChange={(event) => setUserForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder="Temporary password"
              type="password"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <input
              value={userForm.displayName}
              onChange={(event) => setUserForm((prev) => ({ ...prev, displayName: event.target.value }))}
              placeholder="Display name (optional)"
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <div className="flex items-center gap-4 text-xs text-text-muted">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={userForm.emailVerified}
                  onChange={(event) =>
                    setUserForm((prev) => ({ ...prev, emailVerified: event.target.checked }))
                  }
                />
                email verified
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={userForm.isActive}
                  onChange={(event) =>
                    setUserForm((prev) => ({ ...prev, isActive: event.target.checked }))
                  }
                />
                active
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={userForm.isTestUser}
                  onChange={(event) =>
                    setUserForm((prev) => ({ ...prev, isTestUser: event.target.checked }))
                  }
                />
                test user
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={userForm.isAdminUser}
                  onChange={(event) =>
                    setUserForm((prev) => ({ ...prev, isAdminUser: event.target.checked }))
                  }
                />
                admin user
              </label>
            </div>
          </div>
          <button
            onClick={createUser}
            disabled={creatingUser}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {creatingUser ? 'Creating...' : 'Create User'}
          </button>
        </div>

        {loadingUsers ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <div className="space-y-2">
            {users.map((user) => (
              <div key={user.id} className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">{user.email}</div>
                    <div className="text-xs text-text-muted">
                      {user.display_name || 'No display name'} | Created{' '}
                      {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                    </div>
                    <div className="text-xs mt-1 flex flex-wrap gap-2">
                      <span className={user.tier === 'pro' ? 'text-accent' : 'text-text-muted'}>
                        Tier: {user.tier.toUpperCase()}
                      </span>
                      <span className={user.email_verified ? 'text-green-400' : 'text-yellow-300'}>
                        {user.email_verified ? 'email verified' : 'email unverified'}
                      </span>
                      <span className={user.is_active ? 'text-green-400' : 'text-red-400'}>
                        {user.is_active ? 'active' : 'disabled'}
                      </span>
                      {user.has_active_subscription && (
                        <span className="text-green-400">subscription active</span>
                      )}
                      {user.pro_override && (
                        <span className="text-yellow-300">manual override</span>
                      )}
                      {user.is_test_user && (
                        <span className="text-sky-300">test user</span>
                      )}
                      {user.is_admin_user && (
                        <span className="text-fuchsia-300">admin user</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => startEditUser(user)}
                      className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:text-text-primary"
                    >
                      Edit User
                    </button>
                    <button
                      onClick={() => startEditOverride(user)}
                      className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
                    >
                      Pro Override
                    </button>
                    <button
                      onClick={() => setDeleteUserId(user.id)}
                      className="text-xs px-3 py-1 bg-red-900/30 border border-red-700 rounded text-red-300 hover:bg-red-900/50"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {editingAccountId === user.id && (
                  <div className="mt-3 bg-surface border border-text-ghost rounded p-3 space-y-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <input
                        value={editUserForm.email}
                        onChange={(event) =>
                          setEditUserForm((prev) => ({ ...prev, email: event.target.value }))
                        }
                        placeholder="Email"
                        className="bg-surface-raised border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                      />
                      <input
                        value={editUserForm.password}
                        onChange={(event) =>
                          setEditUserForm((prev) => ({ ...prev, password: event.target.value }))
                        }
                        placeholder="New password (optional)"
                        type="password"
                        className="bg-surface-raised border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                      />
                      <input
                        value={editUserForm.displayName}
                        onChange={(event) =>
                          setEditUserForm((prev) => ({ ...prev, displayName: event.target.value }))
                        }
                        placeholder="Display name"
                        className="bg-surface-raised border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
                      />
                      <div className="flex items-center gap-4 text-xs text-text-muted">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editUserForm.emailVerified}
                            onChange={(event) =>
                              setEditUserForm((prev) => ({
                                ...prev,
                                emailVerified: event.target.checked,
                              }))
                            }
                          />
                          email verified
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editUserForm.isActive}
                            onChange={(event) =>
                              setEditUserForm((prev) => ({ ...prev, isActive: event.target.checked }))
                            }
                          />
                          active
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editUserForm.isTestUser}
                            onChange={(event) =>
                              setEditUserForm((prev) => ({
                                ...prev,
                                isTestUser: event.target.checked,
                              }))
                            }
                          />
                          test user
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editUserForm.isAdminUser}
                            onChange={(event) =>
                              setEditUserForm((prev) => ({
                                ...prev,
                                isAdminUser: event.target.checked,
                              }))
                            }
                          />
                          admin user
                        </label>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => saveUserEdit(user.id)}
                        className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
                      >
                        Save User
                      </button>
                      <button
                        onClick={() => setEditingAccountId(null)}
                        className="text-xs px-3 py-1 text-text-muted hover:text-text-primary"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

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
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h2 className="text-xl text-accent">Personal Reading Jobs</h2>
          <div className="flex items-center gap-2">
            <select
              value={readingJobStatusFilter}
              onChange={(event) =>
                setReadingJobStatusFilter(
                  event.target.value as 'all' | 'queued' | 'running' | 'completed' | 'failed',
                )
              }
              className="bg-surface border border-text-ghost rounded px-3 py-1 text-xs text-text-primary"
            >
              <option value="all">all statuses</option>
              <option value="queued">queued</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
            </select>
            <button
              onClick={loadReadingJobs}
              className="px-3 py-1 text-xs bg-surface-raised border border-text-ghost rounded text-text-secondary hover:text-text-primary"
            >
              Refresh
            </button>
          </div>
        </div>
        {loadingReadingJobs ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <div className="space-y-2">
            {readingJobs.map((job) => (
              <div key={job.id} className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                  <div>
                    <div className="text-sm text-text-primary">{job.user_email}</div>
                    <div className="text-xs text-text-muted">
                      {job.payload?.tier || 'unknown'} tier | created{' '}
                      {job.created_at ? new Date(job.created_at).toLocaleString() : '-'}
                    </div>
                    <div className="text-xs mt-1">
                      <span className={job.status === 'failed' ? 'text-red-300' : 'text-text-secondary'}>
                        {job.status}
                      </span>
                      {job.error_message && (
                        <span className="text-red-300 ml-2">{job.error_message}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-text-muted">
                    Attempts: {job.attempts}
                    {job.finished_at && (
                      <span className="ml-2">
                        finished {new Date(job.finished_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {readingJobs.length === 0 && (
              <div className="text-sm text-text-muted">No personal reading jobs found.</div>
            )}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={!!deleteUserId}
        title="Delete User"
        message="This permanently deletes the user account, profile, subscriptions, and personal readings."
        onConfirm={deleteUser}
        onCancel={() => setDeleteUserId(null)}
        confirmLabel="Delete User"
        destructive
      />
    </div>
  );
}
