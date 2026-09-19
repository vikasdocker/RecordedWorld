import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Colors } from '@/constants/config';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: Colors.background },
          headerTintColor: Colors.text,
          contentStyle: { backgroundColor: Colors.background },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="capture"
          options={{
            title: 'Capture',
            presentation: 'fullScreenModal',
          }}
        />
        <Stack.Screen
          name="preview/[id]"
          options={{
            title: 'Preview',
          }}
        />
      </Stack>
    </>
  );
}
