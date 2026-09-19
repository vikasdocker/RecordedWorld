import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Colors } from '@/constants/config';

interface CaptureCardProps {
  id: number;
  title: string;
  status: string;
  date: string;
  thumbnail?: string;
  onPress: () => void;
}

export function CaptureCard({
  id,
  title,
  status,
  date,
  onPress,
}: CaptureCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return Colors.success;
      case 'processing': return Colors.warning;
      case 'failed': return Colors.error;
      default: return Colors.textSecondary;
    }
  };

  return (
    <TouchableOpacity style={styles.card} onPress={onPress}>
      <View style={styles.thumbnail}>
        <Text style={styles.emoji}>🎬</Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
        <Text style={styles.date}>{date}</Text>
        <View style={styles.statusRow}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: getStatusColor(status) },
            ]}
          />
          <Text style={styles.statusText}>{status}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  thumbnail: {
    width: 80,
    height: 80,
    borderRadius: 8,
    backgroundColor: Colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emoji: {
    fontSize: 32,
  },
  info: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.text,
  },
  date: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    color: Colors.textSecondary,
    textTransform: 'capitalize',
  },
});
