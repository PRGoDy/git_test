import { Route, Routes, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Catalog from './pages/Catalog';
import RequestWizard from './pages/RequestWizard';
import MyAccess from './pages/MyAccess';
import Audit from './pages/Audit';
import DeviceApproval from './pages/DeviceApproval';
import Layout from './components/Layout';

const App = () => {
  return (
    <Routes>
      <Route path="/device" element={<DeviceApproval />} />
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="catalog" element={<Catalog />} />
        <Route path="request" element={<RequestWizard />} />
        <Route path="access" element={<MyAccess />} />
        <Route path="audit" element={<Audit />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
