import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '@/constants/config';

interface GpsOverlayProps {
  latitude?: number;
  longitude?: number;
  accuracy?: number;
}

export function GpsOverlay({ latitude, longitude, accuracy }: GpsOverlayProps) {
  return (
    <View style={styles.container}>
      <View style={styles.dot} />
      <View style={styles.info}>
        {latitude && longitude ? (
          <Text style={styles.coordinates}>
            {latitude.toFixed(6)}, {longitude.toFixed(6)}
          </Text>
        ) : (
          <Text style={styles.searching}>Acquiring GPS...</Text>
        )}
        {accuracy && (
          <Text style={styles.accuracy}>±{Math.round(accuracy)}m</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    alignSelf: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary,
    marginRight: 8,
  },
  info: {
    alignItems: 'flex-start',
  },
  coordinates: {
    color: Colors.primary,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  searching: {
    color: Colors.warning,
    fontSize: 12,
  },
  accuracy: {
    color: Colors.textSecondary,
    fontSize: 10,
    marginTop: 2,
  },
});
