// src/App.js
import React, { useState, useEffect } from 'react';
import { api } from './api';
import './App.css';

function App() {
  const [chainInfo, setChainInfo] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Input States
  const [formData, setFormData] = useState({
    sender: '', recipient: '', amount: 0, privateKey: '',
    target: '', level: 1, dataId: '', content: ''
  });

  // Fetch Data Loop
  const fetchData = async () => {
    try {
      const infoRes = await api.getInfo();
      const blocksRes = await api.getBlocks();
      setChainInfo(infoRes.data);
      setBlocks(blocksRes.data.reverse()); // Show newest first
    } catch (err) {
      console.error("API Error:", err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // Refresh every 3s
    return () => clearInterval(interval);
  }, []);

  const handleMine = async () => {
    setLoading(true);
    try {
      await api.mineBlock();
      await fetchData();
      alert("Block Mined Successfully!");
    } catch (err) {
      alert("Mining Failed: " + err.message);
    }
    setLoading(false);
  };

  const handleSubmit = async (type) => {
    setLoading(true);
    try {
      if (type === 'transfer') {
        await api.sendTransaction(formData.sender, formData.recipient, parseFloat(formData.amount), formData.privateKey);
      } else if (type === 'promote') {
        await api.promoteUser(formData.sender, formData.target, parseInt(formData.level), formData.privateKey);
      } else if (type === 'store') {
        await api.storeData(formData.sender, formData.dataId, formData.content, parseInt(formData.level), formData.privateKey);
      }
      alert("Transaction Submitted!");
    } catch (err) {
      alert("Error: " + (err.response?.data?.detail || err.message));
    }
    setLoading(false);
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>🛡️ Military Blockchain Console</h1>
        <div className="status-badge">
          Status: <span className={chainInfo ? "online" : "offline"}>
            {chainInfo ? "ONLINE" : "CONNECTING..."}
          </span>
        </div>
      </header>

      <div className="main-layout">
        {/* Sidebar */}
        <nav className="sidebar">
          <button onClick={() => setActiveTab('dashboard')} className={activeTab === 'dashboard' ? 'active' : ''}>📊 Dashboard</button>
          <button onClick={() => setActiveTab('transfer')} className={activeTab === 'transfer' ? 'active' : ''}>💸 Transfer Funds</button>
          <button onClick={() => setActiveTab('permissions')} className={activeTab === 'permissions' ? 'active' : ''}>👮 Permissions</button>
          <button onClick={() => setActiveTab('intel')} className={activeTab === 'intel' ? 'active' : ''}>📁 Classified Intel</button>
          <div className="mine-section">
            <button className="mine-btn" onClick={handleMine} disabled={loading}>
              {loading ? "Mining..." : "⛏️ Mine Block"}
            </button>
          </div>
        </nav>

        {/* Content Area */}
        <main className="content">
          {activeTab === 'dashboard' && chainInfo && (
            <div className="dashboard-grid">
              <div className="card">
                <h3>Chain ID</h3>
                <p>{chainInfo.chain_id}</p>
              </div>
              <div className="card">
                <h3>Height</h3>
                <p>{chainInfo.height}</p>
              </div>
              <div className="card">
                <h3>Consensus</h3>
                <p>{chainInfo.consensus}</p>
              </div>
              <div className="card">
                <h3>Pending Txs</h3>
                <p>{chainInfo.pending_transactions}</p>
              </div>
              
              <div className="blocks-list">
                <h3>Recent Blocks</h3>
                {blocks.map(block => (
                  <div key={block.hash} className="block-item">
                    <div className="block-header">
                      <span className="block-height">#{block.height}</span>
                      <span className="block-hash">{block.hash.substring(0, 16)}...</span>
                      <span className="block-txs">{block.transactions.length} Txs</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'transfer' && (
            <div className="form-card">
              <h2>Send Crypto</h2>
              <input placeholder="Sender Address" onChange={e => setFormData({...formData, sender: e.target.value})} />
              <input placeholder="Private Key" type="password" onChange={e => setFormData({...formData, privateKey: e.target.value})} />
              <input placeholder="Recipient Address" onChange={e => setFormData({...formData, recipient: e.target.value})} />
              <input placeholder="Amount" type="number" onChange={e => setFormData({...formData, amount: e.target.value})} />
              <button onClick={() => handleSubmit('transfer')}>Sign & Send</button>
            </div>
          )}

          {activeTab === 'permissions' && (
            <div className="form-card">
              <h2>Promote Officer</h2>
              <input placeholder="Admin Address" onChange={e => setFormData({...formData, sender: e.target.value})} />
              <input placeholder="Admin Private Key" type="password" onChange={e => setFormData({...formData, privateKey: e.target.value})} />
              <input placeholder="Target Officer Address" onChange={e => setFormData({...formData, target: e.target.value})} />
              <select onChange={e => setFormData({...formData, level: e.target.value})}>
                <option value="1">Level 1 - Unclassified</option>
                <option value="2">Level 2 - Restricted</option>
                <option value="3">Level 3 - Confidential</option>
                <option value="4">Level 4 - Secret</option>
                <option value="5">Level 5 - Top Secret</option>
              </select>
              <button onClick={() => handleSubmit('promote')}>Promote User</button>
            </div>
          )}

           {activeTab === 'intel' && (
            <div className="form-card">
              <h2>Store Classified Intel</h2>
              <input placeholder="Officer Address" onChange={e => setFormData({...formData, sender: e.target.value})} />
              <input placeholder="Private Key" type="password" onChange={e => setFormData({...formData, privateKey: e.target.value})} />
              <input placeholder="Intel ID (e.g., 'mission-report')" onChange={e => setFormData({...formData, dataId: e.target.value})} />
              <textarea placeholder="Content..." onChange={e => setFormData({...formData, content: e.target.value})} />
              <select onChange={e => setFormData({...formData, level: e.target.value})}>
                <option value="5">Level 5 - Top Secret</option>
                <option value="3">Level 3 - Confidential</option>
                <option value="1">Level 1 - Public</option>
              </select>
              <button onClick={() => handleSubmit('store')}>Encrypt & Store</button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;