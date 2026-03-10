// frontend/src/App.js
import React, { useState, useEffect, useCallback } from 'react';
import { api, setToken, clearToken } from './api';
import './App.css';


// ── Auth Screen ───────────────────────────────────────────────────────────────
function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (loading) return; // prevent double-submission
    if (!username.trim() || !password.trim()) {
      setError('Username and password are required.'); return;
    }
    setLoading(true); setError('');
    try {
      if (mode === 'register') {
        await api.register(username, password);
        setMode('login');
        alert('Account created! Please login.');
      } else {
        const res = await api.login(username, password);
        setToken(res.data.token);
        onLogin({ username: res.data.username, address: res.data.address, token: res.data.token });
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  return (
    <div className="setup-overlay">
      <div className="setup-card" style={{ width: 400 }}>
        <div className="setup-icon">⛓️</div>
        <h2>{mode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
        <p>{mode === 'login' ? 'Login to access your blockchains' : 'Register to get started'}</p>
        <label>Username</label>
        <input value={username} onChange={e => setUsername(e.target.value)}
          placeholder="Enter username" onKeyDown={e => e.key === 'Enter' && handleSubmit()} />
        <label>Password</label>
        <input value={password} onChange={e => setPassword(e.target.value)}
          placeholder="Enter password" type="password"
          onKeyDown={e => e.key === 'Enter' && handleSubmit()} />
        {error && <div className="setup-error">{error}</div>}
        <button className="btn-primary" style={{ marginTop: '1.25rem' }}
          onClick={handleSubmit} disabled={loading}>
          {loading ? '...' : mode === 'login' ? 'Login' : 'Register'}
        </button>
        <p style={{ textAlign: 'center', marginTop: '1rem', marginBottom: 0 }}>
          <span style={{ color: '#64748b', fontSize: '0.88rem' }}>
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          </span>
          <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
            style={{
              background: 'none', border: 'none', color: '#6366f1',
              cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600, padding: 0
            }}>
            {mode === 'login' ? 'Register' : 'Login'}
          </button>
        </p>
      </div>
    </div>
  );
}


// ── Create Chain Wizard ───────────────────────────────────────────────────────
function CreateChainWizard({ onComplete, onCancel }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [config, setConfig] = useState({
    chain_id: '', consensus: 'poa', permission_levels: 3,
    level_names: ['Unclassified', 'Restricted', 'Confidential'],
    max_transactions_per_block: 100,
    allow_file_storage: false,
    open_membership: true,
  });

  const CONSENSUS = [
    { value: 'poa', label: 'Proof of Authority', desc: 'Trusted validators. Best for private networks.' },
    { value: 'pos', label: 'Proof of Stake', desc: 'Validators stake tokens. Energy efficient.' },
    { value: 'pbft', label: 'PBFT', desc: 'Byzantine fault tolerant.' },
    { value: 'round_robin', label: 'Round Robin', desc: 'Rotating validator. Good for demos.' },
    { value: 'tendermint', label: 'Tendermint', desc: 'BFT with instant finality.' },
    { value: 'raft', label: 'Raft', desc: 'Leader-based log replication.' },
  ];

  const handleLevelCount = (n) => {
    const defaults = ['Unclassified', 'Restricted', 'Confidential', 'Secret', 'Top Secret',
      'Level 5', 'Level 6', 'Level 7', 'Level 8', 'Level 9'];
    const names = Array.from({ length: parseInt(n) }, (_, i) => config.level_names[i] || defaults[i]);
    setConfig({ ...config, permission_levels: parseInt(n), level_names: names });
  };

  const handleCreate = async () => {
    setLoading(true); setError('');
    try {
      const res = await api.setupInit(config);
      onComplete(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  if (step === 1) return (
    <div className="create-chain-full">
      <div className="create-chain-card">
        <button className="back-btn" onClick={onCancel}>← Back</button>
        <div className="setup-icon">⛓️</div>
        <div className="setup-step">Step 1 of 2 — Chain Identity</div>
        <h2>Create New Blockchain</h2>
        <label>Chain Name / ID</label>
        <input value={config.chain_id}
          onChange={e => setConfig({ ...config, chain_id: e.target.value })}
          placeholder="e.g. my-org-chain" />
        <label>Consensus Mechanism</label>
        <div className="consensus-grid">
          {CONSENSUS.map(opt => (
            <div key={opt.value}
              className={`consensus-card ${config.consensus === opt.value ? 'selected' : ''}`}
              onClick={() => setConfig({ ...config, consensus: opt.value })}>
              <strong>{opt.label}</strong>
              <span>{opt.desc}</span>
            </div>
          ))}
        </div>
        <label>Membership</label>
        <div className="toggle-row">
          <div className={`toggle-option ${config.open_membership ? 'selected' : ''}`}
            onClick={() => setConfig({ ...config, open_membership: true })}>
            🌐 Open — Anyone can join
          </div>
          <div className={`toggle-option ${!config.open_membership ? 'selected' : ''}`}
            onClick={() => setConfig({ ...config, open_membership: false })}>
            🔒 Invite Only
          </div>
        </div>
        {error && <div className="setup-error">{error}</div>}
        <button className="btn-primary" style={{ marginTop: '1.5rem' }} onClick={() => {
          if (!config.chain_id.trim()) { setError('Chain name is required.'); return; }
          setError(''); setStep(2);
        }}>Next →</button>
      </div>
    </div>
  );

  return (
    <div className="create-chain-full">
      <div className="create-chain-card">
        <button className="back-btn" onClick={() => setStep(1)}>← Back</button>
        <div className="setup-step">Step 2 of 2 — Access & Limits</div>
        <h2>Configure Properties</h2>
        <label>Number of Permission Levels</label>
        <select value={config.permission_levels} onChange={e => handleLevelCount(e.target.value)}>
          {[2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => <option key={n} value={n}>{n} levels</option>)}
        </select>
        <label>Level Names</label>
        <div className="level-names">
          {config.level_names.map((name, i) => (
            <div key={i} className="level-row">
              <span className="level-badge">L{i + 1}</span>
              <input value={name} onChange={e => {
                const updated = [...config.level_names];
                updated[i] = e.target.value;
                setConfig({ ...config, level_names: updated });
              }} />
            </div>
          ))}
        </div>
        <label>Max Transactions per Block</label>
        <input type="number" value={config.max_transactions_per_block}
          onChange={e => setConfig({ ...config, max_transactions_per_block: parseInt(e.target.value) })}
          min={1} max={10000} />
        <label>File Storage</label>
        <div className="toggle-row">
          <div className={`toggle-option ${config.allow_file_storage ? 'selected' : ''}`}
            onClick={() => setConfig({ ...config, allow_file_storage: true })}>
            📁 Enabled
          </div>
          <div className={`toggle-option ${!config.allow_file_storage ? 'selected' : ''}`}
            onClick={() => setConfig({ ...config, allow_file_storage: false })}>
            🚫 Disabled
          </div>
        </div>
        {error && <div className="setup-error">{error}</div>}
        <div className="setup-nav" style={{ marginTop: '1.5rem' }}>
          <button className="btn-secondary" onClick={() => setStep(1)}>← Back</button>
          <button className="btn-primary" onClick={handleCreate} disabled={loading}>
            {loading ? 'Deploying…' : '🚀 Deploy Blockchain'}
          </button>
        </div>
      </div>
    </div>
  );
}


// ── Main Dashboard ────────────────────────────────────────────────────────────
function Dashboard({ user, onLogout }) {
  const [activePanel, setActivePanel] = useState('properties');
  const [chainInfo, setChainInfo] = useState(null);
  const [chainConfig, setChainConfig] = useState(null);
  const [myInfo, setMyInfo] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [chains, setChains] = useState([]);
  const [members, setMembers] = useState([]);
  const [discoverable, setDiscoverable] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateChain, setShowCreateChain] = useState(false);
  const [copied, setCopied] = useState(false);
  // FIX #1 & #2: consensusInfo state now lives in Dashboard where it's used
  const [consensusInfo, setConsensusInfo] = useState(null);
  const [formData, setFormData] = useState({
    recipient: '', amount: 0,
    target: '', level: 0,
    dataId: '', content: '', securityLevel: 1,
    inviteAddress: '',
    inviteLevel: 1, // FIX #7: initialise to 1, not 0
    myFiles: null, allFiles: null,
  });
  const [invites, setInvites] = useState([]);
  const [result, setResult] = useState(null);

  // FIX #1: loadConsensusInfo defined in Dashboard scope so fetchAll can call it
  const loadConsensusInfo = useCallback(async () => {
    try {
      const res = await api.getConsensusInfo();
      setConsensusInfo(res.data);
    } catch (err) { /* silent */ }
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [meRes, chainsRes] = await Promise.all([api.getMe(), api.getChains()]);
      setMyInfo(meRes.data);
      setChains(chainsRes.data.chains);
      if (chainsRes.data.active) {
        const [infoRes, configRes, blocksRes] = await Promise.all([
          api.getChainInfo(), api.getChainConfig(), api.getBlocks()
        ]);
        setChainInfo(infoRes.data);
        setChainConfig(configRes.data);
        // FIX #3: avoid mutating original array with reverse()
        setBlocks([...blocksRes.data].reverse());
      } else {
        setChainInfo(null); setChainConfig(null); setBlocks([]);
      }
      await loadConsensusInfo();
    } catch (err) {
      if (err.response?.status === 401) onLogout();
    }
  }, [onLogout, loadConsensusInfo]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 4000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // FIX #6: guard against switching to the already-active chain
  const handleSwitchChain = async (chain_id) => {
    if (chain_id === chainConfig?.chain_id) return;
    setResult(null);
    await api.switchChain(chain_id);
    await fetchAll();
  };

  const handleMine = async () => {
    setLoading(true);
    try {
      const res = await api.mineBlock();
      setResult(`✅ Block #${res.data.block_height} mined with ${res.data.tx_count} transactions`);
      await fetchAll();
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
    setLoading(false);
  };

  const handleTransfer = async () => {
    setLoading(true);
    try {
      const res = await api.sendTransaction(formData.recipient, parseFloat(formData.amount));
      setResult('✅ Submitted: ' + res.data.hash.slice(0, 20) + '...');
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
    setLoading(false);
  };

  const handlePromote = async () => {
    setLoading(true);
    try {
      await api.promoteUser(formData.target, parseInt(formData.level));
      setResult('✅ Promotion submitted');
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
    setLoading(false);
  };

  const handleStoreData = async () => {
    setLoading(true);
    try {
      const res = await api.storeData(formData.dataId, formData.content, formData.securityLevel);
      setResult(`✅ Stored! ID: ${res.data.unique_id}`);
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
    setLoading(false);
  };

  const handleInvite = async () => {
    if (!chainConfig) return;
    setLoading(true);
    try {
      await api.inviteMember(chainConfig.chain_id, formData.inviteAddress, parseInt(formData.inviteLevel));
      setResult('✅ Member invited');
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
    setLoading(false);
  };

  const handleJoinDiscoverable = async (chain_id) => {
    try {
      await api.joinChain(chain_id); await fetchAll();
      setResult(`✅ Joined chain: ${chain_id}`);
    } catch (err) { setResult('❌ ' + (err.response?.data?.detail || err.message)); }
  };

  const loadDiscoverable = async () => {
    const res = await api.getDiscoverable();
    setDiscoverable(res.data.chains);
  };

  const loadMembers = async () => {
    if (!chainConfig) return;
    const res = await api.getMembers(chainConfig.chain_id);
    setMembers(res.data.members);
  };

  if (showCreateChain) {
    return <CreateChainWizard
      onComplete={async () => { setShowCreateChain(false); await fetchAll(); }}
      onCancel={() => setShowCreateChain(false)} />;
  }

  const noChain = !chainInfo;
  const myLevel = myInfo?.permission_level ?? 1;

  const levelOptions = Array.from(
    { length: chainConfig?.permission_levels || 2 }, (_, i) => ({
      value: i + 1,
      label: `L${i + 1} — ${chainConfig?.level_names?.[i] ?? `Level ${i + 1}`}`,
    })
  );

  // Only show levels up to user's own level in the file store dropdown
  const allowedLevelOptions = levelOptions.filter(opt => opt.value <= myLevel);

  return (
    <div className="app-shell">
      {/* ── Top Bar ── */}
      <div className="top-bar">
        <div className="top-bar-logo">⛓️ BlockchainManager</div>
        <div className="top-bar-chain">
          <span className="top-bar-label">Current Blockchain:</span>
          <select className="chain-select"
            value={chainConfig?.chain_id || ''}
            onChange={e => e.target.value === '__new__'
              ? setShowCreateChain(true)
              : handleSwitchChain(e.target.value)}>
            {chains.map(c => (
              <option key={c.chain_id} value={c.chain_id}>{c.chain_id}</option>
            ))}
            <option value="__new__">＋ Create New Blockchain</option>
          </select>
        </div>
        <div className="top-bar-user">
          <span>{user.username}</span>
          <button className="logout-btn" onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div className="main-layout">
        {/* ── Left Panel ── */}
        <div className="left-panel">
          {[
            { id: 'properties', label: '🔧 Blockchain Properties' },
            { id: 'transactions', label: '💸 Create Transaction' },
            { id: 'data', label: '🔐 Secret File' },
            { id: 'permissions', label: '🛡️ Permissions' },
            { id: 'members', label: '👥 Members' },
            { id: 'discover', label: '🌐 Discover Chains' },
            { id: 'mine', label: '⛏️ Mine Block' },
          ].map(item => (
            <button key={item.id}
              className={`panel-btn ${activePanel === item.id ? 'active' : ''}`}
              onClick={() => {
                setActivePanel(item.id); setResult(null);
                if (item.id === 'members') loadMembers();
                if (item.id === 'discover') loadDiscoverable();
              }}>
              {item.label}
            </button>
          ))}
        </div>

        {/* ── Centre Panel ── */}
        <div className="centre-panel">
          {result && (
            <div className={`result-banner ${result.startsWith('✅') ? 'success' : 'error'}`}>
              {result}
            </div>
          )}

          {noChain && activePanel !== 'discover' && (
            <div className="empty-state">
              <p>No active blockchain.</p>
              <button className="btn-primary" style={{ width: 'auto', marginTop: '1rem' }}
                onClick={() => setShowCreateChain(true)}>
                ＋ Create Your First Blockchain
              </button>
            </div>
          )}

          {/* Blockchain Properties */}
          {!noChain && activePanel === 'properties' && chainConfig && (
            <div className="panel-content">
              <h2>Blockchain Properties</h2>
              <div className="prop-grid">
                <div className="prop-item"><span>Chain ID</span><strong>{chainConfig.chain_id}</strong></div>
                <div className="prop-item"><span>Consensus</span><strong>{chainConfig.consensus}</strong></div>
                <div className="prop-item"><span>Height</span><strong>{chainInfo.height}</strong></div>
                <div className="prop-item"><span>Pending Txs</span><strong>{chainInfo.pending_transactions}</strong></div>
                <div className="prop-item"><span>Permission Levels</span><strong>{chainConfig.permission_levels}</strong></div>
                <div className="prop-item"><span>Max Txs/Block</span><strong>{chainConfig.max_transactions_per_block}</strong></div>
                <div className="prop-item"><span>File Storage</span><strong>{chainConfig.allow_file_storage ? '✅ Enabled' : '🚫 Disabled'}</strong></div>
                <div className="prop-item"><span>Membership</span><strong>{chainConfig.open_membership ? '🌐 Open' : '🔒 Invite Only'}</strong></div>
              </div>
              <h3 style={{ marginTop: '1.5rem' }}>Permission Levels</h3>
              <div className="level-chips">
                {chainConfig.level_names?.map((name, i) => (
                  <div key={i} className="level-chip">
                    <span className="level-badge">L{i + 1}</span>{name}
                  </div>
                ))}
              </div>
              <h3 style={{ marginTop: '1.5rem' }}>Recent Blocks</h3>
              <div className="blocks-list">
                {blocks.map(b => (
                  <div key={b.height} className="block-card">
                    <span>Block #{b.height}</span>
                    <span>{b.transactions?.length ?? 0} txs</span>
                    <span className="hash">{b.hash?.slice(0, 16)}…</span>
                  </div>
                ))}
              </div>
              <h3 style={{ marginTop: '1.5rem' }}>Consensus Evidence</h3>
              {consensusInfo ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

                  {/* Mechanism banner */}
                  <div style={{
                    background: '#1e1b4b', border: '1px solid #4338ca',
                    borderRadius: '8px', padding: '0.75rem 1rem',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                  }}>
                    <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Active Mechanism</span>
                    <span style={{ color: '#818cf8', fontWeight: 700, fontSize: '1rem', letterSpacing: '0.08em' }}>
                      {consensusInfo.mechanism.toUpperCase()}
                    </span>
                  </div>

                  {/* Live mechanism state */}
                  <div style={{ background: '#0f172a', borderRadius: '8px', padding: '0.75rem 1rem' }}>
                    <div style={{
                      color: '#64748b', fontSize: '0.72rem',
                      textTransform: 'uppercase', letterSpacing: '0.08em',
                      marginBottom: '0.5rem'
                    }}>
                      Live Mechanism State
                    </div>
                    {Object.entries(consensusInfo.mechanism_state).map(([k, v]) => (
                      <div key={k} style={{
                        display: 'flex', justifyContent: 'space-between',
                        padding: '0.2rem 0', borderBottom: '1px solid #1e293b',
                        fontSize: '0.78rem'
                      }}>
                        <span style={{ color: '#94a3b8' }}>{k.replace(/_/g, ' ')}</span>
                        <span style={{
                          color: '#e2e8f0', fontFamily: 'monospace',
                          maxWidth: '55%', textAlign: 'right', wordBreak: 'break-all'
                        }}>
                          {String(v)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Validators */}
                  <div style={{ background: '#0f172a', borderRadius: '8px', padding: '0.75rem 1rem' }}>
                    <div style={{
                      color: '#64748b', fontSize: '0.72rem',
                      textTransform: 'uppercase', letterSpacing: '0.08em',
                      marginBottom: '0.5rem'
                    }}>
                      Validators ({consensusInfo.validators.length})
                    </div>
                    {consensusInfo.validators.map((v, i) => (
                      <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '1fr 60px 60px 70px',
                        gap: '0.5rem', padding: '0.25rem 0',
                        borderBottom: '1px solid #1e293b', fontSize: '0.76rem',
                        alignItems: 'center'
                      }}>
                        <span style={{ fontFamily: 'monospace', color: '#22c55e' }}>{v.address_short}</span>
                        <span style={{ color: '#94a3b8' }}>pwr: {v.power}</span>
                        <span style={{ color: v.active ? '#22c55e' : '#ef4444' }}>
                          {v.active ? '● active' : '○ inactive'}
                        </span>
                        <span style={{ color: '#64748b' }}>{v.blocks_proposed} blks</span>
                      </div>
                    ))}
                  </div>

                  {/* Per-block proof log */}
                  <div style={{ background: '#0f172a', borderRadius: '8px', padding: '0.75rem 1rem' }}>
                    <div style={{
                      color: '#64748b', fontSize: '0.72rem',
                      textTransform: 'uppercase', letterSpacing: '0.08em',
                      marginBottom: '0.5rem'
                    }}>
                      Block-by-Block Proof Log
                    </div>
                    {consensusInfo.block_log.slice().reverse().map(b => (
                      <div key={b.height} style={{
                        padding: '0.35rem 0', borderBottom: '1px solid #1e293b',
                        fontSize: '0.76rem'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                          <span style={{ color: '#6366f1', fontWeight: 600 }}>Block #{b.height}</span>
                          <span style={{ color: b.signed ? '#22c55e' : '#f59e0b' }}>
                            {b.signed ? '✓ signed' : b.height === 0 ? '⚡ genesis' : '⚠ unsigned'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                          <span style={{ color: '#94a3b8' }}>
                            proposer: <span style={{ fontFamily: 'monospace', color: '#22c55e' }}>
                              {b.proposer_short}
                            </span>
                          </span>
                          <span style={{ color: '#94a3b8' }}>txs: {b.tx_count}</span>
                          <span style={{ color: '#94a3b8' }}>
                            merkle: <span style={{ fontFamily: 'monospace', color: '#64748b' }}>
                              {b.merkle_root_short}
                            </span>
                          </span>
                        </div>
                        {/* Consensus-specific fields inline */}
                        {Object.keys(b.consensus_data).length > 0 && (
                          <div style={{
                            marginTop: '0.2rem', display: 'flex', gap: '0.75rem',
                            flexWrap: 'wrap', color: '#475569', fontSize: '0.72rem'
                          }}>
                            {Object.entries(b.consensus_data)
                              .filter(([k]) => !['consensus', 'proposer', 'timestamp'].includes(k))
                              .map(([k, v]) => (
                                <span key={k}>
                                  {k.replace(/_/g, ' ')}: <span style={{ color: '#818cf8' }}>{String(v)}</span>
                                </span>
                              ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                </div>
              ) : (
                <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Loading consensus data…</div>
              )}
            </div>
          )}

          {/* Create Transaction */}
          {!noChain && activePanel === 'transactions' && (
            <div className="panel-content">
              <h2>Create Transaction</h2>
              <label>Recipient Address</label>
              <input placeholder="0x..." value={formData.recipient}
                onChange={e => setFormData({ ...formData, recipient: e.target.value })} />
              <label>Amount</label>
              <input type="number" value={formData.amount} min={0}
                onChange={e => setFormData({ ...formData, amount: e.target.value })} />
              <button className="btn-primary" onClick={handleTransfer} disabled={loading}>
                Send Transfer
              </button>
            </div>
          )}

          {/* Secret File */}
          {!noChain && activePanel === 'data' && (
            <div className="panel-content">

              {/* Store */}
              <h2>Store Secret File</h2>
              <label>File Name</label>
              <input placeholder="e.g. mission-alpha" value={formData.dataId}
                onChange={e => setFormData({ ...formData, dataId: e.target.value })} />
              <label>Content</label>
              <textarea placeholder="Enter classified content..." value={formData.content}
                onChange={e => setFormData({ ...formData, content: e.target.value })} />
              <label>Security Level (max: your level L{myLevel})</label>
              <select value={formData.securityLevel}
                onChange={e => setFormData({ ...formData, securityLevel: parseInt(e.target.value) })}>
                {allowedLevelOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <button className="btn-primary" onClick={handleStoreData} disabled={loading}>
                Store File
              </button>

              <hr style={{ borderColor: '#334155', margin: '1.5rem 0' }} />

              {/* My Accessible Files */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ margin: 0 }}>My Accessible Files</h2>
                <button className="btn-primary"
                  style={{ width: 'auto', padding: '0.3rem 0.9rem', fontSize: '0.85rem' }}
                  onClick={async () => {
                    try {
                      const res = await api.listMyData();
                      setFormData(f => ({ ...f, myFiles: res.data.items }));
                    } catch (err) {
                      setResult('❌ ' + (err.response?.data?.detail || err.message));
                    }
                  }}>
                  Refresh
                </button>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                {!formData.myFiles && <p style={{ color: '#64748b' }}>Click Refresh to load.</p>}
                {formData.myFiles?.length === 0 && <p style={{ color: '#64748b' }}>No accessible files.</p>}
                {formData.myFiles?.map(item => (
                  <div key={item.data_id} className="member-card"
                    style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.4rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <div>
                        <strong>{item.name}</strong>
                        <span style={{ color: '#64748b', fontSize: '0.78rem', marginLeft: '0.5rem' }}>
                          ID: {item.data_id}
                        </span>
                      </div>
                      <span className="level-badge">L{item.security_level}</span>
                    </div>
                    <span style={{ color: '#64748b', fontSize: '0.78rem' }}>
                      Owner: {item.owner?.slice(0, 16)}…
                    </span>
                    <button className="btn-primary"
                      style={{ width: '100%', padding: '0.25rem', fontSize: '0.82rem' }}
                      onClick={async () => {
                        try {
                          const res = await api.readData(item.data_id);
                          setResult(`📄 [${res.data.name}] ${res.data.content}`);
                        } catch (err) {
                          setResult('❌ ' + (err.response?.data?.detail || err.message));
                        }
                      }}>
                      Read
                    </button>
                  </div>
                ))}
              </div>

              <hr style={{ borderColor: '#334155', margin: '1.5rem 0' }} />

              {/* All Files in Chain */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ margin: 0 }}>All Files in Chain</h2>
                <button className="btn-primary"
                  style={{ width: 'auto', padding: '0.3rem 0.9rem', fontSize: '0.85rem' }}
                  onClick={async () => {
                    try {
                      const res = await api.listAllData();
                      setFormData(f => ({ ...f, allFiles: res.data.items }));
                    } catch (err) {
                      setResult('❌ ' + (err.response?.data?.detail || err.message));
                    }
                  }}>
                  Refresh
                </button>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                {!formData.allFiles && <p style={{ color: '#64748b' }}>Click Refresh to load.</p>}
                {formData.allFiles?.length === 0 && <p style={{ color: '#64748b' }}>No files stored yet.</p>}
                {formData.allFiles?.map(item => (
                  <div key={item.data_id} className="member-card"
                    style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '0.3rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <div>
                        <strong>{item.name}</strong>
                        <span style={{ color: '#64748b', fontSize: '0.78rem', marginLeft: '0.5rem' }}>
                          ID: {item.data_id}
                        </span>
                      </div>
                      <span className="level-badge">L{item.security_level}</span>
                    </div>
                    <span style={{ color: '#64748b', fontSize: '0.78rem' }}>
                      Owner: {item.owner?.slice(0, 16)}…
                    </span>
                    <button className="btn-primary"
                      style={{ width: '100%', padding: '0.25rem', fontSize: '0.82rem', marginTop: '0.2rem' }}
                      onClick={async () => {
                        try {
                          const res = await api.readData(item.data_id);
                          setResult(`📄 [${res.data.name}] ${res.data.content}`);
                        } catch (err) {
                          setResult('❌ ACCESS DENIED — your permission level is too low');
                        }
                      }}>
                      Read (if permitted)
                    </button>
                  </div>
                ))}
              </div>

            </div>
          )}

          {/* Permissions */}
          {!noChain && activePanel === 'permissions' && (
            <div className="panel-content">
              <h2>Promote User</h2>
              <label>Target Address</label>
              <input placeholder="0x..." value={formData.target}
                onChange={e => setFormData({ ...formData, target: e.target.value })} />
              <label>New Permission Level</label>
              <select value={formData.level}
                onChange={e => setFormData({ ...formData, level: parseInt(e.target.value) })}>
                {levelOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <button className="btn-primary" onClick={handlePromote} disabled={loading}>
                Promote
              </button>

              {!chainConfig?.open_membership && (
                <>
                  <hr style={{ borderColor: '#334155', margin: '1.5rem 0' }} />
                  <h2>Invite Member</h2>
                  <label>Address to Invite</label>
                  <input placeholder="0x..." value={formData.inviteAddress}
                    onChange={e => setFormData({ ...formData, inviteAddress: e.target.value })} />
                  <label>Starting Permission Level</label>
                  <select value={formData.inviteLevel}
                    onChange={e => setFormData({ ...formData, inviteLevel: parseInt(e.target.value) })}>
                    {levelOptions.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <button className="btn-primary" onClick={handleInvite} disabled={loading}>
                    Send Invite
                  </button>
                </>
              )}
            </div>
          )}

          {/* Members */}
          {activePanel === 'members' && (
            <div className="panel-content">
              <h2>Chain Members</h2>
              {members.length === 0
                ? <p style={{ color: '#64748b' }}>No members loaded yet.</p>
                : members.map(m => (
                  <div key={m.address} className="member-card">
                    <span className="hash">{m.address.slice(0, 20)}…</span>
                    <span className="level-badge">L{m.level} — {m.label}</span>
                  </div>
                ))
              }
            </div>
          )}

          {/* Discover Chains */}
          {/* FIX #4: removed the orphaned duplicate <h2>Open Blockchains</h2> at the bottom;
                      restructured so open chains and pending invites are clearly separated */}
          {activePanel === 'discover' && (
            <div className="panel-content">
              <h2>Discover Open Blockchains</h2>
              {discoverable.length === 0
                ? <p style={{ color: '#64748b' }}>No open chains available to join.</p>
                : discoverable.map(c => (
                  <div key={c.chain_id} className="member-card">
                    <div>
                      <strong>{c.chain_id}</strong>
                      <span style={{ color: '#64748b', fontSize: '0.82rem', marginLeft: '0.75rem' }}>
                        {c.consensus} · {c.permission_levels} levels
                      </span>
                    </div>
                    <button className="btn-primary"
                      style={{ width: 'auto', padding: '0.3rem 0.9rem', fontSize: '0.85rem' }}
                      onClick={() => handleJoinDiscoverable(c.chain_id)}>
                      Join
                    </button>
                  </div>
                ))
              }

              <hr style={{ borderColor: '#334155', margin: '1.5rem 0' }} />

              {/* Pending Invites */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ margin: 0 }}>Pending Invites</h2>
                <button className="btn-primary"
                  style={{ width: 'auto', padding: '0.3rem 0.9rem', fontSize: '0.85rem' }}
                  onClick={async () => {
                    const res = await api.getInvites();
                    setInvites(res.data.invites);
                  }}>
                  Refresh
                </button>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                {invites.length === 0
                  ? <p style={{ color: '#64748b' }}>No pending invites.</p>
                  : invites.map(c => (
                    <div key={c.chain_id} className="member-card">
                      <div>
                        <strong>{c.chain_id}</strong>
                        <span style={{ color: '#64748b', fontSize: '0.82rem', marginLeft: '0.75rem' }}>
                          {c.consensus} · {c.permission_levels} levels
                        </span>
                      </div>
                      <button className="btn-primary"
                        style={{ width: 'auto', padding: '0.3rem 0.9rem', fontSize: '0.85rem' }}
                        onClick={async () => {
                          await api.switchChain(c.chain_id);
                          await fetchAll();
                          setResult(`✅ Joined: ${c.chain_id}`);
                        }}>
                        Accept
                      </button>
                    </div>
                  ))
                }
              </div>
            </div>
          )}

          {/* Mine Block */}
          {!noChain && activePanel === 'mine' && (
            <div className="panel-content">
              <h2>Mine Block</h2>
              <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
                Package all pending transactions into a new block.
                Max {chainConfig?.max_transactions_per_block} transactions per block.
              </p>
              <button className="btn-primary mine-btn" onClick={handleMine} disabled={loading}>
                {loading ? 'Mining…' : '⛏️ Mine Block'}
              </button>
            </div>
          )}
        </div>

        {/* ── Right Panel ── */}
        <div className="right-panel" style={{ minWidth: '220px', width: '220px' }}>
          <div className="right-panel-title">Your Account</div>
          {myInfo ? (
            <>
              <div className="user-card">
                <span className="user-label">Username</span>
                <span className="user-value">{myInfo.username}</span>
              </div>

              <div className="user-card">
                <span className="user-label">Wallet Address</span>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                  marginTop: '0.2rem', flexWrap: 'wrap'
                }}>
                  <span className="user-value hash" style={{ fontSize: '0.78rem' }}>
                    {myInfo.address?.slice(0, 20)}…
                  </span>
                  <button
                    onClick={() => {
                      try {
                        if (navigator.clipboard && window.isSecureContext) {
                          navigator.clipboard.writeText(myInfo.address);
                        } else {
                          const el = document.createElement('textarea');
                          el.value = myInfo.address;
                          el.style.position = 'fixed';
                          el.style.opacity = '0';
                          document.body.appendChild(el);
                          el.focus(); el.select();
                          document.execCommand('copy');
                          document.body.removeChild(el);
                        }
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      } catch (e) { console.error('Copy failed:', e); }
                    }}
                    title="Copy full wallet address"
                    style={{
                      background: 'none', border: '1px solid #334155',
                      borderRadius: '4px', cursor: 'pointer',
                      color: copied ? '#22c55e' : '#94a3b8',
                      fontSize: '0.75rem', padding: '0.1rem 0.35rem',
                      lineHeight: 1.4, transition: 'color 0.2s', flexShrink: 0,
                    }}>
                    {copied ? '✅ Copied' : '📋 Copy'}
                  </button>
                </div>
              </div>

              {myInfo.balance !== undefined && (
                <div className="user-card">
                  <span className="user-label">Account Balance</span>
                  <span className="user-value">{myInfo.balance}</span>
                </div>
              )}
              {myInfo.permission_label && (
                <div className="user-card">
                  <span className="user-label">Permission Level</span>
                  <span className="user-value">
                    <span className="level-badge">L{myInfo.permission_level}</span>
                    {' '}{myInfo.permission_label}
                  </span>
                </div>
              )}
              <div className="user-card">
                <span className="user-label">Chains Joined</span>
                <span className="user-value">{myInfo.chains?.length || 0}</span>
              </div>
            </>
          ) : (
            <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Loading...</p>
          )}
        </div>
      </div>
    </div>
  );
}


// ── Root App ──────────────────────────────────────────────────────────────────
function App() {
  const [user, setUser] = useState(null);

  const handleLogin = (userData) => setUser(userData);
  const handleLogout = async () => {
    try { await api.logout(); } catch (_) { }
    clearToken(); setUser(null);
  };

  if (!user) return <AuthScreen onLogin={handleLogin} />;
  return <Dashboard user={user} onLogout={handleLogout} />;
}

export default App;