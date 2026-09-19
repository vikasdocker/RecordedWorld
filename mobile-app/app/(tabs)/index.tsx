import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Colors } from '@/constants/config';
import { api, Capture } from '@/services/api';
import { useUpload } from '@/hooks/useUpload';

export default function HomeScreen() {
  const router = useRouter();
  const { queueLength, isConnected } = useUpload();
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadCaptures = async () => {
    try {
      const data = await api.listCaptures();
      setCaptures(data);
    } catch (error) {
      console.error('Failed to load captures:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCaptures();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadCaptures();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return Colors.success;
      case 'processing': return Colors.warning;
      case 'failed': return Colors.error;
      default: return Colors.textSecondary;
    }
  };

  const renderCapture = ({ item }: { item: Capture }) => (
    <TouchableOpacity
      style={styles.captureCard}
      onPress={() => router.push(`/preview/${item.id}`)}
    >
      <View style={styles.captureThumbnail}>
        <Text style={styles.captureEmoji}>🎬</Text>
      </View>
      <View style={styles.captureInfo}>
        <Text style={styles.captureTitle}>{item.title}</Text>
        <Text style={styles.captureDate}>
          {new Date(item.created_at).toLocaleDateString()}
        </Text>
        <View style={styles.statusRow}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: getStatusColor(item.status) },
            ]}
          />
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{captures.length}</Text>
            <Text style={styles.statLabel}>Captures</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{queueLength}</Text>
            <Text style={styles.statLabel}>In Queue</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: isConnected ? Colors.success : Colors.error }]}>
              {isConnected ? 'Online' : 'Offline'}
            </Text>
            <Text style={styles.statLabel}>Status</Text>
          </View>
        </View>
      </View>

      <FlatList
        data={captures}
        renderItem={renderCapture}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
          />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>📹</Text>
            <Text style={styles.emptyText}>No captures yet</Text>
            <Text style={styles.emptySubtext}>
              Tap the Capture tab to start recording
            </Text>
          </View>
        }
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push('/capture')}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
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
  header: {
    padding: 16,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: Colors.primary,
  },
  statLabel: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  list: {
    padding: 16,
  },
  captureCard: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  captureThumbnail: {
    width: 80,
    height: 80,
    borderRadius: 8,
    backgroundColor: Colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureEmoji: {
    fontSize: 32,
  },
  captureInfo: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  captureTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.text,
  },
  captureDate: {
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
  fab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  fabText: {
    fontSize: 28,
    color: Colors.background,
    fontWeight: 'bold',
  },
});
