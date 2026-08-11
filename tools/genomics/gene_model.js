/* Port of scripts/dc34_gene.py + approx_frame for offline browser use. */
(function (global) {
  const HAPLOID_SIZE = 9;

  const BadgeType = {
    UBER: 0, OTHER: 1, COMMUNITY: 2, VILLAGE: 3, CTF: 4, HUMAN: 5, GOON: 6, NONE: 7,
  };
  const BadgeNames = ["uber", "other", "community", "village", "ctf", "human", "goon", "none"];
  /**
   * 13 physical colorways (12 peacock hexes + Uber). Firmware only has 7 BadgeTypes;
   * CTF+Contest share SAO 001 / CtfContest, exhibitor-class share SAO 100 / Other.
   * PCB hexes matched to public CHEESO / media colorways (Human black, Artist pink, …).
   * No promo photos are bundled — outlines live in assets/*.svg only.
   */
  const Colorways = [
    { id: "human", label: "Human", family: "human", badgeType: 5, sao: "101", pcb: "#161412", color: "#c47832", hint: "attendee sun · black + white ink + copper rim" },
    { id: "goon", label: "Goon", family: "inhuman", badgeType: 6, sao: "011", pcb: "#b01c24", color: "#b01c24", hint: "goon / ops · red gears" },
    { id: "village", label: "Village", family: "inhuman", badgeType: 3, sao: "110", pcb: "#e45c12", color: "#e45c12", hint: "village staff · orange gears" },
    { id: "community", label: "Community", family: "inhuman", badgeType: 2, sao: "010", pcb: "#2bb3a3", color: "#2bb3a3", hint: "community · teal gears" },
    { id: "ctf", label: "CTF", family: "inhuman", badgeType: 4, sao: "001", pcb: "#1a2744", color: "#1a2744", hint: "CTF · navy gears (same firmware type as Contest)" },
    { id: "contest", label: "Contest", family: "inhuman", badgeType: 4, sao: "001", pcb: "#f0c40a", color: "#f0c40a", hint: "contest · yellow gears (SAO 001 w/ CTF)" },
    { id: "cfp", label: "CFP", family: "inhuman", badgeType: 1, sao: "100", pcb: "#f3f1ea", color: "#d4af37", hint: "call for papers · white gears" },
    { id: "artist", label: "Artist", family: "inhuman", badgeType: 1, sao: "100", pcb: "#e0187a", color: "#e0187a", hint: "artist · hot pink gears" },
    { id: "press", label: "Press", family: "inhuman", badgeType: 1, sao: "100", pcb: "#2d9a3a", color: "#2d9a3a", hint: "press · green gears" },
    { id: "exhibitor", label: "Exhibitor", family: "inhuman", badgeType: 1, sao: "100", pcb: "#8b8d86", color: "#8b8d86", hint: "exhibitor · cool gray gears" },
    { id: "vendor", label: "Vendor", family: "inhuman", badgeType: 1, sao: "100", pcb: "#5c248a", color: "#5c248a", hint: "vendor · purple gears" },
    { id: "speaker", label: "Speaker", family: "inhuman", badgeType: 1, sao: "100", pcb: "#12b5dc", color: "#12b5dc", hint: "speaker · cyan gears" },
    { id: "uber", label: "Uber", family: "inhuman", badgeType: 0, sao: "000", pcb: "#121214", color: "#d4af37", hint: "uber · black machined · 18 LEDs on hardware" },
  ];
  const ColorwayOrder = Colorways.map((c) => c.id);
  /** Firmware type picker order (legacy). Prefer ColorwayOrder in the UI. */
  const BadgeSelectOrder = [5, 6, 3, 2, 4, 1, 0];
  const BadgeInfo = [
    { id: 0, name: "uber", label: "Uber", family: "inhuman", sao: "000", color: "#d4af37", hint: "machined · 18 LEDs on hardware" },
    { id: 1, name: "other", label: "Other", family: "inhuman", sao: "100", color: "#8b8d86", hint: "CFP / artist / press / exhibitor / vendor / speaker" },
    { id: 2, name: "community", label: "Community", family: "inhuman", sao: "010", color: "#2bb3a3", hint: "community staff" },
    { id: 3, name: "village", label: "Village", family: "inhuman", sao: "110", color: "#e45c12", hint: "village staff" },
    { id: 4, name: "ctf", label: "CTF", family: "inhuman", sao: "001", color: "#1a2744", hint: "CTF + contest (shared firmware type)" },
    { id: 5, name: "human", label: "Human", family: "human", sao: "101", color: "#c47832", hint: "attendee sun carrier" },
    { id: 6, name: "goon", label: "Goon", family: "inhuman", sao: "011", color: "#b01c24", hint: "goon / ops" },
  ];
  const MutationRate = { NONE: 0, BASELINE: 64, ELEVATED: 100, RADIOACTIVE: 140, APOCALYPTIC: 240 };
  const MutationNames = { 0: "none", 64: "baseline", 100: "elevated", 140: "radioactive", 240: "apocalyptic" };
  const DC34_HEADER = [0x49, 0xdb, 0x76, 0x71, 0xf3, 0x44, 0x35, 0xed, 0x5f, 0xdd, 0xff, 0xdf, 0xcb, 0xb7, 0x50, 0x8a];
  const K0_HASH_PREFIX = "dca9ea49";
  /** Public conference k0 (community drop; see docs/CREDITS.md). K = Ko‖Kp. */
  const PUBLIC_K0_HEX = "7ad84ed0e00aec0499ede65615e1da517c0150230d2abc6ec7b566e621e740b3";
  const B45_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";

  const RANGES = {
    hue: {
      6: [0, 20], 2: [32, 80], 3: [80, 128], 5: [128, 160], 1: [160, 192], 4: [192, 220], 0: [220, 255], 7: [128, 160],
    },
    sat: {
      6: [160, 255], 2: [32, 160], 3: [32, 160], 5: [32, 255], 1: [16, 255], 4: [16, 255], 0: [130, 255], 7: [32, 255],
    },
    chaser: {
      6: [90, 255], 2: [90, 255], 3: [90, 255], 5: [90, 255], 1: [0, 255], 4: [90, 255], 0: [0, 45], 7: [90, 255],
    },
    nonlin: {
      6: [0, 255], 2: [0, 255], 3: [0, 255], 5: [0, 255], 1: [0, 90], 4: [0, 90], 0: [0, 44], 7: [0, 255],
    },
    cd_dir: {
      6: [0, 255], 2: [0, 255], 3: [0, 45], 5: [0, 255], 1: [0, 255], 4: [0, 255], 0: [0, 45], 7: [0, 255],
    },
    cd_period_max: { 6: 4, 2: 2, 3: 4, 5: 5, 1: 6, 4: 6, 0: 3, 7: 4 },
  };

  const LOCI = [
    "cd_period", "cd_rate", "cd_dir", "sat", "hue_ratedir", "hue_base", "hue_bound", "chaser", "nonlin",
  ];

  function randInt(lo, hi, rng) {
    return lo + Math.floor(rng() * (hi - lo + 1));
  }
  function randU8(rng) { return randInt(0, 255, rng); }
  function mulberry32(a) {
    return function () {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function rngFromSeed(seed) {
    if (seed == null || seed === "") return Math.random;
    return mulberry32(Number(seed) >>> 0 || 0xdc34);
  }

  function haploidFromType(bt, rng) {
    rng = rng || Math.random;
    const h = {};
    h.cd_period = randInt(0, RANGES.cd_period_max[bt], rng);
    h.cd_rate = randU8(rng);
    let [lo, hi] = RANGES.cd_dir[bt];
    h.cd_dir = randInt(lo, hi, rng);
    [lo, hi] = RANGES.sat[bt];
    h.sat = randInt(lo, hi, rng);
    h.hue_ratedir = randU8(rng);
    [lo, hi] = RANGES.hue[bt];
    h.hue_base = bt === BadgeType.GOON ? 0 : randInt(lo, hi, rng);
    h.hue_bound = bt === BadgeType.UBER ? 255 : randInt(h.hue_base, hi, rng);
    [lo, hi] = RANGES.chaser[bt];
    h.chaser = randInt(lo, hi, rng);
    [lo, hi] = RANGES.nonlin[bt];
    h.nonlin = randInt(lo, hi, rng);
    return h;
  }

  function serialize(h) {
    return LOCI.map((k) => h[k] & 0xff);
  }
  function deserialize(bytes) {
    if (!bytes || bytes.length < 9) return null;
    const h = {};
    LOCI.forEach((k, i) => { h[k] = bytes[i] & 0xff; });
    return h;
  }
  function toHex(bytes) {
    return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  function fromHex(hex) {
    const s = hex.replace(/\s+/g, "");
    if (s.length % 2) throw new Error("odd hex");
    const out = [];
    for (let i = 0; i < s.length; i += 2) out.push(parseInt(s.slice(i, i + 2), 16));
    return out;
  }

  function phenotype(a, b) {
    const e = {
      cd_period: Math.min(Math.floor((a.cd_period + b.cd_period) / 2), 6),
      cd_rate: Math.floor((a.cd_rate + b.cd_rate) / 2) & 0xff,
      cd_dir: Math.min(a.cd_dir + b.cd_dir, 255),
      sat: Math.min(a.sat + b.sat, 255),
      hue_ratedir: (2 + (14 - Math.min(a.hue_ratedir + b.hue_ratedir, 14))) % 14,
      hue_base: Math.min(a.hue_base, b.hue_base),
      hue_bound: Math.max(a.hue_bound, b.hue_bound),
      chaser: Math.min(a.chaser + b.chaser, 255),
      nonlin: Math.min(a.chaser + b.nonlin, 255),
    };
    e.hue_bound = Math.max(e.hue_bound, e.hue_base);
    return e;
  }

  function meiosis(a, b, rng) {
    rng = rng || Math.random;
    const pick = () => (rng() < 0.5 ? a : b);
    const p0 = pick();
    const g = {
      cd_period: p0.cd_period,
      cd_rate: p0.cd_rate,
      cd_dir: p0.cd_dir,
      sat: pick().sat,
    };
    const p1 = pick();
    g.hue_ratedir = p1.hue_ratedir;
    g.hue_base = p1.hue_base;
    g.hue_bound = p1.hue_bound;
    g.chaser = pick().chaser;
    g.nonlin = pick().nonlin;
    return g;
  }

  function grayEncode(n) { n &= 0xff; return n ^ (n >> 1); }
  function grayDecode(n) {
    n &= 0xff;
    let p = n;
    while ((n >> 1) !== 0) { n >>= 1; p ^= n; }
    return p & 0xff;
  }
  function mutationFunc(gene, bits, rng) {
    const shift = randInt(0, 7, rng);
    return grayDecode(grayEncode(gene) ^ ((bits << shift) & 0xff));
  }
  function mutate(h, rate, rng) {
    rng = rng || Math.random;
    if (rate === 0) return { ...h };
    const bitsMap = { 0: 0, 64: 1, 100: 3, 140: 7, 240: 0x1f };
    const bits = bitsMap[rate] ?? 1;
    const out = { ...h };
    for (const k of LOCI) {
      if (rng() * 256 < rate) {
        let v = mutationFunc(out[k], bits, rng);
        if (k === "cd_period") v %= 7;
        out[k] = v;
      }
    }
    return out;
  }

  function serializeDiploid(a, b) {
    return serialize(a).concat(serialize(b));
  }
  function deserializeDiploid(bytes) {
    if (!bytes || bytes.length < 18) return null;
    return { a: deserialize(bytes.slice(0, 9)), b: deserialize(bytes.slice(9, 18)) };
  }

  function getPaddedGamete(diploid, badgeType, rate, rng) {
    rng = rng || Math.random;
    let g = meiosis(diploid.a, diploid.b, rng);
    if (rate) g = mutate(g, rate, rng);
    const d = new Array(16).fill(0);
    const ser = serialize(g);
    for (let i = 0; i < 9; i++) d[i] = ser[i];
    d[15] = badgeType & 0xff;
    return { haploid: g, padded: d };
  }

  function haploidFromPadded(padded) {
    if (!padded || padded.length < 9) return null;
    return { haploid: deserialize(padded), badgeType: padded[15] & 0xff };
  }

  function inbreedingRate(badgeType) {
    return badgeType === BadgeType.HUMAN ? MutationRate.ELEVATED : MutationRate.BASELINE;
  }

  function maxRate(a, b) {
    return Math.max(a || 0, b || 0);
  }

  /**
   * Vault syngamy: optional inbreeding mutate on sperm, egg = meiosis+mutate,
   * new diploid = [egg, sperm]. Caller keeps prior for rollback.
   */
  function syngamy(diploid, sperm, incomingType, myType, ambientRate, rng) {
    rng = rng || Math.random;
    const same = (incomingType & 0xff) === (myType & 0xff);
    let rateUsed = ambientRate || 0;
    let spermOut = { ...sperm };
    if (same) {
      rateUsed = maxRate(inbreedingRate(myType), ambientRate || 0);
      spermOut = mutate(spermOut, rateUsed, rng);
    }
    const eggRate = maxRate(same ? rateUsed : 0, ambientRate || 0);
    let egg = meiosis(diploid.a, diploid.b, rng);
    egg = mutate(egg, eggRate, rng);
    return {
      egg,
      sperm: spermOut,
      diploid: { a: egg, b: spermOut },
      inbreeding: same,
      rate: rateUsed,
    };
  }

  function b45encode(bytes) {
    bytes = Array.from(bytes);
    let out = "";
    let i = 0;
    while (i + 1 < bytes.length) {
      const v = bytes[i] * 256 + bytes[i + 1];
      const c = v % 45;
      const d = Math.floor(v / 45) % 45;
      const e = Math.floor(v / (45 * 45));
      out += B45_ALPHABET[c] + B45_ALPHABET[d] + B45_ALPHABET[e];
      i += 2;
    }
    if (i < bytes.length) {
      const v = bytes[i];
      out += B45_ALPHABET[v % 45] + B45_ALPHABET[Math.floor(v / 45)];
    }
    return out;
  }

  function b45decode(str) {
    const s = String(str).replace(/[\r\n]/g, "");
    const idx = (ch) => {
      const i = B45_ALPHABET.indexOf(ch);
      if (i < 0) throw new Error("invalid base45 char " + JSON.stringify(ch));
      return i;
    };
    if (s.length % 3 === 1) throw new Error("invalid base45 length");
    const out = [];
    let i = 0;
    while (i + 2 < s.length) {
      const v = idx(s[i]) + idx(s[i + 1]) * 45 + idx(s[i + 2]) * 45 * 45;
      if (v > 0xffff) throw new Error("base45 overflow");
      out.push((v >> 8) & 0xff, v & 0xff);
      i += 3;
    }
    if (i < s.length) {
      const v = idx(s[i]) + idx(s[i + 1]) * 45;
      if (v > 0xff) throw new Error("base45 overflow");
      out.push(v & 0xff);
    }
    return out;
  }

  function bytesEqual(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if ((a[i] & 0xff) !== (b[i] & 0xff)) return false;
    return true;
  }

  function parseBreedPayload(raw) {
    let bytes;
    if (typeof raw === "string") {
      const t = raw.replace(/[\r\n]/g, "").trim();
      const compact = t.replace(/\s+/g, "");
      if (/^[0-9a-fA-F]+$/.test(compact) && compact.length % 2 === 0 &&
          [24, 32, 56, 64].includes(compact.length)) {
        bytes = fromHex(compact);
      } else {
        bytes = b45decode(t);
      }
    } else {
      bytes = Array.from(raw);
    }
    if (bytes.length === 12) return { kind: "nonce", nonce: bytes, raw: bytes };
    if (bytes.length >= 28 && bytesEqual(bytes.slice(0, 16), DC34_HEADER)) {
      return { kind: "nonce", nonce: bytes.slice(16, 28), raw: bytes };
    }
    if (bytes.length === 32) return { kind: "gene", ctTag: bytes, raw: bytes };
    if (bytes.length === 16) return { kind: "gamete", padded: bytes, raw: bytes };
    return { kind: "unknown", raw: bytes };
  }

  function noncePayload(nonce12) {
    return DC34_HEADER.concat(Array.from(nonce12).slice(0, 12));
  }

  function randomNonce() {
    const n = new Uint8Array(12);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) crypto.getRandomValues(n);
    else for (let i = 0; i < 12; i++) n[i] = Math.floor(Math.random() * 256);
    // firmware rejects nonce == header[:12]
    if (bytesEqual(Array.from(n), DC34_HEADER.slice(0, 12))) n[0] ^= 1;
    return Array.from(n);
  }

  function infoFor(bt) {
    return BadgeInfo[bt] || BadgeInfo[BadgeType.HUMAN];
  }

  function colorwayFor(id) {
    if (id && typeof id === "object" && id.id) return id;
    if (typeof id === "number") {
      return Colorways.find((c) => c.badgeType === id) || Colorways[0];
    }
    const s = String(id == null ? "" : id).toLowerCase();
    if (!s) return Colorways[0];
    const byId = Colorways.find((c) => c.id === s);
    if (byId) return byId;
    const fi = BadgeNames.indexOf(s);
    if (fi >= 0) return Colorways.find((c) => c.badgeType === fi) || Colorways[0];
    return Colorways[0];
  }

  function firmwareLabel(bt) {
    return (BadgeInfo[bt] || BadgeInfo[BadgeType.HUMAN]).label;
  }

  function hsvToRgb(h, s, v) {
    h &= 0xff; s &= 0xff; v &= 0xff;
    if (s === 0) return [v, v, v];
    const region = Math.floor(h / 43);
    const remainder = (h - region * 43) * 6;
    const p = (v * (255 - s)) >> 8;
    const q = (v * (255 - ((s * remainder) >> 8))) >> 8;
    const t = (v * (255 - ((s * (255 - remainder)) >> 8))) >> 8;
    switch (region) {
      case 0: return [v, t, p];
      case 1: return [q, v, p];
      case 2: return [p, v, t];
      case 3: return [p, q, v];
      case 4: return [t, p, v];
      default: return [v, p, q];
    }
  }

  function approxFrame(pheno, tMs, opts) {
    opts = opts || {};
    const count = opts.ringLeds || 8;
    let tau = Math.floor(60 + (pheno.cd_rate / 255) * (700 - 60));
    tau = Math.max(1, tau);
    const curtime = tMs / 10;
    const indextime = -(curtime % tau);
    let loop = opts.loop != null ? opts.loop & 0x1ff : Math.floor(tMs / Math.max(tau / 8, 1)) & 0x1ff;
    const hueRate = pheno.hue_ratedir & 0xf;
    const hueDir = ((pheno.hue_ratedir >> 4) & 0xf) > 10 ? 1 : 0;
    const half = Math.max(Math.floor(count / 2), 1);
    const ring = [];
    let eyeLeft = [0, 0, 0];
    let eyeRight = [0, 0, 0];
    let shootI = -1;
    if (pheno.chaser < 88) {
      shootI = Math.floor(loop / 2) % count;
      if (shootI < half) eyeLeft = [192, 192, 192];
      else eyeRight = [192, 192, 192];
    }
    for (let i = 0; i < count; i++) {
      let hueTemp = hueDir
        ? (((128 / half) * i - loop * hueRate) & 0x1ff)
        : (((128 / half) * i + loop * hueRate) & 0x1ff);
      if (hueTemp > 0xff) hueTemp = 511 - hueTemp;
      const span = Math.max(pheno.hue_bound - pheno.hue_base, 0);
      const hh = span ? pheno.hue_base + Math.floor((hueTemp * span) / 255) : pheno.hue_base;
      const space = 2 * Math.PI * pheno.cd_period * (i / Math.max(count - 1, 1));
      const time = (2 * Math.PI * indextime) / tau;
      const spacetime = pheno.cd_dir > 128 ? space + time : space - time;
      let val = Math.floor(127 * (1 + Math.cos(spacetime))) & 0xff;
      if (pheno.nonlin > 127) val = (val * val) >> 8;
      let rgb;
      if (pheno.chaser < 88 && shootI === i) rgb = [160, 160, 160];
      else rgb = hsvToRgb(hh, pheno.sat, val);
      if (pheno.chaser >= 88) {
        if (i === 0) eyeLeft = rgb.slice();
        if (i === half) eyeRight = rgb.slice();
      }
      ring.push(rgb);
    }
    const dimShift = opts.dimShift == null ? 0 : opts.dimShift;
    const eyeShift = opts.eyeShift == null ? dimShift : opts.eyeShift;
    const dim = (c, sh) => (sh ? c.map((x) => x >> sh) : c);
    return {
      ring: ring.map((c) => dim(c, dimShift)),
      eyes: [dim(eyeLeft, eyeShift), dim(eyeRight, eyeShift)],
      loop,
      tauMs: tau * 10,
    };
  }

  function cloneHaploid(h) {
    const out = {};
    LOCI.forEach((k) => { out[k] = (h[k] || 0) & 0xff; });
    if (out.hue_bound < out.hue_base) out.hue_bound = out.hue_base;
    return out;
  }

  global.DC34Gene = {
    BadgeType,
    BadgeNames,
    BadgeSelectOrder,
    BadgeInfo,
    Colorways,
    ColorwayOrder,
    colorwayFor,
    firmwareLabel,
    MutationRate,
    MutationNames,
    DC34_HEADER,
    K0_HASH_PREFIX,
    PUBLIC_K0_HEX,
    LOCI,
    RANGES,
    haploidFromType,
    serialize,
    deserialize,
    serializeDiploid,
    deserializeDiploid,
    toHex,
    fromHex,
    phenotype,
    meiosis,
    mutate,
    getPaddedGamete,
    haploidFromPadded,
    inbreedingRate,
    maxRate,
    syngamy,
    approxFrame,
    cloneHaploid,
    rngFromSeed,
    b45encode,
    b45decode,
    parseBreedPayload,
    noncePayload,
    randomNonce,
    infoFor,
  };
})(typeof window !== "undefined" ? window : globalThis);
