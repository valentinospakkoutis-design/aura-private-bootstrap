import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';

export default function PrivacyScreen() {
  return (
    <PageTransition type="fade">
      <View style={styles.container}>
        <Text style={styles.title}>Πολιτική Απορρήτου</Text>
        <Text style={styles.body}>
          Προσωρινή placeholder οθόνη για την πολιτική απορρήτου. Το route υπάρχει πλέον κανονικά ώστε να μην αποτυγχάνει το navigation.
        </Text>
      </View>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.ui.background,
  },
  title: {
    fontSize: theme.typography.sizes['2xl'],
    fontFamily: theme.typography.fontFamily.bold,
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  body: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.regular,
    color: theme.colors.text.secondary,
    lineHeight: 24,
  },
});
