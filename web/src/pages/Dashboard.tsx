import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getRoles, startConsole } from '../api/client';

const Dashboard = () => {
  const { data: roles = [] } = useQuery({ queryKey: ['roles'], queryFn: getRoles });
  const primaryRole = roles[0];

  const openConsole = async () => {
    if (!primaryRole) return;
    const { redirect_url } = await startConsole(primaryRole.arn, primaryRole.default_duration_seconds);
    window.location.href = redirect_url;
  };

  return (
    <div className="grid grid-2">
      <div className="card">
        <h2>Request Access</h2>
        <p>Submit self-service access requests for IAM roles across connected AWS accounts.</p>
        <Link to="/request"><button>Start request</button></Link>
      </div>
      <div className="card">
        <h2>Open AWS Console</h2>
        <p>Launch the AWS Console with short-lived credentials for an approved role.</p>
        <button disabled={!primaryRole} onClick={openConsole}>Open console</button>
      </div>
      <div className="card">
        <h2>Use CLI</h2>
        <p>Download the Access Hub CLI and run <code>hub login</code> to fetch credentials.</p>
        <a href="https://example.com/cli" target="_blank" rel="noreferrer">Read CLI docs</a>
      </div>
      <div className="card">
        <h2>Recent Roles</h2>
        <ul>
          {roles.slice(0, 5).map(role => (
            <li key={role.arn}>
              <span style={{ fontWeight: 600 }}>{role.name}</span>
              <span className="badge" style={{ marginLeft: '0.5rem' }}>{role.sensitivity_tag}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default Dashboard;
