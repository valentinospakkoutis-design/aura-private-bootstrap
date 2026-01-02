import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedListItem } from '../mobile/src/components/AnimatedListItem';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { Button } from '../mobile/src/components/Button';
import { SkeletonList } from '../mobile/src/components/SkeletonLoader';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { NoData } from '../mobile/src/components/NoData';
import { theme } from '../mobile/src/constants/theme';
import { DateFormatter } from '../mobile/src/utils/DateFormatter';

interface Notification {
  id: string;
  type: 'trade' | 'prediction' | 'alert' | 'system';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

export default function NotificationsScreen() {
  const router = useRouter();
  const { showToast } = useAppStore();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const {
    loading,
    error,
    execute: fetchNotifications,
  } = useApi(api.getNotifications, { showLoading: false, showToast: false });

  const {
    loading: markingRead,
    execute: markAsRead,
  } = useApi(api.markNotificationAsRead, { showLoading: false, showToast: false });

  const {
    loading: deleting,
    execute: deleteNotification,
  } = useApi(api.deleteNotification, { showLoading: false, showToast: false });

  useEffect(() => {
    loadNotifications();
  }, [filter]);

  const loadNotifications = async () => {
    try {
      const data = await fetchNotifications();
      if (Array.isArray(data)) {
        setNotifications(data);
      } else if (data?.notifications && Array.isArray(data.notifications)) {
        setNotifications(data.notifications);
      }
    } catch (err) {
      console.error('Failed to load notifications:', err);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadNotifications();
    setRefreshing(false);
  }, [loadNotifications]);

  const handleMarkAsRead = useCallback(async (id: string) => {
    try {
      await markAsRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
      showToast('Ενημερώθηκε', 'success');
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης', 'error');
    }
  }, [markAsRead, showToast]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await deleteNotification(id);
      setNotifications(prev => prev.filter(n => n.id !== id));
      showToast('Διαγράφηκε', 'success');
    } catch (err) {
      showToast('Αποτυχία διαγραφής', 'error');
    }
  }, [deleteNotification, showToast]);

  const handleNotificationPress = useCallback((notification: Notification) => {
    if (notification.actionUrl) {
      router.push(notification.actionUrl);
    }
    if (!notification.read) {
      handleMarkAsRead(notification.id);
    }
  }, [router, handleMarkAsRead]);

  const handleMarkAllAsRead = useCallback(async () => {
    try {
      const unreadIds = notifications.filter(n => !n.read).map(n => n.id);
      await Promise.all(unreadIds.map(id => markAsRead(id)));
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      showToast('Όλες οι ειδοποιήσεις ενημερώθηκαν', 'success');
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης', 'error');
    }
  }, [notifications, markAsRead, showToast]);

  const filteredNotifications = filter === 'unread' 
    ? notifications.filter(n => !n.read)
    : notifications;

  const unreadCount = notifications.filter(n => !n.read).length;

  if (loading && !refreshing && !notifications.length) {
    return (
      <PageTransition type="fade">
        <View style={styles.container}>
          <SkeletonList count={5} />
        </View>
      </PageTransition>
    );
  }

  if (error && !notifications.length) {
    return (
      <PageTransition type="fade">
        <NoData onRetry={loadNotifications} />
      </PageTransition>
    );
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'trade':
        return '💰';
      case 'prediction':
        return '🤖';
      case 'alert':
        return '⚠️';
      case 'system':
        return '🔔';
      default:
        return '📬';
    }
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case 'trade':
        return theme.colors.brand.primary;
      case 'prediction':
        return theme.colors.market.neutral;
      case 'alert':
        return theme.colors.semantic.warning;
      case 'system':
        return theme.colors.text.secondary;
      default:
        return theme.colors.text.secondary;
    }
  };

  const renderNotification = ({ item, index }: { item: Notification; index: number }) => (
    <SwipeableCard
      onDelete={() => handleDelete(item.id)}
      deleteText="Διαγραφή"
    >
      <AnimatedListItem
        index={index}
        onPress={() => handleNotificationPress(item)}
      >
        <View style={[styles.notificationCard, !item.read && styles.notificationUnread]}>
          {/* Icon & Content */}
          <View style={styles.notificationContent}>
            <View style={[styles.notificationIcon, { backgroundColor: getNotificationColor(item.type) + '20' }]}>
              <Text style={styles.notificationIconText}>{getNotificationIcon(item.type)}</Text>
            </View>
            <View style={styles.notificationTextContainer}>
              <View style={styles.notificationHeader}>
                <Text style={styles.notificationTitle}>{item.title}</Text>
                {!item.read && <View style={styles.unreadDot} />}
              </View>
              <Text style={styles.notificationMessage} numberOfLines={2}>
                {item.message}
              </Text>
              <Text style={styles.notificationTime}>
                {DateFormatter.toRelativeTime(item.timestamp)}
              </Text>
            </View>
          </View>

          {/* Mark as Read Button */}
          {!item.read && (
            <TouchableOpacity
              style={styles.markReadButton}
              onPress={() => handleMarkAsRead(item.id)}
            >
              <Text style={styles.markReadText}>✓</Text>
            </TouchableOpacity>
          )}
        </View>
      </AnimatedListItem>
    </SwipeableCard>
  );

  return (
    <PageTransition type="slideUp">
      <View style={styles.container}>
        {/* Header Actions */}
        <View style={styles.headerActions}>
          <View style={styles.filterContainer}>
            <TouchableOpacity
              style={[styles.filterButton, filter === 'all' && styles.filterButtonActive]}
              onPress={() => setFilter('all')}
            >
              <Text style={[styles.filterText, filter === 'all' && styles.filterTextActive]}>
                Όλες
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.filterButton, filter === 'unread' && styles.filterButtonActive]}
              onPress={() => setFilter('unread')}
            >
              <Text style={[styles.filterText, filter === 'unread' && styles.filterTextActive]}>
                Μη Διαβασμένες ({unreadCount})
              </Text>
            </TouchableOpacity>
          </View>
          {unreadCount > 0 && (
            <Button
              title="Σημάνω Όλες"
              onPress={handleMarkAllAsRead}
              variant="ghost"
              size="small"
            />
          )}
        </View>

        {/* Notifications List */}
        {filteredNotifications.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>
              {filter === 'unread' ? '📭' : '📬'}
            </Text>
            <Text style={styles.emptyTitle}>
              {filter === 'unread' ? 'Δεν Υπάρχουν Μη Διαβασμένες' : 'Δεν Υπάρχουν Ειδοποιήσεις'}
            </Text>
            <Text style={styles.emptyDescription}>
              {filter === 'unread' 
                ? 'Όλες οι ειδοποιήσεις έχουν διαβαστεί'
                : 'Θα εμφανιστούν ειδοποιήσεις εδώ όταν υπάρχουν νέα updates'
              }
            </Text>
          </View>
        ) : (
          <FlatList
            data={filteredNotifications}
            keyExtractor={(item) => item.id}
            renderItem={renderNotification}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor={theme.colors.brand.primary}
              />
            }
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  headerActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  filterContainer: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    flex: 1,
  },
  filterButton: {
    paddingVertical: theme.spacing.xs,
    paddingHorizontal: theme.spacing.md,
    borderRadius: theme.borderRadius.medium,
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
  },
  filterButtonActive: {
    backgroundColor: theme.colors.brand.primary,
    borderColor: theme.colors.brand.primary,
  },
  filterText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.secondary,
  },
  filterTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  notificationCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  notificationUnread: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderLeftWidth: 3,
    borderLeftColor: theme.colors.brand.primary,
  },
  notificationContent: {
    flexDirection: 'row',
    flex: 1,
    alignItems: 'center',
  },
  notificationIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: theme.spacing.md,
  },
  notificationIconText: {
    fontSize: 24,
  },
  notificationTextContainer: {
    flex: 1,
  },
  notificationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing.xs,
  },
  notificationTitle: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '700',
    color: theme.colors.text.primary,
    flex: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.brand.primary,
    marginLeft: theme.spacing.xs,
  },
  notificationMessage: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
    marginBottom: theme.spacing.xs,
  },
  notificationTime: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.text.tertiary,
  },
  markReadButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.colors.brand.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: theme.spacing.sm,
  },
  markReadText: {
    fontSize: 18,
    color: theme.colors.brand.primary,
    fontWeight: '700',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.xl,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: theme.spacing.lg,
  },
  emptyTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
    textAlign: 'center',
  },
  emptyDescription: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    textAlign: 'center',
    paddingHorizontal: theme.spacing.xl,
  },
});

