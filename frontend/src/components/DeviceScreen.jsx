import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import JMuxer from 'jmuxer';

const DeviceScreen = ({ target = 'com.example.app', targetWidth = 1080, targetHeight = 2400, isMockMode = false }) => {
  const canvasRef = useRef(null);
  const streamWsRef = useRef(null);
  const controlWsRef = useRef(null);
  const jmuxerRef = useRef(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [streamDebugMsg, setStreamDebugMsg] = useState("");
  const [bytesReceived, setBytesReceived] = useState(0);
  
  // Drag state for swipe
  const isDragging = useRef(false);
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
    };

    streamWsRef.current.onmessage = (event) => {
      if (!isMounted) return;
      if (typeof event.data === 'string') {
        console.warn("Stream Debug:", event.data);
        setStreamDebugMsg(prev => prev + event.data + "\n");
        return;
      }
      
      if (event.data instanceof ArrayBuffer) {
        setBytesReceived(prev => prev + event.data.byteLength);
        if (jmuxerRef.current) {
          jmuxerRef.current.feed({
            video: new Uint8Array(event.data)
          });
        }
      } else if (event.data instanceof Blob) {
        setBytesReceived(prev => prev + event.data.size);
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
    };
    
    streamWsRef.current.onerror = (e) => {
      if (!isMounted) return;
    };

    return () => {
      isMounted = false;
      if (streamWsRef.current) {
        const streamSocket = streamWsRef.current;
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
    const offsetX = e.clientX - rect.left;
    const offsetY = e.clientY - rect.top;
    
    // mapping
    const realX = Math.round((offsetX / rect.width) * targetWidth);
    const realY = Math.round((offsetY / rect.height) * targetHeight);
    
    return { realX, realY };
  };

  const sendControl = (payload) => {
    if (controlWsRef.current && controlWsRef.current.readyState === WebSocket.OPEN) {
      controlWsRef.current.send(JSON.stringify(payload));
    }
  };

  const handleMouseDown = (e) => {
    isDragging.current = true;
    const { realX, realY } = getRealCoords(e);
    startPos.current = { x: realX, y: realY };
    startTime.current = Date.now();
  };

  const handleMouseUp = (e) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    
    const { realX, realY } = getRealCoords(e);
    const duration = Date.now() - startTime.current;
    
    // If it's a quick click and distance is small, it's a tap
    const distance = Math.sqrt(Math.pow(realX - startPos.current.x, 2) + Math.pow(realY - startPos.current.y, 2));
    
    if (distance < 20 && duration < 300) {
      // Tap
      sendControl({
        action: 'tap',
        x: realX,
        y: realY
      });
    } else {
      // Swipe
      sendControl({
        action: 'swipe',
        start_x: startPos.current.x,
        start_y: startPos.current.y,
        end_x: realX,
        end_y: realY,
        duration: Math.min(duration, 2000) // cap duration
      });
    }
  };

  const handleMouseLeave = (e) => {
    if (isDragging.current) {
      handleMouseUp(e); // treat leave as release
    }
  };

  const handleKeyevent = (keycode) => {
    sendControl({
      action: 'keyevent',
      keycode: keycode
    });
  };

  return (
    <div className="device-screen-container glass-panel flex-1 min-h-0">
      <h3>Remote Device Screen</h3>
      <div className="canvas-wrapper" style={{ position: 'relative', display: 'flex', justifyContent: 'center', flex: 1, minHeight: 0 }}>
        {isMockMode ? (
          <div style={{
            height: '100%',
            width: '100%',
            aspectRatio: `${targetWidth}/${targetHeight}`,
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
            onError={(e) => {
              const err = e.target.error;
              setStreamDebugMsg(prev => prev + `[Video Error] Code ${err?.code}: ${err?.message || 'Unknown playback error'}\n`);
            }}
            style={{
              height: '100%',
              width: '100%',
              aspectRatio: `${targetWidth}/${targetHeight}`,
              backgroundColor: '#000',
              cursor: 'pointer',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: '8px',
              objectFit: 'contain'
            }}
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
          />
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
            <div style={{color: '#94a3b8'}}>Bytes Received: {bytesReceived.toLocaleString()} bytes</div>
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
};

export default DeviceScreen;
