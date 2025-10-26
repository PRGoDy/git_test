import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRoles, Role } from '../api/client';

const filterRoles = (roles: Role[], query: string) => {
  if (!query) return roles;
  const lower = query.toLowerCase();
  return roles.filter(role => role.name.toLowerCase().includes(lower) || role.arn.toLowerCase().includes(lower));
};

const Catalog = () => {
  const { data: roles = [] } = useQuery({ queryKey: ['roles'], queryFn: getRoles });
  const [query, setQuery] = useState('');
  const filtered = filterRoles(roles, query);

  return (
    <div className="card">
      <h2>Account &amp; Role Catalog</h2>
      <p>Discover AWS accounts and IAM roles with tagging for environment and owner teams.</p>
      <input placeholder="Search roles" value={query} onChange={event => setQuery(event.target.value)} />
      <table className="table" style={{ marginTop: '1rem' }}>
        <thead>
          <tr>
            <th>Role</th>
            <th>Account</th>
            <th>Sensitivity</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(role => (
            <tr key={role.arn}>
              <td>{role.name}</td>
              <td>{role.account.name}</td>
              <td><span className="badge">{role.sensitivity_tag}</span></td>
              <td>
                {Object.entries(role.tags || {}).map(([k, v]) => (
                  <span key={k} className="badge" style={{ marginRight: '0.5rem' }}>{k}:{v}</span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Catalog;
