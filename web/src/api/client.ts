import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true
});

export interface Role {
  arn: string;
  name: string;
  account: { id: string; name: string };
  sensitivity_tag: string;
  default_duration_seconds: number;
  tags: Record<string, string>;
}

export const getMe = async () => {
  const { data } = await api.get('/me');
  return data;
};

export const getRoles = async () => {
  const { data } = await api.get('/catalog/roles');
  return data as Role[];
};

export const submitRequest = async (payload: { role_arns: string[]; justification: string; duration_seconds: number; break_glass: boolean; }) => {
  const { data } = await api.post('/requests', payload);
  return data;
};

export const getAuditLogs = async () => {
  const { data } = await api.get('/audit');
  return data;
};

export const startConsole = async (roleArn: string, duration: number) => {
  const { data } = await api.post('/console', { role_arn: roleArn, duration_seconds: duration });
  return data;
};

export const logout = async () => {
  await api.post('/auth/logout');
};

export const deviceActivate = async (userCode: string) => {
  await api.post('/auth/device/activate', { user_code: userCode });
};

export const devicePoll = async (deviceCode: string) => {
  const { data } = await api.post('/auth/device/poll', { device_code: deviceCode });
  return data;
};

export const deviceStart = async () => {
  const { data } = await api.post('/auth/device/start');
  return data;
};
