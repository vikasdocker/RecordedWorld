import { Config } from '@/constants/config';

export interface Capture {
  id: number;
  user_id: number;
  title: string;
  description?: string;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  video_path: string;
  model_3d_path?: string;
  thumbnail_path?: string;
  latitude?: string;
  longitude?: string;
  created_at: string;
  processed_at?: string;
}

export interface UploadProgress {
  captureId: number;
  progress: number;
  status: 'pending' | 'uploading' | 'complete' | 'error';
  error?: string;
}

class ApiService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = Config.api.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  async listCaptures(userId: number = 1): Promise<Capture[]> {
    return this.request<Capture[]>(`/api/captures/?user_id=${userId}`);
  }

  async getCapture(id: number): Promise<Capture> {
    return this.request<Capture>(`/api/captures/${id}`);
  }

  async uploadCapture(
    file: { uri: string; type: string; name: string },
    title: string,
    description: string = '',
    latitude?: string,
    longitude?: string,
    heading?: string,
    onProgress?: (progress: number) => void
  ): Promise<Capture> {
    const formData = new FormData();
    formData.append('file', file as any);
    formData.append('title', title);
    formData.append('description', description);
    formData.append('user_id', '1');

    if (latitude) formData.append('latitude', latitude);
    if (longitude) formData.append('longitude', longitude);
    if (heading) formData.append('heading', heading);

    const url = `${this.baseUrl}/api/captures/`;

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = (event.loaded / event.total) * 100;
          onProgress(progress);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed: ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  }

  async getPipelineStatus(captureId: number): Promise<any> {
    return this.request(`/api/pipeline/status/${captureId}`);
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.request<{ status: string }>('/health');
      return response.status === 'healthy';
    } catch {
      return false;
    }
  }
}

export const api = new ApiService();
