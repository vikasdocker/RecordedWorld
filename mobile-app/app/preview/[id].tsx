import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  Dimensions,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors } from '@/constants/config';
import { api, Capture } from '@/services/api';

const { width } = Dimensions.get('window');

export default function PreviewScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [capture, setCapture] = useState<Capture | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    loadCapture();
  }, [id]);

  const loadCapture = async () => {
    try {
      const data = await api.getCapture(parseInt(id!));
      setCapture(data);
      if (data.status === 'processing') {
        setProcessing(true);
        pollStatus(data.id);
      }
    } catch (error) {
      console.error('Failed to load capture:', error);
      Alert.alert('Error', 'Failed to load capture details');
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = async (captureId: number) => {
    const interval = setInterval(async () => {
      try {
        const status = await api.getPipelineStatus(captureId);
        if (status.status === 'complete' || status.status === 'ready') {
          clearInterval(interval);
          setProcessing(false);
          loadCapture();
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setProcessing(false);
          Alert.alert('Error', 'Processing failed');
        }
      } catch (error) {
        // Continue polling
      }
    }, 2000);

    return () => clearInterval(interval);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return Colors.success;
      case 'processing': return Colors.warning;
      case 'failed': return Colors.error;
      default: return Colors.textSecondary;
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (!capture) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>Capture not found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* Video preview placeholder */}
      <View style={styles.videoContainer}>
        <Text style={styles.videoPlaceholder}>🎬</Text>
        {processing && (
          <View style={styles.processingOverlay}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.processingText}>Processing 3D model...</Text>
          </View>
        )}
      </View>

      {/* Capture info */}
      <View style={styles.infoContainer}>
        <Text style={styles.title}>{capture.title}</Text>
        <Text style={styles.date}>
          {new Date(capture.created_at).toLocaleString()}
        </Text>

        <View style={styles.statusRow}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: getStatusColor(capture.status) },
            ]}
          />
          <Text style={styles.statusText}>{capture.status}</Text>
        </View>

        {capture.description && (
          <Text style={styles.description}>{capture.description}</Text>
        )}
      </View>

      {/* Location */}
      {capture.latitude && capture.longitude && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📍 Location</Text>
          <Text style={styles.locationText}>
            {parseFloat(capture.latitude).toFixed(6)},{' '}
            {parseFloat(capture.longitude).toFixed(6)}
          </Text>
        </View>
      )}

      {/* 3D Model info */}
      {capture.model_3d_path && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🎮 3D Model</Text>
          <View style={styles.modelCard}>
            <Text style={styles.modelStatus}>Ready to explore</Text>
            <TouchableOpacity style={styles.exploreButton}>
              <Text style={styles.exploreButtonText}>Open in PC Client</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Actions */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => {
            Alert.alert('Delete', 'Are you sure?', [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Delete', style: 'destructive' },
            ]);
          }}
        >
          <Text style={styles.deleteText}>Delete Capture</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  errorText: {
    color: Colors.error,
    fontSize: 16,
  },
  videoContainer: {
    width: width,
    height: width * 0.6,
    backgroundColor: Colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  videoPlaceholder: {
    fontSize: 64,
  },
  processingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  processingText: {
    color: Colors.primary,
    fontSize: 16,
    marginTop: 12,
  },
  infoContainer: {
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: Colors.text,
  },
  date: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 8,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusText: {
    fontSize: 14,
    color: Colors.textSecondary,
    textTransform: 'capitalize',
  },
  description: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 12,
    lineHeight: 20,
  },
  section: {
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.text,
    marginBottom: 12,
  },
  locationText: {
    fontSize: 14,
    color: Colors.primary,
    fontFamily: 'monospace',
  },
  modelCard: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modelStatus: {
    color: Colors.success,
    fontSize: 14,
    marginBottom: 12,
  },
  exploreButton: {
    backgroundColor: Colors.primary,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  exploreButtonText: {
    color: Colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
  actions: {
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  actionButton: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  deleteText: {
    color: Colors.error,
    fontSize: 16,
  },
});
