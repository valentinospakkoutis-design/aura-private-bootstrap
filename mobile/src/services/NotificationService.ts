import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { logger } from '../utils/Logger';
import { SecureStorage, STORAGE_KEYS } from '../utils/SecureStorage';

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export class NotificationService {
  private expoPushToken: string | null = null;

  // Request permissions and get push token
  async registerForPushNotifications(): Promise<string | null> {
    if (!Device.isDevice) {
      logger.warn('Push notifications only work on physical devices');
      return null;
    }

    try {
      // Check existing permissions
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      // Request permissions if not granted
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== 'granted') {
        logger.warn('Push notification permissions not granted');
        return null;
      }

      // Get push token
      const token = (await Notifications.getExpoPushTokenAsync()).data;
      this.expoPushToken = token;

      // Store token securely
      await SecureStorage.set(STORAGE_KEYS.PUSH_TOKEN, token);

      logger.info('Push token registered:', token);

      // Configure Android channel
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'default',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#FF231F7C',
        });
      }

      return token;
    } catch (error) {
      logger.error('Failed to register for push notifications:', error);
      return null;
    }
  }

  // Send local notification
  async sendLocalNotification(title: string, body: string, data?: any) {
    try {
      await Notifications.scheduleNotificationAsync({
        content: {
          title,
          body,
          data,
          sound: true,
        },
        trigger: null, // Show immediately
      });
      logger.info('Local notification sent:', title);
    } catch (error) {
      logger.error('Failed to send local notification:', error);
    }
  }

  // Schedule notification
  async scheduleNotification(
    title: string,
    body: string,
    trigger: Notifications.NotificationTriggerInput,
    data?: any
  ) {
    try {
      const id = await Notifications.scheduleNotificationAsync({
        content: {
          title,
          body,
          data,
          sound: true,
        },
        trigger,
      });
      logger.info('Notification scheduled:', id);
      return id;
    } catch (error) {
      logger.error('Failed to schedule notification:', error);
      return null;
    }
  }

  // Cancel notification
  async cancelNotification(id: string) {
    try {
      await Notifications.cancelScheduledNotificationAsync(id);
      logger.info('Notification cancelled:', id);
    } catch (error) {
      logger.error('Failed to cancel notification:', error);
    }
  }

  // Cancel all notifications
  async cancelAllNotifications() {
    try {
      await Notifications.cancelAllScheduledNotificationsAsync();
      logger.info('All notifications cancelled');
    } catch (error) {
      logger.error('Failed to cancel all notifications:', error);
    }
  }

  // Get badge count
  async getBadgeCount(): Promise<number> {
    try {
      return await Notifications.getBadgeCountAsync();
    } catch (error) {
      logger.error('Failed to get badge count:', error);
      return 0;
    }
  }

  // Set badge count
  async setBadgeCount(count: number) {
    try {
      await Notifications.setBadgeCountAsync(count);
      logger.info('Badge count set:', count);
    } catch (error) {
      logger.error('Failed to set badge count:', error);
    }
  }

  // Add notification listeners
  addNotificationReceivedListener(handler: (notification: Notifications.Notification) => void) {
    return Notifications.addNotificationReceivedListener(handler);
  }

  addNotificationResponseReceivedListener(
    handler: (response: Notifications.NotificationResponse) => void
  ) {
    return Notifications.addNotificationResponseReceivedListener(handler);
  }

  // Get push token
  getPushToken(): string | null {
    return this.expoPushToken;
  }
}

// Create singleton instance
export const notificationService = new NotificationService();

