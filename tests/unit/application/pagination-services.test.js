import assert from 'node:assert/strict';
import test from 'node:test';
import { createAlertService } from '../../../src/application/alerts/alert-service.js';
import { createDetectionService } from '../../../src/application/detections/detection-service.js';

test('alertas normaliza límites y filtros antes de consultar la API', async () => {
  let path = '';
  const service = createAlertService({ inferenceClient: async (value) => { path = value; return { items: [] }; } });
  await service.list({ limit: 'Infinity', offset: -14.2, camera: '  camara1  ', status: ' active ' });
  assert.equal(path, '/alerts?limit=100&offset=0&camera=camara1&status=active');
});

test('alertas transmite clase al backend junto a cámara y estado', async () => {
  let path = '';
  const service = createAlertService({ inferenceClient: async (value) => { path = value; return { items: [] }; } });
  await service.list({ camera: 'camara1', status: 'interrupted', clase: 'robo', limit: 8, offset: 16 });
  assert.equal(path, '/alerts?limit=8&offset=16&camera=camara1&status=interrupted&clase=robo');
});

test('detecciones evita NaN y trunca valores decimales', async () => {
  let path = '';
  const service = createDetectionService({ inferenceClient: async (value) => { path = value; return []; } });
  await service.list({ limit: 17.9, offset: 'NaN' });
  assert.equal(path, '/detections?limit=17&offset=0');
});

test('detecciones transmite filtros y conserva paginación en el backend', async () => {
  let path = '';
  const service = createDetectionService({ inferenceClient: async (value) => { path = value; return []; } });
  await service.list({ limit: 10, offset: 20, clase: 'robo', query: 'entrada', since: '2026-11-01', until: '2026-11-17' });
  assert.equal(path, '/detections?limit=10&offset=20&clase=robo&q=entrada&since=2026-11-01&until=2026-11-17');
});

test('detecciones usa el total enviado en la cabecera sin cambiar la lista', async () => {
  const service = createDetectionService({ inferenceClient: async () => ({
    data: [{ id: 'det-1' }], headers: { 'x-total-count': '42' }
  }) });
  const result = await service.list();
  assert.deepEqual(result, { items: [{ id: 'det-1' }], total: 42 });
});

test('resumen diario solicita el endpoint de agregados', async () => {
  let path = '';
  const service = createDetectionService({ inferenceClient: async (value) => { path = value; return { total: 4 }; } });
  await service.summary({ date: '2026-11-10' });
  assert.equal(path, '/detections/summary?date=2026-11-10');
});
