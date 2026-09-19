import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface LocationData {
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy?: number;
  heading?: number;
  timestamp: number;
}

const CACHE_KEY = 'last_known_location';
const MAX_ACCURACY_METERS = 100;

class LocationService {
  private watchSubscription: Location.LocationSubscription | null = null;
  private currentLocation: LocationData | null = null;

  async requestPermissions(): Promise<boolean> {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status === 'granted') return true;

    if (status === 'denied') {
      const { status: again } = await Location.requestForegroundPermissionsAsync();
      return again === 'granted';
    }
    return false;
  }

  getPermissionDeniedMessage(): string {
    return 'Location permission is required for GPS tracking. Please enable it in your device settings to record accurate location data with your captures.';
  }

  async cacheLocation(location: LocationData): Promise<void> {
    try {
      await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(location));
    } catch (error) {
      console.warn('Failed to cache location:', error);
    }
  }

  async getCachedLocation(): Promise<LocationData | null> {
    try {
      const cached = await AsyncStorage.getItem(CACHE_KEY);
      if (cached) {
        return JSON.parse(cached) as LocationData;
      }
    } catch (error) {
      console.warn('Failed to read cached location:', error);
    }
    return null;
  }

  isAccuracyAcceptable(location: LocationData): boolean {
    if (location.accuracy === undefined || location.accuracy === null) return true;
    return location.accuracy <= MAX_ACCURACY_METERS;
  }

  async getCurrentLocation(): Promise<LocationData | null> {
    try {
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      const locationData: LocationData = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        altitude: location.coords.altitude || undefined,
        accuracy: location.coords.accuracy || undefined,
        heading: location.coords.heading || undefined,
        timestamp: location.timestamp,
      };

      if (!this.isAccuracyAcceptable(locationData)) {
        console.warn(
          `GPS accuracy ${locationData.accuracy?.toFixed(1)}m exceeds threshold of ${MAX_ACCURACY_METERS}m. Using cached location.`
        );
        const cached = await this.getCachedLocation();
        if (cached && this.isAccuracyAcceptable(cached)) {
          return cached;
        }
      }

      this.currentLocation = locationData;
      await this.cacheLocation(locationData);
      return this.currentLocation;
    } catch (error) {
      console.error('Failed to get location:', error);
      return await this.getCachedLocation();
    }
  }

  async startWatching(
    callback: (location: LocationData) => void
  ): Promise<void> {
    const hasPermission = await this.requestPermissions();
    if (!hasPermission) return;

    this.watchSubscription = await Location.watchPositionAsync(
      {
        accuracy: Location.Accuracy.High,
        distanceInterval: 1,
        timeInterval: 1000,
      },
      async (location) => {
        const locationData: LocationData = {
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          altitude: location.coords.altitude || undefined,
          accuracy: location.coords.accuracy || undefined,
          heading: location.coords.heading || undefined,
          timestamp: location.timestamp,
        };

        if (this.isAccuracyAcceptable(locationData)) {
          this.currentLocation = locationData;
          await this.cacheLocation(locationData);
          callback(locationData);
        }
      }
    );
  }

  stopWatching(): void {
    if (this.watchSubscription) {
      this.watchSubscription.remove();
      this.watchSubscription = null;
    }
  }

  getCurrentPosition(): LocationData | null {
    return this.currentLocation;
  }
}

export const locationService = new LocationService();
