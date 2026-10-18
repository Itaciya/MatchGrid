import { createContext, useContext, useEffect, useState } from 'react';
import { wsClient } from './websocketClient';

const RealtimeContext = createContext({ status: 'idle' });

export function RealtimeProvider({ children }) {
  const [status, setStatus] = useState(wsClient.status);

  useEffect(() => {
    const off = wsClient.onStatus(setStatus);
    wsClient.connect();
    return () => { off(); wsClient.disconnect(); };
  }, []);

  return <RealtimeContext.Provider value={{ status }}>{children}</RealtimeContext.Provider>;
}

export const useRealtimeStatus = () => useContext(RealtimeContext).status;

export function useRealtimeEvent(type, handler) {
  useEffect(() => wsClient.on(type, handler), [type, handler]);
}
