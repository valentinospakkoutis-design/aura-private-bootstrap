import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';
import LoadingState from '../mobile/src/components/LoadingState';
import EmptyState from '../mobile/src/components/EmptyState';
import NetworkErrorHandler from '../mobile/src/components/NetworkErrorHandler';

export default function NotificationsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState('all'); // all, unread, trade_executed, price_alert, ai_signal
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load notifications
      const unreadOnly = filter === 'unread';
      const notifType = filter !== 'all' && filter !== 'unread' ? filter : null;
      
      const notifsData = await api.get(
        `/api/notifications?unread_only=${unreadOnly}&notification_type=${notifType || ''}&limit=100`
      );
      setNotifications(notifsData.notifications || []);
      setUnreadCount(notifsData.unread_count || 0);
      
      // Load stats
      const statsData = await api.get('/api/notifications/stats');
      setStats(statsData);
    } catch (err) {
      console.error('Error loading notifications:', err);
      setError(err);
      const userMessage = err.userMessage || err.message || 'Σφάλμα φόρτωσης ειδοποιήσεων';
      if (!refreshing) {
        Alert.alert('Σφάλμα', userMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleMarkAsRead = async (notificationId) => {
    try {
      await api.put(`/api/notifications/${notificationId}/read`, {}, { clearCacheOnSuccess: true });
      loadData();
    } catch (err) {
      console.error('Error marking as read:', err);
      const userMessage = err.userMessage || 'Αποτυχία ενημέρωσης';
      Alert.alert('Σφάλμα', userMessage);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.put('/api/notifications/read-all');
      Alert.alert('Επιτυχία', 'Όλες οι ειδοποιήσεις σημειώθηκαν ως διαβασμένες');
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', 'Αποτυχία ενημέρωσης');
    }
  };

  const handleDelete = async (notificationId) => {
    try {
      await api.delete(`/api/notifications/${notificationId}`);
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', 'Αποτυχία διαγραφής');
    }
  };

  const handleDeleteAllRead = async () => {
    Alert.alert(
      'Διαγραφή',
      'Διαγραφή όλων των διαβασμένων ειδοποιήσεων;',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Διαγραφή',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete('/api/notifications/read');
              Alert.alert('Επιτυχία', 'Διαγράφηκαν όλες οι διαβασμένες ειδοποιήσεις');
              loadData();
            } catch (error) {
              Alert.alert('Σφάλμα', 'Αποτυχία διαγραφής');
            }
          }
        }
      ]
    );
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'trade_executed': return '💰';
      case 'price_alert': return '📈';
      case 'ai_signal': return '🤖';
      case 'portfolio_update': return '💼';
      case 'risk_alert': return '⚠️';
      default: return '🔔';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'urgent': return '#ff6b6b';
      case 'high': return '#FFA726';
      case 'medium': return '#4CAF50';
      default: return '#999';
    }
  };

  const formatTime = (timestamp) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
      if (diffMins < 10080) return `${Math.floor(diffMins / 1440)}d ago`;
      return date.toLocaleDateString('el-GR', { day: 'numeric', month: 'short' });
    } catch {
      return 'N/A';
    }
  };

  if (loading && !notifications.length) {
    return <LoadingState message="Φόρτωση ειδοποιήσεων..." />;
  }

  if (error && !refreshing && !notifications.length) {
    return (
      <NetworkErrorHandler 
        error={error}
        onRetry={loadData}
      />
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <View style={styles.headerRight}>
            <Text style={styles.title}>🔔 Notifications</Text>
            {unreadCount > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{unreadCount}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Stats */}
        {stats && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📊 Statistics</Text>
            
            <View style={styles.statsRow}>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{stats.total}</Text>
                <Text style={styles.statLabel}>Total</Text>
              </View>
              
              <View style={styles.statBox}>
                <Text style={[styles.statValue, { color: '#4CAF50' }]}>
                  {stats.unread}
                </Text>
                <Text style={styles.statLabel}>Unread</Text>
              </View>
              
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{stats.read}</Text>
                <Text style={styles.statLabel}>Read</Text>
              </View>
            </View>
          </View>
        )}

        {/* Filters */}
        <View style={styles.filters}>
          {['all', 'unread', 'trade_executed', 'price_alert', 'ai_signal'].map((f) => (
            <TouchableOpacity
              key={f}
              style={[styles.filterButton, filter === f && styles.filterButtonActive]}
              onPress={() => {
                setFilter(f);
                loadData();
              }}
            >
              <Text style={[
                styles.filterButtonText,
                filter === f && styles.filterButtonTextActive
              ]}>
                {f === 'all' ? 'All' : f === 'unread' ? 'Unread' : f.replace('_', ' ')}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Actions */}
        <View style={styles.actionsRow}>
          <TouchableOpacity
            style={styles.actionButton}
            onPress={handleMarkAllRead}
          >
            <Text style={styles.actionButtonText}>✓ Mark All Read</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.actionButton, styles.actionButtonDanger]}
            onPress={handleDeleteAllRead}
          >
            <Text style={styles.actionButtonText}>🗑️ Delete Read</Text>
          </TouchableOpacity>
        </View>

        {/* Notifications List */}
        {notifications.length === 0 ? (
          <EmptyState
            emoji={filter === 'unread' ? '✅' : '📭'}
            title={filter === 'unread' ? 'Δεν υπάρχουν μη διαβασμένες' : 'Δεν υπάρχουν ειδοποιήσεις'}
            message={filter === 'unread' 
              ? 'Όλες οι ειδοποιήσεις είναι διαβασμένες!'
              : 'Όταν λάβετε νέες ειδοποιήσεις, θα εμφανιστούν εδώ.'}
          />
        ) : (
          notifications.map((notification) => (
            <TouchableOpacity
              key={notification.id}
              style={[
                styles.notificationCard,
                !notification.read && styles.notificationCardUnread
              ]}
              onPress={() => handleMarkAsRead(notification.id)}
            >
              <View style={styles.notificationHeader}>
                <View style={styles.notificationIconContainer}>
                  <Text style={styles.notificationIcon}>
                    {getNotificationIcon(notification.type)}
                  </Text>
                </View>
                
                <View style={styles.notificationContent}>
                  <View style={styles.notificationTitleRow}>
                    <Text style={styles.notificationTitle}>
                      {notification.title}
                    </Text>
                    {!notification.read && (
                      <View style={styles.unreadDot} />
                    )}
                  </View>
                  
                  <Text style={styles.notificationMessage}>
                    {notification.message}
                  </Text>
                  
                  <View style={styles.notificationFooter}>
                    <Text style={styles.notificationTime}>
                      {formatTime(notification.created_at)}
                    </Text>
                    <View style={[
                      styles.priorityBadge,
                      { backgroundColor: getPriorityColor(notification.priority) }
                    ]}>
                      <Text style={styles.priorityBadgeText}>
                        {notification.priority}
                      </Text>
                    </View>
                  </View>
                </View>
                
                <TouchableOpacity
                  style={styles.deleteIcon}
                  onPress={() => handleDelete(notification.id)}
                >
                  <Text style={styles.deleteIconText}>✕</Text>
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          ))
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            🔔 Notifications - Stay updated on your trades
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  content: {
    padding: 20,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    color: '#999',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 30,
    marginTop: 10,
  },
  backButton: {
    marginRight: 15,
    padding: 5,
  },
  backButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  headerRight: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  badge: {
    backgroundColor: '#ff6b6b',
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minWidth: 24,
    alignItems: 'center',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  card: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  statLabel: {
    fontSize: 12,
    color: '#999',
  },
  filters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 20,
  },
  filterButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  filterButtonActive: {
    backgroundColor: '#4CAF50',
  },
  filterButtonText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#999',
    textTransform: 'capitalize',
  },
  filterButtonTextActive: {
    color: '#fff',
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 20,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
  },
  actionButtonDanger: {
    backgroundColor: '#3a1a1a',
    borderWidth: 1,
    borderColor: '#5a2a2a',
  },
  actionButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#fff',
  },
  emptyContainer: {
    alignItems: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#999',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
  },
  notificationCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  notificationCardUnread: {
    borderColor: '#4CAF50',
    borderWidth: 2,
    backgroundColor: '#1a2a1a',
  },
  notificationHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  notificationIconContainer: {
    marginRight: 12,
  },
  notificationIcon: {
    fontSize: 24,
  },
  notificationContent: {
    flex: 1,
  },
  notificationTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  notificationTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
    flex: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#4CAF50',
    marginLeft: 8,
  },
  notificationMessage: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
    marginBottom: 8,
  },
  notificationFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  notificationTime: {
    fontSize: 12,
    color: '#666',
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  priorityBadgeText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#fff',
    textTransform: 'uppercase',
  },
  deleteIcon: {
    padding: 5,
    marginLeft: 8,
  },
  deleteIconText: {
    fontSize: 18,
    color: '#666',
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
});

