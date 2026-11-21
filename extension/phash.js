// Perceptual hash (32x32 grayscale -> DCT -> 8x8 low frequencies vs median) computed in the page.
// Exposes globalThis.TROP_phash(imageSource) -> 16 hex chars, or null when pixels are unreadable (tainted canvas).
(function () {
  const N = 32, K = 8;
  const cosT = Array.from({ length: K }, (_, u) =>
    Array.from({ length: N }, (_, x) => Math.cos(((2 * x + 1) * u * Math.PI) / (2 * N))));

  function dct8(gray) {
    const out = new Array(K * K).fill(0);
    for (let u = 0; u < K; u++) {
      for (let v = 0; v < K; v++) {
        let s = 0;
        for (let y = 0; y < N; y++) {
          const cy = cosT[v][y];
          for (let x = 0; x < N; x++) s += gray[y * N + x] * cosT[u][x] * cy;
        }
        out[v * K + u] = s;
      }
    }
    return out;
  }

  function phashFromGray(gray) {
    const c = dct8(gray);
    const sorted = c.slice(1).sort((a, b) => a - b); // without DC
    const med = (sorted[31] + sorted[32]) / 2;
    let hex = "";
    for (let i = 0; i < 64; i += 4) {
      let nib = 0;
      for (let j = 0; j < 4; j++) nib = (nib << 1) | (i + j > 0 && c[i + j] > med ? 1 : 0);
      hex += nib.toString(16);
    }
    return hex;
  }

  function phash(source) {
    try {
      const cv = document.createElement("canvas");
      cv.width = N; cv.height = N;
      const ctx = cv.getContext("2d", { willReadFrequently: true });
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, N, N);
      ctx.drawImage(source, 0, 0, N, N);
      const d = ctx.getImageData(0, 0, N, N).data; // throws SecurityError when tainted
      const gray = new Array(N * N);
      for (let i = 0; i < N * N; i++) gray[i] = 0.299 * d[4 * i] + 0.587 * d[4 * i + 1] + 0.114 * d[4 * i + 2];
      return phashFromGray(gray);
    } catch (e) {
      return null;
    }
  }

  globalThis.TROP_phash = phash;
})();
