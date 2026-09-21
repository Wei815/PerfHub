import { useState, useEffect, useRef, useCallback } from 'react';

const MAX_DATA_POINTS = 60; // 60 seconds sliding window

export function useWebSocket(url, target = "com.example.app", isMockMode = false) {
  const [data, setData] = useState([]);
  const [currentMetrics, setCurrentMetrics] = useState({ cpu_percent: 0, memory_mb: 0, fps: 0, rx_kbps: 0, tx_kbps: 0 });
  const [deviceInfo, setDeviceInfo] = useState({
    model: '等待數據...',
    resolution_w: 1080,
    resolution_h: 2400,
    target_package: '等待數據...',
    os_version: '等待數據...'
  });
  const [status, setStatus] = useState('disconnected'); // 'connected', 'disconnected', 'error'
  const [errorMessage, setErrorMessage] = useState('');
  const [isRecording, setIsRecording] = useState(true);
  
  const ws = useRef(null);
  const dataRef = useRef([]);
  const isRecordingRef = useRef(isRecording);
  const mockIntervalRef = useRef(null);
  const mockMetricsRef = useRef({ cpu: 30.0, memory: 300.0, fps: 60.0, rx: 0, tx: 0 });

  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  const connect = useCallback(() => {
    if (ws.current) {
        ws.current.close();
        ws.current = null;
    }
    if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current);
        mockIntervalRef.current = null;
    }

    if (isMockMode) {
      setStatus('connected');
      setErrorMessage('');
      setDeviceInfo({
        model: 'Mock Phone (Frontend)',
        resolution_w: 1080,
        resolution_h: 2400,
        target_package: target,
        os_version: 'Frontend Mock OS'
      });

      mockIntervalRef.current = setInterval(() => {
        const m = mockMetricsRef.current;
        m.cpu = Math.max(0, Math.min(100, m.cpu + (Math.random() * 6 - 3)));
        m.memory = Math.max(100, Math.min(2048, m.memory + (Math.random() * 40 - 20)));
        m.fps = Math.max(10, Math.min(60, m.fps + (Math.random() * 4 - 2)));
        m.rx = Math.max(0, m.rx + (Math.random() * 100 - 50));
        m.tx = Math.max(0, m.tx + (Math.random() * 50 - 25));

        const metricsObj = {
          cpu_percent: parseFloat(m.cpu.toFixed(1)),
          memory_mb: parseFloat(m.memory.toFixed(1)),
          fps: Math.round(m.fps),
          rx_kbps: parseFloat(m.rx.toFixed(1)),
          tx_kbps: parseFloat(m.tx.toFixed(1))
        };
        const timestamp = new Date().toISOString();

        setCurrentMetrics(metricsObj);

        if (isRecordingRef.current) {
          const newPoint = {
            time: new Date(timestamp).toLocaleTimeString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            cpu: metricsObj.cpu_percent,
            memory: metricsObj.memory_mb,
            fps: metricsObj.fps,
            rx: metricsObj.rx_kbps,
            tx: metricsObj.tx_kbps,
            timestamp: timestamp
          };
          setData((prevData) => {
            const newData = [...prevData, newPoint];
            return newData.length > MAX_DATA_POINTS ? newData.slice(newData.length - MAX_DATA_POINTS) : newData;
          });
        }
      }, 1000);
      return;
    }

    setStatus('connecting');
    const targetUrl = new URL(url);
    targetUrl.searchParams.set('target', target);
    targetUrl.searchParams.set('mock', 'false');
    ws.current = new WebSocket(targetUrl.toString());

    ws.current.onopen = () => {
      console.log('WS connected to', targetUrl.toString());
      setStatus('connected');
      setErrorMessage('');
    };

    ws.current.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        
        if (payload.status_code !== 200) {
          setStatus('error');
          setErrorMessage(payload.error_message || 'Unknown error');
          return;
        }
        
        setStatus('connected');
        setErrorMessage('');
        
        if (payload.device_info) {
          setDeviceInfo(payload.device_info);
        }

        const newPoint = {
          time: new Date(payload.timestamp).toLocaleTimeString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          cpu: payload.metrics.cpu_percent,
          memory: payload.metrics.memory_mb,
          fps: payload.metrics.fps,
          rx: payload.metrics.rx_kbps,
          tx: payload.metrics.tx_kbps,
          timestamp: payload.timestamp
        };

        setCurrentMetrics(payload.metrics);

        if (isRecordingRef.current) {
            setData((prevData) => {
                const newData = [...prevData, newPoint];
                if (newData.length > MAX_DATA_POINTS) {
                  return newData.slice(newData.length - MAX_DATA_POINTS);
                }
                return newData;
            });
            dataRef.current = data;
        }
      } catch (err) {
        console.error("Failed to parse message:", err);
      }
    };

    ws.current.onclose = () => {
      console.log('WS closed');
      setStatus('disconnected');
      ws.current = null;
    };

    ws.current.onerror = (error) => {
      console.error('WS error:', error);
      setStatus('error');
      setErrorMessage('WebSocket connection failed');
    };
  }, [url, target, isMockMode]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
    if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current);
        mockIntervalRef.current = null;
    }
  }, []);

  const startRecording = useCallback(() => setIsRecording(true), []);
  const pauseRecording = useCallback(() => setIsRecording(false), []);
  const clearData = useCallback(() => {
    setData([]);
    dataRef.current = [];
  }, []);

  const exportCSV = useCallback(() => {
    if (data.length === 0) return;
    
    const headers = ['Timestamp', 'Time', 'CPU (%)', 'Memory (MB)', 'FPS', 'Rx (KB/s)', 'Tx (KB/s)'];
    const rows = data.map(d => [d.timestamp, d.time, d.cpu, d.memory, d.fps, d.rx, d.tx]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(e => e.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `perfhub_report_${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [data]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Update recording state handler dependency correctly
  useEffect(() => {
    if(ws.current) {
      // Re-bind to use updated isRecording if needed, though state is accessed in setter
    }
  }, [isRecording]);

  return {
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
  };
}
