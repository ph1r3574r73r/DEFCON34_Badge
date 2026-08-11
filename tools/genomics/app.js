/* global DC34Gene, AesGcmSiv, QrAlnum, DC34LedLayout, BarcodeDetector */
(function () {
  const G = DC34Gene;

  const GENE_CONTROLS = [
    { type: "slider", key: "cd_period", label: "Waves", max: 6, hint: "Brightness peaks around the ring (0 = flat · 6 = busy)" },
    { type: "slider", key: "cd_rate", label: "Speed", max: 255, hint: "Animation loop (higher = slower)" },
    { type: "toggle", key: "cd_dir", label: "Reverse wave", off: 40, on: 200, isOn: (v) => v > 128 },
    { type: "slider", key: "sat", label: "Saturation", max: 255 },
    { type: "slider", key: "hue_rate", label: "Hue scroll", max: 15, hint: "How fast colors drift around the ring" },
    { type: "toggle", key: "hue_reverse", label: "Reverse hue", pack: "hue_ratedir" },
    { type: "slider", key: "hue_base", label: "Hue min", max: 255, hint: "Palette window (0≈red · ~85 green · ~170 blue)" },
    { type: "slider", key: "hue_bound", label: "Hue max", max: 255, hint: "Must be ≥ hue min" },
    { type: "toggle", key: "chaser", label: "Shoot / flash", off: 200, on: 40, isOn: (v) => v < 88, hint: "Rare traveling flash + eye pop (~3%)" },
    { type: "toggle", key: "nonlin", label: "Battery dim", off: 0, on: 200, isOn: (v) => v > 127, hint: "Square brightness curve — softer, longer runtime" },
  ];

  function hueRateOf(g) {
    return g.hue_ratedir & 0xf;
  }

  function hueReverseOf(g) {
    return ((g.hue_ratedir >> 4) & 0xf) > 10;
  }

  function packHueRateDir(rate, reverse) {
    const r = rate & 0xf;
    return reverse ? (0xb0 | r) : r;
  }

  function toggleOn(meta, g) {
    if (meta.key === "hue_reverse") return hueReverseOf(g);
    return meta.isOn(g[meta.key]);
  }

  function setToggle(meta, g, on) {
    if (meta.key === "hue_reverse") {
      g.hue_ratedir = packHueRateDir(hueRateOf(g), on);
      return;
    }
    g[meta.key] = on ? meta.on : meta.off;
  }

  const PRESETS = [
    {
      id: "cyan-pulse",
      label: "Cyan pulse",
      gene: { cd_period: 2, cd_rate: 40, cd_dir: 200, sat: 255, hue_ratedir: 0x02, hue_base: 128, hue_bound: 160, chaser: 200, nonlin: 0 },
    },
    {
      id: "rainbow",
      label: "Rainbow scroll",
      gene: { cd_period: 1, cd_rate: 80, cd_dir: 40, sat: 255, hue_ratedir: 0x14, hue_base: 0, hue_bound: 255, chaser: 180, nonlin: 0 },
    },
    {
      id: "goon-red",
      label: "Goon red",
      gene: { cd_period: 3, cd_rate: 30, cd_dir: 200, sat: 255, hue_ratedir: 0x01, hue_base: 0, hue_bound: 18, chaser: 200, nonlin: 0 },
    },
    {
      id: "shoot",
      label: "Shooter",
      gene: { cd_period: 2, cd_rate: 50, cd_dir: 200, sat: 200, hue_ratedir: 0x08, hue_base: 160, hue_bound: 220, chaser: 40, nonlin: 0 },
    },
    {
      id: "soft",
      label: "Soft square",
      gene: { cd_period: 1, cd_rate: 120, cd_dir: 40, sat: 160, hue_ratedir: 0x03, hue_base: 90, hue_bound: 140, chaser: 200, nonlin: 200 },
    },
  ];

  function colorwayFamilyLine(cw) {
    const shape = cw.family === "human" ? "sun" : "gears";
    return `${cw.label} · ${shape} · SAO ${cw.sao}`;
  }

  function colorwayGridDetail(cw) {
    if (cw.family === "human") return "sun · SAO 101";
    return `gears · SAO ${cw.sao}`;
  }

  function cloneGene(h) {
    const out = {};
    G.LOCI.forEach((k) => { out[k] = h[k] & 0xff; });
    if (out.hue_bound < out.hue_base) out.hue_bound = out.hue_base;
    return out;
  }

  function makeBadge(colorwayId, gene) {
    const cw = G.colorwayFor(colorwayId);
    const g = cloneGene(gene || G.haploidFromType(cw.badgeType));
    return {
      colorway: cw.id,
      type: cw.badgeType,
      a: cloneGene(g),
      b: cloneGene(g),
    };
  }

  const state = {
    badge: makeBadge("human", PRESETS[0].gene),
    jackEyes: true,
    paused: false,
    t0: performance.now(),
    k0: null,
    k0Prefix: null,
    qrKind: null,
    lastNonceHex: null,
    oledMode: "idle", // idle | cam | qr
    cam: {
      stream: null,
      raf: 0,
      detector: null,
      busy: false,
      lastRaw: "",
      lastAt: 0,
      hitBox: null,
      frame: null,
    },
    oledHit: null,
  };

  const canvas = document.getElementById("badge-canvas");
  const ctx = canvas.getContext("2d");
  const L = typeof DC34LedLayout !== "undefined" ? DC34LedLayout : null;
  const artCache = {};

  function artKind(colorwayId) {
    const cw = G.colorwayFor(colorwayId);
    if (L && L.typeArt && L.typeArt[cw.id]) return L.typeArt[cw.id];
    return cw.family === "human" ? "human" : "inhuman";
  }

  function ledLayoutFor(colorwayId) {
    const cw = G.colorwayFor(colorwayId);
    if (L && L.layouts && cw.id === "uber" && L.layouts.uber) {
      return L.layouts.uber;
    }
    return { ring: L && L.ring, eyes: L && L.eyes, ringCount: 8 };
  }

  function ledCenterFor(colorwayId) {
    return colorwayId === "uber" ? { u: 0.5, v: 0.43 } : { u: 0.5, v: 0.5 };
  }

  function frameForBadge(badge, pheno, tMs) {
    const cw = G.colorwayFor(badge.colorway || badge.type);
    const layout = ledLayoutFor(cw.id);
    const ringLeds = layout.ringCount || (layout.ring ? layout.ring.length : 8);
    return G.approxFrame(pheno, tMs, { ringLeds, dimShift: 0, eyeShift: 0 });
  }

  function boostRgb(rgb, gain) {
    if (gain === 1) return rgb;
    return rgb.map((c) => Math.min(255, Math.round(c * gain)));
  }

  function cacheKey(colorwayId) {
    const cw = G.colorwayFor(colorwayId);
    const kind = artKind(cw.id);
    if (kind === "human") return "human";
    if (kind === "uber") return "uber";
    return "inhuman:" + cw.id;
  }

  function loadSvgImage(url) {
    const img = new Image();
    img.onload = () => { state._artReady = true; };
    img.src = url;
    return img;
  }

  async function ensureArt() {
    if (!L || !L.art) return;
    if (!artCache.human && L.art.human) {
      artCache.human = loadSvgImage(L.art.human.file);
    }
    if (L.art.uber && !artCache.uber) {
      artCache.uber = loadSvgImage(L.art.uber.file);
    }
    if (!L.art.inhuman) return;
    let tmpl = artCache._inhumanTmpl;
    if (!tmpl) {
      try {
        const res = await fetch(L.art.inhuman.file);
        tmpl = await res.text();
      } catch {
        tmpl = null;
      }
      if (tmpl) artCache._inhumanTmpl = tmpl;
    }
    const marker = L.art.inhuman.pcbMarker || "#PCBCOLOR";
    G.Colorways.forEach((cw) => {
      if (artKind(cw.id) !== "inhuman") return;
      const key = "inhuman:" + cw.id;
      if (artCache[key]) return;
      const fill = (L.typePcb && L.typePcb[cw.id]) || cw.pcb || "#1a4a68";
      if (tmpl) {
        const svg = tmpl.replaceAll(marker, fill);
        const blob = new Blob([svg], { type: "image/svg+xml" });
        artCache[key] = loadSvgImage(URL.createObjectURL(blob));
      } else {
        artCache[key] = loadSvgImage(L.art.inhuman.file);
      }
    });
  }

  function containRect(iw, ih, cw, ch) {
    const s = Math.min(cw / iw, ch / ih);
    const dw = iw * s;
    const dh = ih * s;
    return { x: (cw - dw) / 2, y: (ch - dh) / 2, w: dw, h: dh };
  }

  /** Inset OLED/content rect inside the core module window. */
  function oledContentRect(fit, colorwayId) {
    const rect = moduleWindow(fit, colorwayId);
    if (!rect || rect.w < 4 || rect.h < 4) return null;
    const pad = Math.max(2, Math.min(rect.w, rect.h) * 0.08);
    return {
      x: rect.x + pad,
      y: rect.y + pad,
      w: rect.w - pad * 2,
      h: rect.h - pad * 2,
    };
  }

  function canvasPoint(evt) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (evt.clientX - rect.left) * scaleX,
      y: (evt.clientY - rect.top) * scaleY,
    };
  }

  function pointInRect(p, r) {
    return !!(r && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h);
  }

  function updateOledCursor() {
    const mode = currentOledMode();
    canvas.classList.toggle("oled-tap", mode === "idle" || mode === "qr");
    canvas.classList.toggle("oled-scanning", mode === "cam");
    const title = mode === "qr"
      ? "Tap gene QR to scan another badge"
      : mode === "cam"
        ? "Scanning — point at your badge’s nonce QR"
        : "Tap core to scan your badge";
    canvas.title = title;
  }

  function uvToCanvas(u, v, fit) {
    return { x: fit.x + u * fit.w, y: fit.y + v * fit.h };
  }


  function drawOutlineFallback(ctx2, fit, cw) {
    ctx2.fillStyle = cw.family === "human" ? "#161412" : (cw.pcb || "#12161c");
    ctx2.strokeStyle = cw.color || "#c47832";
    ctx2.lineWidth = 2;
    if (!L || !L.outline || L.outline.length < 3) {
      ctx2.fillRect(fit.x, fit.y, fit.w, fit.h);
      return;
    }
    const bb = L.pcb_bbox_mm;
    const bw = bb[2] - bb[0];
    const bh = bb[3] - bb[1];
    ctx2.beginPath();
    L.outline.forEach((pt, i) => {
      const x = fit.x + ((pt[0] - bb[0]) / bw) * fit.w;
      const y = fit.y + ((pt[1] - bb[1]) / bh) * fit.h;
      if (i === 0) ctx2.moveTo(x, y);
      else ctx2.lineTo(x, y);
    });
    ctx2.closePath();
    ctx2.fill();
    ctx2.stroke();
  }

  function drawRgbDie(ctx2, x, y, rgb, scale, r) {
    const [R, Gv, B] = rgb;
    const rad = Math.max(r * scale, 1.6);
    // Soft per-die glow (kept under the die, not a big wash).
    if (R + Gv + B > 12) {
      const g = ctx2.createRadialGradient(x, y, 0, x, y, rad * 3.2);
      g.addColorStop(0, `rgba(${R},${Gv},${B},0.85)`);
      g.addColorStop(1, `rgba(${R},${Gv},${B},0)`);
      ctx2.fillStyle = g;
      ctx2.beginPath();
      ctx2.arc(x, y, rad * 3.2, 0, Math.PI * 2);
      ctx2.fill();
    }
    ctx2.beginPath();
    ctx2.arc(x, y, rad, 0, Math.PI * 2);
    ctx2.fillStyle = `rgb(${Math.min(255, R + 40)},${Math.min(255, Gv + 40)},${Math.min(255, B + 40)})`;
    ctx2.fill();
    ctx2.strokeStyle = "rgba(0,0,0,0.55)";
    ctx2.lineWidth = Math.max(0.6, scale * 0.35);
    ctx2.stroke();
  }

  function drawSideFireBloom(ctx2, x, y, inward, rgb, scale, strength) {
    const [R, Gv, B] = rgb;
    if (R + Gv + B < 8) return;
    const k = strength == null ? 1 : strength;
    const dx = Math.cos(inward);
    const dy = Math.sin(inward);
    const wash = 10 * scale * (0.85 + k * 0.25);
    const g = ctx2.createRadialGradient(
      x + dx * wash * 0.55, y + dy * wash * 0.55, 0,
      x + dx * wash, y + dy * wash, wash * 1.8,
    );
    g.addColorStop(0, `rgba(${R},${Gv},${B},${Math.min(0.72, 0.35 * k)})`);
    g.addColorStop(1, `rgba(${R},${Gv},${B},0)`);
    ctx2.fillStyle = g;
    ctx2.beginPath();
    ctx2.arc(x + dx * wash * 0.5, y + dy * wash * 0.5, wash * 1.8, 0, Math.PI * 2);
    ctx2.fill();
  }

  function roundedRectPath(ctx2, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx2.beginPath();
    ctx2.moveTo(x + rr, y);
    ctx2.arcTo(x + w, y, x + w, y + h, rr);
    ctx2.arcTo(x + w, y + h, x, y + h, rr);
    ctx2.arcTo(x, y + h, x, y, rr);
    ctx2.arcTo(x, y, x + w, y, rr);
    ctx2.closePath();
  }

  /** SK6812SIDE: black 4.0×1.6 package, 3 RGB dies in a row, fires inward. */
  function drawSideFirePkg(ctx2, x, y, inward, rgb, scale) {
    const s = Math.max(scale, 1.15);
    ctx2.save();
    ctx2.translate(x, y);
    // Package long axis is tangential; light fires along `inward`.
    ctx2.rotate(inward + Math.PI / 2);
    const pw = 5.2 * s;
    const ph = 2.1 * s;
    ctx2.fillStyle = "#0a0a0c";
    ctx2.strokeStyle = "rgba(180,180,190,0.45)";
    ctx2.lineWidth = Math.max(0.5, s * 0.25);
    roundedRectPath(ctx2, -pw / 2, -ph / 2, pw, ph, 0.35 * s);
    ctx2.fill();
    ctx2.stroke();
    drawRgbDie(ctx2, -1.55 * s, 0, [rgb[0], 4, 4], s, 0.95);
    drawRgbDie(ctx2, 0, 0, [4, rgb[1], 4], s, 0.95);
    drawRgbDie(ctx2, 1.55 * s, 0, [4, 4, rgb[2]], s, 0.95);
    ctx2.restore();
  }

  function drawEyeBloom(ctx2, x, y, rgb, scale, strength) {
    const [R, Gv, B] = rgb;
    if (R + Gv + B < 8) return;
    const k = strength == null ? 1 : strength;
    const g = ctx2.createRadialGradient(x, y, 0, x, y, 14 * scale * (0.9 + k * 0.2));
    g.addColorStop(0, `rgba(${R},${Gv},${B},${Math.min(0.78, 0.45 * k)})`);
    g.addColorStop(1, `rgba(${R},${Gv},${B},0)`);
    ctx2.fillStyle = g;
    ctx2.beginPath();
    ctx2.arc(x, y, 14 * scale * (0.9 + k * 0.2), 0, Math.PI * 2);
    ctx2.fill();
  }

  /** WS2812B-2020: RGB triangle on a square die. */
  function drawEyePkg(ctx2, x, y, rgb, scale) {
    const [R, Gv, B] = rgb;
    const s = Math.max(scale, 1.15);
    ctx2.save();
    ctx2.translate(x, y);
    const half = 2.4 * s;
    ctx2.fillStyle = "#0a0a0c";
    ctx2.strokeStyle = "rgba(180,180,190,0.45)";
    ctx2.lineWidth = Math.max(0.5, s * 0.25);
    roundedRectPath(ctx2, -half, -half, half * 2, half * 2, 0.3 * s);
    ctx2.fill();
    ctx2.stroke();
    drawRgbDie(ctx2, -1.35 * s, 1.05 * s, [R, 4, 4], s, 0.9);
    drawRgbDie(ctx2, 0, -1.35 * s, [4, Gv, 4], s, 0.9);
    drawRgbDie(ctx2, 1.35 * s, 1.05 * s, [4, 4, B], s, 0.9);
    ctx2.restore();
  }

  function drawDimCarrier(ctx2, img, fit, cw, punchHoles) {
    const isUber = cw.id === "uber";
    ctx2.save();
    ctx2.globalAlpha = isUber ? 0.78 : 0.55;
    ctx2.drawImage(img, fit.x, fit.y, fit.w, fit.h);
    ctx2.globalAlpha = 1;
    ctx2.fillStyle = isUber
      ? "rgba(5, 4, 8, 0.34)"
      : cw.family === "human"
        ? "rgba(5, 4, 3, 0.48)"
        : "rgba(5, 4, 8, 0.58)";
    // Dim veil with cutouts so LED packages sit above the mask, not under it.
    ctx2.beginPath();
    ctx2.rect(fit.x, fit.y, fit.w, fit.h);
    (punchHoles || []).forEach((h) => {
      ctx2.moveTo(h.x + h.r, h.y);
      ctx2.arc(h.x, h.y, h.r, 0, Math.PI * 2, true);
    });
    ctx2.fill("evenodd");
    ctx2.restore();
  }

  const MODULE_UV = {
    human: { u0: 0.3438, v0: 0.3816, u1: 0.6557, v1: 0.7112 },
    inhuman: { u0: 0.345, v0: 0.3817, u1: 0.6564, v1: 0.7035 },
    uber: { u0: 0.31, v0: 0.36, u1: 0.69, v1: 0.74 },
  };

  function uvRectToCanvas(uv, fit) {
    const x = fit.x + uv.u0 * fit.w;
    const y = fit.y + uv.v0 * fit.h;
    return {
      x,
      y,
      w: (uv.u1 - uv.u0) * fit.w,
      h: (uv.v1 - uv.v0) * fit.h,
    };
  }

  /** Full core-module window (the black square on the carrier), not just the OLED inset. */
  function moduleWindow(fit, colorwayId) {
    const kind = artKind(colorwayId);
    const art = L && L.art && L.art[kind];
    const uv = (art && (art.module || art.oled)) || MODULE_UV[kind] || MODULE_UV.inhuman;
    return uvRectToCanvas(uv, fit);
  }

  /** Cover-fit draw of a video/image into dest rect (clips to dest). */
  function drawCover(ctx2, src, dx, dy, dw, dh, srcW, srcH) {
    if (!srcW || !srcH || dw < 1 || dh < 1) return;
    const scale = Math.max(dw / srcW, dh / srcH);
    const sw = dw / scale;
    const sh = dh / scale;
    const sx = (srcW - sw) / 2;
    const sy = (srcH - sh) / 2;
    ctx2.drawImage(src, sx, sy, sw, sh, dx, dy, dw, dh);
  }

  function drawContain(ctx2, src, dx, dy, dw, dh, srcW, srcH) {
    if (!srcW || !srcH || dw < 1 || dh < 1) return;
    const scale = Math.min(dw / srcW, dh / srcH);
    const tw = srcW * scale;
    const th = srcH * scale;
    ctx2.drawImage(src, dx + (dw - tw) / 2, dy + (dh - th) / 2, tw, th);
  }

  function captureCamFrame() {
    const video = document.getElementById("cam-video");
    if (!state.cam.stream || !video || video.readyState < 2 || !video.videoWidth) return null;
    if (!state.cam.frame) state.cam.frame = document.createElement("canvas");
    const fc = state.cam.frame;
    if (fc.width !== video.videoWidth || fc.height !== video.videoHeight) {
      fc.width = video.videoWidth;
      fc.height = video.videoHeight;
    }
    const fctx = fc.getContext("2d");
    fctx.drawImage(video, 0, 0);
    return fc;
  }

  function currentOledMode() {
    if (state.oledMode === "cam" || state.oledMode === "qr") return state.oledMode;
    if (state.qrKind === "gene") return "qr";
    if (state.cam.stream) return "cam";
    return "idle";
  }

  function drawOledIdle(ctx2, rect) {
    const { x, y, w, h } = rect;
    ctx2.fillStyle = "#0a0e0b";
    ctx2.fillRect(x, y, w, h);
    ctx2.strokeStyle = "rgba(196, 120, 50, 0.55)";
    ctx2.lineWidth = Math.max(1.5, w * 0.025);
    ctx2.strokeRect(x + 2, y + 2, w - 4, h - 4);

    const mono = getComputedStyle(document.body).getPropertyValue("--mono") || "monospace";
    ctx2.textAlign = "center";
    ctx2.textBaseline = "middle";
    if (state.cam.stream) {
      ctx2.fillStyle = "rgba(200, 180, 138, 0.95)";
      ctx2.font = `600 ${Math.max(9, w * 0.08)}px ${mono}`;
      ctx2.fillText("Scanning…", x + w / 2, y + h / 2);
      return;
    }
    ctx2.fillStyle = "rgba(200, 180, 138, 0.95)";
    ctx2.font = `700 ${Math.max(10, w * 0.09)}px ${mono}`;
    ctx2.fillText("Click to scan", x + w / 2, y + h * 0.42);
    ctx2.fillStyle = "rgba(154, 148, 132, 0.95)";
    ctx2.font = `500 ${Math.max(8, w * 0.075)}px ${mono}`;
    ctx2.fillText("your badge", x + w / 2, y + h * 0.62);
  }

  function drawOledContent(ctx2, fit, colorwayId) {
    const rect = oledContentRect(fit, colorwayId);
    if (!rect) return;
    const { x, y, w, h } = rect;
    state.oledHit = rect;
    const qr = document.getElementById("qr-canvas");
    const mode = currentOledMode();
    const frame = state.cam.stream ? captureCamFrame() : null;
    const showCam = mode === "cam" && frame && frame.width;
    const showQr = mode === "qr" && qr && qr.width > 0;

    ctx2.save();
    ctx2.beginPath();
    const rr = Math.max(2, w * 0.04);
    roundedRectPath(ctx2, x, y, w, h, rr);
    ctx2.clip();

    if (showCam) {
      ctx2.fillStyle = "#000";
      ctx2.fillRect(x, y, w, h);
      drawCover(ctx2, frame, x, y, w, h, frame.width, frame.height);
      if (state.cam.hitBox && frame.width) {
        const b = state.cam.hitBox;
        const scale = Math.max(w / frame.width, h / frame.height);
        const vw = frame.width * scale;
        const vh = frame.height * scale;
        const ox = x + (w - vw) / 2;
        const oy = y + (h - vh) / 2;
        ctx2.strokeStyle = "#8ec46a";
        ctx2.lineWidth = Math.max(2, w * 0.025);
        ctx2.strokeRect(ox + b.x * scale, oy + b.y * scale, b.width * scale, b.height * scale);
      }
    } else if (showQr) {
      ctx2.fillStyle = "#ffffff";
      ctx2.fillRect(x, y, w, h);
      const qpad = w * 0.06;
      drawContain(ctx2, qr, x + qpad, y + qpad, w - qpad * 2, h - qpad * 2, qr.width, qr.height);
      const mono = getComputedStyle(document.body).getPropertyValue("--mono") || "monospace";
      ctx2.fillStyle = "rgba(80, 72, 62, 0.88)";
      ctx2.font = `500 ${Math.max(7, w * 0.055)}px ${mono}`;
      ctx2.textAlign = "center";
      ctx2.textBaseline = "bottom";
      ctx2.fillText("tap to scan again", x + w / 2, y + h - Math.max(3, h * 0.04));
    } else {
      drawOledIdle(ctx2, { x, y, w, h });
    }
    ctx2.restore();

    ctx2.save();
    ctx2.strokeStyle = showCam
      ? "rgba(108, 188, 120, 0.7)"
      : showQr
        ? "rgba(200, 180, 138, 0.7)"
        : "rgba(196, 120, 50, 0.45)";
    ctx2.lineWidth = Math.max(1.5, w * 0.02);
    roundedRectPath(ctx2, x, y, w, h, rr);
    ctx2.stroke();
    ctx2.restore();
  }

  function drawBadge(ctx2, cvs, badge, frame) {
    const w = cvs.width;
    const h = cvs.height;
    ctx2.setTransform(1, 0, 0, 1, 0, 0);
    ctx2.globalAlpha = 1;
    ctx2.globalCompositeOperation = "source-over";
    ctx2.fillStyle = "#050504";
    ctx2.fillRect(0, 0, w, h);
    const cw = G.colorwayFor(badge.colorway || badge.type);
    const layout = ledLayoutFor(cw.id);
    const ringLeds = layout.ring || [];
    const eyeLeds = layout.eyes || [];
    const lc = ledCenterFor(cw.id);
    const img = artCache[cacheKey(cw.id)];
    let fit;
    if (img && img.complete && img.naturalWidth) {
      fit = containRect(img.naturalWidth, img.naturalHeight, w, h);
    } else {
      fit = { x: w * 0.08, y: h * 0.05, w: w * 0.84, h: h * 0.9 };
    }
    const isUber = cw.id === "uber";
    const ledScale = Math.max(Math.max(fit.w, fit.h) / 320, 1.35) * (isUber ? 1.22 : 1);
    const ledGain = isUber ? 1.18 : 1;
    const bloomStrength = isUber ? 1.45 : 1;
    const holeMul = isUber ? 8.8 : 7;
    const showEyes = state.jackEyes || badge.type === G.BadgeType.UBER;
    const holes = [];
    if (ringLeds.length) {
      ringLeds.forEach((led) => {
        const p = uvToCanvas(led.u, led.v, fit);
        holes.push({ x: p.x, y: p.y, r: holeMul * ledScale });
      });
      if (showEyes) {
        eyeLeds.forEach((led) => {
          const p = uvToCanvas(led.u, led.v, fit);
          holes.push({ x: p.x, y: p.y, r: (holeMul - 1) * ledScale });
        });
      }
    } else if (L && L.ring) {
      L.ring.forEach((led) => {
        const p = uvToCanvas(led.u, led.v, fit);
        holes.push({ x: p.x, y: p.y, r: holeMul * ledScale });
      });
      if (showEyes) {
        L.eyes.forEach((led) => {
          const p = uvToCanvas(led.u, led.v, fit);
          holes.push({ x: p.x, y: p.y, r: (holeMul - 1) * ledScale });
        });
      }
    }
    if (img && img.complete && img.naturalWidth) {
      drawDimCarrier(ctx2, img, fit, cw, holes);
    } else {
      drawOutlineFallback(ctx2, fit, cw);
    }

    if (!ringLeds.length && (!L || !L.ring)) {
      drawOledContent(ctx2, fit, cw.id);
      return;
    }

    function inwardFor(led) {
      if (led.rot != null && cw.id === "uber") return (led.rot * Math.PI) / 180;
      return Math.atan2(lc.v - led.v, lc.u - led.u);
    }

    // LEDs always above the mask, full opacity.
    ctx2.save();
    ctx2.globalAlpha = 1;
    ctx2.globalCompositeOperation = "lighter";
    ringLeds.forEach((led, i) => {
      const p = uvToCanvas(led.u, led.v, fit);
      drawSideFireBloom(
        ctx2, p.x, p.y, inwardFor(led),
        boostRgb(frame.ring[i] || [0, 0, 0], ledGain),
        ledScale, bloomStrength,
      );
    });
    if (showEyes) {
      eyeLeds.forEach((led, i) => {
        const p = uvToCanvas(led.u, led.v, fit);
        drawEyeBloom(ctx2, p.x, p.y, boostRgb(frame.eyes[i] || [0, 0, 0], ledGain), ledScale, bloomStrength);
      });
    }
    ctx2.restore();

    ctx2.save();
    ctx2.globalAlpha = 1;
    ctx2.globalCompositeOperation = "source-over";
    ringLeds.forEach((led, i) => {
      const p = uvToCanvas(led.u, led.v, fit);
      drawSideFirePkg(
        ctx2, p.x, p.y, inwardFor(led),
        boostRgb(frame.ring[i] || [0, 0, 0], ledGain),
        ledScale,
      );
    });
    if (showEyes) {
      eyeLeds.forEach((led, i) => {
        const p = uvToCanvas(led.u, led.v, fit);
        drawEyePkg(ctx2, p.x, p.y, boostRgb(frame.eyes[i] || [0, 0, 0], ledGain), ledScale);
      });
    }
    ctx2.restore();

    // Core OLED on top — camera / gene QR.
    drawOledContent(ctx2, fit, cw.id);
    updateOledCursor();
  }

  function designGene() {
    return cloneGene(state.badge.a);
  }

  function applyGene(gene, { syncSliders } = { syncSliders: true }) {
    const g = cloneGene(gene);
    state.badge.a = g;
    state.badge.b = cloneGene(g);
    state.lastNonceHex = null;
    if (state.qrKind === "gene") hideQr();
    if (syncSliders !== false) syncGeneControls();
    refreshMeta();
  }

  function pheno(badge) {
    /* Designer preview: show the donated haploid as if it were the sole genome. */
    return cloneGene(badge.a);
  }

  function refreshMeta() {
    const cw = G.colorwayFor(state.badge.colorway || state.badge.type);
    document.getElementById("badge-family").textContent = colorwayFamilyLine(cw);
    document.getElementById("badge-caption").textContent =
      `${cw.label} donor · previewing designed gene`;
    syncTypeGrid("type-badge", cw.id);
    const hexInput = document.getElementById("gene-hex");
    if (hexInput && document.activeElement !== hexInput) {
      hexInput.value = G.toHex(G.serialize(designGene()));
    }
  }

  function syncTypeGrid(id, selectedId) {
    document.querySelectorAll(`#${id} .type-btn`).forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.colorway === selectedId);
    });
  }

  function renderTypeGrid(el) {
    el.innerHTML = "";
    G.Colorways.forEach((cw) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "type-btn";
      btn.dataset.colorway = cw.id;
      btn.style.setProperty("--type-color", cw.pcb || cw.color);
      btn.innerHTML = `<strong>${cw.label}</strong><span>${colorwayGridDetail(cw)}</span>`;
      btn.title = cw.hint;
      btn.onclick = () => {
        /* Keep designed gene; only swap donor type / art. */
        state.badge.colorway = cw.id;
        state.badge.type = cw.badgeType;
        state.lastNonceHex = null;
        if (state.qrKind === "gene") hideQr();
        refreshMeta();
      };
      el.appendChild(btn);
    });
  }

  function syncGeneControls() {
    const g = designGene();
    GENE_CONTROLS.forEach((meta) => {
      if (meta.type === "slider") {
        const input = document.getElementById(`gene-${meta.key}`);
        const val = document.getElementById(`gene-val-${meta.key}`);
        if (!input || !val) return;
        const v = meta.key === "hue_rate" ? hueRateOf(g) : g[meta.key];
        input.value = String(v);
        val.textContent = String(v);
        return;
      }
      const input = document.getElementById(`gene-${meta.key}`);
      if (input) input.checked = toggleOn(meta, g);
    });
  }

  function renderGeneControls() {
    const root = document.getElementById("gene-controls");
    root.innerHTML = "";
    const g = designGene();
    GENE_CONTROLS.forEach((meta) => {
      const row = document.createElement("div");
      if (meta.type === "slider") {
        const v = meta.key === "hue_rate" ? hueRateOf(g) : g[meta.key];
        row.className = "gene-row slider";
        row.innerHTML = `
          <label for="gene-${meta.key}">${meta.label}</label>
          <input type="range" id="gene-${meta.key}" min="0" max="${meta.max}" value="${v}" />
          <span class="val" id="gene-val-${meta.key}">${v}</span>
          ${meta.hint ? `<p class="hint-mini">${meta.hint}</p>` : ""}`;
        root.appendChild(row);
        const input = row.querySelector("input");
        const val = row.querySelector(".val");
        input.addEventListener("input", () => {
          const next = designGene();
          const n = Number(input.value) & 0xff;
          if (meta.key === "hue_rate") {
            next.hue_ratedir = packHueRateDir(n, hueReverseOf(next));
          } else {
            next[meta.key] = n;
            if (meta.key === "hue_base" && next.hue_bound < next.hue_base) next.hue_bound = next.hue_base;
            if (meta.key === "hue_bound" && next.hue_bound < next.hue_base) next.hue_base = next.hue_bound;
          }
          val.textContent = String(n);
          applyGene(next, { syncSliders: false });
          syncGeneControls();
        });
        return;
      }
      row.className = "gene-row toggle";
      row.innerHTML = `
        <label class="check gene-toggle" for="gene-${meta.key}">
          <input type="checkbox" id="gene-${meta.key}" ${toggleOn(meta, g) ? "checked" : ""} />
          ${meta.label}
        </label>
        ${meta.hint ? `<p class="hint-mini">${meta.hint}</p>` : ""}`;
      root.appendChild(row);
      const input = row.querySelector("input");
      input.addEventListener("change", () => {
        const next = designGene();
        setToggle(meta, next, input.checked);
        applyGene(next, { syncSliders: false });
        syncGeneControls();
      });
    });
  }

  function renderPresets() {
    const row = document.getElementById("preset-row");
    row.innerHTML = "";
    PRESETS.forEach((p) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = p.label;
      btn.onclick = () => applyGene(p.gene);
      row.appendChild(btn);
    });
  }

  function mutRate() {
    return Number(document.getElementById("mut-badge").value);
  }

  function showQr(kind, payload, caption) {
    state.qrKind = kind;
    if (kind === "gene") state.oledMode = "qr";
    const stage = document.getElementById("qr-stage");
    if (stage) stage.hidden = false;
    const idle = document.getElementById("gene-idle");
    if (idle) idle.hidden = true;
    document.getElementById("qr-caption").textContent = caption;
    document.getElementById("qr-b45").textContent = payload;
    const copyBtn = document.getElementById("btn-copy-b45");
    if (copyBtn) copyBtn.disabled = !payload;
    try {
      QrAlnum.draw(document.getElementById("qr-canvas"), payload);
    } catch (e) {
      console.warn("QR draw failed", e);
    }
    updateOledCursor();
  }

  function hideQr() {
    state.qrKind = null;
    if (state.oledMode === "qr") state.oledMode = state.cam.stream ? "cam" : "idle";
    const stage = document.getElementById("qr-stage");
    if (stage) stage.hidden = true;
    const idle = document.getElementById("gene-idle");
    if (idle) idle.hidden = false;
    document.getElementById("qr-caption").textContent = "";
    document.getElementById("qr-b45").textContent = "";
    const copyBtn = document.getElementById("btn-copy-b45");
    if (copyBtn) copyBtn.disabled = true;
    updateOledCursor();
  }

  function prepareRescan() {
    hideQr();
    state.lastNonceHex = null;
    stopCamera();
  }

  function hasK0() {
    return !!(state.k0 && state.k0.length === 32);
  }

  function updateK0Ui() {
    const locked = !hasK0();
    const cryptoOk = hasSubtle();
    document.getElementById("btn-respond-paste").disabled = locked || !cryptoOk;
  }

  function hasSubtle() {
    return !!(globalThis.crypto && globalThis.crypto.subtle);
  }

  function requireSubtle() {
    if (hasSubtle()) return;
    throw new Error(
      "WebCrypto unavailable — open over https:// or http://localhost (not file://)",
    );
  }

  /** Pure SHA-256 so k0 prefix check works even when crypto.subtle is missing. */
  function sha256hexSync(bytes) {
    const K = new Uint32Array([
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]);
    const rotr = (x, n) => (x >>> n) | (x << (32 - n));
    const u8 = Uint8Array.from(bytes);
    const bitLen = u8.length * 8;
    const withPad = new Uint8Array(((u8.length + 9 + 63) & ~63));
    withPad.set(u8);
    withPad[u8.length] = 0x80;
    const view = new DataView(withPad.buffer);
    view.setUint32(withPad.length - 4, bitLen >>> 0);
    view.setUint32(withPad.length - 8, Math.floor(bitLen / 0x100000000));
    let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
    let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
    const w = new Uint32Array(64);
    for (let i = 0; i < withPad.length; i += 64) {
      for (let j = 0; j < 16; j++) w[j] = view.getUint32(i + j * 4);
      for (let j = 16; j < 64; j++) {
        const s0 = rotr(w[j - 15], 7) ^ rotr(w[j - 15], 18) ^ (w[j - 15] >>> 3);
        const s1 = rotr(w[j - 2], 17) ^ rotr(w[j - 2], 19) ^ (w[j - 2] >>> 10);
        w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0;
      }
      let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
      for (let j = 0; j < 64; j++) {
        const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + K[j] + w[j]) >>> 0;
        const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0;
        d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
      h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
    }
    return [h0, h1, h2, h3, h4, h5, h6, h7]
      .map((x) => x.toString(16).padStart(8, "0"))
      .join("");
  }

  async function sha256hex(bytes) {
    if (hasSubtle()) {
      const d = await crypto.subtle.digest("SHA-256", Uint8Array.from(bytes));
      return Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, "0")).join("");
    }
    return sha256hexSync(bytes);
  }

  function showSecureBanner() {
    const el = document.getElementById("secure-banner");
    if (!el) return;
    const blocked = !hasSubtle();
    el.hidden = !blocked;
    if (blocked) {
      document.getElementById("btn-respond-paste").disabled = true;
      setScanStatus("WebCrypto blocked — use https:// or http://localhost");
    }
  }

  async function setK0(hex) {
    const clean = hex.replace(/\s+/g, "").toLowerCase();
    if (clean.length !== 64 || /[^0-9a-f]/.test(clean)) {
      throw new Error("k0 must be 64 hex chars (32 bytes)");
    }
    const key = G.fromHex(clean);
    const digest = await sha256hex(key);
    const prefix = digest.slice(0, 8);
    if (prefix !== G.K0_HASH_PREFIX) {
      throw new Error(`k0 sha256 prefix is ${prefix}, expected ${G.K0_HASH_PREFIX}`);
    }
    state.k0 = key;
    state.k0Prefix = prefix;
    updateK0Ui();
    showSecureBanner();
  }

  async function restoreK0() {
    if (!G.PUBLIC_K0_HEX) return;
    try {
      await setK0(G.PUBLIC_K0_HEX);
    } catch (e) {
      console.warn("k0 restore", e);
    }
  }

  function setScanStatus(msg) {
    document.getElementById("scan-status").textContent = msg;
  }

  async function mintGeneFromNonce(nonceBytes, sourceLabel) {
    if (!hasK0()) throw new Error("k0 locked");
    requireSubtle();
    const nonceHex = G.toHex(nonceBytes);
    if (nonceHex === state.lastNonceHex && state.qrKind === "gene") {
      stopCamera();
      setScanStatus(`Same nonce · gene QR ready (${sourceLabel})`);
      return;
    }
    const rate = mutRate();
    const { padded } = G.getPaddedGamete(
      { a: state.badge.a, b: state.badge.b },
      state.badge.type,
      rate,
    );
    const ct = await AesGcmSiv.encrypt(state.k0, nonceBytes, Uint8Array.from(padded), new Uint8Array(0));
    const b45 = G.b45encode(ct);
    const cw = G.colorwayFor(state.badge.colorway);
    state.lastNonceHex = nonceHex;
    showQr(
      "gene",
      b45,
      `${cw.label} gene QR · scan with your badge · nonce ${nonceHex.slice(0, 8)}…`,
    );
    stopCamera();
    setScanStatus(`Gene ready on core · tap QR to scan another badge (${sourceLabel})`);
  }

  async function handleRawPayload(raw, sourceLabel) {
    let parsed;
    try {
      parsed = G.parseBreedPayload(raw);
    } catch (e) {
      setScanStatus(`Not a breed QR: ${e.message || e}`);
      return false;
    }
    if (parsed.kind !== "nonce") {
      setScanStatus(`Saw ${parsed.kind} · need a nonce QR from your badge`);
      return false;
    }
    try {
      await mintGeneFromNonce(parsed.nonce, sourceLabel);
      return true;
    } catch (e) {
      setScanStatus(e.message || String(e));
      alert(e.message || e);
      return false;
    }
  }

  async function respondPaste() {
    const raw = document.getElementById("qr-paste").value;
    if (!raw.trim()) return alert("Paste a nonce payload first.");
    await handleRawPayload(raw, "paste");
  }

  function camSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  function detectorSupported() {
    return typeof BarcodeDetector !== "undefined";
  }

  async function startCamera() {
    if (!hasK0()) return alert("Conference k0 not loaded.");
    if (!camSupported()) {
      return alert("No camera API. Use HTTPS/localhost, or paste the nonce below.");
    }
    if (!detectorSupported()) {
      return alert(
        "This browser has no BarcodeDetector (try Chrome or Safari 17+). Paste the nonce below instead.",
      );
    }
    stopCamera();
    try {
      state.cam.detector = new BarcodeDetector({ formats: ["qr_code"] });
      state.cam.stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });
    } catch (e) {
      setScanStatus("Camera blocked: " + (e.message || e));
      return alert("Camera permission failed: " + (e.message || e));
    }
    const video = document.getElementById("cam-video");
    video.srcObject = state.cam.stream;
    video.muted = true;
    video.setAttribute("playsinline", "");
    video.playsInline = true;
    await video.play();
    // Force a decode path even if the element is nearly invisible.
    captureCamFrame();
    state.oledMode = "cam";
    document.getElementById("breed-dock").classList.add("scanning");
    setScanStatus("Point at your badge’s nonce QR…");
    updateOledCursor();
    scanLoop();
  }

  function stopCamera() {
    if (state.cam.raf) {
      cancelAnimationFrame(state.cam.raf);
      state.cam.raf = 0;
    }
    if (state.cam.stream) {
      state.cam.stream.getTracks().forEach((t) => t.stop());
      state.cam.stream = null;
    }
    state.cam.frame = null;
    state.cam.hitBox = null;
    if (state.oledMode === "cam") {
      state.oledMode = state.qrKind === "gene" ? "qr" : "idle";
    }
    const video = document.getElementById("cam-video");
    video.srcObject = null;
    document.getElementById("breed-dock").classList.remove("scanning");
    state.cam.hitBox = null;
    const overlay = document.getElementById("cam-overlay");
    if (overlay) {
      const octx = overlay.getContext("2d");
      octx.clearRect(0, 0, overlay.width, overlay.height);
    }
    if (state.qrKind !== "gene") {
      setScanStatus("Tap the core on the preview to scan your badge");
    }
    updateOledCursor();
  }

  async function handleOledTap() {
    if (!hasK0()) return alert("Conference k0 not loaded.");
    if (!hasSubtle()) {
      return alert("WebCrypto unavailable — open over https:// or http://localhost (not file://).");
    }
    const mode = currentOledMode();
    if (mode === "qr") {
      prepareRescan();
      await startCamera();
      return;
    }
    if (mode === "cam") return;
    await startCamera();
  }

  async function scanLoop() {
    const video = document.getElementById("cam-video");
    const overlay = document.getElementById("cam-overlay");
    if (!state.cam.stream || video.readyState < 2) {
      state.cam.raf = requestAnimationFrame(scanLoop);
      return;
    }
    if (overlay.width !== video.videoWidth || overlay.height !== video.videoHeight) {
      overlay.width = video.videoWidth || 640;
      overlay.height = video.videoHeight || 480;
    }
    const octx = overlay.getContext("2d");
    octx.clearRect(0, 0, overlay.width, overlay.height);

    if (!state.cam.busy && state.cam.detector) {
      state.cam.busy = true;
      try {
        const codes = await state.cam.detector.detect(video);
        if (codes && codes.length) {
          const code = codes[0];
          const raw = (code.rawValue || "").trim();
          if (code.boundingBox) {
            const b = code.boundingBox;
            state.cam.hitBox = { x: b.x, y: b.y, width: b.width, height: b.height };
            octx.strokeStyle = "#8ec46a";
            octx.lineWidth = 3;
            octx.strokeRect(b.x, b.y, b.width, b.height);
          }
          const now = performance.now();
          if (raw && (raw !== state.cam.lastRaw || now - state.cam.lastAt > 2500)) {
            state.cam.lastRaw = raw;
            state.cam.lastAt = now;
            await handleRawPayload(raw, "webcam");
          }
        } else {
          state.cam.hitBox = null;
        }
      } catch (e) {
        /* transient detect errors — keep looping */
      }
      state.cam.busy = false;
    }
    state.cam.raf = requestAnimationFrame(scanLoop);
  }

  function tick(now) {
    if (state.paused) {
      if (!state._freezeT) state._freezeT = now - state.t0;
    } else {
      state._freezeT = null;
    }
    const t = state._freezeT != null ? state._freezeT : now - state.t0;
    drawBadge(ctx, canvas, state.badge, frameForBadge(state.badge, pheno(state.badge), t));
    requestAnimationFrame(tick);
  }

  renderTypeGrid(document.getElementById("type-badge"));
  renderPresets();
  renderGeneControls();
  ensureArt().catch((e) => console.warn("badge SVG", e));
  refreshMeta();
  updateK0Ui();

  document.getElementById("btn-reroll").onclick = () => {
    applyGene(G.haploidFromType(state.badge.type));
  };
  document.getElementById("mut-badge").onchange = () => refreshMeta();
  document.getElementById("gene-hex").addEventListener("change", () => {
    try {
      const h = G.deserialize(G.fromHex(document.getElementById("gene-hex").value.trim()));
      if (!h) throw new Error("need 9-byte haploid hex");
      applyGene(h);
    } catch (e) {
      alert(e.message || e);
      refreshMeta();
    }
  });
  document.getElementById("jack-eyes").onchange = (e) => { state.jackEyes = e.target.checked; };
  document.getElementById("paused").onchange = (e) => { state.paused = e.target.checked; };

  function onBadgePointer(evt) {
    const p = canvasPoint(evt);
    const hit = state.oledHit;
    if (!pointInRect(p, hit)) return;
    evt.preventDefault();
    handleOledTap();
  }

  canvas.addEventListener("click", onBadgePointer);
  canvas.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" || evt.key === " ") {
      evt.preventDefault();
      handleOledTap();
    }
  });

  document.getElementById("btn-respond-paste").onclick = () => respondPaste();
  document.getElementById("btn-copy-b45").onclick = () => {
    const t = document.getElementById("qr-b45").textContent;
    if (t) navigator.clipboard.writeText(t);
  };

  window.addEventListener("beforeunload", () => stopCamera());

  restoreK0().then(() => {
    showSecureBanner();
    if (hasSubtle() && typeof AesGcmSiv !== "undefined" && AesGcmSiv.selftest) {
      AesGcmSiv.selftest().catch((e) => console.warn("GCM-SIV selftest", e));
    }
    if (!detectorSupported()) {
      setScanStatus("No BarcodeDetector — tap core or use paste fallback (Chrome / Safari 17+)");
    }
  }).catch((e) => {
    console.warn("k0 restore", e);
    showSecureBanner();
  });
  requestAnimationFrame(tick);
})();
