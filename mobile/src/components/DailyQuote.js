import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useQuoteOfDay } from '../hooks/useApi';

export default function DailyQuote({ style }) {
  const { data, loading, error } = useQuoteOfDay();

  if (loading) {
    return (
      <View style={[styles.card, style, styles.loadingContainer]}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Φόρτωση γνωμικού...</Text>
      </View>
    );
  }

  if (error) {
    // Fallback quote if API fails
    const fallbackQuote = {
      el: "Η υπομονή είναι το κλειδί του παραδείσου. Και του πλούτου.",
      en: "Patience is the key to paradise. And to wealth."
    };
    
    return (
      <View style={[styles.card, style]}>
        <View style={styles.header}>
          <Text style={styles.title}>💎 Γνωμικό της Ημέρας</Text>
        </View>
        <Text style={styles.quote}>{fallbackQuote.el}</Text>
        <Text style={styles.author}>— Ελληνική Παροιμία</Text>
      </View>
    );
  }

  const quote = data?.quote;
  
  if (!quote) {
    return null;
  }

  return (
    <View style={[styles.card, style]}>
      <View style={styles.header}>
        <Text style={styles.title}>💎 Γνωμικό της Ημέρας</Text>
      </View>
      <Text style={styles.quote}>{quote.el}</Text>
      <Text style={styles.author}>— Ελληνική Παροιμία</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  header: {
    marginBottom: 15,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  quote: {
    fontSize: 18,
    color: '#fff',
    fontStyle: 'italic',
    lineHeight: 28,
    marginBottom: 10,
  },
  author: {
    fontSize: 14,
    color: '#666',
    textAlign: 'right',
  },
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 120,
  },
  loadingText: {
    marginTop: 10,
    fontSize: 14,
    color: '#999',
  },
});

