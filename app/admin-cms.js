import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../mobile/src/services/api';

export default function AdminCMSScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [quotes, setQuotes] = useState([]);
  const [settings, setSettings] = useState(null);
  const [activeTab, setActiveTab] = useState('quotes');
  
  // Quote editing
  const [editingQuote, setEditingQuote] = useState(null);
  const [quoteForm, setQuoteForm] = useState({ el: '', en: '', author: '', category: 'general' });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load quotes
      const quotesData = await api.get('/api/cms/quotes');
      setQuotes(quotesData.quotes || []);
      
      // Load settings
      const settingsData = await api.get('/api/cms/settings');
      setSettings(settingsData);
    } catch (error) {
      console.error('Error loading CMS data:', error);
      Alert.alert('Σφάλμα', 'Αποτυχία φόρτωσης δεδομένων');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleAddQuote = () => { // eslint-disable-line no-unused-vars
    setEditingQuote(null);
    setQuoteForm({ el: '', en: '', author: '', category: 'general' });
  };

  const handleEditQuote = (quote) => {
    setEditingQuote(quote);
    setQuoteForm({
      el: quote.el || '',
      en: quote.en || '',
      author: quote.author || '',
      category: quote.category || 'general'
    });
  };

  const handleSaveQuote = async () => {
    if (!quoteForm.el || !quoteForm.en) {
      Alert.alert('Σφάλμα', 'Παρακαλώ συμπληρώστε ελληνικά και αγγλικά');
      return;
    }

    try {
      if (editingQuote) {
        await api.put(`/api/cms/quotes/${editingQuote.id}`, quoteForm);
        Alert.alert('Επιτυχία', 'Το quote ενημερώθηκε');
      } else {
        await api.post('/api/cms/quotes', quoteForm);
        Alert.alert('Επιτυχία', 'Νέο quote προστέθηκε');
      }
      
      setEditingQuote(null);
      setQuoteForm({ el: '', en: '', author: '', category: 'general' });
      loadData();
    } catch (error) {
      Alert.alert('Σφάλμα', error.message || 'Αποτυχία αποθήκευσης');
    }
  };

  const handleDeleteQuote = (quoteId) => {
    Alert.alert(
      'Διαγραφή Quote',
      'Είστε σίγουροι ότι θέλετε να διαγράψετε αυτό το quote;',
      [
        { text: 'Ακύρωση', style: 'cancel' },
        {
          text: 'Διαγραφή',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/api/cms/quotes/${quoteId}`);
              Alert.alert('Επιτυχία', 'Το quote διαγράφηκε');
              loadData();
            } catch (error) {
              Alert.alert('Σφάλμα', 'Αποτυχία διαγραφής');
            }
          }
        }
      ]
    );
  };

  if (loading && !quotes.length) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4CAF50" />
          <Text style={styles.loadingText}>Φόρτωση CMS...</Text>
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
          <Text style={styles.title}>📝 CMS Admin</Text>
        </View>

        {/* Tabs */}
        <View style={styles.tabs}>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'quotes' && styles.tabActive]}
            onPress={() => setActiveTab('quotes')}
          >
            <Text style={[styles.tabText, activeTab === 'quotes' && styles.tabTextActive]}>
              Quotes
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'settings' && styles.tabActive]}
            onPress={() => setActiveTab('settings')}
          >
            <Text style={[styles.tabText, activeTab === 'settings' && styles.tabTextActive]}>
              Settings
            </Text>
          </TouchableOpacity>
        </View>

        {/* Quotes Tab */}
        {activeTab === 'quotes' && (
          <>
            {/* Add/Edit Quote Form */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>
                {editingQuote ? '✏️ Επεξεργασία Quote' : '➕ Προσθήκη Quote'}
              </Text>

              <TextInput
                style={styles.input}
                placeholder="Ελληνικά"
                placeholderTextColor="#666"
                value={quoteForm.el}
                onChangeText={(text) => setQuoteForm({ ...quoteForm, el: text })}
                multiline
              />

              <TextInput
                style={styles.input}
                placeholder="English"
                placeholderTextColor="#666"
                value={quoteForm.en}
                onChangeText={(text) => setQuoteForm({ ...quoteForm, en: text })}
                multiline
              />

              <TextInput
                style={styles.input}
                placeholder="Συγγραφέας (προαιρετικό)"
                placeholderTextColor="#666"
                value={quoteForm.author}
                onChangeText={(text) => setQuoteForm({ ...quoteForm, author: text })}
              />

              <View style={styles.buttonRow}>
                <TouchableOpacity
                  style={styles.saveButton}
                  onPress={handleSaveQuote}
                >
                  <Text style={styles.saveButtonText}>
                    {editingQuote ? '💾 Αποθήκευση' : '➕ Προσθήκη'}
                  </Text>
                </TouchableOpacity>
                
                {editingQuote && (
                  <TouchableOpacity
                    style={styles.cancelButton}
                    onPress={() => {
                      setEditingQuote(null);
                      setQuoteForm({ el: '', en: '', author: '', category: 'general' });
                    }}
                  >
                    <Text style={styles.cancelButtonText}>✖️ Ακύρωση</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Quotes List */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>📚 Quotes ({quotes.length})</Text>
              
              {quotes.map((quote, index) => (
                <View key={quote.id || index} style={styles.quoteItem}>
                  <View style={styles.quoteContent}>
                    <Text style={styles.quoteText}>{quote.el}</Text>
                    <Text style={styles.quoteTextEn}>{quote.en}</Text>
                    {quote.author && (
                      <Text style={styles.quoteAuthor}>— {quote.author}</Text>
                    )}
                  </View>
                  
                  <View style={styles.quoteActions}>
                    <TouchableOpacity
                      style={styles.editButton}
                      onPress={() => handleEditQuote(quote)}
                    >
                      <Text style={styles.editButtonText}>✏️</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.deleteButton}
                      onPress={() => handleDeleteQuote(quote.id)}
                    >
                      <Text style={styles.deleteButtonText}>🗑️</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          </>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && settings && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>⚙️ CMS Settings</Text>
            
            <View style={styles.settingItem}>
              <Text style={styles.settingLabel}>App Name</Text>
              <Text style={styles.settingValue}>{settings.app_name}</Text>
            </View>
            
            <View style={styles.settingItem}>
              <Text style={styles.settingLabel}>Tagline</Text>
              <Text style={styles.settingValue}>{settings.app_tagline}</Text>
            </View>
            
            <View style={styles.settingItem}>
              <Text style={styles.settingLabel}>Maintenance Mode</Text>
              <Text style={styles.settingValue}>
                {settings.maintenance_mode ? '✅ Enabled' : '❌ Disabled'}
              </Text>
            </View>
            
            {settings.features && (
              <View style={styles.featuresSection}>
                <Text style={styles.featuresTitle}>Features</Text>
                {Object.entries(settings.features).map(([key, value]) => (
                  <View key={key} style={styles.featureItem}>
                    <Text style={styles.featureLabel}>{key}</Text>
                    <Text style={styles.featureValue}>
                      {value ? '✅' : '❌'}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            💡 CMS Admin Panel - Manage content easily
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
  tabs: {
    flexDirection: 'row',
    marginBottom: 20,
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 4,
  },
  tab: {
    flex: 1,
    padding: 12,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: {
    backgroundColor: '#4CAF50',
  },
  tabText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#999',
  },
  tabTextActive: {
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
  input: {
    backgroundColor: '#2a2a2a',
    borderRadius: 8,
    padding: 14,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#3a3a3a',
    marginBottom: 12,
    minHeight: 50,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
  saveButton: {
    flex: 1,
    backgroundColor: '#4CAF50',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
  },
  saveButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  cancelButton: {
    flex: 1,
    backgroundColor: '#3a3a3a',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  quoteItem: {
    backgroundColor: '#2a2a2a',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  quoteContent: {
    flex: 1,
  },
  quoteText: {
    fontSize: 14,
    color: '#fff',
    marginBottom: 5,
  },
  quoteTextEn: {
    fontSize: 12,
    color: '#999',
    fontStyle: 'italic',
    marginBottom: 5,
  },
  quoteAuthor: {
    fontSize: 11,
    color: '#666',
  },
  quoteActions: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
  },
  editButton: {
    padding: 8,
  },
  editButtonText: {
    fontSize: 18,
  },
  deleteButton: {
    padding: 8,
  },
  deleteButtonText: {
    fontSize: 18,
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  settingLabel: {
    fontSize: 14,
    color: '#999',
  },
  settingValue: {
    fontSize: 14,
    color: '#fff',
    fontWeight: 'bold',
  },
  featuresSection: {
    marginTop: 20,
  },
  featuresTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
  },
  featureItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  featureLabel: {
    fontSize: 14,
    color: '#999',
    textTransform: 'capitalize',
  },
  featureValue: {
    fontSize: 14,
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

