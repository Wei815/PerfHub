import React, { useState, useEffect, useRef } from 'react';
import { Trash2, Copy, Check } from 'lucide-react';

const LogTerminal = ({ target = 'com.example.app', isMockMode = false }) => {
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    if (isMockMode) {
      const interval = setInterval(() => {
        if (!isMounted) return;
        const randomMs = Math.floor(Math.random() * 1000);
        const timeStr = new Date().toLocaleTimeString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const messages = [
          { text: `${timeStr} [資訊] 系統運作順暢，延遲: ${randomMs}ms`, annotation: '' },
          { text: `${timeStr} [警告/ActivityManager] 偵測到操作緩慢，請注意資源消耗！`, annotation: '系統資源警告' },
          { text: `${timeStr} [錯誤/RenderThread] 遺失 Vsync 訊號達 12ms！畫面可能發生卡頓`, annotation: '畫面掉幀警告' },
        ];
        const msg = messages[Math.floor(Math.random() * messages.length)];
        setLogs(prev => {
          const newLogs = [...prev, msg];
          return newLogs.length > 200 ? newLogs.slice(newLogs.length - 200) : newLogs;
        });
      }, 1500);
      return () => {
        isMounted = false;
        clearInterval(interval);
      };
    }
    
    const url = new URL('ws://127.0.0.1:8000/ws/logs');
    url.searchParams.set('target', target);
    url.searchParams.set('mock', 'false');
    
    wsRef.current = new WebSocket(url.toString());
    
    wsRef.current.onmessage = (event) => {
      if (!isMounted) return;
      const rawText = event.data;
      
      // 1. 過濾無用的華為/系統底層雜訊
      const spamKeywords = [
        'WifiHAL', 'WificondControl', 'Thermal-daemon', 'BDLog', 
        'NotificationInflation23', 'JankService', 'HwChrExceptionListener', 
        'HwCHRWifiFile', 'HwCHRWifi', 'ZeroHung', 'NetworkManager', 'NetworkMonitor',
        'zygote', 'libprocessgroup', 'iMonitor', 'HsmCoreServiceImpl',
        'ro.config.vol_steps', 'register_com_android_internal_os_Zygote',
        'DateView', 'ndroid.systemu', 'HwLauncher', 'HwRecSys', 'HiBoard',
        'HwID', 'FastSDKEngine', 'ProcessInfoCollector', 'MemoryLeakMonitorManager',
        'FileLogNode', 'HiAdKit', 'UpdateVersionManager', 'teec_app_load',
        'IpCountryUtil', 'AIDLLoginManager', 'HSM_BG', 'dubaid', 'storaged',
        'WifiProCHRManager', 'HwLocation', 'HwXmlLogParse', 'HwReportTool',
        'AppInfoMgr', 'Feedback_', 'setgid: Operation not permitted', 'EasyInvokeUtils',
        'ro.vr_display.service', 'ro.kirin.product.platform', 'HwExtendedCodec',
        'OMXNodeInstance', 'HWComposer', 'iptables cmd', 'ZrHungImpl',
        'AuthPII', 'Not starting debugger since process cannot load the jdwp agent',
        'HwGrsSdk', 'HwConnectivityService', 'CloudAlbumSDK', 'AppLifeChangeSensor',
        'Hicom_PolicyCenterService', 'AwareLog', 'XEngineMpipControl', 'DollieAdapterService',
        'BufferQueueProducer', 'SpannableStringBuilder', 'chromium', 'ServiceManager',
        'Parcel  :', 'blob    :',
        // 螢幕旋轉 & GPU 渲染雜訊
        'SurfaceFlinger', 'media.codec', 'TWGraphicBufferProducer', 'eglSwapBuffers',
        'mali gles error', 'GL error', 'Invalid output fence',
        // 華為觸控 & 動作偵測
        'TS_HAL', 'TS_Service', 'hwTsSetAftAlgoOrientation', 'HwMotionRecognition',
        'DsSearchIndexablesProvider',
        // 華為系統設定重建索引
        'RoundCornerDisplay', 'ExternalAppConfigDataChecker', 'HwEffectHelper',
        'Sdencryption', 'SdEncryptionUtils', 'BaseSearchIndex', 'antiTheft',
        'MoreInputMethodSettings', 'WifiSetting', 'WifiTracker',
        'IndexableItem', 'target is not exported',
        'com.huawei.android.airsharing', 'DollieActivityManagerAdapter',
        'HwActivityManagerServiceEx', 'HwActivityNotifierEx',
        'DE N DES', 'getSupportedInternal',
        // 華為啟動器 & 搜尋
        'HiSearch', 'LauncherOverlayService', 'not attached to window manager',
        'SnapshotStartingWindow', 'com.huawei.intelligent'
      ];
      if (spamKeywords.some(kw => rawText.includes(kw))) {
        return; // 直接略過，不上螢幕
      }

      // 2. 判斷錯誤類型並加入中文註解
      let annotation = '';
      if (rawText.includes('FATAL EXCEPTION') || rawText.includes('AndroidRuntime')) {
        annotation = 'APP 崩潰閃退';
      } else if (rawText.includes('OutOfMemoryError')) {
        annotation = '記憶體耗盡 (OOM)';
      } else if (rawText.includes('NullPointerException')) {
        annotation = '遇到空指標例外 (NPE)';
      } else if (rawText.includes('ActivityManager') || rawText.includes('ActivityTaskManager')) {
        annotation = '系統生命週期或 ANR 警告';
      } else if (rawText.includes('WindowManager')) {
        annotation = '視窗管理員或渲染警告';
      } else if (rawText.includes('ClassNotFoundException')) {
        annotation = '找不到對應的 Class 模組';
      }

      const logEntry = { text: rawText, annotation };
      
      setLogs(prev => {
        const newLogs = [...prev, logEntry];
        if (newLogs.length > 200) {
          return newLogs.slice(newLogs.length - 200);
        }
        return newLogs;
      });
    };
    
    wsRef.current.onerror = (e) => {
      if (!isMounted) return;
    };

    return () => {
      isMounted = false;
      if (wsRef.current) {
        const socket = wsRef.current;
        if (socket.readyState === WebSocket.CONNECTING) {
          socket.onopen = () => socket.close();
        } else if (socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
        wsRef.current = null;
      }
    };
  }, [target, isMockMode]);

  useEffect(() => {
    if (scrollRef.current) {
      const parent = scrollRef.current.parentElement;
      if (parent) {
        parent.scrollTop = parent.scrollHeight;
      }
    }
  }, [logs]);

  const [isCopied, setIsCopied] = useState(false);

  const clearLogs = () => setLogs([]);

  const copyLogs = () => {
    const textToCopy = logs.map(log => log.text + (log.annotation ? ' // ' + log.annotation : '')).join('\n');
    navigator.clipboard.writeText(textToCopy).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  };

  const getLogStyle = (text) => {
    if (text.includes('E/') || text.includes('Exception') || text.includes('Error') || text.includes('錯誤')) {
      return { color: 'var(--danger-color)' };
    }
    if (text.includes('W/') || text.includes('Warning') || text.includes('警告') || text.includes(' W ')) {
      return { color: '#fbbf24' };
    }
    if (text.includes(' E ')) {
      return { color: 'var(--danger-color)' };
    }
    return { color: '#d4d4d8' };
  };

  return (
    <div className="log-terminal-container">
      <div className="log-header">
        <span className="log-title">Logcat Terminal</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="log-clear-btn" onClick={copyLogs} title="Copy Logs">
            {isCopied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
          </button>
          <button className="log-clear-btn" onClick={clearLogs} title="Clear Logs"><Trash2 size={14} /></button>
        </div>
      </div>
      <div className="log-body">
        {logs.map((log, idx) => (
          <div key={idx} className="log-line" style={getLogStyle(log.text)}>
            <span>{log.text}</span>
            {log.annotation && (
              <span style={{ color: '#10b981', marginLeft: '12px', fontWeight: 'bold' }}>
                // {log.annotation}
              </span>
            )}
          </div>
        ))}
        <div ref={scrollRef} />
      </div>
    </div>
  );
};

export default LogTerminal;
