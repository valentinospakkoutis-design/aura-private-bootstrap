import { useEffect, useState } from 'react';
import { notificationService } from '../services/NotificationService';
import { useAppStore } from '../stores/appStore';
import { logger } from '../utils/Logger';
import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';

export function useNotifications() {
  const [pushToken, setPushToken] = useState<string | null>(null);
  const [isRegistered, setIsRegistered] = useState(false);
  const { showToast } = useAppStore();
  const router = useRouter();

  useEffect(() => {
    // Register for push notifications
    registerPushNotifications();

    // Listen for notifications received while app is open
    const receivedSubscription = notificationService.addNotificationReceivedListener(
      (notification) => {
        logger.info('Notification received:', notification);
        const { title, body } = notification.request.content;
        showToast(title || 'New notification', 'info');
      }
    );

    // Listen for notification taps
    const responseSubscription = notificationService.addNotificationResponseReceivedListener(
      (response) => {
        logger.info('Notification tapped:', response);
        const data = response.notification.request.content.data;
        
        // Navigate based on notification data
        if (data?.screen) {
          router.push(data.screen as any);
        }
      }
    );

    // Cleanup
    return () => {
      receivedSubscription.remove();
      responseSubscription.remove();
    };
  }, [showToast, router]);

  const registerPushNotifications = async () => {
    try {
      const token = await notificationService.registerForPushNotifications();
      if (token) {
        setPushToken(token);
        setIsRegistered(true);
        logger.info('Push notifications registered successfully');
      }
    } catch (error) {
      logger.error('Failed to register push notifications:', error);
      setIsRegistered(false);
    }
  };

  const sendLocalNotification = async (title: string, body: string, data?: any) => {
    await notificationService.sendLocalNotification(title, body, data);
  };

  const scheduleNotification = async (
    title: string,
    body: string,
    trigger: Notifications.NotificationTriggerInput,
    data?: any
  ) => {
    return await notificationService.scheduleNotification(title, body, trigger, data);
  };

  const cancelNotification = async (id: string) => {
    await notificationService.cancelNotification(id);
  };

  const setBadgeCount = async (count: number) => {
    await notificationService.setBadgeCount(count);
  };

  return {
    pushToken,
    isRegistered,
    sendLocalNotification,
    scheduleNotification,
    cancelNotification,
    setBadgeCount,
  };
}

