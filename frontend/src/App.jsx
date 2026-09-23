import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Play, Pause, Trash2, Download, Activity, Cpu, HardDrive, Smartphone, Info, Wifi, WifiOff, Globe, RefreshCw } from 'lucide-react';
import { useWebSocket } from './hooks/useWebSocket';
import DeviceScreen from './components/DeviceScreen';
import LogTerminal from './components/LogTerminal';
import './index.css';

function App() {
  const [targetPackage, setTargetPackage] = useState('');
  const [isMockMode, setIsMockMode] = useState(false);
  const [inputPackage, setInputPackage] = useState('');
  const [availablePackages, setAvailablePackages] = useState([]);
  const [isLandscape, setIsLandscape] = useState(false);

  const toggleMockMode = () => setIsMockMode(prev => !prev);
  const {
    data,
    currentMetrics,
    deviceInfo,
    status,
    errorMessage,
    isRecording,
    startRecording,
    pauseRecording,
    clearData,
    exportCSV
  } = useWebSocket('ws://127.0.0.1:8000/ws/perf', targetPackage, isMockMode);

  // Fetch package list
  useEffect(() => {
    fetch(`http://127.0.0.1:8000/api/packages?mock=${isMockMode}`)
      .then(res => res.json())
      .then(data => {
        if (data.packages) {
          setAvailablePackages(data.packages);
        }
      })
      .catch(err => console.error("Failed to fetch packages:", err));
  }, [isMockMode]);

  const { cpu_percent, memory_mb, fps, rx_kbps, tx_kbps } = currentMetrics;

  const isCpuDanger = cpu_percent > 80;
  const isFpsDanger = fps > 0 && fps < 45; 

  return (
    <div className="app-container">
      {/* 頂部導覽列 */}
      <header className="topbar glass-panel">
        <div className="brand">
          <h1>PerfHub Pro</h1>
          <span className="badge">Cloud Device Farm</span>
        </div>
      </header>

      {/* 三欄式主佈局 */}
      <div className={`main-layout ${isLandscape ? 'landscape-mode' : ''}`}>
        
        {/* ================= 左欄：設備資料與控制 ================= */}
        <aside className="left-panel glass-panel">
          <div className="panel-section">
            <h2 className="section-title"><Smartphone size={18} /> 設備狀態</h2>
            <div className="info-list">
              <div className="info-item">
                <span className="label">連線狀態</span>
                {status === 'connected' ? (
                  <span className="value text-success"><Wifi size={14}/> 穩定連線</span>
                ) : status === 'error' ? (
                  <span className="value text-danger"><WifiOff size={14}/> 連線異常</span>
                ) : (
                  <span className="value text-secondary">連線中...</span>
                )}
              </div>
              <div className="info-item">
                <span className="label">設備型號</span>
                <span className="value">{deviceInfo?.model || '等待數據...'}</span>
              </div>
              <div className="info-item">
                <span className="label">作業系統</span>
                <span className="value">{deviceInfo?.os_version || '等待數據...'}</span>
              </div>
              <div className="info-item">
                <span className="label">目標包名</span>
                <select 
                  value={targetPackage}
                  onChange={(e) => {
                    setInputPackage(e.target.value);
                    setTargetPackage(e.target.value);
                  }}
                  style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '4px', borderRadius: '4px', fontSize: '0.75rem', width: 'auto', maxWidth: '180px', cursor: 'pointer' }}
                >
                  <option value="">Global System (整機)</option>
                  {availablePackages.map((pkg, idx) => (
                    <option key={idx} value={pkg}>{pkg}</option>
                  ))}
                </select>
              </div>
              {targetPackage === '' && (
                <div className="info-item">
                  <span className="label">監控模式</span>
                  <span className="value text-success">Global System (整機監控)</span>
                </div>
              )}
              <div className="info-item">
                <span className="label">WiFi 網路</span>
                <span className="value">{status === 'error' || !deviceInfo?.wifi_ssid ? '等待數據...' : deviceInfo.wifi_ssid}</span>
              </div>
              <div className="info-item">
                <span className="label">IP 位置</span>
                <span className="value">{status === 'error' || !deviceInfo?.wifi_ip ? '等待數據...' : deviceInfo.wifi_ip}</span>
              </div>
              <div className="info-item">
                <span className="label">VPN IP</span>
                <span className="value">{status === 'error' || !deviceInfo?.vpn_ip ? '未連線' : (deviceInfo.vpn_ip === 'Unknown' ? '未連線' : deviceInfo.vpn_ip)}</span>
              </div>
              <div className="info-item">
                <span className="label">畫面比例</span>
                <span className="value">{status === 'error' || !deviceInfo?.resolution_w ? '等待數據...' : `${deviceInfo.resolution_w}:${deviceInfo.resolution_h}`}</span>
              </div>
            </div>
            {/* 串流狀態的 Portal 容器 */}
            <div id="stream-status-portal" style={{ marginTop: '1rem' }}></div>
          </div>

          <div className="panel-section mt-auto">
            <h2 className="section-title"><Info size={18} /> 測試控制</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '8px' }}>
              <input type="checkbox" id="mockMode" checked={isMockMode} onChange={toggleMockMode} style={{ cursor: 'pointer' }} />
              <label htmlFor="mockMode" style={{ fontSize: '0.9rem', cursor: 'pointer', userSelect: 'none', color: isMockMode ? 'var(--accent-color)' : 'inherit' }}>Mock Mode (模擬數據)</label>
            </div>
            <div className="action-buttons">
              <button 
                className={`primary ${isRecording ? 'recording' : ''}`} 
                onClick={isRecording ? pauseRecording : startRecording}
                disabled={status !== 'connected'}
              >
                {isRecording ? <><Pause size={18}/> 暫停採集</> : <><Play size={18}/> 開始錄製</>}
              </button>
              <button onClick={() => window.location.reload()}><RefreshCw size={18}/> 重新整理 (Reload)</button>
              <button onClick={clearData}><Trash2 size={18}/> 清除畫面</button>
              <button onClick={exportCSV} disabled={data.length === 0}><Download size={18}/> 匯出 CSV</button>
            </div>
            {status === 'error' && (
              <div className="error-alert">
                {errorMessage}
              </div>
            )}
          </div>
        </aside>

        {/* ================= 中欄：手機畫面同步與終端機 ================= */}
        <main className="center-panel glass-panel" style={{ padding: 0 }}>
          <div style={{ flex: '1 1 65%', display: 'flex', flexDirection: 'column', width: '100%', padding: '1rem', minHeight: 0 }}>
            <DeviceScreen 
              target={targetPackage} 
              isMockMode={isMockMode} 
              targetWidth={status === 'error' || !deviceInfo?.resolution_w ? (isLandscape ? 2400 : 1080) : (isLandscape ? deviceInfo.resolution_h : deviceInfo.resolution_w)} 
              targetHeight={status === 'error' || !deviceInfo?.resolution_h ? (isLandscape ? 1080 : 2400) : (isLandscape ? deviceInfo.resolution_w : deviceInfo.resolution_h)} 
              onOrientationChange={setIsLandscape}
            />
          </div>
        </main>

        {/* ================= 右欄：效能數據監控 ================= */}
        <aside className="right-panel">
          
          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* 頂部：數據指標卡片 */}
            <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', flexShrink: 0 }}>
              <div className={`metric-card glass-panel ${isCpuDanger ? 'danger' : ''}`}>
                <div className="metric-label"><Cpu size={14}/> CPU Usage</div>
                <div className="metric-value">{cpu_percent.toFixed(1)}<span>%</span></div>
              </div>
              <div className="metric-card glass-panel">
                <div className="metric-label"><HardDrive size={14}/> Memory PSS</div>
                <div className="metric-value">{memory_mb.toFixed(1)}<span>MB</span></div>
              </div>
              <div className={`metric-card glass-panel ${isFpsDanger ? 'danger' : ''}`}>
                <div className="metric-label"><Activity size={14}/> FPS</div>
                <div className="metric-value">{fps}<span>Hz</span></div>
              </div>
              <div className="metric-card glass-panel">
                <div className="metric-label"><Globe size={14}/> Network</div>
                <div className="metric-value" style={{ fontSize: '1.1rem', display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
                  <span style={{color: '#a78bfa'}}>↓ {rx_kbps || 0} <span style={{fontSize: '0.7rem'}}>KB/s</span></span>
                  <span style={{color: '#38bdf8'}}>↑ {tx_kbps || 0} <span style={{fontSize: '0.7rem'}}>KB/s</span></span>
                </div>
              </div>
            </div>

            {/* 中間：折線圖列表 (支援捲動) */}
            <div className="charts-scroll-area custom-scrollbar" style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: '4px', display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
              <div className="chart-box glass-panel">
                <h3>CPU 趨勢 (%)</h3>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 5, right: 0, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={true} />
                      <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} stroke="var(--text-secondary)" tick={{fontSize: 10}} />
                      <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: 'none', borderRadius: '8px' }} />
                      <Area type="monotone" dataKey="cpu" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.15} strokeWidth={2} dot={false} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '25px', paddingRight: '5px', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  <span>60 秒</span>
                  <span>0</span>
                </div>
              </div>

              <div className="chart-box glass-panel">
                <h3>記憶體趨勢 (MB)</h3>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 5, right: 0, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={true} />
                      <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
                      <YAxis domain={['auto', 'auto']} stroke="var(--text-secondary)" tick={{fontSize: 10}} />
                      <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: 'none', borderRadius: '8px' }} />
                      <Area type="monotone" dataKey="memory" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.15} strokeWidth={2} dot={false} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '25px', paddingRight: '5px', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  <span>60 秒</span>
                  <span>0</span>
                </div>
              </div>

              <div className="chart-box glass-panel">
                <h3>流暢度 FPS (Hz)</h3>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 5, right: 0, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={true} />
                      <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 65]} stroke="var(--text-secondary)" tick={{fontSize: 10}} />
                      <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: 'none', borderRadius: '8px' }} />
                      <Area type="monotone" dataKey="fps" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} dot={false} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '25px', paddingRight: '5px', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  <span>60 秒</span>
                  <span>0</span>
                </div>
              </div>

              <div className="chart-box glass-panel">
                <h3>Network 流量 (KB/s)</h3>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 5, right: 0, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={true} />
                      <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
                      <YAxis domain={['auto', 'auto']} stroke="var(--text-secondary)" tick={{fontSize: 10}} />
                      <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: 'none', borderRadius: '8px' }} />
                      <Area type="monotone" dataKey="rx" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.3} isAnimationActive={false} />
                      <Area type="monotone" dataKey="tx" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.3} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '25px', paddingRight: '5px', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  <span>60 秒</span>
                  <span>0</span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="log-terminal-wrapper">
            <LogTerminal target={targetPackage} isMockMode={isMockMode} />
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;
