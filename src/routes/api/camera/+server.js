import { json } from '@sveltejs/kit';
import { normalizePlaybackUrl, streamPathFromPlaybackUrl } from '#domain/camera/camera.js';
import { cameraService } from '#presentation/server/server-services.js';

/** @param {unknown} error @param {string} fallback */
function apiErrorMessage(error, fallback) {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return message.replace(/^FastAPI\s+\d+:\s*/i, '') || fallback;
}

export async function GET() {
  try {
    return json({ cameras: await cameraService.list() });
  } catch (error) {
    console.error('Error al obtener las cámaras:', error);
    return json({ error: apiErrorMessage(error, 'No se pudieron consultar las cámaras.') }, { status: 500 });
  }
}

export async function POST({ request }) {
  const body = await request.json().catch(() => null);
  const name = typeof body?.name === 'string' ? body.name.trim() : '';
  const normalizedUrl = normalizePlaybackUrl(body?.url);
  const streamPath = streamPathFromPlaybackUrl(normalizedUrl);

  if (!name || name.length > 100) {
    return json({ error: 'El nombre es obligatorio y debe tener como máximo 100 caracteres.' }, { status: 400 });
  }
  if (!normalizedUrl || !streamPath || !/^[a-z0-9_-]{1,64}$/.test(streamPath)) {
    return json({ error: 'Ingresa una URL HTTPS válida cuyo último segmento sea el identificador de la cámara.' }, { status: 400 });
  }

  try {
    return json(await cameraService.register({ name, normalizedUrl, streamPath }), { status: 201 });
  } catch (error) {
    console.error('[SentriX] Error al registrar cámara:', error);
    return json({ error: apiErrorMessage(error, 'No se pudo registrar la cámara.') }, { status: 500 });
  }
}

export async function PUT({ request, url }) {
  const id = url.searchParams.get('id')?.trim();
  const body = await request.json().catch(() => null);
  const name = typeof body?.name === 'string' ? body.name.trim() : '';
  const normalizedUrl = normalizePlaybackUrl(body?.url);
  const streamPath = streamPathFromPlaybackUrl(normalizedUrl);
  if (!id) return json({ error: 'Falta el identificador de la cámara.' }, { status: 400 });
  if (!name || name.length > 100) return json({ error: 'El nombre es obligatorio y debe tener como máximo 100 caracteres.' }, { status: 400 });
  if (!normalizedUrl || !streamPath || !/^[a-z0-9_-]{1,64}$/.test(streamPath)) {
    return json({ error: 'Ingresa una URL HTTPS válida cuyo último segmento sea el identificador de la cámara.' }, { status: 400 });
  }
  try {
    return json({ camera: await cameraService.update(id, { name, normalizedUrl, streamPath }) });
  } catch (error) {
    console.error('[SentriX] Error al actualizar cámara:', error);
    return json({ error: apiErrorMessage(error, 'No se pudo actualizar la cámara.') }, { status: 500 });
  }
}

export async function DELETE({ url }) {
  const id = url.searchParams.get('id')?.trim();
  if (!id) return json({ error: 'Falta el identificador de la cámara.' }, { status: 400 });

  try {
    return json(await cameraService.remove(id));
  } catch (error) {
    console.error('[SentriX] Error al eliminar cámara:', error);
    return json({ error: apiErrorMessage(error, 'No se pudo eliminar la cámara.') }, { status: 500 });
  }
}
