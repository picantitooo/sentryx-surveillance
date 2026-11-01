import { json } from '@sveltejs/kit';
import { alertService } from '#presentation/server/server-services.js';

export async function GET({ params }) {
  try {
    return json(await alertService.get(params.id));
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : String(error) }, { status: 502 });
  }
}
