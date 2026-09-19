import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Location from 'expo-location';
import * as FileSystem from 'expo-file-system';
import { useRouter } from 'expo-router';
import { Colors } from '@/constants/config';
import { useLocation } from '@/hooks/useLocation';
import { useUpload } from '@/hooks/useUpload';

type CaptureState = 'idle' | 'recording' | 'stopping' | 'uploading' | 'done' | 'error';

function getHeadingLabel(heading: number): string {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const idx = Math.round(heading / 45) % 8;
  return dirs[idx];
}

export default function CaptureScreen() {
  const router = useRouter();
  const { location, permission: locationPermission } = useLocation();
  const { addToQueue, isConnected } = useUpload();
  const [permission, requestPermission] = useCameraPermissions();
  const [captureState, setCaptureState] = useState<CaptureState>('idle');
  const [duration, setDuration] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const cameraRef = useRef<CameraView>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const startTimer = () => {
    setDuration(0);
    timerRef.current = setInterval(() => {
      setDuration((prev) => prev + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const startRecording = async () => {
    if (!cameraRef.current) return;

    setCaptureState('recording');
    startTimer();

    try {
      await cameraRef.current.recordAsync({
        maxDuration: 300,
      });
    } catch (error) {
      console.error('Recording error:', error);
      setCaptureState('error');
      stopTimer();
    }
  };

  const stopRecording = async () => {
    if (!cameraRef.current) return;

    setCaptureState('stopping');
    stopTimer();

    try {
      const video = await cameraRef.current.stopRecording();
      if (video && video.uri) {
        await handleVideoCapture(video.uri);
      }
    } catch (error) {
      console.error('Stop recording error:', error);
      setCaptureState('error');
    }
  };

  const handleVideoCapture = async (uri: string) => {
    setCaptureState('uploading');
    setUploadProgress(0);

    const title = `Capture ${new Date().toLocaleTimeString()}`;
    const latitude = location?.latitude?.toString();
    const longitude = location?.longitude?.toString();
    const heading = location?.heading?.toString();

    try {
      if (isConnected) {
        // Upload directly
        const { api } = await import('@/services/api');
        const fileName = uri.split('/').pop() || 'capture.mp4';

        await api.uploadCapture(
          { uri, type: 'video/mp4', name: fileName },
          title,
          '',
          latitude,
          longitude,
          heading,
          (progress) => setUploadProgress(progress)
        );
        setCaptureState('done');
        Alert.alert('Success', 'Capture uploaded successfully!', [
          { text: 'OK', onPress: () => router.back() },
        ]);
      } else {
        // Add to offline queue
        await addToQueue(uri, title, '', latitude, longitude, heading);
        setCaptureState('done');
        Alert.alert(
          'Queued',
          'You are offline. Video will upload when connected.',
          [{ text: 'OK', onPress: () => router.back() }]
        );
      }
    } catch (error) {
      console.error('Upload error:', error);
      setCaptureState('error');
      Alert.alert('Error', 'Failed to upload. Video saved to queue.');
    }
  };

  if (!permission) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
        <Text style={styles.permEmoji}>📷</Text>
        <Text style={styles.permTitle}>Camera Permission Required</Text>
        <Text style={styles.permText}>
          Recorded World needs access to your camera to capture real-world
          environments for 3D world generation.
        </Text>
        <TouchableOpacity style={styles.permButton} onPress={requestPermission}>
          <Text style={styles.permButtonText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} mode="video">
        {/* Viewfinder overlay */}
        <View style={styles.overlay}>
          <View style={styles.cornerTopLeft} />
          <View style={styles.cornerTopRight} />
          <View style={styles.cornerBottomLeft} />
          <View style={styles.cornerBottomRight} />
        </View>

        {/* Recording indicator */}
        {captureState === 'recording' && (
          <View style={styles.recordingBar}>
            <View style={styles.recordingDot} />
            <Text style={styles.recordingText}>REC {formatDuration(duration)}</Text>
          </View>
        )}

        {/* Upload progress */}
        {captureState === 'uploading' && (
          <View style={styles.uploadOverlay}>
            <View style={styles.uploadBox}>
              <ActivityIndicator size="large" color={Colors.primary} />
              <Text style={styles.uploadText}>
                Uploading... {Math.round(uploadProgress)}%
              </Text>
              <View style={styles.progressBar}>
                <View
                  style={[styles.progressFill, { width: `${uploadProgress}%` }]}
                />
              </View>
            </View>
          </View>
        )}

        {/* GPS info */}
        <View style={styles.gpsBar}>
          <Text style={styles.gpsText}>
            {location
              ? `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`
              : 'Getting location...'}
          </Text>
          {location?.heading != null && location.heading > 0 && (
            <Text style={styles.headingText}>
              {Math.round(location.heading)}° {getHeadingLabel(location.heading)}
            </Text>
          )}
        </View>
      </CameraView>

      {/* Controls */}
      <View style={styles.controls}>
        <Text style={styles.statusText}>
          {captureState === 'idle' && 'Tap to start recording'}
          {captureState === 'recording' && 'Recording... Tap to stop'}
          {captureState === 'stopping' && 'Processing...'}
          {captureState === 'uploading' && 'Uploading video...'}
          {captureState === 'done' && 'Complete!'}
          {captureState === 'error' && 'Error occurred. Tap to retry'}
        </Text>

        <TouchableOpacity
          style={[
            styles.recordButton,
            captureState === 'recording' && styles.recordButtonActive,
            captureState === 'uploading' && styles.recordButtonDisabled,
          ]}
          onPress={captureState === 'recording' ? stopRecording : startRecording}
          disabled={captureState === 'uploading' || captureState === 'stopping'}
        >
          <View
            style={[
              styles.recordButtonInner,
              captureState === 'recording' && styles.recordButtonInnerActive,
            ]}
          />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.cancelButton}
          onPress={() => router.back()}
        >
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
    padding: 32,
  },
  camera: {
    flex: 1,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    margin: 20,
  },
  cornerTopLeft: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: 30,
    height: 30,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: Colors.primary,
  },
  cornerTopRight: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 30,
    height: 30,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderColor: Colors.primary,
  },
  cornerBottomLeft: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: 30,
    height: 30,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderColor: Colors.primary,
  },
  cornerBottomRight: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 30,
    height: 30,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderColor: Colors.primary,
  },
  recordingBar: {
    position: 'absolute',
    top: 50,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 0, 0, 0.8)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  recordingDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#fff',
    marginRight: 8,
  },
  recordingText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
  uploadOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  uploadBox: {
    backgroundColor: Colors.surface,
    padding: 32,
    borderRadius: 16,
    alignItems: 'center',
    width: '80%',
  },
  uploadText: {
    color: Colors.text,
    fontSize: 16,
    marginTop: 16,
  },
  progressBar: {
    width: '100%',
    height: 8,
    backgroundColor: Colors.surfaceLight,
    borderRadius: 4,
    marginTop: 16,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: Colors.primary,
    borderRadius: 4,
  },
  gpsBar: {
    position: 'absolute',
    bottom: 100,
    alignSelf: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  gpsText: {
    color: Colors.primary,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  headingText: {
    color: Colors.warning,
    fontSize: 12,
    fontFamily: 'monospace',
    marginTop: 4,
  },
  controls: {
    backgroundColor: Colors.background,
    padding: 24,
    alignItems: 'center',
  },
  statusText: {
    color: Colors.textSecondary,
    fontSize: 14,
    marginBottom: 20,
  },
  recordButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(255, 68, 68, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 4,
    borderColor: Colors.error,
  },
  recordButtonActive: {
    backgroundColor: 'rgba(255, 68, 68, 0.5)',
    borderColor: '#ff0000',
  },
  recordButtonDisabled: {
    opacity: 0.5,
  },
  recordButtonInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.error,
  },
  recordButtonInnerActive: {
    borderRadius: 8,
    width: 30,
    height: 30,
  },
  cancelButton: {
    marginTop: 16,
  },
  cancelText: {
    color: Colors.textSecondary,
    fontSize: 16,
  },
  permEmoji: {
    fontSize: 64,
  },
  permTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.text,
    marginTop: 16,
  },
  permText: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 20,
  },
  permButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: 32,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 24,
  },
  permButtonText: {
    color: Colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
});
