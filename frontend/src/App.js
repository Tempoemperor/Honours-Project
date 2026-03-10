// src/App.js
import React, { useState, useEffect } from 'react';
import { api } from './api';
import './App.css';

// ─── Setup Wizard ─────────────────────────────────────────────────────────────
function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [adminKeys, setAdminKeys] = useState(null);
  const [config, setConfig] = useState({
    chain_id: '',
    consensus: 'poa',
    permission_levels: 3,
    level_names: ['Unclassified', 'Restricted', 'Confidential'],
  });

  const CONSENSUS_OPTIONS = [
    { value: 'poa',        label: 'Proof of Authority',   desc: 'Fast, trusted validators. Best for private networks.' },
    { value: 'pos',        label: 'Proof of Stake',        desc: 'Validators stake tokens. Energy efficient.' },
    { value: 'pbft',       label: 'PBFT',                  desc: 'Byzantine fault tolerant. Best for small validator sets.' },
    { value: 'round_robin',label: 'Round Robin',           desc: 'Simple rotating validator. Good for demos.' },
  ];

  const handleLevelNameChange = (i, value) => {
    const updated = [...config.level_names];
    updated[i] = value;
    setConfig({ ...config, level_names: updated });
  };

  const handleLevelCountChange = (count) => {
    const n = parseInt(count);
    const defaults = ['Unclassified', 'Restricted', 'Confidential', 'Secret', 'Top Secret'];
    const names = Array.from({ length: n }, (_, i) => config.level_names[i] || defaults[i] || `Level ${i + 1}`);
    setConfig({ ...config, permission_levels: n, level_names: names });
  };

  const handleCreate = async () => {
    if (!config.chain_id.trim()) { setError('Chain ID is required.'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await api.setupInit(config);
      setAdminKeys({ address: res.data.admin_address, privateKey: res.data.admin_private_key });
      setStep(3);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  // Step 3 — show keys, must acknowledge before proceeding
  if (step === 3 && adminKeys) {
    return (
      <div className="setup-overlay">
        <div className="setup-card">
          <div className="setup-icon">🔑</div>
          <h2>Save Your Admin Keys</h2>
          <p className="setup-warning">⚠️ This is the only time your private key will be shown. Save it now.</p>
          <div className="key-box">
            <label>Admin Address</label>
            <code>{adminKeys.address}</code>
          </div>
          <div className="key-box">
            <label>Private Key</label>
            <code>{adminKeys.privateKey}</code>
          </div>
          <button className="btn-primary" onClick={() => onComplete()}>
            I've saved my keys → Enter Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Step 2 — permission levels
  if (step === 2) {
    return (
      <div className="setup-overlay">
        <div className="setup-card">
          <div className="setup-step">Step 2 of 2</div>
          <h2>Permission Levels</h2>
          <p>Define the classification tiers for your blockchain data.</p>

          <label>Number of Levels</label>
          <select value={config.permission_levels} onChange={e => handleLevelCountChange(e.target.value)}>
            {[2,3,4,5].map(n => <option key={n} value={n}>{n} levels</option>)}
          </select>

          <div className="level-names">
            {config.level_names.map((name, i) => (
              <div key={i} className="level-row">
                <span className="level-badge">L{i}</span>
                <input
                  value={name}
                  onChange={e => handleLevelNameChange(i, e.target.value)}
                  placeholder={`Level ${i} name`}
                />
              </div>
            ))}
          </div>

          {error && <div className="setup-error">{error}</div>}
          <div className="setup-nav">
            <button className="btn-secondary" onClick={() => setStep(1)}>← Back</button>
            <button className="btn-primary" onClick={handleCreate} disabled={loading}>
              {loading ? 'Creating…' : 'Create Blockchain →'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 1 — chain ID + consensus
  return (
    <div className="setup-overlay">
      <div className="setup-card">
        <div className="setup-icon">⛓️</div>
        <div className="setup-step">Step 1 of 2</div>
        <h2>Create Your Blockchain</h2>
        <p>Configure the core properties of your new chain.</p>

        <label>Chain ID</label>
        <input
          value={config.chain_id}
          onChange={e => setConfig({ ...config, chain_id: e.target.value })}
          placeholder="e.g. my-org-chain"
        />

        <label>Consensus Mechanism</label>
        <div className="consensus-grid">
          {CONSENSUS_OPTIONS.map(opt => (
            <div
              key={opt.value}
              className={`consensus-card ${config.consensus === opt.value ? 'selected' : ''}`}
              onClick={() => setConfig({ ...config, consensus: opt.value })}
            >
              <strong>{opt.label}</strong>
              <span>{opt.desc}</span>
            </div>
          ))}
        </div>

        {error && <div className="setup-error">{error}</div>}
        <button className="btn-primary" onClick={() => {
          if (!config.chain_id.trim()) { setError('Chain ID is required.'); return; }
          setError('');
          setStep(2);
        }}>
          Next →
        </button>
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
function App() {
  const [chainInfo, setChainInfo]   = useState(null);
  const [blocks, setBlocks]         = useState([]);
  const [loading, setLoading]       = useState(false);
  const [activeTab, setActiveTab]   = useState('dashboard');
  const [needsSetup, setNeedsSetup] = useState(false);
  const [formData, setFormData]     = useState({
    sender: '', recipient: '', amount: 0, privateKey: '',
    target: '', level: 1, dataId: '', content: ''
  });

  const fetchData = async () => {
    try {
      const infoRes   = await api.getInfo();
      const blocksRes = await api.getBlocks();
      setChainInfo(infoRes.data);
      setBlocks(blocksRes.data.reverse());
      setNeedsSetup(false);
    } catch (err) {
      if (err.response?.status === 503) setNeedsSetup(true);
      else console.error('API Error:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleMine = async () => {
    setLoading(true);
    try {
      await api.mineBlock();
      await fetchData();
      alert('Block Mined Successfully!');
    } catch (err) {
      alert('Mining Failed: ' + err.message);
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
      alert('Transaction Submitted!');
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    }
    setLoading(false);
  };

  // Show setup wizard if no chain exists
  if (needsSetup) {
    return <SetupWizard onComplete={() => { setNeedsSetup(false); fetchData(); }} />;
  }

  if (!chainInfo) {
    return <div className="loading-screen">⛓️ Connecting to blockchain node…</div>;
  }

  return (
    <div className="App">
      <header className="app-header">
        <h1>⛓️ {chainInfo.chain_id}</h1>
        <nav>
          {['dashboard', 'transactions', 'permissions', 'data'].map(tab => (
            <button
              key={tab}
              className={activeTab === tab ? 'active' : ''}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {activeTab === 'dashboard' && (
          <div className="dashboard">
            <div className="stats-grid">
              <div className="stat-card"><h3>Chain ID</h3><p>{chainInfo.chain_id}</p></div>
              <div className="stat-card"><h3>Height</h3><p>{chainInfo.height}</p></div>
              <div className="stat-card"><h3>Consensus</h3><p>{chainInfo.consensus}</p></div>
              <div className="stat-card"><h3>Pending Txs</h3><p>{chainInfo.pending_transactions}</p></div>
            </div>
            <button className="btn-primary mine-btn" onClick={handleMine} disabled={loading}>
              {loading ? 'Mining…' : '⛏️ Mine Block'}
            </button>
            <h2>Recent Blocks</h2>
            <div className="blocks-list">
              {blocks.map(b => (
                <div key={b.height} className="block-card">
                  <span>Block #{b.height}</span>
                  <span>{b.tx_count} txs</span>
                  <span className="hash">{b.hash?.slice(0, 16)}…</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="form-section">
            <h2>Send Transfer</h2>
            <input placeholder="Sender Address"    value={formData.sender}     onChange={e => setFormData({...formData, sender: e.target.value})} />
            <input placeholder="Private Key"       value={formData.privateKey} onChange={e => setFormData({...formData, privateKey: e.target.value})} type="password" />
            <input placeholder="Recipient Address" value={formData.recipient}  onChange={e => setFormData({...formData, recipient: e.target.value})} />
            <input placeholder="Amount"            value={formData.amount}     onChange={e => setFormData({...formData, amount: e.target.value})} type="number" />
            <button className="btn-primary" onClick={() => handleSubmit('transfer')} disabled={loading}>Send</button>
          </div>
        )}

        {activeTab === 'permissions' && (
          <div className="form-section">
            <h2>Promote User</h2>
            <input placeholder="Your Address (Admin)"  value={formData.sender}     onChange={e => setFormData({...formData, sender: e.target.value})} />
            <input placeholder="Private Key"           value={formData.privateKey} onChange={e => setFormData({...formData, privateKey: e.target.value})} type="password" />
            <input placeholder="Target Address"        value={formData.target}     onChange={e => setFormData({...formData, target: e.target.value})} />
            <input placeholder="Permission Level (0-4)"value={formData.level}      onChange={e => setFormData({...formData, level: e.target.value})} type="number" />
            <button className="btn-primary" onClick={() => handleSubmit('promote')} disabled={loading}>Promote</button>
          </div>
        )}

        {activeTab === 'data' && (
          <div className="form-section">
            <h2>Store Classified Data</h2>
            <input placeholder="Your Address"      value={formData.sender}     onChange={e => setFormData({...formData, sender: e.target.value})} />
            <input placeholder="Private Key"       value={formData.privateKey} onChange={e => setFormData({...formData, privateKey: e.target.value})} type="password" />
            <input placeholder="Data ID"           value={formData.dataId}     onChange={e => setFormData({...formData, dataId: e.target.value})} />
            <textarea placeholder="Content"        value={formData.content}    onChange={e => setFormData({...formData, content: e.target.value})} />
            <input placeholder="Classification Level" value={formData.level}   onChange={e => setFormData({...formData, level: e.target.value})} type="number" />
            <button className="btn-primary" onClick={() => handleSubmit('store')} disabled={loading}>Store</button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
