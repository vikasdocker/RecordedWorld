import * as FileSystem from 'expo-file-system';
import * as Network from 'expo-network';
import { api, UploadProgress } from './api';

export interface QueuedUpload {
  id: string;
  fileUri: string;
  title: string;
  description: string;
  latitude?: string;
  longitude?: string;
  heading?: string;
  retries: number;
  createdAt: number;
}

const QUEUE_FILE = FileSystem.documentDirectory + 'upload_queue.json';

class UploadService {
  private queue: QueuedUpload[] = [];
  private isUploading = false;
  private onProgressCallback?: (progress: UploadProgress) => void;

  constructor() {
    this.loadQueue();
  }

  private async loadQueue(): Promise<void> {
    try {
      const info = await FileSystem.getInfoAsync(QUEUE_FILE);
      if (info.exists) {
        const content = await FileSystem.readAsStringAsync(QUEUE_FILE);
        this.queue = JSON.parse(content);
      }
    } catch (error) {
      console.error('Failed to load queue:', error);
      this.queue = [];
    }
  }

  private async saveQueue(): Promise<void> {
    try {
      await FileSystem.writeAsStringAsync(
        QUEUE_FILE,
        JSON.stringify(this.queue)
      );
    } catch (error) {
      console.error('Failed to save queue:', error);
    }
  }

  async addToQueue(
    fileUri: string,
    title: string,
    description: string = '',
    latitude?: string,
    longitude?: string,
    heading?: string
  ): Promise<string> {
    const id = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const item: QueuedUpload = {
      id,
      fileUri,
      title,
      description,
      latitude,
      longitude,
      heading,
      retries: 0,
      createdAt: Date.now(),
    };

    this.queue.push(item);
    await this.saveQueue();

    // Try to upload immediately if online
    this.processQueue();

    return id;
  }

  async processQueue(): Promise<void> {
    if (this.isUploading || this.queue.length === 0) return;

    const isConnected = await Network.getNetworkStateAsync();
    if (!isConnected.isConnected) return;

    this.isUploading = true;

    while (this.queue.length > 0) {
      const item = this.queue[0];

      try {
        const fileInfo = await FileSystem.getInfoAsync(item.fileUri);
        if (!fileInfo.exists) {
          this.queue.shift();
          await this.saveQueue();
          continue;
        }

        const fileName = item.fileUri.split('/').pop() || 'capture.mp4';

        await api.uploadCapture(
          {
            uri: item.fileUri,
            type: 'video/mp4',
            name: fileName,
          },
          item.title,
          item.description,
          item.latitude,
          item.longitude,
          item.heading,
          (progress) => {
            if (this.onProgressCallback) {
              this.onProgressCallback({
                captureId: 0,
                progress,
                status: 'uploading',
              });
            }
          }
        );

        // Upload successful, remove from queue
        this.queue.shift();
        await this.saveQueue();

        if (this.onProgressCallback) {
          this.onProgressCallback({
            captureId: 0,
            progress: 100,
            status: 'complete',
          });
        }
      } catch (error) {
        item.retries++;
        if (item.retries >= 3) {
          // Remove after 3 failed attempts
          this.queue.shift();
          if (this.onProgressCallback) {
            this.onProgressCallback({
              captureId: 0,
              progress: 0,
              status: 'error',
              error: 'Max retries exceeded',
            });
          }
        }
        await this.saveQueue();
        break;
      }
    }

    this.isUploading = false;
  }

  onProgress(callback: (progress: UploadProgress) => void): void {
    this.onProgressCallback = callback;
  }

  getQueue(): QueuedUpload[] {
    return [...this.queue];
  }

  getQueueLength(): number {
    return this.queue.length;
  }

  async clearQueue(): Promise<void> {
    this.queue = [];
    await this.saveQueue();
  }

  async removeFromQueue(id: string): Promise<void> {
    this.queue = this.queue.filter((item) => item.id !== id);
    await this.saveQueue();
  }
}

export const uploadService = new UploadService();
