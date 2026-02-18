// src/api.js
import axios from 'axios';

const API_URL = 'http://localhost:8000';

export const api = {
    // Get Chain Status
    getInfo: () => axios.get(`${API_URL}/chain/info`),
    
    // Get Recent Blocks
    getBlocks: () => axios.get(`${API_URL}/chain/blocks`),
    
    // Send Transaction
    sendTransaction: (sender, recipient, amount, privateKey) => 
        axios.post(`${API_URL}/transaction/transfer`, {
            sender, recipient, amount, private_key: privateKey
        }),
    
    // Promote User (Permission System)
    promoteUser: (sender, target, level, privateKey) =>
        axios.post(`${API_URL}/permissions/promote`, {
            sender, target, level, private_key: privateKey
        }),

    // Store Data (Intel)
    storeData: (sender, dataId, content, level, privateKey) =>
        axios.post(`${API_URL}/data/store`, {
            sender, data_id: dataId, content, security_level: level, private_key: privateKey
        }),

    // Force Mine (Demo Only)
    mineBlock: () => axios.post(`${API_URL}/mine`)
};