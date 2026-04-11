import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { LoadingSpinner } from '../mobile/src/components/LoadingSpinner';
import { Button } from '../mobile/src/components/Button';
import { theme } from '../mobile/src/constants/theme';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useLanguage } from '../mobile/src/hooks/useLanguage';

type RecordingStatus = 'idle' | 'recording' | 'stopped' | 'uploading';

export default function VoiceBriefingScreen() {
  const { user, showToast } = useAppStore();
  const { t } = useLanguage();
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus>('idle');
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [sound, setSound] = useState<Audio.Sound | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [briefingUrl, setBriefingUrl] = useState<string | null>(null);
  const [briefingText, setBriefingText] = useState<string | null>(null);
  const [durationInterval, setDurationInterval] = useState<NodeJS.Timeout | null>(null);

  const {
    loading: loadingBriefing,
    execute: fetchBriefing,
  } = useApi(() => api.getVoiceBriefing(), { showLoading: false, showToast: false });

  const {
    loading: uploadingVoice,
    execute: uploadVoice,
  } = useApi((audioUri: string) => api.uploadVoiceSample(audioUri), { showLoading: false, showToast: false });

  useEffect(() => {
    loadBriefing();
    setupAudio();

    return () => {
      cleanupAudio();
      if (durationInterval) {
        clearInterval(durationInterval);
      }
    };
  }, []);

  const setupAudio = async () => {
    try {
      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
    } catch (err) {
      console.error('Failed to setup audio:', err);
      showToast('Αποτυχία ρύθμισης ήχου', 'error');
    }
  };

  const cleanupAudio = async () => {
    try {
      if (recording) {
        await recording.stopAndUnloadAsync();
      }
      if (sound) {
        await sound.unloadAsync();
      }
    } catch (err) {
      console.error('Error cleaning up audio:', err);
    }
  };

  const loadBriefing = async () => {
    try {
      const data = await fetchBriefing();
      if (data) {
        console.log('Briefing loaded:', data.briefing_id || 'briefing');
        setBriefingUrl(data.audio_url || null);
        setBriefingText(data.text || data.full_text || null);
      }
    } catch (err) {
      console.error('Failed to load briefing:', err);
      showToast('Αποτυχία φόρτωσης briefing', 'error');
    }
  };

  const startRecording = async () => {
    try {
      // Check permissions
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        showToast('Χρειάζεται άδεια για το μικρόφωνο', 'error');
        return;
      }

      // Stop any existing recording
      if (recording) {
        await recording.stopAndUnloadAsync();
      }

      // Configure audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Start recording
      const { recording: newRecording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      setRecording(newRecording);
      setRecordingStatus('recording');
      setRecordingDuration(0);

      // Update duration every second
      const interval = setInterval(() => {
        setRecordingDuration((prev) => {
          if (prev >= 30) {
            stopRecording();
            return 30;
          }
          return prev + 1;
        });
      }, 1000);

      setDurationInterval(interval);

      showToast('Ηχογράφηση ξεκίνησε!', 'info');
    } catch (err) {
      console.error('Failed to start recording:', err);
      showToast('Αποτυχία ηχογράφησης', 'error');
      setRecordingStatus('idle');
    }
  };

  const stopRecording = async () => {
    try {
      if (!recording) return;

      if (durationInterval) {
        clearInterval(durationInterval);
        setDurationInterval(null);
      }

      setRecordingStatus('stopped');
      await recording.stopAndUnloadAsync();
      
      const uri = recording.getURI();
      
      if (!uri) {
        throw new Error('No recording URI');
      }

      // Check if recording is long enough (minimum 5 seconds)
      if (recordingDuration < 5) {
        showToast('Η ηχογράφηση πρέπει να είναι τουλάχιστον 5 δευτερόλεπτα', 'warning');
        setRecordingStatus('idle');
        setRecording(null);
        return;
      }

      showToast('Ηχογράφηση ολοκληρώθηκε!', 'success');
      
      // Ask user if they want to upload
      Alert.alert(
        'Ηχογράφηση Ολοκληρώθηκε',
        'Θέλεις να ανεβάσεις τη φωνή σου για cloning;',
        [
          {
            text: 'Ακύρωση',
            style: 'cancel',
            onPress: () => {
              setRecordingStatus('idle');
              setRecording(null);
            },
          },
          {
            text: 'Ανέβασμα',
            onPress: () => handleUploadVoice(uri),
          },
        ]
      );
    } catch (err) {
      console.error('Failed to stop recording:', err);
      showToast('Αποτυχία διακοπής ηχογράφησης', 'error');
      setRecordingStatus('idle');
    }
  };

  const handleUploadVoice = async (uri: string) => {
    try {
      setRecordingStatus('uploading');

      // Validate file exists
      const fileInfo = await FileSystem.getInfoAsync(uri);
      if (!fileInfo.exists) {
        throw new Error('Recording file not found');
      }

      await uploadVoice(uri);
      
      showToast('Η φωνή σου ανέβηκε επιτυχώς! 🎉', 'success');
      setRecordingStatus('idle');
      setRecording(null);
      
      // Reload briefing
      await loadBriefing();
    } catch (err) {
      console.error('Failed to upload voice:', err);
      showToast('Αποτυχία ανεβάσματος φωνής', 'error');
      setRecordingStatus('stopped');
    }
  };

  const playBriefing = async () => {
    try {
      if (!briefingUrl) {
        showToast(t('noVoiceBriefing') || 'Δεν υπάρχει διαθέσιμο briefing', 'warning');
        return;
      }

      // Stop existing sound
      if (sound) {
        await sound.unloadAsync();
      }

      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: briefingUrl },
        { shouldPlay: true }
      );

      setSound(newSound);
      setIsPlaying(true);

      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setIsPlaying(false);
        }
      });
    } catch (err) {
      console.error('Failed to play briefing:', err);
      showToast('Αποτυχία αναπαραγωγής', 'error');
    }
  };

  const stopBriefing = async () => {
    try {
      if (sound) {
        await sound.stopAsync();
        setIsPlaying(false);
      }
    } catch (err) {
      console.error('Failed to stop briefing:', err);
    }
  };

  if (loadingBriefing) {
    return <LoadingSpinner fullScreen message="Φόρτωση..." />;
  }

  const isRecording = recordingStatus === 'recording';
  const isUploading = recordingStatus === 'uploading';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Voice Clone Card */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>🎙️ Voice Cloning</Text>
        <Text style={styles.cardDescription}>
          Ηχογράφησε τη φωνή σου για 30 δευτερόλεπτα και το AURA θα την κλωνοποιήσει για να σου δίνει καθημερινά briefings!
        </Text>

        {/* Recording Status */}
        {isRecording && (
          <View style={styles.recordingIndicator}>
            <View style={styles.recordingDot} />
            <Text style={styles.recordingText}>
              Ηχογράφηση... {recordingDuration}/30s
            </Text>
          </View>
        )}

        {/* Recording Progress */}
        {isRecording && (
          <View style={styles.progressBar}>
            <View 
              style={[
                styles.progressFill,
                { width: `${(recordingDuration / 30) * 100}%` }
              ]} 
            />
          </View>
        )}

        {/* Recording Buttons */}
        <View style={styles.buttonContainer}>
          {!isRecording && recordingStatus !== 'stopped' && (
            <Button
              title="Ξεκίνα Ηχογράφηση"
              onPress={startRecording}
              variant="primary"
              size="large"
              fullWidth
              disabled={isUploading}
              loading={isUploading}
            />
          )}

          {isRecording && (
            <Button
              title="Σταμάτημα"
              onPress={stopRecording}
              variant="danger"
              size="large"
              fullWidth
            />
          )}
        </View>

        {/* Voice Clone Status */}
        {user?.voiceCloned && (
          <View style={styles.successBadge}>
            <Text style={styles.successText}>✓ Η φωνή σου είναι έτοιμη!</Text>
          </View>
        )}
      </View>

      {/* Daily Briefing Card */}
      {(briefingUrl || briefingText) && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📊 Καθημερινό Briefing</Text>
          {briefingText ? (
            <Text style={styles.cardDescription}>{briefingText}</Text>
          ) : null}

          {briefingUrl ? (
            <Button
              title={isPlaying ? '⏸️ Σταμάτημα' : '▶️ Αναπαραγωγή'}
              onPress={isPlaying ? stopBriefing : playBriefing}
              variant={isPlaying ? 'secondary' : 'primary'}
              size="large"
              fullWidth
            />
          ) : null}
        </View>
      )}

      {/* Tips Card */}
      <View style={styles.tipsCard}>
        <Text style={styles.tipsTitle}>💡 Συμβουλές για καλύτερη ηχογράφηση:</Text>
        <Text style={styles.tipText}>• Βρες ένα ήσυχο μέρος</Text>
        <Text style={styles.tipText}>• Μίλα φυσιολογικά και καθαρά</Text>
        <Text style={styles.tipText}>• Κράτα το τηλέφωνο κοντά στο στόμα</Text>
        <Text style={styles.tipText}>• Μίλα για 30 δευτερόλεπτα συνεχόμενα</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
  },
  card: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
  },
  cardTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
  },
  cardDescription: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 22,
    marginBottom: theme.spacing.lg,
  },
  recordingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: theme.spacing.md,
    backgroundColor: theme.colors.semantic.error + '10',
    borderRadius: theme.borderRadius.md,
    marginBottom: theme.spacing.md,
  },
  recordingDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: theme.colors.semantic.error,
    marginRight: theme.spacing.sm,
  },
  recordingText: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.semantic.error,
  },
  progressBar: {
    height: 8,
    backgroundColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    marginBottom: theme.spacing.lg,
  },
  progressFill: {
    height: '100%',
    backgroundColor: theme.colors.brand.primary,
    borderRadius: theme.borderRadius.md,
  },
  buttonContainer: {
    gap: theme.spacing.sm,
  },
  buttonIcon: {
    fontSize: 18,
  },
  successBadge: {
    marginTop: theme.spacing.md,
    padding: theme.spacing.md,
    backgroundColor: theme.colors.semantic.success + '20',
    borderRadius: theme.borderRadius.md,
    alignItems: 'center',
  },
  successText: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.semantic.success,
  },
  tipsCard: {
    backgroundColor: theme.colors.brand.primary + '10',
    borderRadius: theme.borderRadius.xlarge,
    padding: theme.spacing.lg,
    borderWidth: 1,
    borderColor: theme.colors.brand.primary + '30',
  },
  tipsTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  tipText: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    lineHeight: 24,
    marginBottom: theme.spacing.xs,
  },
});


