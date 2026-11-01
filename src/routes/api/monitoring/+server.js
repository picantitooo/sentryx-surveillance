import { json } from '@sveltejs/kit';
import { MonitoringUnavailableError } from '#application/monitoring/monitoring-service.js';
import { monitoringService } from '#presentation/server/server-services.js';

export async function GET() {
  try { return json(await monitoringService.getDashboardSnapshot()); }
  catch (error) {
    if (!(error instanceof MonitoringUnavailableError)) throw error;
    return json({ available: false, health: null, alerts: [], sources: {}, error: error.message }, { status: 502 });
  }
}
