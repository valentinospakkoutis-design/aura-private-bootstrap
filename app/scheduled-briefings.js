import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, ActivityIndicator, RefreshControl, TextInput, Switch } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function ScheduledBriefingsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [schedules, setSchedules] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  
  // Create form state
  const [formTime, setFormTime] = useState('09:00');
  const [formDays, setFormDays] = useState({
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false
  });
  const [formEnabled, setFormEnabled] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load schedules
      const schedulesData = await api.get('/api/scheduler/schedules?schedule_type=morning_briefing');
      setSchedules(schedulesData.schedules || []);
      
      // Load upcoming
      const upcomingData = await api.get('/api/scheduler/upcoming?limit=10');
      setUpcoming(upcomingData.schedules || []);
    } catch (error) {
      console.error('Error loading schedules:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleCreateSchedule = async () => {
    const selectedDays = Object.entries(formDays)
      .filter(([_, selected]) => selected)
      .map(([day, _]) => day);
    
    if (selectedDays.length === 0) {
      Alert.alert('Σφάλμα', 'Επιλέξτε τουλάχιστον μία ημέρα');
      return;
    }

    try {
      await api.post('/api/scheduler/schedules', {
        schedule_type: 'morning_briefing',
        time: formTime,
        days: selectedDays,
        enabled: formEnabled,
        config: {
          include_news: true,
          include_predictions: true,
          include_portfolio: true
        }
      });
      
      Alert.alert('Επιτυχία', 'Schedule created successfully');
      setShowCreateForm(false);
      setFormTime('09:00');
      setFormDays({
        monday: true,
        tuesday: true,
        wednesday: true,
        thursday: true,
        friday: true,
        saturday: false,
        sunday: false
      });
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία δημιουργίας schedule');
    }
  };

  const handleToggleSchedule = async (scheduleId, currentEnabled) => {
    try {
      await api.put(`/api/scheduler/schedules/${scheduleId}`, {
        enabled: !currentEnabled
      });
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', 'Αποτυχία ενημέρωσης schedule');
    }
  };

  const handleDeleteSchedule = (scheduleId) => {
    Alert.alert(
      'Διαγραφή Schedule',
      'Είστε σίγουροι ότι θέλετε να διαγράψετε αυτό το schedule;',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Διαγραφή',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/api/scheduler/schedules/${scheduleId}`);
              Alert.alert('Επιτυχία', 'Schedule deleted');
              loadData();
            } catch (error) {
              Alert.alert('Σφάλμα', 'Αποτυχία διαγραφής');
            }
          }
        }
      ]
    );
  };

  const formatNextExecution = (nextExec) => {
    if (!nextExec) return 'N/A';
    try {
      const date = new Date(nextExec);
      const now = new Date();
      const diffMs = date - now;
      const diffMins = Math.floor(diffMs / 60000);
      
      if (diffMins < 0) return 'Overdue';
      if (diffMins < 60) return `In ${diffMins} mins`;
      if (diffMins < 1440) return `In ${Math.floor(diffMins / 60)} hours`;
      return date.toLocaleDateString('el-GR', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch {
      return 'N/A';
    }
  };

  const formatDays = (days) => {
    const dayNames = {
      monday: 'Δευ',
      tuesday: 'Τρί',
      wednesday: 'Τετ',
      thursday: 'Πέμ',
      friday: 'Παρ',
      saturday: 'Σάβ',
      sunday: 'Κυρ'
    };
    return days.map(d => dayNames[d.toLowerCase()] || d).join(', ');
  };

  if (loading && !schedules.length) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση Schedules...</Text>
        </View>
      </View>
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
          <Text style={styles.title}>⏰ Scheduled Briefings</Text>
        </View>

        {/* Create Schedule Button */}
        <TouchableOpacity
          style={styles.createButton}
          onPress={() => setShowCreateForm(!showCreateForm)}
        >
          <Text style={styles.createButtonText}>
            {showCreateForm ? '✖️ Cancel' : '➕ Create Schedule'}
          </Text>
        </TouchableOpacity>

        {/* Create Form */}
        {showCreateForm && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📅 New Schedule</Text>
            
            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Time</Text>
              <TextInput
                style={styles.timeInput}
                value={formTime}
                onChangeText={setFormTime}
                placeholder="09:00"
                placeholderTextColor="#666"
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Days</Text>
              {Object.entries(formDays).map(([day, selected]) => (
                <View key={day} style={styles.dayRow}>
                  <Text style={styles.dayLabel}>{day.charAt(0).toUpperCase() + day.slice(1)}</Text>
                  <Switch
                    value={selected}
                    onValueChange={(value) => setFormDays({ ...formDays, [day]: value })}
                    trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
                    thumbColor={selected ? '#fff' : '#999'}
                  />
                </View>
              ))}
            </View>

            <View style={styles.formGroup}>
              <View style={styles.dayRow}>
                <Text style={styles.dayLabel}>Enabled</Text>
                <Switch
                  value={formEnabled}
                  onValueChange={setFormEnabled}
                  trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
                  thumbColor={formEnabled ? '#fff' : '#999'}
                />
              </View>
            </View>

            <TouchableOpacity
              style={styles.saveButton}
              onPress={handleCreateSchedule}
            >
              <Text style={styles.saveButtonText}>💾 Create Schedule</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Upcoming Schedules */}
        {upcoming.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>⏰ Upcoming Briefings</Text>
            
            {upcoming.map((schedule, index) => (
              <View key={index} style={styles.scheduleItem}>
                <View style={styles.scheduleHeader}>
                  <Text style={styles.scheduleTime}>{schedule.time}</Text>
                  <Text style={styles.scheduleNext}>
                    {formatNextExecution(schedule.next_execution)}
                  </Text>
                </View>
                <Text style={styles.scheduleDays}>
                  {formatDays(schedule.days)}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Active Schedules */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📋 Active Schedules</Text>
          
          {schedules.length === 0 ? (
            <Text style={styles.emptyText}>No schedules created yet</Text>
          ) : (
            schedules.map((schedule) => (
              <View key={schedule.id} style={styles.scheduleCard}>
                <View style={styles.scheduleCardHeader}>
                  <View>
                    <Text style={styles.scheduleCardTime}>{schedule.time}</Text>
                    <Text style={styles.scheduleCardDays}>
                      {formatDays(schedule.days)}
                    </Text>
                  </View>
                  <Switch
                    value={schedule.enabled}
                    onValueChange={() => handleToggleSchedule(schedule.id, schedule.enabled)}
                    trackColor={{ false: '#3a3a3a', true: '#4CAF50' }}
                    thumbColor={schedule.enabled ? '#fff' : '#999'}
                  />
                </View>
                
                {schedule.next_execution && (
                  <Text style={styles.scheduleCardNext}>
                    Next: {formatNextExecution(schedule.next_execution)}
                  </Text>
                )}
                
                {schedule.execution_count > 0 && (
                  <Text style={styles.scheduleCardCount}>
                    Executed {schedule.execution_count} times
                  </Text>
                )}
                
                <TouchableOpacity
                  style={styles.deleteButton}
                  onPress={() => handleDeleteSchedule(schedule.id)}
                >
                  <Text style={styles.deleteButtonText}>🗑️ Delete</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
        </View>

        {/* Info */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ Scheduled Briefings</Text>
          <Text style={styles.infoText}>
            Προγραμματίστε αυτόματα morning briefings:
          </Text>
          <Text style={styles.infoText}>• Επιλέξτε ώρα και ημέρες</Text>
          <Text style={styles.infoText}>• Το briefing θα παίξει αυτόματα</Text>
          <Text style={styles.infoText}>• Μπορείτε να ενεργοποιήσετε/απενεργοποιήσετε</Text>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            ⏰ Scheduled Briefings - Never miss your morning update!
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
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  createButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 20,
  },
  createButtonText: {
    fontSize: 18,
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
  formGroup: {
    marginBottom: 20,
  },
  formLabel: {
    fontSize: 14,
    color: '#999',
    marginBottom: 8,
  },
  timeInput: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 14,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#3a3a3a',
    fontSize: 16,
  },
  dayRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  dayLabel: {
    fontSize: 14,
    color: '#fff',
  },
  saveButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  saveButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  scheduleItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  scheduleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  scheduleTime: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  scheduleNext: {
    fontSize: 12,
    color: '#999',
  },
  scheduleDays: {
    fontSize: 12,
    color: '#666',
  },
  emptyText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    padding: 20,
  },
  scheduleCard: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 12,
  },
  scheduleCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  scheduleCardTime: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 4,
  },
  scheduleCardDays: {
    fontSize: 12,
    color: '#999',
  },
  scheduleCardNext: {
    fontSize: 12,
    color: '#666',
    marginBottom: 5,
  },
  scheduleCardCount: {
    fontSize: 12,
    color: '#666',
    marginBottom: 10,
  },
  deleteButton: {
    backgroundColor: '#3a1a1a',
    borderRadius: 8,
    padding: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#5a2a2a',
  },
  deleteButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#ff6b6b',
  },
  infoCard: {
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
    marginBottom: 10,
  },
  infoText: {
    fontSize: 14,
    color: '#999',
    lineHeight: 20,
    marginBottom: 5,
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

