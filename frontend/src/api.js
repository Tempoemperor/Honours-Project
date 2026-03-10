// frontend/src/api.js
import axios from 'axios';

const API_URL = 'http://localhost:8000';

const client = axios.create({ baseURL: API_URL });

export function setToken(t) {
  client.defaults.headers.common['Authorization'] = `Bearer ${t}`;
}

export function clearToken() {
  delete client.defaults.headers.common['Authorization'];
}

export const api = {
  // Auth
  register:       (username, password)       => client.post('/auth/register', { username, password }),
  login:          (username, password)       => client.post('/auth/login',    { username, password }),
  logout:         ()                         => client.post('/auth/logout'),

  // User
  getMe:          ()                         => client.get('/user/me'),

  // Chains
  getChains:      ()                         => client.get('/chains'),
  getDiscoverable:()                         => client.get('/chains/discoverable'),
  switchChain:    (chain_id)                 => client.post('/chains/switch', { chain_id }),
  joinChain:      (chain_id)                 => client.post('/chains/join',   { chain_id }),
  setupInit:      (cfg)                      => client.post('/setup/init',    cfg),
  inviteMember:   (chain_id, target_address, permission_level) =>
                    client.post(`/chains/${chain_id}/invite`, { target_address, permission_level }),
  getMembers:     (chain_id)                 => client.get(`/chains/${chain_id}/members`),
  getInvites: () => client.get('/chains/invites'),

  // Chain info
  getChainInfo:   ()                         => client.get('/chain/info'),
  getChainConfig: ()                         => client.get('/chain/config'),
  getBlocks:      (limit = 10)              => client.get(`/chain/blocks?limit=${limit}`),
  getConsensusLog: (limit = 20) => client.get(`/chain/consensus-log?limit=${limit}`),
  getConsensusInfo: () => client.get('/chain/consensus-info'),

  // Transactions
  sendTransaction:(recipient, amount)        => client.post('/transaction/transfer', { recipient, amount }),

  // Permissions
  promoteUser:    (target, level)            => client.post('/permissions/promote', { target, level }),

  // Data / Secret Files
  storeData:      (data_id, content, security_level) =>
                    client.post('/data/store', { data_id, content, security_level }),
  readData:       (data_id)                  => client.get(`/data/access/${data_id}`),
  listAllData:    ()                         => client.get('/data/list'),
  listMyData:     ()                         => client.get('/data/mine'),

  // Mine
  mineBlock:      ()                         => client.post('/mine'),
};
