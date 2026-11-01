import { json } from '@sveltejs/kit';
import { detectionService } from '#presentation/server/server-services.js';

export async function GET({ url }) {
  const limit = Number(url.searchParams.get('limit')) || 10;
  const offset = Number(url.searchParams.get('offset')) || 0;
  try { return json(await detectionService.list({ limit, offset })); }
  catch (error) { return json({ items: [], total: 0, error: error instanceof Error ? error.message : String(error) }, { status: 502 }); }
}
