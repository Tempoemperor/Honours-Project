import axios from 'axios';

async function getBackendUrl() {
    if (window.electron) {
        const port = await window.electron.getBackendPort();
        return `http://127.0.0.1:${port}`;
    }
    const params = new URLSearchParams(window.location.search);
    const port = params.get('backendPort') || '8000';
    return `http://127.0.0.1:${port}`;
}

let API_URL = null;

async function client() {
    if (!API_URL) {
        API_URL = await getBackendUrl();
    }
    return axios.create({ baseURL: API_URL });
}

export const api = {
    
    getInfo:      async () => (await client()).get('/chain/info'),
    getBlocks:    async () => (await client()).get('/chain/blocks'),
    getUserLevel: async (address) => (await client()).get(`/permissions/user/${address}`),

    getChainConfig: () => axios.get(`${API_URL}/chain/config`),
    setupInit: (config) => axios.post(`${API_URL}/setup/init`, config),

    sendTransaction: async (sender, recipient, amount, privateKey) =>
        (await client()).post('/transaction/transfer', {
            sender, recipient, amount, private_key: privateKey,
        }),

    promoteUser: async (sender, target, level, privateKey) =>
        (await client()).post('/permissions/promote', {
            sender, target, level, private_key: privateKey,
        }),

    storeData: async (sender, dataId, content, level, privateKey) =>
        (await client()).post('/data/store', {
            sender, data_id: dataId, content, security_level: level, private_key: privateKey,
        }),

    accessData: async (userAddress, dataId) =>
        (await client()).get(`/data/access/${dataId}`, {
            params: { user_address: userAddress },
        }),

    mineBlock: async () => (await client()).post('/mine'),

    getAdminInfo: async () => (await client()).get('/admin/info')
    
};
