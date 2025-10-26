import { useQuery } from '@tanstack/react-query';
import { getAuditLogs } from '../api/client';

const MyAccess = () => {
  const { data: logs = [] } = useQuery({ queryKey: ['audit'], queryFn: getAuditLogs });
  const approvals = logs.filter((log: any) => log.action === 'request.decided' && log.metadata?.approved);

  return (
    <div className="card">
      <h2>My Access</h2>
      <p>View active approvals and session history.</p>
      <table className="table">
        <thead>
          <tr>
            <th>Request</th>
            <th>Approved</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {approvals.map((approval: any) => (
            <tr key={approval.id}>
              <td>{approval.target}</td>
              <td>{approval.metadata.approved ? 'Approved' : 'Denied'}</td>
              <td>{new Date(approval.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MyAccess;
