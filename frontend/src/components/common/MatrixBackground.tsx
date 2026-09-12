import React, { useEffect, useRef } from 'react';

const WORDS = [
  'CONNECT', 'INIT_SEQ', 'HANDSHAKE', 'USER_01', 'PEER_ID',
  'MESSAGE', 'LOG_ON', 'STREAM', 'SYNCH', 'RELAY',
  'ENCRYPT', 'TOKEN', 'SESSION', 'SOCKET', 'PACKET',
  'AUTH_OK', 'KEY_EXCHANGE', 'PING', 'PONG', 'CHANNEL',
  'NODE_02', 'CLIENT', 'BUFFER', 'SECURE', 'HANDSHAKE', 
  'DATA_SYNC', 'LISTENER', 'PORT_5432', 'DB_POOL', 'TUNNEL'
];

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
}

interface FloatingWord {
  x: number;
  y: number;
  text: string;
  opacity: number;
  fadeState: 'in' | 'hold' | 'disintegrating';
  lifeTimer: number;
  holdDuration: number;
  fontSize: number;
  particles: Particle[];
}

export const MatrixBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);

    // Active floating words
    const wordsList: FloatingWord[] = [];
    const maxWords = 32;

    const spawnWord = (): FloatingWord => {
      const text = WORDS[Math.floor(Math.random() * WORDS.length)];

      // Center exclusion zone: width 480px, height 580px around screen center
      const centerX = width / 2;
      const centerY = height / 2;
      const cardHalfW = 250; 
      const cardHalfH = 300;

      let x = 0;
      let y = 0;
      let attempts = 0;

      while (attempts < 25) {
        x = Math.random() * (width - 160) + 30;
        y = Math.random() * (height - 80) + 40;

        const inCenterX = x + 100 > centerX - cardHalfW && x < centerX + cardHalfW;
        const inCenterY = y > centerY - cardHalfH && y - 20 < centerY + cardHalfH;

        if (!inCenterX || !inCenterY) {
          break; 
        }
        attempts++;
      }

      return {
        x,
        y,
        text,
        opacity: 0,
        fadeState: 'in',
        lifeTimer: 0,
        holdDuration: 120 + Math.random() * 120, 
        fontSize: Math.floor(10 + Math.random() * 4), 
        particles: [],
      };
    };

    for (let i = 0; i < 8; i++) {
      const word = spawnWord();
      word.opacity = Math.random() * 0.6;
      word.fadeState = 'hold';
      wordsList.push(word);
    }

    const render = () => {
      ctx.fillStyle = '#050505';
      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = 'rgba(255, 255, 255, 0.025)';
      for (let x = 0; x < width; x += 32) {
        for (let y = 0; y < height; y += 32) {
          ctx.fillRect(x, y, 1, 1);
        }
      }

      if (wordsList.length < maxWords && Math.random() < 0.08) {
        wordsList.push(spawnWord());
      }

      for (let i = wordsList.length - 1; i >= 0; i--) {
        const w = wordsList[i];

        if (w.fadeState === 'in') {
          w.opacity += 0.015;
          if (w.opacity >= 0.7) {
            w.opacity = 0.7;
            w.fadeState = 'hold';
          }
        } else if (w.fadeState === 'hold') {
          w.lifeTimer++;
          if (w.lifeTimer >= w.holdDuration) {
            w.fadeState = 'disintegrating';
            ctx.font = `600 ${w.fontSize}px 'JetBrains Mono', 'Courier New', monospace`;
            const textMetrics = ctx.measureText(w.text);
            const textWidth = textMetrics.width;

            const numParticles = Math.floor(w.text.length * 8);
            for (let p = 0; p < numParticles; p++) {
              const px = w.x + Math.random() * textWidth;
              const py = w.y - w.fontSize + Math.random() * w.fontSize;

              w.particles.push({
                x: px,
                y: py,
                // Эффект дуновения: плавный снос вправо и вверх
                vx: 0.6 + Math.random() * 0.4, 
                vy: -0.3 - Math.random() * 0.2, 
                life: 1,
                maxLife: 50 + Math.random() * 30,
                size: Math.random() > 0.7 ? 1.2 : 0.8,
              });
            }
          }
        } else if (w.fadeState === 'disintegrating') {
          w.opacity -= 0.02; // Плавное угасание текста
          w.x += 0.4;        // Сам затухающий текст тоже чуть-чуть сдувает вправо
          if (w.opacity < 0) w.opacity = 0;
        }

        if (w.opacity > 0) {
          ctx.font = `600 ${w.fontSize}px 'JetBrains Mono', 'Courier New', monospace`;
          ctx.fillStyle = `rgba(220, 220, 230, ${w.opacity})`;
          ctx.letterSpacing = '2px';
          ctx.fillText(w.text, w.x, w.y);
        }

        if (w.particles.length > 0) {
          for (let pIdx = w.particles.length - 1; pIdx >= 0; pIdx--) {
            const p = w.particles[pIdx];
            p.x += p.vx;
            p.y += p.vy;
            p.life++;

            const particleAlpha = (1 - p.life / p.maxLife) * 0.7;
            if (particleAlpha > 0) {
              ctx.fillStyle = `rgba(240, 240, 255, ${particleAlpha})`;
              ctx.fillRect(p.x, p.y, p.size, p.size);
            } else {
              w.particles.splice(pIdx, 1);
            }
          }
        }

        if (w.opacity <= 0 && w.particles.length === 0) {
          wordsList.splice(i, 1);
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ background: '#050505' }}
    />
  );
};