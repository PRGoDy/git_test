import { FormEvent, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRoles, submitRequest } from '../api/client';

const RequestWizard = () => {
  const { data: roles = [] } = useQuery({ queryKey: ['roles'], queryFn: getRoles });
  const [selected, setSelected] = useState<string[]>([]);
  const [justification, setJustification] = useState('');
  const [duration, setDuration] = useState(3600);
  const [breakGlass, setBreakGlass] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const toggleRole = (arn: string) => {
    setSelected(prev => prev.includes(arn) ? prev.filter(item => item !== arn) : [...prev, arn]);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await submitRequest({ role_arns: selected, justification, duration_seconds: duration, break_glass: breakGlass });
    setStatus('Request submitted for approval.');
    setSelected([]);
    setJustification('');
  };

  return (
    <div className="card">
      <h2>Request Access</h2>
      <form onSubmit={submit} className="grid">
        <div>
          <label>Select roles</label>
          <div style={{ maxHeight: '200px', overflow: 'auto', border: '1px solid rgba(148,163,184,0.2)', borderRadius: '8px' }}>
            {roles.map(role => (
              <div key={role.arn} style={{ padding: '0.5rem', display: 'flex', justifyContent: 'space-between' }}>
                <label>
                  <input type="checkbox" checked={selected.includes(role.arn)} onChange={() => toggleRole(role.arn)} />
                  <span style={{ marginLeft: '0.5rem' }}>{role.name}</span>
                </label>
                <span className="badge">{role.sensitivity_tag}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <label>Justification</label>
          <textarea value={justification} required minLength={10} onChange={event => setJustification(event.target.value)} />
        </div>
        <div>
          <label>Duration (seconds)</label>
          <input type="number" min={900} max={43200} value={duration} onChange={event => setDuration(Number(event.target.value))} />
        </div>
        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input type="checkbox" checked={breakGlass} onChange={event => setBreakGlass(event.target.checked)} />
          Break glass (requires justification keyword)
        </label>
        <button type="submit" disabled={!selected.length}>Submit</button>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
};

export default RequestWizard;
