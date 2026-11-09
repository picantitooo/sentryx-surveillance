/** @param {{ inferenceClient: (path: string) => Promise<any> }} dependencies */
export function createDetectionService({ inferenceClient }) {
  return {
    /** @param {{ limit?: number, offset?: number }} options */
    async list({ limit = 10, offset = 0 } = {}) {
      const safeLimit = boundedInteger(limit, 10, 1, 100);
      const safeOffset = boundedInteger(offset, 0, 0, Number.MAX_SAFE_INTEGER);
      const payload = await inferenceClient(`/detections?limit=${safeLimit}&offset=${safeOffset}`);
      return Array.isArray(payload) ? { items: payload, total: null } : { items: payload.items ?? payload.detections ?? [], total: Number.isFinite(payload.total) ? payload.total : null };
    }
  };
}

/** @param {unknown} value @param {number} fallback @param {number} minimum @param {number} maximum */
function boundedInteger(value, fallback, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(Math.max(Math.trunc(number), minimum), maximum);
}
