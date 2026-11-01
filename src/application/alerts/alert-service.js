/**
 * Servicio de aplicación para los eventos de seguridad.
 * Mantiene el contrato de FastAPI fuera de las rutas HTTP de SvelteKit.
 *
 * @param {{ inferenceClient: (path: string) => Promise<any> }} dependencies
 */
export function createAlertService({ inferenceClient }) {
  return {
    /** @param {{ camera?: string | null, status?: string | null, limit?: number, offset?: number }} filters */
    async list({ camera, status, limit = 100, offset = 0 } = {}) {
      const query = new URLSearchParams({ limit: String(Math.min(Math.max(limit, 1), 500)), offset: String(Math.max(offset, 0)) });
      if (camera) query.set('camera', camera);
      if (status) query.set('status', status);
      return inferenceClient(`/alerts?${query}`);
    },
    /** @param {string} id */
    get(id) { return inferenceClient(`/alerts/${encodeURIComponent(id)}`); },
    /** @param {string} id */
    getClip(id) { return inferenceClient(`/alerts/${encodeURIComponent(id)}/clip`); }
  };
}
