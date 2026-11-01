import { json } from '@sveltejs/kit';
import { alertService } from '#presentation/server/server-services.js';

export async function GET({ url }) {
  const camera = url.searchParams.get('camera')?.trim() || null;
  const status = url.searchParams.get('status')?.trim() || null;
  const limit = Number(url.searchParams.get('limit')) || 100;
  const offset = Number(url.searchParams.get('offset')) || 0;
  try {
    return json(await alertService.list({ camera, status, limit, offset }));
  } catch (error) {
    return json({ items: [], total: 0, limit, offset, error: error instanceof Error ? error.message : String(error) }, { status: 502 });
  }
}
