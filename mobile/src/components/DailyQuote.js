import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useQuoteOfDay } from '../hooks/useApi';

export default function DailyQuote({ style }) {
  const { data, loading, error } = useQuoteOfDay();

  // Debug logging (only in development)
  const isDev = typeof __DEV__ !== 'undefined' ? __DEV__ : process.env.NODE_ENV !== 'production';
  if (isDev) {
    if (error) {
      console.log('DailyQuote Error:', error);
    }
    if (data) {
      console.log('DailyQuote Data:', data);
    }
  }

  if (loading) {
    return (
      <View style={[styles.card, style, styles.loadingContainer]}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Φόρτωση γνωμικού...</Text>
      </View>
    );
  }

  // Fallback quote if API fails or no data
  const fallbackQuote = {
    el: "Η υπομονή είναι το κλειδί του παραδείσου. Και του πλούτου.",
    en: "Patience is the key to paradise. And to wealth.",
    author: "Ελληνική Παροιμία"
  };

  // Determine which quote to use
  let quote = null;
  
  if (data?.quote) {
    // API returned quote
    quote = data.quote;
  } else if (data && !data.quote && data.el) {
    // Direct quote object (fallback structure)
    quote = data;
  } else if (error || !data) {
    // Use fallback on error or no data
    quote = fallbackQuote;
  }

  // If still no quote, use fallback
  if (!quote) {
    quote = fallbackQuote;
  }

  return (
    <View style={[styles.card, style]}>
      <View style={styles.header}>
        <Text style={styles.title}>💎 Γνωμικό της Ημέρας</Text>
      </View>
      <Text style={styles.quote}>{quote.el || quote.en || 'No quote available'}</Text>
      <Text style={styles.author}>— {quote.author || 'Ελληνική Παροιμία'}</Text>
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

