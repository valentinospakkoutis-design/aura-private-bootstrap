import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Audio } from 'expo-av';
import api from '../mobile/src/services/api';

export default function VoiceBriefingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [briefing, setBriefing] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [sound, setSound] = useState(null);
  const [playbackStatus, setPlaybackStatus] = useState(null);
  
  // Settings
  const [includeNews, setIncludeNews] = useState(true);
  const [includePredictions, setIncludePredictions] = useState(true);
  const [includePortfolio, setIncludePortfolio] = useState(true);

  useEffect(() => {
    return () => {
      // Cleanup sound on unmount
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, [sound]);

  const loadBriefing = async () => {
    try {
      setLoading(true);
      const data = await api.getMorningBriefing(
        includeNews,
        includePredictions,
        includePortfolio,
        90
      );
      setBriefing(data);
    } catch (error) {
      console.error('Error loading briefing:', error);
      Alert.alert('Σφάλμα', 'Αποτυχία φόρτωσης briefing');
    } finally {
      setLoading(false);
    }
  };

  const speakText = async (text) => {
    try {
      // Request audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
      });

      // Use Web Speech API for web, native TTS for mobile
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        // Web browser - use Web Speech API
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'el-GR';
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        return new Promise((resolve, reject) => {
          utterance.onend = resolve;
          utterance.onerror = reject;
          window.speechSynthesis.speak(utterance);
        });
      } else {
        // Mobile - would use expo-speech or native TTS
        // For now, show alert
        Alert.alert('Voice Briefing', text);
      }
    } catch (error) {
      console.error('Error speaking:', error);
      Alert.alert('Σφάλμα', 'Αποτυχία αναπαραγωγής φωνής');
    }
  };

  const handlePlay = async () => {
    if (!briefing) {
      await loadBriefing();
      return;
    }

    if (isPlaying) {
      // Stop playback
      if (sound) {
        await sound.stopAsync();
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      setIsPlaying(false);
    } else {
      // Start playback
      setIsPlaying(true);
      await speakText(briefing.full_text);
      setIsPlaying(false);
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Text style={styles.backButtonText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>🎙️ Voice Briefing</Text>
        </View>

        {/* Settings */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>⚙️ Ρυθμίσεις Briefing</Text>
          
          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => setIncludeNews(!includeNews)}
          >
            <Text style={styles.settingLabel}>📰 Market News</Text>
            <View style={[styles.toggle, includeNews && styles.toggleActive]}>
              <View style={[styles.toggleThumb, includeNews && styles.toggleThumbActive]} />
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => setIncludePredictions(!includePredictions)}
          >
            <Text style={styles.settingLabel}>🤖 AI Predictions</Text>
            <View style={[styles.toggle, includePredictions && styles.toggleActive]}>
              <View style={[styles.toggleThumb, includePredictions && styles.toggleThumbActive]} />
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => setIncludePortfolio(!includePortfolio)}
          >
            <Text style={styles.settingLabel}>💼 Portfolio Summary</Text>
            <View style={[styles.toggle, includePortfolio && styles.toggleActive]}>
              <View style={[styles.toggleThumb, includePortfolio && styles.toggleThumbActive]} />
            </View>
          </TouchableOpacity>
        </View>

        {/* Generate/Play Button */}
        <TouchableOpacity
          style={[styles.playButton, isPlaying && styles.playButtonActive]}
          onPress={handlePlay}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Text style={styles.playButtonIcon}>
                {isPlaying ? '⏸️' : '▶️'}
              </Text>
              <Text style={styles.playButtonText}>
                {isPlaying ? 'Παύση' : briefing ? 'Αναπαραγωγή' : 'Δημιουργία Briefing'}
              </Text>
            </>
          )}
        </TouchableOpacity>

        {/* Briefing Content */}
        {briefing && (
          <View style={styles.card}>
            <View style={styles.briefingHeader}>
              <Text style={styles.cardTitle}>📋 Morning Briefing</Text>
              <Text style={styles.duration}>
                {formatDuration(briefing.duration_seconds)}
              </Text>
            </View>

            <Text style={styles.date}>
              {new Date(briefing.date).toLocaleDateString('el-GR', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}
            </Text>

            {/* Sections */}
            {briefing.sections.map((section, index) => (
              <View key={index} style={styles.section}>
                <View style={styles.sectionHeader}>
                  <Text style={styles.sectionIcon}>
                    {section.type === 'greeting' && '👋'}
                    {section.type === 'news' && '📰'}
                    {section.type === 'prediction' && '🤖'}
                    {section.type === 'portfolio' && '💼'}
                    {section.type === 'closing' && '👋'}
                  </Text>
                  <Text style={styles.sectionType}>
                    {section.type === 'greeting' && 'Χαιρετισμός'}
                    {section.type === 'news' && 'Ειδήσεις'}
                    {section.type === 'prediction' && 'AI Πρόβλεψη'}
                    {section.type === 'portfolio' && 'Portfolio'}
                    {section.type === 'closing' && 'Κλείσιμο'}
                  </Text>
                </View>
                <Text style={styles.sectionText}>{section.text}</Text>
              </View>
            ))}

            {/* Full Text */}
            <View style={styles.fullTextContainer}>
              <Text style={styles.fullTextLabel}>Full Text:</Text>
              <Text style={styles.fullText}>{briefing.full_text}</Text>
            </View>
          </View>
        )}

        {/* Info */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ Πληροφορίες</Text>
          <Text style={styles.infoText}>
            Το Voice Briefing περιλαμβάνει:
          </Text>
          <Text style={styles.infoText}>• Market news (3 ειδήσεις)</Text>
          <Text style={styles.infoText}>• AI predictions για precious metals</Text>
          <Text style={styles.infoText}>• Portfolio summary</Text>
          <Text style={styles.infoText}>• Διάρκεια: 45-90 δευτερόλεπτα</Text>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            🎙️ Voice Briefing - Καλημέρα από το AURA!
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
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  settingLabel: {
    fontSize: 16,
    color: '#fff',
  },
  toggle: {
    width: 50,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#3a3a3a',
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  toggleActive: {
    backgroundColor: '#4CAF50',
  },
  toggleThumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#fff',
    alignSelf: 'flex-start',
  },
  toggleThumbActive: {
    alignSelf: 'flex-end',
  },
  playButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
  },
  playButtonActive: {
    backgroundColor: '#ff6b6b',
  },
  playButtonIcon: {
    fontSize: 24,
  },
  playButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  briefingHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  duration: {
    fontSize: 14,
    color: '#999',
    fontWeight: 'bold',
  },
  date: {
    fontSize: 14,
    color: '#999',
    marginBottom: 20,
    fontStyle: 'italic',
  },
  section: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionIcon: {
    fontSize: 20,
    marginRight: 8,
  },
  sectionType: {
    fontSize: 12,
    color: '#999',
    fontWeight: 'bold',
    textTransform: 'uppercase',
  },
  sectionText: {
    fontSize: 14,
    color: '#fff',
    lineHeight: 20,
  },
  fullTextContainer: {
    marginTop: 20,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#2a2a2a',
  },
  fullTextLabel: {
    fontSize: 12,
    color: '#999',
    marginBottom: 8,
    fontWeight: 'bold',
  },
  fullText: {
    fontSize: 14,
    color: '#ccc',
    lineHeight: 22,
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

