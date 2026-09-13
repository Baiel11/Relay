// Pure TypeScript WebSocket Singleton Service
// Resilient connection manager with auto-reconnection, outbox buffering, and auto-resubscription

type FrameHandler = (frame: any) => void;
type TokenProvider = () => Promise<string | null> | string | null;

class WebSocketService {
  private ws: WebSocket | null = null;
  private pingInterval: any = null;
  private reconnectTimer: any = null;
  private currentToken: string | null = null;
  private tokenProvider: TokenProvider | null = null;
  private frameHandlers: Set<FrameHandler> = new Set();
  private openCallbacks: Set<() => void> = new Set();
  private outbox: any[] = [];
  private currentConversationId: string | null = null;
  private reconnectAttempts = 0;
  private isManualClose = false;

  public setTokenProvider(provider: TokenProvider) {
    this.tokenProvider = provider;
  }

  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public isConnecting(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.CONNECTING;
  }

  public connect(token?: string | null) {
    this.isManualClose = false;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    const activeToken = token || this.currentToken;
    if (!activeToken) {
      console.warn('[Relay WS] Cannot connect: no access token available');
      return;
    }

    // Already connected or connecting with this token
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) &&
      this.currentToken === activeToken
    ) {
      return;
    }

    // Cleanup previous socket if token changed
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }

    this.currentToken = activeToken;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws?token=${activeToken}`;

    console.log(`[Relay WS] Connecting to ${wsUrl.slice(0, 40)}...`);
    const socket = new WebSocket(wsUrl);
    this.ws = socket;

    socket.onopen = () => {
      console.log('[Relay WS] WebSocket connected successfully');
      this.reconnectAttempts = 0;

      // Start 25s ping heartbeat for Redis presence TTL
      if (this.pingInterval) clearInterval(this.pingInterval);
      this.pingInterval = setInterval(() => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.sendRaw({ type: 'ping' });
        }
      }, 25000);

      // 1. Auto-resubscribe active conversation if one is selected
      if (this.currentConversationId) {
        console.log(`[Relay WS] Auto-subscribing active chat: ${this.currentConversationId}`);
        this.sendRaw({
          type: 'subscribe',
          conversation_id: this.currentConversationId,
          subscribed: true,
        });
        this.sendRaw({
          type: 'mark_read',
          conversation_id: this.currentConversationId,
        });
      }

      // 2. Flush any queued outbound messages
      if (this.outbox.length > 0) {
        console.log(`[Relay WS] Flushing ${this.outbox.length} buffered outbound frames`);
        while (this.outbox.length > 0) {
          const item = this.outbox.shift();
          this.sendRaw(item);
        }
      }

      // 3. Trigger registered on-open hooks
      this.openCallbacks.forEach((cb) => {
        try {
          cb();
        } catch (err) {
          console.error('[Relay WS] Error in onOpen callback:', err);
        }
      });
    };

    socket.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data);
        this.frameHandlers.forEach((handler) => {
          try {
            handler(frame);
          } catch (err) {
            console.error('[Relay WS] Error in frame handler:', err);
          }
        });
      } catch (err) {
        console.error('[Relay WS] Failed to parse incoming frame:', err);
      }
    };

    socket.onclose = (event) => {
      console.warn(`[Relay WS] Socket closed (code=${event.code}, reason=${event.reason || 'none'})`);
      if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
      this.ws = null;

      if (!this.isManualClose) {
        this.scheduleReconnect();
      }
    };

    socket.onerror = (err) => {
      console.warn('[Relay WS] Socket error:', err);
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts - 1), 10000);
    console.log(`[Relay WS] Scheduling reconnection in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})...`);

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      if (this.isManualClose) return;

      // Attempt to retrieve fresh token if provider registered
      if (this.tokenProvider) {
        try {
          const freshToken = await this.tokenProvider();
          if (freshToken) {
            this.currentToken = freshToken;
          }
        } catch {
          // ignore provider error and try with current token
        }
      }

      if (this.currentToken) {
        this.connect(this.currentToken);
      }
    }, delay);
  }

  public disconnect() {
    this.isManualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.ws) {
      try {
        this.ws.close(1000);
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.currentToken = null;
    this.outbox = [];
    this.currentConversationId = null;
  }

  private sendRaw(payload: any): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  public send(payload: any): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
      return true;
    }

    // If socket is connecting, buffer payload into outbox to flush on open
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
      console.log(`[Relay WS] Buffering ${payload.type} frame until socket is open`);
      this.outbox.push(payload);
      return true;
    }

    // Socket closed, attempt reconnect if we have token
    if (this.currentToken && !this.isManualClose) {
      this.outbox.push(payload);
      this.connect();
    }
    return false;
  }

  public subscribeConversation(conversationId: string) {
    this.currentConversationId = conversationId;
    return this.send({
      type: 'subscribe',
      conversation_id: conversationId,
      subscribed: true,
    });
  }

  public markRead(conversationId: string) {
    return this.send({
      type: 'mark_read',
      conversation_id: conversationId,
    });
  }

  public sendTyping(conversationId: string, isTyping: boolean) {
    return this.send({
      type: 'typing',
      conversation_id: conversationId,
      is_typing: isTyping,
    });
  }

  public sendMessage(conversationId: string, content: string) {
    return this.send({
      type: 'send_message',
      conversation_id: conversationId,
      content,
    });
  }

  public addFrameHandler(handler: FrameHandler): () => void {
    this.frameHandlers.add(handler);
    return () => {
      this.frameHandlers.delete(handler);
    };
  }

  public addOpenCallback(cb: () => void): () => void {
    this.openCallbacks.add(cb);
    return () => {
      this.openCallbacks.delete(cb);
    };
  }
}

export const websocketService = new WebSocketService();
