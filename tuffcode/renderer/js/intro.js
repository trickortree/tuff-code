(() => {
  window.TUFF_ACCENTS = [
    { id: 'electric', name: 'Blue', a: '#3574f0', b: '#22d3ee' },
    { id: 'neon', name: 'Neon', a: '#8b5cf6', b: '#ec4899' },
    { id: 'toxic', name: 'Toxic', a: '#22c55e', b: '#a3e635' },
    { id: 'sunset', name: 'Sunset', a: '#f97316', b: '#f43f5e' },
  ];

  const $ = (id) => document.getElementById(id);
  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const SPRITES = 24;
  const TAGLINE = 'coding made easy.';
  const FONT = '"Segoe UI Black", "Arial Black", Impact, sans-serif';

  function shuffle(a) {
    for (let i = a.length - 1; i > 0; i--) {
      const j = (Math.random() * (i + 1)) | 0;
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function play({ initial, onReveal }) {
    return new Promise((resolve) => {
      const intro = $('intro'), canvas = $('intro-canvas'), ctx = canvas.getContext('2d');
      const titleEl = $('intro-title'), tagEl = $('intro-tagline'), card = $('intro-card'), flash = $('intro-flash'), skip = $('intro-skip');

      const accent = initial || window.TUFF_ACCENTS[0];
      let W = 0, H = 0, DPR = 1;
      let parts = [];
      let dust = [];
      let rings = [];
      let sprites = [];
      let colors = [];
      let stage = 'drift';
      let layout = 'big';
      let exitAt = 0;
      let raf = 0;
      let last = performance.now();
      const start = last;
      const timers = [];
      const mouse = { x: -1e4, y: -1e4 };
      const later = (ms, fn) => timers.push(setTimeout(fn, ms));

      intro.classList.remove('hidden', 'fade-out', 'shake');
      titleEl.className = 'intro-title';
      card.className = 'intro-card';
      flash.className = 'intro-flash';
      skip.classList.remove('gone');
      tagEl.innerHTML = '';

      // ---------- colors ----------
      function buildSprites() {
        const A = rgb(accent.a), B = rgb(accent.b);
        sprites = [];
        colors = [];
        for (let k = 0; k < SPRITES; k++) {
          const c = mix(A, B, k / (SPRITES - 1));
          const s = document.createElement('canvas');
          s.width = s.height = 32;
          const g = s.getContext('2d');
          const grad = g.createRadialGradient(16, 16, 0, 16, 16, 16);
          grad.addColorStop(0, 'rgba(255,255,255,1)');
          grad.addColorStop(0.22, `rgba(${c},0.95)`);
          grad.addColorStop(0.5, `rgba(${c},0.25)`);
          grad.addColorStop(1, `rgba(${c},0)`);
          g.fillStyle = grad;
          g.fillRect(0, 0, 32, 32);
          sprites.push(s);
          colors.push(`rgb(${mix(c, [255, 255, 255], 0.25)})`);
        }
      }

      // ---------- layout ----------
      const bigFs = () => Math.min(W * 0.24, H * 0.34);
      const smallFs = () => Math.min(W * 0.13, H * 0.17);
      const wordFs = () => (layout === 'big' ? bigFs() : smallFs());
      const wordY = () => (layout === 'big' ? H * 0.4 : H * 0.12 + smallFs() * 0.5);

      function sampleText(fs, cy, gap) {
        const c = document.createElement('canvas');
        c.width = W;
        c.height = H;
        const g = c.getContext('2d', { willReadFrequently: true });
        g.fillStyle = '#fff';
        g.textAlign = 'center';
        g.textBaseline = 'middle';
        g.letterSpacing = `${Math.round(fs * 0.05)}px`;
        g.font = `900 ${fs}px ${FONT}`;
        const width = g.measureText('TUFF').width;
        if (width > W * 0.86) {
          fs *= (W * 0.86) / width;
          g.font = `900 ${fs}px ${FONT}`;
        }
        g.fillText('TUFF', W / 2, cy);
        const d = g.getImageData(0, 0, W, H).data;
        const pts = [];
        const step = Math.max(2, Math.round(gap));
        for (let y = 0; y < H; y += step) {
          for (let x = 0; x < W; x += step) {
            if (d[(y * W + x) * 4 + 3] > 140) pts.push({ x: x + (Math.random() - 0.5) * step * 0.5, y: y + (Math.random() - 0.5) * step * 0.5 });
          }
        }
        return shuffle(pts);
      }

      function retarget(sweep) {
        const fs = wordFs();
        const big = bigFs();
        const baseGap = Math.max(4, Math.round(big / 30));
        const gap = layout === 'big' ? baseGap : (baseGap * fs) / big;
        const pts = sampleText(fs, wordY(), gap);
        if (!pts.length) return;
        if (!parts.length) {
          const n = Math.min(pts.length, 3200);
          for (let i = 0; i < n; i++) {
            parts.push({
              x: Math.random() * W, y: Math.random() * H,
              vx: (Math.random() - 0.5) * 2, vy: (Math.random() - 0.5) * 2,
              tx: 0, ty: 0, delay: Infinity, seed: Math.random() * 1000,
              size: 2.2 + Math.random() * 2.6, alpha: 0,
            });
          }
        }
        const now = performance.now();
        parts.forEach((p, i) => {
          const t = pts[i % pts.length];
          p.tx = t.x;
          p.ty = t.y;
          if (sweep) p.delay = now + (t.x / W) * 650 + Math.random() * 250;
        });
        placeText();
      }

      function placeText() {
        const fs = wordFs();
        const titleTop = wordY() + fs * (layout === 'big' ? 0.5 : 0.42) + 10;
        titleEl.style.top = `${titleTop}px`;
        card.style.top = `${titleTop + titleEl.offsetHeight + 26}px`;
      }

      function resize() {
        DPR = window.devicePixelRatio || 1;
        W = innerWidth;
        H = innerHeight;
        canvas.width = W * DPR;
        canvas.height = H * DPR;
        ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
        ctx.fillStyle = '#05060a';
        ctx.fillRect(0, 0, W, H);
        if (parts.length && stage !== 'exit') retarget(false);
      }

      // ---------- stages ----------
      function form() {
        if (stage !== 'drift') return;
        stage = 'form';
        retarget(true);
      }

      function boom() {
        if (stage === 'title' || stage === 'card' || stage === 'exit') return;
        if (stage === 'drift') form();
        stage = 'title';
        rings.push({ x: W / 2, y: wordY(), r: 20, a: 1 }, { x: W / 2, y: wordY(), r: 0, a: 0.6 });
        intro.classList.remove('shake');
        void intro.offsetWidth;
        intro.classList.add('shake');
        titleEl.classList.add('show');
        typeTagline();
      }

      let typing = 0;
      function typeTagline() {
        let i = 0;
        clearInterval(typing);
        typing = setInterval(() => {
          i++;
          tagEl.innerHTML = TAGLINE.slice(0, i) + '<span class="caret"></span>';
          if (i >= TAGLINE.length) {
            clearInterval(typing);
            tagEl.innerHTML = 'coding made <span class="kw">easy</span>.<span class="caret"></span>';
          }
        }, 55);
      }

      function showCard() {
        if (stage === 'card' || stage === 'exit') return;
        if (stage !== 'title') boom();
        stage = 'card';
        layout = 'small';
        retarget(false);
        setTimeout(() => {
          if (stage !== 'card') return;
          card.classList.add('show');
          $('intro-start').focus({ preventScroll: true });
        }, 550);
      }

      function exit() {
        if (stage === 'exit') return;
        stage = 'exit';
        exitAt = performance.now();
        timers.forEach(clearTimeout);
        clearInterval(typing);
        skip.classList.add('gone');
        card.classList.remove('show');
        card.classList.add('leave');
        titleEl.classList.add('leave');
        rings.push({ x: W / 2, y: wordY(), r: 0, a: 1 });
        setTimeout(() => flash.classList.add('on'), 700);
        setTimeout(() => {
          onReveal && onReveal();
          flash.classList.add('off');
          intro.classList.add('fade-out');
        }, 900);
        setTimeout(finish, 1750);
      }

      function finish() {
        cancelAnimationFrame(raf);
        removeEventListener('resize', resize);
        removeEventListener('keydown', onKey, true);
        intro.removeEventListener('mousemove', onMouse);
        intro.classList.add('hidden');
        intro.classList.remove('fade-out', 'shake');
        resolve(accent);
      }

      // ---------- input ----------
      const onMouse = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; };
      const onKey = (e) => {
        if (e.key === 'Escape') { e.preventDefault(); exit(); }
        else if (e.key === 'Enter') { e.preventDefault(); stage === 'card' ? exit() : showCard(); }
      };
      intro.addEventListener('mousemove', onMouse);
      intro.onmouseleave = () => { mouse.x = mouse.y = -1e4; };
      intro.onclick = (e) => { if (stage !== 'card' && stage !== 'exit' && !e.target.closest('button')) showCard(); };
      addEventListener('keydown', onKey, true);
      addEventListener('resize', resize);
      skip.onclick = exit;
      $('intro-start').onclick = exit;

      // ---------- render loop ----------
      function frame(now) {
        const dt = clamp((now - last) / 16.67, 0.2, 3);
        last = now;
        const t = now - start;
        const exitT = stage === 'exit' ? (now - exitAt) / 1000 : 0;

        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = stage === 'exit' ? 'rgba(5,6,10,0.2)' : 'rgba(5,6,10,0.3)';
        ctx.fillRect(0, 0, W, H);

        // nebula
        const A = rgb(accent.a), B = rgb(accent.b);
        const neb = (cx, cy, r, c, a) => {
          const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
          g.addColorStop(0, `rgba(${c},${a})`);
          g.addColorStop(1, `rgba(${c},0)`);
          ctx.fillStyle = g;
          ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
        };
        const glow = clamp(t / 2500, 0, 1) * 0.05;
        neb(W * (0.3 + Math.sin(t / 4100) * 0.1), H * (0.4 + Math.cos(t / 3700) * 0.12), Math.max(W, H) * 0.5, A, glow);
        neb(W * (0.7 + Math.cos(t / 4600) * 0.1), H * (0.55 + Math.sin(t / 3900) * 0.1), Math.max(W, H) * 0.45, B, glow);

        ctx.globalCompositeOperation = 'lighter';

        // dust
        for (const d of dust) {
          d.x += d.vx * dt;
          d.y += d.vy * dt;
          if (stage === 'exit') {
            d.vx += (d.x - W / 2) * 0.002 * dt * (1 + exitT * 8);
            d.vy += (d.y - H / 2) * 0.002 * dt * (1 + exitT * 8);
          } else {
            if (d.x < -10) d.x = W + 10; if (d.x > W + 10) d.x = -10;
            if (d.y < -10) d.y = H + 10; if (d.y > H + 10) d.y = -10;
          }
          ctx.globalAlpha = d.a * (0.6 + 0.4 * Math.sin(t / 600 + d.seed));
          const s = d.size;
          ctx.drawImage(sprites[d.k], d.x - s, d.y - s, s * 2, s * 2);
        }

        // text particles
        const cx = W / 2, cy = wordY();
        for (const p of parts) {
          if (stage === 'exit') {
            const dx = p.x - cx, dy = p.y - cy;
            const f = 0.01 * (1 + exitT * 10) * dt;
            p.vx += dx * f;
            p.vy += dy * f;
            p.vx *= 0.99;
            p.vy *= 0.99;
          } else if (now < p.delay) {
            p.vx += (Math.sin(p.seed + t / 900) * 0.04) * dt;
            p.vy += (Math.cos(p.seed * 1.3 + t / 1100) * 0.04) * dt;
            p.vx *= 0.985;
            p.vy *= 0.985;
          } else {
            const k = 0.05;
            p.vx += (p.tx - p.x) * k * dt;
            p.vy += (p.ty - p.y) * k * dt;
            p.vx *= Math.pow(0.8, dt);
            p.vy *= Math.pow(0.8, dt);
            p.vx += Math.sin(t / 300 + p.seed) * 0.02;
            p.vy += Math.cos(t / 340 + p.seed) * 0.02;
          }
          const mdx = p.x - mouse.x, mdy = p.y - mouse.y;
          const md2 = mdx * mdx + mdy * mdy;
          if (md2 < 110 * 110 && stage !== 'exit') {
            const md = Math.sqrt(md2) || 1;
            const f = (1 - md / 110) * 2.6 * dt;
            p.vx += (mdx / md) * f;
            p.vy += (mdy / md) * f;
          }
          const px = p.x, py = p.y;
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          p.alpha = Math.min(1, p.alpha + 0.02 * dt);

          const ki = clamp(Math.round(((p.x - W * 0.2) / (W * 0.6)) * (SPRITES - 1)), 0, SPRITES - 1);
          const speed = Math.abs(p.vx) + Math.abs(p.vy);
          if (stage === 'exit' && speed > 3) {
            ctx.globalAlpha = Math.max(0, 1 - exitT * 0.6);
            ctx.strokeStyle = colors[ki];
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            ctx.moveTo(px - p.vx * 1.5, py - p.vy * 1.5);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          } else {
            ctx.globalAlpha = p.alpha * (0.75 + 0.25 * Math.sin(t / 250 + p.seed));
            const s = p.size * (layout === 'small' ? 0.8 : 1) * (1 + Math.min(speed, 12) * 0.04);
            ctx.drawImage(sprites[ki], p.x - s, p.y - s, s * 2, s * 2);
          }
        }

        // shockwaves
        for (const r of rings) {
          r.r += 16 * dt;
          r.a -= 0.018 * dt;
          if (r.a <= 0) continue;
          ctx.globalAlpha = r.a;
          ctx.strokeStyle = accent.b;
          ctx.lineWidth = 2 + r.a * 4;
          ctx.beginPath();
          ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2);
          ctx.stroke();
          ctx.globalAlpha = r.a * 0.35;
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(r.x, r.y, r.r * 0.92, 0, Math.PI * 2);
          ctx.stroke();
        }
        rings = rings.filter((r) => r.a > 0);
        ctx.globalAlpha = 1;

        raf = requestAnimationFrame(frame);
      }

      // ---------- go ----------
      buildSprites();
      resize();
      retarget(false);
      parts.forEach((p) => { p.delay = Infinity; });
      dust = Array.from({ length: Math.round((W * H) / 5000) }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25 - 0.08,
        size: 1 + Math.random() * 2.4, a: 0.15 + Math.random() * 0.35, seed: Math.random() * 100,
        k: (Math.random() * SPRITES) | 0,
      }));
      raf = requestAnimationFrame(frame);

      later(650, form);
      later(2250, boom);
      later(4400, showCard);
    });
  }

  window.TuffIntro = { play };
})();
