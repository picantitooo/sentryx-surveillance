import assert from 'node:assert/strict';
import test from 'node:test';
import { CameraNotFoundError, createCameraService } from '../../../src/application/cameras/camera-service.js';

function registry(cameras = []) {
  return {
    list: async () => cameras,
    get: async (id) => cameras.find((camera) => camera.id === id) ?? null,
    save: async (camera) => { cameras.push(camera); return camera; },
    remove: async (id) => {
      const index = cameras.findIndex((camera) => camera.id === id);
      if (index >= 0) cameras.splice(index, 1);
    }
  };
}

test('registra en el repositorio e inicia su fuente con el ID devuelto', async () => {
  const calls = [];
  const cameras = [];
  const inferenceClient = async (path, options = {}) => {
    calls.push({ path, options });
    return { source_id: options.body.source_id, status: 'running' };
  };
  const service = createCameraService({ inferenceClient, cameraRegistry: registry(cameras) });

  const result = await service.register({
    name: 'Entrada', normalizedUrl: 'https://media.example/camera01', streamPath: 'camera01'
  });

  assert.equal(result.camera.id, 'camara1');
  assert.equal(result.camera.streamPath, 'camera01');
  assert.equal(cameras.length, 1);
  assert.equal(result.inference.available, true);
  assert.deepEqual(calls.map((call) => call.path), ['/sources/start']);
});

test('mantiene la cámara registrada por el backend aunque inferencia no esté disponible', async () => {
  const cameras = [];
  const service = createCameraService({
    inferenceClient: async () => { throw new Error('sin conexión'); },
    cameraRegistry: registry(cameras)
  });

  const result = await service.register({
    name: 'Patio', normalizedUrl: 'https://media.example/camera03', streamPath: 'camera03'
  });

  assert.equal(cameras.length, 1);
  assert.equal(result.camera.id, 'camara1');
  assert.equal(result.inference.available, false);
});

test('start informa cuando la cámara no existe', async () => {
  const service = createCameraService({
    inferenceClient: async () => ({}), cameraRegistry: registry([])
  });
  await assert.rejects(() => service.start('camara99'), CameraNotFoundError);
});

test('remove no llama al backend cuando la cámara no existe', async () => {
  let calls = 0;
  const service = createCameraService({
    inferenceClient: async () => { calls += 1; }, cameraRegistry: registry([])
  });
  assert.deepEqual(await service.remove('camara99'), { removed: true });
  assert.equal(calls, 0);
});
