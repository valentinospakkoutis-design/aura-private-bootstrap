import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import DailyQuote from '../mobile/src/components/DailyQuote';
import AuraOrb3D from '../mobile/src/components/AuraOrb3D';
import LoadingState from '../mobile/src/components/LoadingState';
import NetworkErrorHandler from '../mobile/src/components/NetworkErrorHandler';
import DebugInfo from '../mobile/src/components/DebugInfo';
import { AnimatedFadeIn, AnimatedSlideUp } from '../mobile/src/components/AnimatedView';
import { useScreenTracking } from '../mobile/src/hooks/useAnalytics';
import api from '../mobile/src/services/api';

export default function HomeScreen() {
  const router = useRouter();
  const [greeting, setGreeting] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  
  // Track screen view
  useScreenTracking('Home');

  useEffect(() => {
    try {
      const hour = new Date().getHours();
      if (hour < 12) {
        setGreeting('Καλημέρα');
      } else if (hour < 18) {
        setGreeting('Καλό απόγευμα');
      } else {
        setGreeting('Καλησπέρα');
      }
      
      // Load unread notifications count (with delay to avoid blocking startup)
      const timeoutId = setTimeout(() => {
        loadUnreadCount();
      }, 500); // Small delay to let app render first
      
      const interval = setInterval(() => {
        loadUnreadCount();
      }, 30000); // Every 30 seconds
      
      return () => {
        clearTimeout(timeoutId);
        clearInterval(interval);
      };
    } catch (error) {
      console.error('Error in HomeScreen useEffect:', error);
      // Don't crash - just set default values
      setGreeting('Καλημέρα');
      setLoading(false);
    }
  }, []); // Empty dependency array - only run once on mount

  const loadUnreadCount = async () => {
    // Prevent multiple simultaneous calls
    if (loading) {
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      const data = await api.get('/api/notifications?unread_only=true&limit=1');
      setUnreadCount(data.unread_count || 0);
      setLoading(false);
    } catch (err) {
      console.error('Error loading unread count:', err);
      // Don't crash the app - just set error state
      setError(err);
      setUnreadCount(0); // Default to 0 if error
      setLoading(false);
    }
  };

  // Don't block app startup - show content even if loading
  // Only show loading if we're still loading AND have no data
  if (loading && !unreadCount && !error) {
    return <LoadingState message="Φόρτωση δεδομένων..." />;
  }

  // Show error but don't block the app
  // The app should still render even if there's an error

  return (
    <>
      <ScrollView style={styles.container}>
      <View style={styles.content}>
        {/* Header Section */}
        <AnimatedFadeIn duration={400}>
          <View style={styles.header}>
            <View style={styles.headerTop}>
              <Text style={styles.greeting}>{greeting}! 👋</Text>
            <TouchableOpacity
              style={styles.notificationButton}
              onPress={() => router.push('/notifications')}
            >
              <Text style={styles.notificationIcon}>🔔</Text>
              {unreadCount > 0 && (
                <View style={styles.notificationBadge}>
                  <Text style={styles.notificationBadgeText}>
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          </View>
          
          {/* 3D Orb */}
          <AuraOrb3D 
            size={200} 
            color="#4CAF50" 
            speed={0.5}
            style={{ marginVertical: 20 }}
          />
          
            <Text style={styles.title}>AURA</Text>
            <Text style={styles.subtitle}>Το χρηματοοικονομικό σου ον</Text>
          </View>
        </AnimatedFadeIn>

        {/* Status Card */}
        <AnimatedSlideUp delay={100}>
          <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Κατάσταση Συστήματος</Text>
            <View style={styles.statusDot} />
          </View>
          <Text style={styles.cardSubtitle}>✅ Σύστημα Ενεργό</Text>
          <Text style={styles.cardText}>✅ Backend Έτοιμο για σύνδεση</Text>
            <Text style={styles.cardText}>✅ AI Engine Αναμονή</Text>
          </View>
        </AnimatedSlideUp>

        {/* Quote of the Day */}
        <AnimatedSlideUp delay={200}>
          <DailyQuote style={{ marginBottom: 20 }} />
        </AnimatedSlideUp>

        {/* Quick Stats */}
        <AnimatedSlideUp delay={300}>
          <View style={styles.statsContainer}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>0</Text>
            <Text style={styles.statLabel}>Ενεργά Trades</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>€0</Text>
            <Text style={styles.statLabel}>Σημερινό P/L</Text>
          </View>
        </View>
        </AnimatedSlideUp>

        {/* Action Buttons */}
        <AnimatedSlideUp delay={400}>
          <TouchableOpacity 
          style={styles.primaryButton}
          onPress={() => router.push('/paper-trading')}
        >
          <Text style={styles.primaryButtonText}>🚀 Ξεκίνα Paper Trading</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => router.push('/settings')}
        >
          <Text style={styles.secondaryButtonText}>⚙️ Ρυθμίσεις</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => router.push('/profile')}
        >
            <Text style={styles.secondaryButtonText}>👤 Προφίλ</Text>
          </TouchableOpacity>
        </AnimatedSlideUp>

        {/* AI Predictions Quick View */}
        <AnimatedSlideUp delay={500}>
          <TouchableOpacity 
          style={styles.aiCard}
          onPress={() => router.push('/ai-predictions')}
        >
          <Text style={styles.aiCardTitle}>🤖 AI Predictions</Text>
          <Text style={styles.aiCardText}>Δείτε προβλέψεις για χρυσό, άργυρο, πλατίνα, παλλάδιο</Text>
            <Text style={styles.aiCardArrow}>→</Text>
          </TouchableOpacity>
        </AnimatedSlideUp>

        {/* Analytics Quick View */}
        <AnimatedSlideUp delay={600}>
          <TouchableOpacity 
          style={styles.analyticsCard}
          onPress={() => router.push('/analytics')}
        >
          <Text style={styles.analyticsCardTitle}>📊 Analytics</Text>
          <Text style={styles.analyticsCardText}>Performance metrics & insights</Text>
            <Text style={styles.analyticsCardArrow}>→</Text>
          </TouchableOpacity>
        </AnimatedSlideUp>

        {/* Info Section */}
        <AnimatedSlideUp delay={700}>
          <View style={styles.infoSection}>
          <Text style={styles.infoTitle}>📚 Επόμενα Βήματα:</Text>
          <Text style={styles.infoText}>• Σύνδεση με brokers (Binance, eToro)</Text>
          <Text style={styles.infoText}>• Ρύθμιση προφίλ κινδύνου</Text>
          <Text style={styles.infoText}>• Επιλογή στρατηγικών trading</Text>
            <Text style={styles.infoText}>• Ενεργοποίηση AI agent</Text>
          </View>
        </AnimatedSlideUp>

        <AnimatedFadeIn delay={800}>
          <View style={styles.footer}>
            <Text style={styles.footerText}>AURA v1.0.0</Text>
            <Text style={styles.footerSubtext}>Made with 💎 in Cyprus</Text>
            <TouchableOpacity 
              onPress={() => setShowDebug(true)}
              style={styles.debugLink}
            >
              <Text style={styles.debugLinkText}>🔍 Debug Info</Text>
            </TouchableOpacity>
          </View>
        </AnimatedFadeIn>
      </View>
    </ScrollView>
    <DebugInfo 
      visible={showDebug}
      onClose={() => setShowDebug(false)}
    />
    </>
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
  header: {
    marginBottom: 30,
    alignItems: 'center',
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    paddingHorizontal: 10,
    marginBottom: 10,
  },
  greeting: {
    fontSize: 24,
    color: '#999',
  },
  notificationButton: {
    position: 'relative',
    padding: 8,
  },
  notificationIcon: {
    fontSize: 24,
  },
  notificationBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: '#ff6b6b',
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
    borderWidth: 2,
    borderColor: '#0f0f0f',
  },
  notificationBadgeText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#fff',
  },
  title: {
    fontSize: 56,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    fontStyle: 'italic',
  },
  card: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
  },
  cardSubtitle: {
    fontSize: 16,
    color: '#4CAF50',
    marginBottom: 8,
  },
  cardText: {
    fontSize: 14,
    color: '#999',
    marginBottom: 5,
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#4CAF50',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 5,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  statNumber: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  statLabel: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
  primaryButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  secondaryButton: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  secondaryButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  aiCard: {
    backgroundColor: '#1a3a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#4CAF50',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  aiCardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4CAF50',
    marginBottom: 5,
  },
  aiCardText: {
    fontSize: 14,
    color: '#999',
    flex: 1,
  },
  aiCardArrow: {
    fontSize: 24,
    color: '#4CAF50',
    marginLeft: 10,
  },
  analyticsCard: {
    backgroundColor: '#1a2a3a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2196F3',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  analyticsCardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2196F3',
    marginBottom: 5,
  },
  analyticsCardText: {
    fontSize: 14,
    color: '#999',
    flex: 1,
  },
  analyticsCardArrow: {
    fontSize: 24,
    color: '#2196F3',
    marginLeft: 10,
  },
  infoSection: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 15,
  },
  infoText: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
    lineHeight: 20,
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  footerText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
  },
  footerSubtext: {
    fontSize: 12,
    color: '#444',
  },
  debugLink: {
    marginTop: 12,
    padding: 8,
  },
  debugLinkText: {
    fontSize: 12,
    color: '#666',
    textDecorationLine: 'underline',
  },
});

