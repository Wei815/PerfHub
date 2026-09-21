import React, { useEffect, useState, useRef } from 'react';
import { Trash2 } from 'lucide-react';

const LogTerminal = ({ target = 'com.example.app', isMockMode = false }) => {
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (isMockMode) {
      const interval = setInterval(() => {
        const randomMs = Math.floor(Math.random() * 1000);
        const timeStr = new Date().toLocaleTimeString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const messages = [
          `[資訊] 系統運作順暢，延遲: ${randomMs}ms`,
          `[除錯] 正在從資料庫獲取使用者設定檔...`,
          `[資訊] 畫面渲染完成，準備輸出下一幀`,
          `[警告/ActivityManager] 偵測到操作緩慢，請注意資源消耗！`,
          `[錯誤/RenderThread] 遺失 Vsync 訊號達 12ms！畫面可能發生卡頓`,
        ];
        const msg = messages[Math.floor(Math.random() * messages.length)];
        setLogs(prev => {
          const newLogs = [...prev, `${timeStr} ${msg}`];
          return newLogs.length > 200 ? newLogs.slice(newLogs.length - 200) : newLogs;
        });
      }, 1500);
      return () => clearInterval(interval);
    }
    
    const url = new URL('ws://127.0.0.1:8000/ws/logs');
    url.searchParams.set('target', target);
    url.searchParams.set('mock', 'false');
    
    wsRef.current = new WebSocket(url.toString());
    
    wsRef.current.onmessage = (event) => {
      setLogs(prev => {
        const newLogs = [...prev, event.data];
        if (newLogs.length > 200) {
          return newLogs.slice(newLogs.length - 200);
        }
        return newLogs;
      });
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [target, isMockMode]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const clearLogs = () => setLogs([]);

  const getLogStyle = (text) => {
    if (text.includes('E/') || text.includes('Exception') || text.includes('Error') || text.includes('錯誤')) {
      return { color: 'var(--danger-color)' };
    }
    if (text.includes('W/') || text.includes('Warning') || text.includes('警告')) {
      return { color: '#fbbf24' };
    }
    return { color: '#d4d4d8' };
  };

  return (
    <div className="log-terminal-container">
      <div className="log-header">
        <span className="log-title">Logcat Terminal</span>
        <button className="log-clear-btn" onClick={clearLogs} title="Clear Logs"><Trash2 size={14} /></button>
      </div>
      <div className="log-body">
        {logs.map((log, idx) => (
          <div key={idx} className="log-line" style={getLogStyle(log)}>
            {log}
          </div>
        ))}
        <div ref={scrollRef} />
      </div>
    </div>
  );
};

export default LogTerminal;
