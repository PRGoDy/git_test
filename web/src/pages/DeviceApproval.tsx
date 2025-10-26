import { FormEvent, useEffect, useState } from 'react';
import { deviceActivate } from '../api/client';

const DeviceApproval = () => {
  const [userCode, setUserCode] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('user_code');
    if (code) {
      setUserCode(code.toUpperCase());
    }
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await deviceActivate(userCode.trim());
    setMessage('Device approved. Return to the CLI to finish login.');
  };

  return (
    <div className="card" style={{ maxWidth: '480px', margin: '4rem auto' }}>
      <h2>Approve CLI Login</h2>
      <p>Confirm the device code displayed in your CLI session after completing SSO.</p>
      <form onSubmit={handleSubmit} className="grid">
        <label>
          User code
          <input value={userCode} onChange={event => setUserCode(event.target.value.toUpperCase())} required />
        </label>
        <button type="submit">Approve</button>
      </form>
      {message && <p>{message}</p>}
    </div>
  );
};

export default DeviceApproval;
