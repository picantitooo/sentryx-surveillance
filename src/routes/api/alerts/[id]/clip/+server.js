import { json } from '@sveltejs/kit';
import { createServerServices } from '#presentation/server/server-services.js';

export async function GET({ params, request }) {
  const { alertService } = createServerServices(request.headers.get('authorization'));
  try {
    return json(await alertService.getClip(params.id));
  } catch (error) {
    return json({ status: 'missing', url: null, duration_seconds: null, error: error instanceof Error ? error.message : String(error) }, { status: 502 });
  }
}
