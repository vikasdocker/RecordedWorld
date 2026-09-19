import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '@/constants/config';

interface UploadProgressProps {
  progress: number;
  status: 'pending' | 'uploading' | 'complete' | 'error';
  fileName?: string;
}

export function UploadProgress({
  progress,
  status,
  fileName,
}: UploadProgressProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'complete': return Colors.success;
      case 'error': return Colors.error;
      case 'uploading': return Colors.primary;
      default: return Colors.textSecondary;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'pending': return 'Waiting...';
      case 'uploading': return `Uploading ${Math.round(progress)}%`;
      case 'complete': return 'Complete!';
      case 'error': return 'Failed';
      default: return '';
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.fileName} numberOfLines={1}>
          {fileName || 'Video'}
        </Text>
        <Text style={[styles.status, { color: getStatusColor() }]}>
          {getStatusText()}
        </Text>
      </View>

      <View style={styles.progressBar}>
        <View
          style={[
            styles.progressFill,
            {
              width: `${progress}%`,
              backgroundColor: getStatusColor(),
            },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.surface,
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  fileName: {
    flex: 1,
    fontSize: 14,
    color: Colors.text,
    marginRight: 8,
  },
  status: {
    fontSize: 12,
    fontWeight: '600',
  },
  progressBar: {
    height: 4,
    backgroundColor: Colors.surfaceLight,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
});
