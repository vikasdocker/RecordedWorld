import { useState, useEffect, useCallback } from 'react';
import * as Network from 'expo-network';
import { uploadService, QueuedUpload } from '@/services/upload';
import { UploadProgress } from '@/services/api';

export function useUpload() {
  const [isConnected, setIsConnected] = useState(true);
  const [queue, setQueue] = useState<QueuedUpload[]>([]);
  const [progress, setProgress] = useState<UploadProgress | null>(null);

  useEffect(() => {
    (async () => {
      const state = await Network.getNetworkStateAsync();
      setIsConnected(state.isConnected ?? false);
    })();

    const unsubscribe = Network.addNetworkStateListener((state) => {
      setIsConnected(state.isConnected ?? false);
      if (state.isConnected) {
        uploadService.processQueue();
      }
    });

    uploadService.onProgress(setProgress);
    setQueue(uploadService.getQueue());

    return () => unsubscribe.remove();
  }, []);

  const addToQueue = useCallback(
    async (
      fileUri: string,
      title: string,
      description: string = '',
      latitude?: string,
      longitude?: string,
      heading?: string
    ) => {
      await uploadService.addToQueue(fileUri, title, description, latitude, longitude, heading);
      setQueue(uploadService.getQueue());
    },
    []
  );

  const clearQueue = useCallback(async () => {
    await uploadService.clearQueue();
    setQueue([]);
  }, []);

  const processQueue = useCallback(() => {
    uploadService.processQueue();
  }, []);

  return {
    isConnected,
    queue,
    queueLength: queue.length,
    progress,
    addToQueue,
    clearQueue,
    processQueue,
  };
}
