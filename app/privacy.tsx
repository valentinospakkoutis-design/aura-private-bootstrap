import React from 'react';
import { Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { useLanguage } from '../mobile/src/hooks/useLanguage';
import { theme } from '../mobile/src/constants/theme';

type Section = {
  title: string;
  body: string;
  isContact?: boolean;
};

export default function PrivacyScreen() {
  const { language } = useLanguage();
  const isEn = language === 'en';

  const title = isEn ? 'Privacy Policy' : 'Πολιτική Απορρήτου';
  const updatedAt = isEn ? 'Last updated: April 2026' : 'Τελευταία ενημέρωση: Απρίλιος 2026';

  const sections: Section[] = isEn
    ? [
        {
          title: 'Data We Collect',
          body: 'We collect: email, encrypted password, encrypted API keys, transaction history, push tokens. We do NOT collect: card numbers, bank accounts, home addresses.',
        },
        {
          title: 'Use of Data',
          body: 'We use your data exclusively to provide services. We do NOT sell data to third parties.',
        },
        {
          title: 'Security',
          body: 'Password encryption with bcrypt, API keys with Fernet AES-128, transfer via HTTPS/TLS.',
        },
        {
          title: 'Your Rights (GDPR)',
          body: 'You have the right to access, correct, delete and port your data.',
        },
        {
          title: 'Contact',
          body: 'support@aura-trading.app',
          isContact: true,
        },
      ]
    : [
        {
          title: 'Δεδομένα που Συλλέγουμε',
          body: 'Συλλέγουμε: email, κρυπτογραφημένο κωδικό, κρυπτογραφημένα API keys, ιστορικό συναλλαγών, push notification tokens. ΔΕΝ συλλέγουμε: αριθμούς καρτών, τραπεζικούς λογαριασμούς, διευθύνσεις κατοικίας.',
        },
        {
          title: 'Χρήση Δεδομένων',
          body: 'Χρησιμοποιούμε τα δεδομένα σας αποκλειστικά για παροχή υπηρεσιών. ΔΕΝ πωλούμε δεδομένα σε τρίτους.',
        },
        {
          title: 'Ασφάλεια',
          body: 'Κρυπτογράφηση κωδικών με bcrypt, API keys με Fernet AES-128, μεταφορά μέσω HTTPS/TLS.',
        },
        {
          title: 'Δικαιώματά Σας (GDPR)',
          body: 'Έχετε δικαίωμα πρόσβασης, διόρθωσης, διαγραφής και φορητότητας δεδομένων.',
        },
        {
          title: 'Επικοινωνία',
          body: 'support@aura-trading.app',
          isContact: true,
        },
      ];

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.date}>{updatedAt}</Text>

        {sections.map((section, idx) => (
          <View key={section.title}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            {section.isContact ? (
              <TouchableOpacity onPress={() => Linking.openURL('mailto:support@aura-trading.app')}>
                <Text style={styles.email}>{section.body}</Text>
              </TouchableOpacity>
            ) : (
              <Text style={styles.body}>{section.body}</Text>
            )}
            {idx < sections.length - 1 && <View style={styles.divider} />}
          </View>
        ))}
      </ScrollView>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: 20,
    paddingBottom: 36,
  },
  title: {
    fontSize: theme.typography.sizes['2xl'],
    fontFamily: theme.typography.fontFamily.bold,
    color: theme.colors.text.primary,
    marginBottom: 8,
  },
  date: {
    fontSize: 13,
    fontFamily: theme.typography.fontFamily.regular,
    color: theme.colors.text.secondary,
    marginBottom: 6,
  },
  sectionTitle: {
    fontSize: 16,
    fontFamily: theme.typography.fontFamily.bold,
    color: theme.colors.text.primary,
    marginTop: 20,
  },
  body: {
    fontSize: 14,
    fontFamily: theme.typography.fontFamily.regular,
    color: theme.colors.text.secondary,
    lineHeight: 22,
    marginTop: 8,
  },
  divider: {
    height: 1,
    backgroundColor: theme.colors.ui.border,
    marginTop: 16,
  },
  email: {
    fontSize: 14,
    lineHeight: 22,
    marginTop: 8,
    color: theme.colors.brand.primary,
    fontFamily: theme.typography.fontFamily.medium,
  },
});
