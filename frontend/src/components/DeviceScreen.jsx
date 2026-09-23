import React, { useEffect, useRef, useState, memo } from 'react';
import { createPortal } from 'react-dom';
import JMuxer from 'jmuxer';
import { Camera, Video } from 'lucide-react';

const DeviceScreen = memo(({ target = 'com.example.app', targetWidth = 1080, targetHeight = 2400, isMockMode = false }) => {
  const canvasRef = useRef(null);
  const streamWsRef = useRef(null);
  const controlWsRef = useRef(null);
  const jmuxerRef = useRef(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [streamDebugMsg, setStreamDebugMsg] = useState("");
  const bytesRef = useRef(0);
  const bytesTextRef = useRef(null);
  
  // Debug states for Click and Move separately
  const [frontendDebugClick, setFrontendDebugClick] = useState('');
  const [backendDebugClick, setBackendDebugClick] = useState('');
  const [frontendDebugMove, setFrontendDebugMove] = useState('');
  const [backendDebugMove, setBackendDebugMove] = useState('');
  
  // Recording state
  const [isRecordingDevice, setIsRecordingDevice] = useState(false);
  const mediaRecorderRef = useRef(null);
  const recordedChunks = useRef([]);

  // Video aspect ratio state
  const [videoAspect, setVideoAspect] = useState(`${targetWidth}/${targetHeight}`);
  
  // Visual Drag Calibration State
  const [isVisualCalibrating, setIsVisualCalibrating] = useState(false);
  const calibDragStart = useRef(null);
  const [calibDragCurrent, setCalibDragCurrent] = useState(null);
  
  const [calibOffsetX, setCalibOffsetX] = useState(0);
  const [calibOffsetY, setCalibOffsetY] = useState(0);
  
  // Drag state for swipe
  const isDragging = useRef(false);
  const dragStartCoords = useRef(null);
  const dragSlopExceeded = useRef(false);
  const lastMoveTime = useRef(0);
  const startPos = useRef({ x: 0, y: 0 });
  const startTime = useRef(0);

  useEffect(() => {
    let isMounted = true;
    if (isMockMode) return;
    
    setStreamDebugMsg("");

    // Setup Control WebSocket
    const controlUrl = new URL('ws://127.0.0.1:8000/ws/control');
    controlUrl.searchParams.set('target', target);
    controlUrl.searchParams.set('mock', 'false');
    controlWsRef.current = new WebSocket(controlUrl.toString());
    controlWsRef.current.onopen = () => {
      if (!isMounted) return;
      console.log('Control WS connected');
    };
    controlWsRef.current.onerror = (e) => {
      if (!isMounted) return;
    };
    controlWsRef.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'debug_click') {
          setBackendDebugClick(data.info);
        } else if (data.type === 'debug_move') {
          setBackendDebugMove(data.info);
        } else if (data.type === 'stream_debug') {
        }
      } catch (err) {}
    };

    // Setup Stream WebSocket
    const streamUrl = new URL('ws://127.0.0.1:8000/ws/stream');
    streamUrl.searchParams.set('target', target);
    streamUrl.searchParams.set('mock', 'false');
    streamWsRef.current = new WebSocket(streamUrl.toString());
    streamWsRef.current.binaryType = 'arraybuffer';
    
    streamWsRef.current.onopen = () => {
      if (!isMounted) return;
      console.log('Stream WS connected');
      setIsStreaming(true);
      
      jmuxerRef.current = new JMuxer({
        node: canvasRef.current,
        mode: 'video',
        flushingTime: 0,
        fps: 30,
        debug: false
      });
      
      const bytesInterval = setInterval(() => {
        if (isMounted && bytesTextRef.current) {
          bytesTextRef.current.innerText = `Bytes Received: ${bytesRef.current.toLocaleString()} bytes`;
        }
      }, 1000);
      
      streamWsRef.current.bytesInterval = bytesInterval;
    };

    streamWsRef.current.onmessage = (event) => {
      if (!isMounted) return;
      if (typeof event.data === 'string') {
        console.warn("Stream Debug:", event.data);
        setStreamDebugMsg(prev => prev + event.data + "\n");
        return;
      }
      
      if (event.data instanceof ArrayBuffer) {
        bytesRef.current += event.data.byteLength;
        if (jmuxerRef.current) {
          jmuxerRef.current.feed({
            video: new Uint8Array(event.data)
          });
        }
      } else if (event.data instanceof Blob) {
        bytesRef.current += event.data.size;
        event.data.arrayBuffer().then(buffer => {
          if (jmuxerRef.current) {
            jmuxerRef.current.feed({
              video: new Uint8Array(buffer)
            });
          }
        });
      }
    };

    streamWsRef.current.onclose = () => {
      if (!isMounted) return;
      console.log('Stream WS closed');
      setIsStreaming(false);
      if (streamWsRef.current && streamWsRef.current.bytesInterval) {
        clearInterval(streamWsRef.current.bytesInterval);
      }
    };
    
    streamWsRef.current.onerror = (e) => {
      if (!isMounted) return;
    };

    return () => {
      isMounted = false;
      if (streamWsRef.current) {
        const streamSocket = streamWsRef.current;
        if (streamSocket.bytesInterval) clearInterval(streamSocket.bytesInterval);
        if (streamSocket.readyState === WebSocket.CONNECTING) {
          streamSocket.onopen = () => streamSocket.close();
        } else if (streamSocket.readyState === WebSocket.OPEN) {
          streamSocket.close();
        }
        streamWsRef.current = null;
      }
      if (controlWsRef.current) {
        const controlSocket = controlWsRef.current;
        if (controlSocket.readyState === WebSocket.CONNECTING) {
          controlSocket.onopen = () => controlSocket.close();
        } else if (controlSocket.readyState === WebSocket.OPEN) {
          controlSocket.close();
        }
        controlWsRef.current = null;
      }
      if (jmuxerRef.current) {
        jmuxerRef.current.destroy();
        jmuxerRef.current = null;
      }
    };
  }, [target, isMockMode]);

  const getRealCoords = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    let clientX, clientY;
    if (e.changedTouches && e.changedTouches.length > 0) {
      clientX = e.changedTouches[0].clientX;
      clientY = e.changedTouches[0].clientY;
    } else if (e.touches && e.touches.length > 0) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }
    
    const offsetX = clientX - rect.left;
    const offsetY = clientY - rect.top;
    
    // mapping
    const canvasX = clientX - rect.left;
    const canvasY = clientY - rect.top;
    const relX = canvasX / rect.width;
    const relY = canvasY / rect.height;
    
    return { relX, relY, canvasX, canvasY, rectWidth: rect.width, rectHeight: rect.height };
  };

  const sendControl = (payload) => {
    if (controlWsRef.current && controlWsRef.current.readyState === WebSocket.OPEN) {
      controlWsRef.current.send(JSON.stringify(payload));
    }
  };

  const handleMouseDown = (e) => {
    isDragging.current = true;
    dragSlopExceeded.current = false;
    const { relX, relY, canvasX, canvasY, rectWidth, rectHeight } = getRealCoords(e);
    
    dragStartCoords.current = { canvasX, canvasY };

    if (isVisualCalibrating) {
      calibDragStart.current = { relX, relY, canvasX, canvasY };
      setCalibDragCurrent({ canvasX, canvasY });
      return; // Intercept click for calibration
    }

    const finalRelX = relX + calibOffsetX;
    const finalRelY = relY + calibOffsetY;
    
    setFrontendDebugClick(`Frontend (Click): => relX=${finalRelX.toFixed(3)}, relY=${finalRelY.toFixed(3)}`);
    sendControl({ action: 'down', relX: finalRelX, relY: finalRelY });
  };

  const handleMouseMove = (e) => {
    const { relX, relY, canvasX, canvasY, rectWidth, rectHeight } = getRealCoords(e);
    const finalRelX = relX + calibOffsetX;
    const finalRelY = relY + calibOffsetY;

    if (!isDragging.current) {
      // Just hover
      const now = Date.now();
      if (now - lastMoveTime.current < 50) return; // limit to 20fps
      lastMoveTime.current = now;
      sendControl({ action: 'hover', relX: finalRelX, relY: finalRelY });
      return;
    }

    // Apply 5 pixel slop threshold before considering it a swipe
    if (!dragSlopExceeded.current && dragStartCoords.current) {
      const dist = Math.hypot(canvasX - dragStartCoords.current.canvasX, canvasY - dragStartCoords.current.canvasY);
      if (dist < 5) return;
      dragSlopExceeded.current = true; // Mark as a real swipe
    }

    if (isVisualCalibrating && calibDragStart.current) {
      setCalibDragCurrent({ canvasX, canvasY });
      return;
    }
    
    setFrontendDebugMove(`Frontend (Move): => relX=${finalRelX.toFixed(3)}, relY=${finalRelY.toFixed(3)}`);
    sendControl({ action: 'move', relX: finalRelX, relY: finalRelY });
  };

  const handleMouseUp = (e) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    const { relX, relY } = getRealCoords(e);

    if (isVisualCalibrating && calibDragStart.current) {
      const deltaRelX = relX - calibDragStart.current.relX;
      const deltaRelY = relY - calibDragStart.current.relY;
      setCalibOffsetX(prev => prev + deltaRelX);
      setCalibOffsetY(prev => prev + deltaRelY);
      calibDragStart.current = null;
      setCalibDragCurrent(null);
      setIsVisualCalibrating(false); // auto-close after 1 drag
      return;
    }

    const finalRelX = relX + calibOffsetX;
    const finalRelY = relY + calibOffsetY;
    sendControl({ action: 'up', relX: finalRelX, relY: finalRelY });
  };

  const handleMouseLeave = (e) => {
    if (isDragging.current) {
      handleMouseUp(e); // treat leave as release
    }
  };


  const handleTouchStart = (e) => {
    if (e.touches.length > 0) {
      handleMouseDown(e);
    }
  };

  const handleTouchMove = (e) => {
    if (e.touches.length > 0) {
      handleMouseMove(e);
    }
  };

  const handleTouchEnd = (e) => {
    handleMouseUp(e);
  };

  const handleKeyevent = (keycode) => {

    sendControl({
      action: 'keyevent',
      keycode: keycode
    });
  };

  const handleScreenshot = () => {
    if (!canvasRef.current) return;
    const video = canvasRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `screenshot_${new Date().getTime()}.png`;
    a.click();
  };

  const handleRecordDevice = () => {
    if (isRecordingDevice) {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      setIsRecordingDevice(false);
    } else {
      if (!canvasRef.current) return;
      const stream = canvasRef.current.captureStream();
      recordedChunks.current = [];
      try {
        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm; codecs=vp9' });
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            recordedChunks.current.push(e.data);
          }
        };
        recorder.onstop = () => {
          const blob = new Blob(recordedChunks.current, { type: 'video/webm' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `record_${new Date().getTime()}.webm`;
          a.click();
          URL.revokeObjectURL(url);
        };
        recorder.start();
        mediaRecorderRef.current = recorder;
        setIsRecordingDevice(true);
      } catch (err) {
        console.error("MediaRecorder setup failed:", err);
      }
    }
  };

  return (
    <div className="device-screen-container glass-panel flex-1 min-h-0">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', padding: '0 4px' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', fontWeight: '600', letterSpacing: '0.02em' }}>Remote Device Screen</h3>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--accent-color)', border: 'none', borderRadius: '6px', color: '#fff', fontSize: '0.85rem', fontWeight: '500', cursor: 'pointer', whiteSpace: 'nowrap', boxShadow: '0 2px 4px rgba(59, 130, 246, 0.3)' }} onClick={handleScreenshot}>
            <Camera size={16} /> 截圖
          </button>
          <button style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px', background: isRecordingDevice ? '#e11d48' : 'rgba(255, 255, 255, 0.08)', border: isRecordingDevice ? '1px solid #be123c' : '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '6px', color: '#fff', fontSize: '0.85rem', fontWeight: '500', cursor: 'pointer', transition: 'all 0.2s ease', whiteSpace: 'nowrap' }} onClick={handleRecordDevice}>
            <Video size={16} /> {isRecordingDevice ? '停止錄製' : '錄影'}
          </button>
        </div>
      </div>
      <div className="canvas-wrapper" style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, minHeight: 0 }}>
        {isMockMode ? (
          <div style={{
            height: '100%',
            maxWidth: '100%',
            aspectRatio: videoAspect,
            background: 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: '12px',
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '5px',
              background: 'var(--accent-color)',
              boxShadow: '0 0 15px var(--accent-color), 0 0 30px var(--accent-color)',
              animation: 'scan 2.5s ease-in-out infinite'
            }} />
            <div style={{
              color: 'var(--accent-color)',
              fontWeight: 700,
              fontSize: '1.2rem',
              letterSpacing: '0.05em'
            }}>Mock Mode Active</div>
            <style>{`
              @keyframes scan {
                0% { top: 0; opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { top: calc(100% - 5px); opacity: 0; }
              }
            `}</style>
          </div>
        ) : (
          <video
            ref={canvasRef}
            autoPlay
            muted
            playsInline
            onLoadedMetadata={(e) => {
              if (e.target.videoWidth && e.target.videoHeight) {
                setVideoAspect(`${e.target.videoWidth}/${e.target.videoHeight}`);
              }
            }}
            onError={(e) => {
              const err = e.target.error;
              setStreamDebugMsg(prev => prev + `[Video Error] Code ${err?.code}: ${err?.message || 'Unknown playback error'}\n`);
            }}
            style={{
              height: '100%',
              maxWidth: '100%',
              aspectRatio: videoAspect,
              backgroundColor: '#000',
              cursor: 'default',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: '8px',
              objectFit: 'fill'
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
            onDragStart={(e) => e.preventDefault()}
          />
        )}
        
        {/* Visual Calibration Overlay Line */}
        {isVisualCalibrating && calibDragStart.current && calibDragCurrent && (
          <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 10 }}>
            <line 
              x1={calibDragStart.current.canvasX} 
              y1={calibDragStart.current.canvasY} 
              x2={calibDragCurrent.canvasX} 
              y2={calibDragCurrent.canvasY} 
              stroke="#10b981" 
              strokeWidth="3" 
              strokeDasharray="5,5" 
            />
            <circle cx={calibDragStart.current.canvasX} cy={calibDragStart.current.canvasY} r="4" fill="#f43f5e" />
            <circle cx={calibDragCurrent.canvasX} cy={calibDragCurrent.canvasY} r="4" fill="#10b981" />
          </svg>
        )}

        {isVisualCalibrating && (
          <div style={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)', background: 'rgba(16,185,129,0.9)', color: '#fff', padding: '12px 24px', borderRadius: '8px', fontSize: '14px', fontWeight: 'bold', textAlign: 'center', boxShadow: '0 4px 12px rgba(0,0,0,0.5)', zIndex: 10, pointerEvents: 'none' }}>
            教學：請在畫面上，從【實際錯誤發生的位置】，<br/>按住滑鼠【拖曳】到【你原本想點擊的目標位置】！<br/>系統會自動算出偏差值並修正。
          </div>
        )}

        {!isMockMode && !isStreaming && !streamDebugMsg && (
          <div style={{ position: 'absolute', top: '50%', color: 'var(--text-secondary)' }}>
            Waiting for stream...
          </div>
        )}
        {document.getElementById('stream-status-portal') && createPortal(
          <div style={{
            background: 'rgba(0,0,0,0.4)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#10b981',
            padding: '10px',
            borderRadius: '8px',
            fontFamily: 'monospace',
            fontSize: '11px',
            wordWrap: 'break-word',
            whiteSpace: 'pre-wrap'
          }}>
            <div>Stream WS: <span style={{color: isStreaming ? '#10b981' : '#f43f5e'}}>{isStreaming ? "Connected" : "Disconnected"}</span></div>
            <div style={{color: '#94a3b8'}} ref={bytesTextRef}>Bytes Received: 0 bytes</div>
            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.2)' }}>
              <div style={{ fontWeight: 'bold', color: '#fff', marginBottom: '5px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>測試資訊 (Debug Info)</span>
              </div>
              
              <div style={{ fontSize: '11px', marginBottom: '8px', borderBottom: '1px dotted rgba(255,255,255,0.1)', paddingBottom: '8px' }}>
                <div style={{ color: '#fff', fontWeight: 'bold', marginBottom: '4px' }}>📌 【點擊資訊 (Click)】</div>
                <span style={{ color: '#fbbf24' }}>{frontendDebugClick || "Waiting for click..."}</span><br/>
                <span style={{ color: '#38bdf8' }}>{backendDebugClick || "Waiting for backend..."}</span>
              </div>
              
              <div style={{ fontSize: '11px', marginBottom: '4px' }}>
                <div style={{ color: '#fff', fontWeight: 'bold', marginBottom: '4px' }}>🔄 【滑動資訊 (Swipe/Move)】</div>
                <span style={{ color: '#fbbf24' }}>{frontendDebugMove || "Waiting for move..."}</span><br/>
                <span style={{ color: '#38bdf8' }}>{backendDebugMove || "Waiting for backend..."}</span>
              </div>
            </div>
            
            {streamDebugMsg && (
              <div style={{ color: '#f43f5e', marginTop: '5px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '5px' }}>
                {streamDebugMsg}
              </div>
            )}
          </div>,
          document.getElementById('stream-status-portal')
        )}
      </div>
      <div className="device-controls" style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem', paddingBottom: '0.5rem' }}>
        <button style={{ flex: 1, maxWidth: '120px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem' }} onClick={() => handleKeyevent(4)}>Back</button>
        <button style={{ flex: 1, maxWidth: '120px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem' }} onClick={() => handleKeyevent(3)}>Home</button>
        <button style={{ flex: 1, maxWidth: '120px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem' }} onClick={() => handleKeyevent(187)}>Recent</button>
      </div>
    </div>
  );
});

export default DeviceScreen;
