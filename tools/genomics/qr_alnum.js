/* QR alphanumeric ECC-L, versions 2–4, mask 0. Enough for DC34 nonce/gene base45. */
(function (global) {
  const ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";
  const EXP = new Uint8Array(512);
  const LOG = new Uint8Array(256);
  (function initGf() {
    let x = 1;
    for (let i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d;
    }
    for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  })();
  function gfMul(a, b) {
    if (!a || !b) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  const VERSIONS = {
    2: { size: 25, data: 34, ec: 10, align: 18, cap: 47 },
    3: { size: 29, data: 55, ec: 15, align: 22, cap: 77 },
    4: { size: 33, data: 80, ec: 20, align: 26, cap: 114 },
  };

  function rsGen(n) {
    let g = [1];
    for (let i = 0; i < n; i++) {
      const coef = EXP[i];
      const next = new Array(g.length + 1).fill(0);
      for (let j = 0; j < g.length; j++) {
        next[j] ^= gfMul(g[j], coef);
        next[j + 1] ^= g[j];
      }
      g = next;
    }
    g.reverse(); // leading 1 first, matches qrcode rsPoly_LUT
    return g;
  }

  function rsBlock(data, ecLen) {
    const gen = rsGen(ecLen);
    const ec = new Array(ecLen).fill(0);
    for (const byte of data) {
      const factor = byte ^ ec[0];
      ec.shift();
      ec.push(0);
      if (!factor) continue;
      for (let j = 0; j < ecLen; j++) ec[j] ^= gfMul(gen[j + 1], factor);
    }
    return ec;
  }

  function pickVersion(nChars) {
    for (const v of [2, 3, 4]) {
      if (nChars <= VERSIONS[v].cap) return v;
    }
    throw new Error("QR payload too long for v4 alphanumeric L");
  }

  function alnumBits(text) {
    const bits = [];
    const put = (val, n) => {
      for (let i = n - 1; i >= 0; i--) bits.push((val >> i) & 1);
    };
    put(0b0010, 4);
    put(text.length, 9);
    for (let i = 0; i + 1 < text.length; i += 2) {
      const a = ALNUM.indexOf(text[i]);
      const b = ALNUM.indexOf(text[i + 1]);
      if (a < 0 || b < 0) throw new Error("not QR alphanumeric");
      put(a * 45 + b, 11);
    }
    if (text.length & 1) {
      const a = ALNUM.indexOf(text[text.length - 1]);
      if (a < 0) throw new Error("not QR alphanumeric");
      put(a, 6);
    }
    return bits;
  }

  function dataCodewords(text, spec) {
    const bits = alnumBits(text);
    const need = spec.data * 8;
    const term = Math.min(4, need - bits.length);
    for (let i = 0; i < term; i++) bits.push(0);
    while (bits.length % 8) bits.push(0);
    let pad = true;
    while (bits.length + 8 <= need) {
      const p = pad ? 0xec : 0x11;
      pad = !pad;
      for (let i = 7; i >= 0; i--) bits.push((p >> i) & 1);
    }
    while (bits.length < need) bits.push(0);
    const cw = [];
    for (let i = 0; i < bits.length; i += 8) {
      let v = 0;
      for (let j = 0; j < 8; j++) v = (v << 1) | bits[i + j];
      cw.push(v);
    }
    return cw;
  }

  function placeFinder(mat, func, r, c) {
    for (let y = -1; y <= 7; y++) {
      for (let x = -1; x <= 7; x++) {
        const rr = r + y;
        const cc = c + x;
        if (rr < 0 || cc < 0 || rr >= mat.length || cc >= mat.length) continue;
        const on = x >= 0 && x <= 6 && y >= 0 && y <= 6 &&
          (x === 0 || x === 6 || y === 0 || y === 6 || (x >= 2 && x <= 4 && y >= 2 && y <= 4));
        if (y >= 0 && y <= 6 && x >= 0 && x <= 6) {
          mat[rr][cc] = on;
          func[rr][cc] = true;
        } else if (rr >= 0 && cc >= 0 && rr < mat.length && cc < mat.length) {
          mat[rr][cc] = false;
          func[rr][cc] = true;
        }
      }
    }
  }

  function placeAlign(mat, func, pos) {
    for (let y = -2; y <= 2; y++) {
      for (let x = -2; x <= 2; x++) {
        const rr = pos + y;
        const cc = pos + x;
        const on = Math.max(Math.abs(x), Math.abs(y)) !== 1;
        mat[rr][cc] = on;
        func[rr][cc] = true;
      }
    }
  }

  // ECC L + mask 0 format bits (see python-qrcode dump)
  const FMT_L_M0 = [1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0];

  function placeFormat(mat, func, size) {
    const f = FMT_L_M0;
    const set = (r, c, bit) => {
      mat[r][c] = !!bit;
      func[r][c] = true;
    };
    for (let i = 0; i <= 5; i++) set(8, i, f[i]);
    set(8, 7, f[6]);
    set(8, 8, f[7]);
    set(7, 8, f[8]);
    for (let i = 9; i <= 14; i++) set(14 - i, 8, f[i]);
    for (let i = 0; i <= 6; i++) set(size - 1 - i, 8, f[i]);
    set(8, size - 8, f[7]);
    for (let i = 8; i <= 14; i++) set(8, size - 15 + i, f[i]);
    mat[size - 8][8] = true;
    func[size - 8][8] = true;
  }

  function functionMatrix(spec) {
    const n = spec.size;
    const mat = Array.from({ length: n }, () => Array(n).fill(false));
    const func = Array.from({ length: n }, () => Array(n).fill(false));
    placeFinder(mat, func, 0, 0);
    placeFinder(mat, func, 0, n - 7);
    placeFinder(mat, func, n - 7, 0);
    for (let i = 8; i < n - 8; i++) {
      mat[6][i] = i % 2 === 0;
      mat[i][6] = i % 2 === 0;
      func[6][i] = true;
      func[i][6] = true;
    }
    placeAlign(mat, func, spec.align);
    placeFormat(mat, func, n);
    return { mat, func };
  }

  function mapData(mat, func, cw) {
    const n = mat.length;
    const out = mat.map((row) => row.slice());
    let inc = -1;
    let row = n - 1;
    let bitIndex = 7;
    let byteIndex = 0;
    for (let col = n - 1; col > 0; col -= 2) {
      if (col <= 6) col -= 1;
      while (true) {
        for (const c of [col, col - 1]) {
          if (!func[row][c]) {
            let dbit = false;
            if (byteIndex < cw.length) dbit = ((cw[byteIndex] >> bitIndex) & 1) === 1;
            if ((row + c) % 2 === 0) dbit = !dbit; // mask 0
            out[row][c] = dbit;
            bitIndex -= 1;
            if (bitIndex === -1) {
              byteIndex += 1;
              bitIndex = 7;
            }
          }
        }
        row += inc;
        if (row < 0 || row >= n) {
          row -= inc;
          inc = -inc;
          break;
        }
      }
    }
    return out;
  }

  function encode(text) {
    text = String(text);
    const v = pickVersion(text.length);
    const spec = VERSIONS[v];
    const dc = dataCodewords(text, spec);
    const ec = rsBlock(dc, spec.ec);
    const cw = dc.concat(ec);
    const { mat, func } = functionMatrix(spec);
    return { version: v, size: spec.size, matrix: mapData(mat, func, cw) };
  }

  function draw(canvas, text, opts) {
    opts = opts || {};
    const qr = encode(text);
    const { matrix, size, version } = qr;
    const quiet = opts.quiet == null ? 4 : opts.quiet;
    const dim = size + quiet * 2;
    const css = Math.max(canvas.clientWidth || 0, opts.cssSize || 220);
    const scale = Math.max(2, Math.floor(css / dim) || 4);
    canvas.width = dim * scale;
    canvas.height = dim * scale;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#111";
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        if (matrix[y][x]) ctx.fillRect((x + quiet) * scale, (y + quiet) * scale, scale, scale);
      }
    }
    return { version, size };
  }

  global.QrAlnum = { encode, draw, _debug: { dataCodewords, rsBlock, VERSIONS, pickVersion } };
})(typeof window !== "undefined" ? window : globalThis);
