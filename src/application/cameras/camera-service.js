export class CameraNotFoundError extends Error {}

/**
 * @param {{
 *   inferenceClient: (path: string, options?: { method?: string, body?: unknown }) => Promise<any>,
 *   cameraRegistry: {
 *     list: () => Promise<any[]>,
 *     get: (id: string | null | undefined) => Promise<any>,
 *     register: (camera: any) => Promise<any>,
 *     remove: (id: string) => Promise<void>
 *   }
 * }} dependencies
 */
export function createCameraService({ inferenceClient, cameraRegistry }) {
  return {
    async list() {
      return cameraRegistry.list();
    },

    /** @param {{ name: string, normalizedUrl: string, streamPath: string }} input */
    async register({ name, normalizedUrl, streamPath }) {
      // Se prepara un ID de compatibilidad; TA-10 lo ignorará y generará source_id en backend.
      const cameras = await cameraRegistry.list();
      const number = nextAvailableCameraNumber(cameras);
      const id = `camara${number}`;
      const camera = await cameraRegistry.register({ id, name, streamPath, normalizedUrl });

      try {
        const source = await inferenceClient('/sources/start', {
          method: 'POST', body: { source_id: camera.id, stream_path: camera.streamPath ?? streamPath }
        });
        return { camera, inference: { available: true, source } };
      } catch (error) {
        return {
          camera,
          inference: { available: false, error: error instanceof Error ? error.message : String(error) }
        };
      }
    },

    /** @param {string} id */
    async start(id) {
      const camera = await cameraRegistry.get(id);
      if (!camera) throw new CameraNotFoundError('Primero registra una camara.');
      return inferenceClient('/sources/start', {
        method: 'POST', body: { source_id: camera.id, stream_path: camera.streamPath ?? camera.id }
      });
    },

    /** @param {string} id */
    async remove(id) {
      const camera = await cameraRegistry.get(id);
      if (!camera) return { removed: true };

      let warning = null;
      try {
        await inferenceClient(`/sources/${encodeURIComponent(id)}`, { method: 'DELETE' });
      } catch {
        warning = 'No se pudo detener la inferencia antes de eliminar la cámara.';
      }

      if (warning) return { removed: false, inferenceStopped: false, warning };
      await cameraRegistry.remove(id);

      return { removed: true, inferenceStopped: warning === null, warning };
    }
  };
}
import { nextAvailableCameraNumber } from '#domain/camera/camera.js';
