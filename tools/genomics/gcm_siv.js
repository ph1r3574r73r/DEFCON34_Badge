/* AES-256-GCM-SIV (RFC 8452) via WebCrypto AES-CTR + BigInt POLYVAL.
   Matches Python cryptography AESGCMSIV / Rust aes_gcm_siv used by dc34-vault. */
(function (global) {
  const MASK128 = (1n << 128n) - 1n;
  // x^128 + x^127 + x^126 + x^121 + 1  (coeff of x^i is bit i)
  const POLY_R = (1n << 127n) | (1n << 126n) | (1n << 121n) | 1n;
  // RFC 8452: x^-128 = x^127 + x^124 + x^121 + x^114 + 1
  const X_INV_128 = (1n << 127n) | (1n << 124n) | (1n << 121n) | (1n << 114n) | 1n;

  function toU8(x) {
    if (x instanceof Uint8Array) return x;
    if (Array.isArray(x)) return Uint8Array.from(x);
    return new Uint8Array(x);
  }

  function le16ToBig(b) {
    let n = 0n;
    for (let i = 0; i < 16; i++) n |= BigInt(b[i]) << BigInt(8 * i);
    return n;
  }

  function bigToLe16(n) {
    const b = new Uint8Array(16);
    for (let i = 0; i < 16; i++) b[i] = Number((n >> BigInt(8 * i)) & 0xffn);
    return b;
  }

  function mulX(x) {
    const msb = (x >> 127n) & 1n;
    x = (x << 1n) & MASK128;
    if (msb) x ^= POLY_R;
    return x;
  }

  function gfMul(x, y) {
    let z = 0n;
    for (let i = 0; i < 128; i++) {
      if ((y >> BigInt(i)) & 1n) z ^= x;
      x = mulX(x);
    }
    return z;
  }

  /** RFC 8452 dot(a, b) = a * b * x^-128 in the POLYVAL field. */
  function dot(a, b) {
    return gfMul(gfMul(a, b), X_INV_128);
  }

  function polyval(h, data) {
    const H = le16ToBig(h);
    let y = 0n;
    const n = Math.ceil(data.length / 16);
    for (let i = 0; i < n; i++) {
      const block = new Uint8Array(16);
      const sl = data.subarray(i * 16, Math.min((i + 1) * 16, data.length));
      block.set(sl);
      y = dot(y ^ le16ToBig(block), H);
    }
    return bigToLe16(y);
  }

  function lengthBlock(aadLen, ptLen) {
    const b = new Uint8Array(16);
    const dv = new DataView(b.buffer);
    const aadBits = aadLen * 8;
    const ptBits = ptLen * 8;
    dv.setUint32(0, aadBits >>> 0, true);
    dv.setUint32(4, 0, true);
    dv.setUint32(8, ptBits >>> 0, true);
    dv.setUint32(12, 0, true);
    return b;
  }

  function concatBytes(parts) {
    let n = 0;
    for (const p of parts) n += p.length;
    const out = new Uint8Array(n);
    let o = 0;
    for (const p of parts) {
      out.set(p, o);
      o += p.length;
    }
    return out;
  }

  async function importAes(keyBytes) {
    return crypto.subtle.importKey(
      "raw",
      toU8(keyBytes),
      { name: "AES-CTR" },
      false,
      ["encrypt"],
    );
  }

  /** AES_k(block16) via CTR(counter=block, pt=0). */
  async function aesBlock(keyObj, block16) {
    const zeros = new Uint8Array(16);
    const ctr = toU8(block16).slice(0, 16);
    const out = await crypto.subtle.encrypt(
      { name: "AES-CTR", counter: ctr, length: 128 },
      keyObj,
      zeros,
    );
    return new Uint8Array(out);
  }

  function nonceBlock(nonce12, i) {
    // RFC 8452: AES(K, little_endian_32(i) || nonce)
    const b = new Uint8Array(16);
    b[0] = i & 0xff;
    b[1] = (i >>> 8) & 0xff;
    b[2] = (i >>> 16) & 0xff;
    b[3] = (i >>> 24) & 0xff;
    b.set(toU8(nonce12).subarray(0, 12), 4);
    return b;
  }

  async function deriveKeys(key32, nonce12) {
    const k = await importAes(key32);
    const blocks = [];
    for (let i = 0; i < 6; i++) blocks.push(await aesBlock(k, nonceBlock(nonce12, i)));
    const authKey = new Uint8Array(16);
    authKey.set(blocks[0].subarray(0, 8), 0);
    authKey.set(blocks[1].subarray(0, 8), 8);
    const encKey = new Uint8Array(32);
    encKey.set(blocks[2].subarray(0, 8), 0);
    encKey.set(blocks[3].subarray(0, 8), 8);
    encKey.set(blocks[4].subarray(0, 8), 16);
    encKey.set(blocks[5].subarray(0, 8), 24);
    return { authKey, encKey, encObj: await importAes(encKey) };
  }

  function computeS(authKey, plaintext, aad) {
    aad = aad || new Uint8Array(0);
    const parts = [];
    if (aad.length) parts.push(aad);
    if (plaintext.length) parts.push(toU8(plaintext));
    parts.push(lengthBlock(aad.length, plaintext.length));
    return polyval(authKey, concatBytes(parts));
  }

  async function computeTag(encObj, authKey, nonce12, plaintext, aad) {
    const s = computeS(authKey, plaintext, aad);
    const n = toU8(nonce12);
    for (let i = 0; i < 12; i++) s[i] ^= n[i];
    s[15] &= 0x7f;
    return aesBlock(encObj, s);
  }

  async function ctrXor(encObj, tag, data) {
    const counter = toU8(tag).slice();
    counter[15] |= 0x80;
    const out = await crypto.subtle.encrypt(
      { name: "AES-CTR", counter, length: 128 },
      encObj,
      toU8(data),
    );
    return new Uint8Array(out);
  }

  async function encrypt(key32, nonce12, plaintext, aad) {
    if (toU8(key32).length !== 32) throw new Error("AES-GCM-SIV key must be 32 bytes");
    if (toU8(nonce12).length !== 12) throw new Error("AES-GCM-SIV nonce must be 12 bytes");
    const { authKey, encObj } = await deriveKeys(key32, nonce12);
    const tag = await computeTag(encObj, authKey, nonce12, plaintext, aad);
    const ct = await ctrXor(encObj, tag, plaintext);
    const out = new Uint8Array(ct.length + 16);
    out.set(ct, 0);
    out.set(tag, ct.length);
    return out;
  }

  async function decrypt(key32, nonce12, ctTag, aad) {
    const raw = toU8(ctTag);
    if (raw.length < 16) throw new Error("ciphertext too short");
    const ct = raw.subarray(0, raw.length - 16);
    const tag = raw.subarray(raw.length - 16);
    const { authKey, encObj } = await deriveKeys(key32, nonce12);
    const pt = await ctrXor(encObj, tag, ct);
    const expect = await computeTag(encObj, authKey, nonce12, pt, aad);
    let diff = 0;
    for (let i = 0; i < 16; i++) diff |= tag[i] ^ expect[i];
    if (diff) throw new Error("AES-GCM-SIV: invalid tag");
    return pt;
  }

  async function selftest() {
    const k = new Uint8Array(32);
    k[31] = 1;
    const n = new Uint8Array(12).fill(0x11);
    const pt = Uint8Array.from({ length: 16 }, (_, i) => i);
    const ct = await encrypt(k, n, pt, new Uint8Array(0));
    const want = "56b8bea8add7dd13ae4ccf8551bcd79d212ae72e444a0af81d4af99dc7c086cc";
    const hex = Array.from(ct).map((b) => b.toString(16).padStart(2, "0")).join("");
    if (hex !== want) throw new Error("GCM-SIV selftest mismatch: " + hex);
    const back = await decrypt(k, n, ct, new Uint8Array(0));
    for (let i = 0; i < 16; i++) if (back[i] !== pt[i]) throw new Error("GCM-SIV roundtrip fail");
    return true;
  }

  global.AesGcmSiv = { encrypt, decrypt, selftest, polyval };
})(typeof window !== "undefined" ? window : globalThis);
