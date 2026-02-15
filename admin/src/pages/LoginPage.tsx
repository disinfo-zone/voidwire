import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { apiPost } from '../api/client';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totp, setTotp] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setAuthenticated } = useAuth();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await apiPost('/admin/auth/login', { email, password, totp_code: totp });
      setAuthenticated(true);
      navigate('/');
    } catch (e: any) {
      setError(e?.message || 'Invalid credentials');
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-void">
      <form onSubmit={handleSubmit} className="w-80 space-y-4">
        <h1 className="text-xs font-mono tracking-widest text-accent uppercase text-center mb-8">
          VOIDWIRE
        </h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <input
          type="text"
          placeholder="TOTP Code"
          value={totp}
          onChange={(e) => setTotp(e.target.value)}
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          className="w-full bg-surface-raised border border-text-ghost rounded px-3 py-2 text-sm text-accent hover:border-accent transition-colors"
        >
          Sign In
        </button>
      </form>
    </div>
  );
}
