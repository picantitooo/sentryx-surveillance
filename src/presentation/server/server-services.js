import { createCameraService } from '#application/cameras/camera-service.js';
import { createMonitoringService } from '#application/monitoring/monitoring-service.js';
import { createServiceLogService } from '#application/logs/service-log-service.js';
import { createAlertService } from '#application/alerts/alert-service.js';
import { createDetectionService } from '#application/detections/detection-service.js';
import { callInference } from '#infrastructure/inference/fastapi-client.js';
import {
  getRegisteredCamera,
  getRegisteredCameras,
  registerCamera,
  updateRegisteredCamera,
  removeRegisteredCamera
} from '#infrastructure/cameras/fastapi-camera-registry.js';

const cameraRegistry = {
  list: async () => getRegisteredCameras(),
  get: async (/** @type {unknown} */ id) => getRegisteredCamera(typeof id === 'string' ? id : null),
  register: registerCamera,
  update: updateRegisteredCamera,
  remove: removeRegisteredCamera
};

export const cameraService = createCameraService({ inferenceClient: callInference, cameraRegistry });
export const monitoringService = createMonitoringService({ inferenceClient: callInference, cameraRegistry });
export const serviceLogService = createServiceLogService({ inferenceClient: callInference });
export const alertService = createAlertService({ inferenceClient: callInference });
export const detectionService = createDetectionService({ inferenceClient: callInference });
