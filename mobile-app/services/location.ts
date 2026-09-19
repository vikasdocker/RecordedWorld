import * as Location from 'expo-location';

export interface LocationData {
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy?: number;
  heading?: number;
  timestamp: number;
}

class LocationService {
  private watchSubscription: Location.LocationSubscription | null = null;
  private currentLocation: LocationData | null = null;

  async requestPermissions(): Promise<boolean> {
    const { status } = await Location.requestForegroundPermissionsAsync();
    return status === 'granted';
  }

  async getCurrentLocation(): Promise<LocationData | null> {
    try {
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      this.currentLocation = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        altitude: location.coords.altitude || undefined,
        accuracy: location.coords.accuracy || undefined,
        heading: location.coords.heading || undefined,
        timestamp: location.timestamp,
      };

      return this.currentLocation;
    } catch (error) {
      console.error('Failed to get location:', error);
      return null;
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
        distanceInterval: 1, // meters
        timeInterval: 1000, // ms
      },
      (location) => {
        this.currentLocation = {
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          altitude: location.coords.altitude || undefined,
          accuracy: location.coords.accuracy || undefined,
          heading: location.coords.heading || undefined,
          timestamp: location.timestamp,
        };
        callback(this.currentLocation);
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
