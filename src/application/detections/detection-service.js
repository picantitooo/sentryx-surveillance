/** @param {{ inferenceClient: (path: string) => Promise<any> }} dependencies */
export function createDetectionService({ inferenceClient }) {
  return {
    /** @param {{ limit?: number, offset?: number }} options */
    async list({ limit = 10, offset = 0 } = {}) {
      const payload = await inferenceClient(`/detections?limit=${Math.min(Math.max(limit, 1), 100)}&offset=${Math.max(offset, 0)}`);
      return Array.isArray(payload) ? { items: payload, total: null } : { items: payload.items ?? payload.detections ?? [], total: Number.isFinite(payload.total) ? payload.total : null };
    }
  };
}
