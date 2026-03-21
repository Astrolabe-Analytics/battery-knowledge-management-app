import { useState } from 'react';
import { login as apiLogin } from '../services/api';
import styles from './Login.module.css';

export default function Login({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await apiLogin(password);
      localStorage.setItem('astrolabe_token', data.token);
      onLogin();
    } catch (err) {
      setError('Invalid password');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.loginPage}>
      <div className={styles.loginCard}>
        <div className={styles.logo}>
          <h1>Astrolabe</h1>
          <p>Research Paper Library</p>
        </div>
        <form className={styles.form} onSubmit={handleSubmit}>
          {error && <div className={styles.error}>{error}</div>}
          <div className={styles.inputGroup}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter company password"
              autoFocus
            />
          </div>
          <button className={styles.submitBtn} type="submit" disabled={loading || !password}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
