import React from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Colors } from '@/constants/config';
import { useUpload } from '@/hooks/useUpload';

export default function QueueScreen() {
  const { queue, queueLength, isConnected, clearQueue } = useUpload();

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const renderItem = ({ item }: { item: any }) => (
    <View style={styles.queueItem}>
      <View style={styles.itemIcon}>
        <Text style={styles.icon}>📹</Text>
      </View>
      <View style={styles.itemInfo}>
        <Text style={styles.itemTitle}>{item.title}</Text>
        <Text style={styles.itemTime}>Added at {formatTime(item.createdAt)}</Text>
        {item.latitude && (
          <Text style={styles.itemLocation}>
            📍 {parseFloat(item.latitude).toFixed(4)}, {parseFloat(item.longitude).toFixed(4)}
          </Text>
        )}
      </View>
      <View style={styles.itemStatus}>
        <Text style={styles.statusText}>Queued</Text>
        <Text style={styles.retriesText}>Retry {item.retries}/3</Text>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.connectionStatus}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: isConnected ? Colors.success : Colors.error },
            ]}
          />
          <Text style={styles.statusText}>
            {isConnected ? 'Online - Auto-uploading' : 'Offline - Queued for upload'}
          </Text>
        </View>
        <Text style={styles.queueCount}>{queueLength} items in queue</Text>
      </View>

      <FlatList
        data={queue}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>📤</Text>
            <Text style={styles.emptyText}>Queue is empty</Text>
            <Text style={styles.emptySubtext}>
              Videos will appear here when you're offline
            </Text>
          </View>
        }
      />

      {queueLength > 0 && (
        <View style={styles.footer}>
          <TouchableOpacity style={styles.clearButton} onPress={clearQueue}>
            <Text style={styles.clearButtonText}>Clear Queue</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    padding: 16,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusText: {
    color: Colors.textSecondary,
    fontSize: 14,
  },
  queueCount: {
    color: Colors.primary,
    fontSize: 16,
    fontWeight: '600',
  },
  list: {
    padding: 16,
  },
  queueItem: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  itemIcon: {
    width: 50,
    height: 50,
    borderRadius: 8,
    backgroundColor: Colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  icon: {
    fontSize: 24,
  },
  itemInfo: {
    flex: 1,
    marginLeft: 12,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.text,
  },
  itemTime: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  itemLocation: {
    fontSize: 11,
    color: Colors.primary,
    marginTop: 4,
  },
  itemStatus: {
    alignItems: 'flex-end',
  },
  statusText: {
    fontSize: 12,
    color: Colors.warning,
  },
  retriesText: {
    fontSize: 10,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  empty: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyEmoji: {
    fontSize: 64,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 8,
  },
  footer: {
    padding: 16,
    backgroundColor: Colors.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  clearButton: {
    backgroundColor: Colors.error,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  clearButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
