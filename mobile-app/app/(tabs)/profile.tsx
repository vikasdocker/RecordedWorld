import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Colors, Config } from '@/constants/config';
import { api } from '@/services/api';
import { useUpload } from '@/hooks/useUpload';

export default function ProfileScreen() {
  const { queueLength, isConnected } = useUpload();
  const [captureCount, setCaptureCount] = useState(0);
  const [serverStatus, setServerStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    (async () => {
      try {
        const captures = await api.listCaptures();
        setCaptureCount(captures.length);
      } catch (error) {
        console.error('Failed to load captures');
      }

      const healthy = await api.healthCheck();
      setServerStatus(healthy ? 'online' : 'offline');
    })();
  }, []);

  const getStatusColor = () => {
    switch (serverStatus) {
      case 'online': return Colors.success;
      case 'offline': return Colors.error;
      default: return Colors.warning;
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Profile header */}
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>👤</Text>
        </View>
        <Text style={styles.username}>Explorer</Text>
        <Text style={styles.email}>user@recorded.world</Text>
      </View>

      {/* Stats */}
      <View style={styles.statsContainer}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{captureCount}</Text>
          <Text style={styles.statLabel}>Captures</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{queueLength}</Text>
          <Text style={styles.statLabel}>In Queue</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: isConnected ? Colors.success : Colors.error }]}>
            {isConnected ? 'Online' : 'Offline'}
          </Text>
          <Text style={styles.statLabel}>Network</Text>
        </View>
      </View>

      {/* Server Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server Connection</Text>
        <View style={styles.statusCard}>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: getStatusColor() }]} />
            <Text style={styles.statusText}>
              {serverStatus === 'checking' && 'Checking...'}
              {serverStatus === 'online' && 'Connected to server'}
              {serverStatus === 'offline' && 'Server unavailable'}
            </Text>
          </View>
          <Text style={styles.serverUrl}>{Config.api.baseUrl}</Text>
        </View>
      </View>

      {/* Settings */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Settings</Text>

        <TouchableOpacity style={styles.settingItem}>
          <Text style={styles.settingLabel}>Video Quality</Text>
          <Text style={styles.settingValue}>1080p</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.settingItem}>
          <Text style={styles.settingLabel}>Max Duration</Text>
          <Text style={styles.settingValue}>5 min</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.settingItem}>
          <Text style={styles.settingLabel}>Auto-Upload</Text>
          <Text style={styles.settingValue}>On</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.settingItem}>
          <Text style={styles.settingLabel}>GPS Tagging</Text>
          <Text style={styles.settingValue}>On</Text>
        </TouchableOpacity>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.aboutCard}>
          <Text style={styles.appName}>Recorded World</Text>
          <Text style={styles.appVersion}>Version 1.0.0</Text>
          <Text style={styles.appDescription}>
            Capture reality, explore in 3D. Record real-world environments and
            transform them into explorable 3D worlds.
          </Text>
        </View>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>Made with ❤️ for explorers</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    alignItems: 'center',
    padding: 32,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: Colors.primary,
  },
  avatarText: {
    fontSize: 40,
  },
  username: {
    fontSize: 22,
    fontWeight: 'bold',
    color: Colors.text,
    marginTop: 12,
  },
  email: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  statsContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
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
  section: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.text,
    marginBottom: 12,
  },
  statusCard: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  statusText: {
    fontSize: 16,
    color: Colors.text,
  },
  serverUrl: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 8,
    marginLeft: 24,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    padding: 16,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  settingLabel: {
    fontSize: 16,
    color: Colors.text,
  },
  settingValue: {
    fontSize: 14,
    color: Colors.primary,
  },
  aboutCard: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  appName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.primary,
  },
  appVersion: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  appDescription: {
    fontSize: 14,
    color: Colors.textSecondary,
    marginTop: 12,
    lineHeight: 20,
  },
  footer: {
    padding: 32,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: Colors.textSecondary,
  },
});
