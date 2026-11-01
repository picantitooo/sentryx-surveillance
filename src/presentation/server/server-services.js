import { createCameraService } from '#application/cameras/camera-service.js';
import { createMonitoringService } from '#application/monitoring/monitoring-service.js';
import { createServiceLogService } from '#application/logs/service-log-service.js';
import { createAlertService } from '#application/alerts/alert-service.js';
import { createDetectionService } from '#application/detections/detection-service.js';
import { callInference } from '#infrastructure/inference/fastapi-client.js';
import {
  getCamera,
  getCameras,
  putCamera,
  removeCamera
} from '#infrastructure/persistence/json-camera-store.js';

const cameraRegistry = {
  list: async () => getCameras(),
  get: async (/** @type {unknown} */ id) => getCamera(typeof id === 'string' ? id : null),
  save: putCamera,
  remove: removeCamera
};

export const cameraService = createCameraService({ inferenceClient: callInference, cameraRegistry });
export const monitoringService = createMonitoringService({ inferenceClient: callInference, cameraRegistry });
export const serviceLogService = createServiceLogService({ inferenceClient: callInference });
export const alertService = createAlertService({ inferenceClient: callInference });
export const detectionService = createDetectionService({ inferenceClient: callInference });
