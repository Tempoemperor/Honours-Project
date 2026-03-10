// frontend/src/Setup.jsx
import React, { useState } from "react";

const CONSENSUS_OPTIONS = [
  { value: "poa", label: "Proof of Authority (PoA)", desc: "Fast, permissioned. Best for enterprise/demo." },
  { value: "tendermint", label: "Tendermint BFT", desc: "Byzantine fault tolerant, instant finality." },
  { value: "raft", label: "Raft", desc: "Leader-based consensus, simple and reliable." },
];

export default function Setup({ onComplete }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    chain_id: "",
    consensus: "poa",
    permission_levels: 5,
    level_names: [],
  });
  const [levelNames, setLevelNames] = useState(Array(5).fill(""));
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLevelCount = (n) => {
    setForm({ ...form, permission_levels: n });
    setLevelNames(Array(n).fill("").map((_, i) => levelNames[i] || ""));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = {
        ...form,
        level_names: levelNames.some(n => n.trim()) ? levelNames.map((n, i) => n.trim() || `Level ${i + 1}`) : null,
      };
      const res = await fetch("http://127.0.0.1:8000/setup/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Setup failed");
      setResult(data);
      setStep(4);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="setup-overlay">
      <div className="setup-wizard">
        <div className="setup-header">
          <h1>⛓ Create Your Blockchain</h1>
          <div className="step-indicator">
            {[1, 2, 3].map(s => (
              <div key={s} className={`step-dot ${step >= s ? "active" : ""}`}>{s}</div>
            ))}
          </div>
        </div>

        {/* Step 1: Chain Name */}
        {step === 1 && (
          <div className="setup-step">
            <h2>Name Your Blockchain</h2>
            <p>This will be the unique identifier for your chain.</p>
            <input
              className="setup-input"
              placeholder="e.g. my-chain, mil-net-alpha, corp-ledger"
              value={form.chain_id}
              onChange={e => setForm({ ...form, chain_id: e.target.value })}
            />
            <button
              className="setup-btn"
              disabled={!form.chain_id.trim()}
              onClick={() => setStep(2)}
            >
              Next →
            </button>
          </div>
        )}

        {/* Step 2: Consensus */}
        {step === 2 && (
          <div className="setup-step">
            <h2>Choose Consensus Mechanism</h2>
            <div className="consensus-options">
              {CONSENSUS_OPTIONS.map(opt => (
                <div
                  key={opt.value}
                  className={`consensus-card ${form.consensus === opt.value ? "selected" : ""}`}
                  onClick={() => setForm({ ...form, consensus: opt.value })}
                >
                  <h3>{opt.label}</h3>
                  <p>{opt.desc}</p>
                </div>
              ))}
            </div>
            <div className="setup-nav">
              <button className="setup-btn secondary" onClick={() => setStep(1)}>← Back</button>
              <button className="setup-btn" onClick={() => setStep(3)}>Next →</button>
            </div>
          </div>
        )}

        {/* Step 3: Permission Levels */}
        {step === 3 && (
          <div className="setup-step">
            <h2>Permission Levels</h2>
            <p>How many access levels should your blockchain have? (2–10)</p>
            <input
              type="number" min="2" max="10"
              className="setup-input"
              value={form.permission_levels}
              onChange={e => handleLevelCount(Math.min(10, Math.max(2, parseInt(e.target.value) || 2)))}
            />
            <p className="hint">Optionally name each level:</p>
            <div className="level-names">
              {Array(form.permission_levels).fill(0).map((_, i) => (
                <input
                  key={i}
                  className="setup-input small"
                  placeholder={`Level ${i + 1} name (optional)`}
                  value={levelNames[i] || ""}
                  onChange={e => {
                    const updated = [...levelNames];
                    updated[i] = e.target.value;
                    setLevelNames(updated);
                  }}
                />
              ))}
            </div>
            {error && <p className="setup-error">{error}</p>}
            <div className="setup-nav">
              <button className="setup-btn secondary" onClick={() => setStep(2)}>← Back</button>
              <button className="setup-btn" onClick={handleSubmit} disabled={loading}>
                {loading ? "Creating..." : "🚀 Create Blockchain"}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Success — show admin keys */}
        {step === 4 && result && (
          <div className="setup-step">
            <h2>✅ Blockchain Created!</h2>
            <div className="key-card">
              <p><strong>Chain ID:</strong> {result.chain_id}</p>
              <p><strong>Consensus:</strong> {result.consensus}</p>
              <p><strong>Permission Levels:</strong> {result.permission_levels}</p>
              <p><strong>Admin Address:</strong><br /><code>{result.admin_address}</code></p>
              <p><strong>Admin Private Key:</strong><br /><code>{result.admin_private_key}</code></p>
            </div>
            <p className="warning">⚠️ Save your private key now! It won't be shown again after you proceed.</p>
            <button className="setup-btn" onClick={() => onComplete(result)}>
              Enter Dashboard →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
