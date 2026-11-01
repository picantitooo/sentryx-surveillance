import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createMonitoringService,
  MonitoringUnavailableError
} from '../../../src/application/monitoring/monitoring-service.js';

test('devuelve estado saludable cuando todavía no existen cámaras', async () => {
  const service = createMonitoringService({
    inferenceClient: async (path) => path === '/health' ? { status: 'ok' } : null,
    cameraRegistry: { list: async () => [], get: async () => null }
  });
  const result = await service.getSnapshot(null);
  assert.equal(result.available, true);
  assert.equal(result.source, null);
  assert.deepEqual(result.detections, []);
});

test('filtra detecciones anteriores al registro de la cámara', async () => {
  const camera = { id: 'camara1', registeredAt: '2026-10-17T10:00:00.000Z' };
  const inferenceClient = async (path) => {
    if (path === '/health') return { status: 'ok' };
    if (path.includes('/status')) return { status: 'running' };
    if (path.startsWith('/detections')) return [
      { id: 'antigua', fecha_hora: '2026-10-17T09:59:00.000Z' },
      { id: 'reciente', fecha_hora: '2026-10-17T10:01:00.000Z' }
    ];
    return { items: [] };
  };
  const service = createMonitoringService({
    inferenceClient,
    cameraRegistry: { list: async () => [camera], get: async () => camera }
  });
  const result = await service.getSnapshot('camara1');
  assert.deepEqual(result.detections.map((row) => row.id), ['reciente']);
  assert.equal(result.latestDetection.id, 'reciente');
});

test('informa indisponibilidad cuando falla health', async () => {
  const service = createMonitoringService({
    inferenceClient: async () => { throw new Error('sin conexión'); },
    cameraRegistry: { list: async () => [], get: async () => null }
  });
  await assert.rejects(() => service.getSnapshot(null), MonitoringUnavailableError);
});

test('consulta salud y alertas una vez, y solo el estado por cada cámara', async () => {
  const calls = [];
  const service = createMonitoringService({
    inferenceClient: async (path) => {
      calls.push(path);
      if (path === '/health') return { status: 'ok' };
      if (path.startsWith('/alerts')) return { items: [{ id: 'alerta-1', status: 'active' }] };
      return { status: 'running', latest_result: { id: `latest-${path}`, clase: 'normal' } };
    },
    cameraRegistry: { list: async () => [{ id: 'camara1' }, { id: 'camara2' }], get: async () => null }
  });
  const result = await service.getDashboardSnapshot();
  assert.equal(calls.filter((path) => path === '/health').length, 1);
  assert.equal(calls.filter((path) => path.startsWith('/alerts')).length, 1);
  assert.equal(calls.filter((path) => path.startsWith('/sources/')).length, 2);
  assert.equal(calls.some((path) => path.startsWith('/detections')), false);
  assert.equal(result.alerts.length, 1);
});
