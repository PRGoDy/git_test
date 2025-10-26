import { useQuery } from '@tanstack/react-query';
import { getAuditLogs } from '../api/client';

const Audit = () => {
  const { data: logs = [] } = useQuery({ queryKey: ['audit'], queryFn: getAuditLogs });

  return (
    <div className="card">
      <h2>Audit Log</h2>
      <p>Immutable ledger of authentication, approvals, and credential vending events.</p>
      <table className="table">
        <thead>
          <tr>
            <th>Action</th>
            <th>Target</th>
            <th>User</th>
            <th>Metadata</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log: any) => (
            <tr key={log.id}>
              <td>{log.action}</td>
              <td>{log.target}</td>
              <td>{log.user_id}</td>
              <td><code>{JSON.stringify(log.metadata)}</code></td>
              <td>{new Date(log.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Audit;
