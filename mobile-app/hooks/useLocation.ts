import { useState, useEffect, useCallback } from 'react';
import { locationService, LocationData } from '@/services/location';

export function useLocation() {
  const [location, setLocation] = useState<LocationData | null>(null);
  const [permission, setPermission] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [permissionDeniedMessage, setPermissionDeniedMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const hasPermission = await locationService.requestPermissions();
      setPermission(hasPermission);

      if (hasPermission) {
        const current = await locationService.getCurrentLocation();
        setLocation(current);

        await locationService.startWatching((newLocation) => {
          setLocation(newLocation);
        });
      } else {
        setPermissionDeniedMessage(locationService.getPermissionDeniedMessage());
      }

      setLoading(false);
    })();

    return () => {
      locationService.stopWatching();
    };
  }, []);

  const refresh = useCallback(async () => {
    const current = await locationService.getCurrentLocation();
    setLocation(current);
  }, []);

  return { location, permission, loading, refresh, permissionDeniedMessage };
}
