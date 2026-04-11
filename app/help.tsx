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

export default function HelpScreen() {
  const { language } = useLanguage();
  const isEn = language === 'en';

  const title = isEn ? 'Help & Support' : 'Βοήθεια & Support';
  const updatedAt = isEn ? 'Last updated: April 2026' : 'Τελευταία ενημέρωση: Απρίλιος 2026';

  const sections: Section[] = isEn
    ? [
        {
          title: 'What is AURA?',
          body: 'AI-powered app for market analysis and trading automation using XGBoost and RandomForest models for 49+ assets.',
        },
        {
          title: 'Getting Started',
          body: '1. Create account\n2. Connect broker via API keys\n3. Start with Paper Trading\n4. Study AI Predictions\n5. Enable Live Trading when ready',
        },
        {
          title: 'Paper Trading',
          body: 'Simulated trading with $10,000 virtual balance. Test strategies risk-free.',
        },
        {
          title: 'Live Trading',
          body: 'WARNING: Uses real money.\nNEVER grant Withdrawal permissions on API keys.',
        },
        {
          title: 'Auto Trading',
          body: 'Automatic order execution when AI confidence > 90%. Modes: SAFE / BALANCED / AGGRESSIVE',
        },
        {
          title: 'FAQ',
          body: 'Q: Are my API keys safe?\nA: Yes, stored encrypted.\n\nQ: Do you guarantee profits?\nA: NO. You may lose money.\n\nQ: What if the app closes during a trade?\nA: Orders execute on the server.',
        },
        {
          title: 'Contact',
          body: 'Email: support@aura-trading.app\nMonday-Friday, 09:00-18:00 EET',
          isContact: true,
        },
      ]
    : [
        {
          title: 'Τι είναι το AURA;',
          body: 'Εφαρμογή τεχνητής νοημοσύνης για ανάλυση αγορών και αυτοματισμό συναλλαγών με XGBoost και RandomForest μοντέλα για 49+ assets.',
        },
        {
          title: 'Πώς να Ξεκινήσετε',
          body: '1. Δημιουργήστε λογαριασμό\n2. Συνδέστε broker μέσω API keys\n3. Ξεκινήστε με Paper Trading\n4. Μελετήστε τις AI Predictions\n5. Ενεργοποιήστε Live Trading όταν είστε έτοιμοι',
        },
        {
          title: 'Paper Trading',
          body: 'Εικονικό trading με $10,000 εικονικό υπόλοιπο. Δοκιμάστε στρατηγικές χωρίς κίνδυνο.',
        },
        {
          title: 'Live Trading',
          body: 'ΠΡΟΣΟΧΗ: Χρησιμοποιεί πραγματικά χρήματα.\nΜΗΝ δίνετε δικαίωμα Αναλήψεων στα API keys.',
        },
        {
          title: 'Auto Trading',
          body: 'Αυτόματη εκτέλεση εντολών όταν AI confidence > 90%. Modes: SAFE / BALANCED / AGGRESSIVE',
        },
        {
          title: 'FAQ',
          body: 'Ερ: Είναι ασφαλή τα API keys μου;\nΑπ: Ναι, αποθηκεύονται κρυπτογραφημένα.\n\nΕρ: Εγγυάστε κέρδη;\nΑπ: ΟΧΙ. Μπορείτε να χάσετε χρήματα.\n\nΕρ: Τι γίνεται αν κλείσει η εφαρμογή;\nΑπ: Οι εντολές εκτελούνται στον server.',
        },
        {
          title: 'Επικοινωνία',
          body: 'Email: support@aura-trading.app\nΔευτέρα-Παρασκευή, 09:00-18:00 EET',
          isContact: true,
        },
      ];

  const renderContact = (value: string) => {
    const prefix = value.split('support@aura-trading.app')[0] ?? '';
    const suffix = value.split('support@aura-trading.app')[1] ?? '';

    return (
      <Text style={styles.body}>
        {prefix}
        <Text style={styles.email} onPress={() => Linking.openURL('mailto:support@aura-trading.app')}>
          support@aura-trading.app
        </Text>
        {suffix}
      </Text>
    );
  };

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.date}>{updatedAt}</Text>

        {sections.map((section, idx) => (
          <View key={section.title}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            {section.isContact ? renderContact(section.body) : <Text style={styles.body}>{section.body}</Text>}
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
    color: theme.colors.brand.primary,
    fontFamily: theme.typography.fontFamily.medium,
  },
});
