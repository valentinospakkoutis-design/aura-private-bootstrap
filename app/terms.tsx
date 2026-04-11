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

export default function TermsScreen() {
  const { language } = useLanguage();
  const isEn = language === 'en';

  const title = isEn ? 'Terms of Service' : 'Όροι Χρήσης';
  const updatedAt = isEn ? 'Last updated: April 2026' : 'Τελευταία ενημέρωση: Απρίλιος 2026';

  const sections: Section[] = isEn
    ? [
        {
          title: 'Acceptance of Terms',
          body: 'By using AURA Trading Assistant, you fully accept these Terms of Service.',
        },
        {
          title: 'NOT INVESTMENT ADVICE',
          body: 'AURA is a technology tool for market analysis. It does not constitute investment advice and is not a licensed investment firm. Predictions are based on algorithmic models with no guarantee of accuracy or returns.',
        },
        {
          title: 'Risk Warning',
          body: 'Cryptocurrency investments carry high risk. You may lose some or all of your invested capital. Auto Trading places real orders with real money when enabled.',
        },
        {
          title: 'Limitation of Liability',
          body: 'To the maximum extent permitted by law, we disclaim all liability for damages from use of the app, incorrect predictions, technical failures or third-party service failures (Binance, Bybit).',
        },
        {
          title: 'User Obligations',
          body: 'You are solely responsible for safeguarding credentials and API keys, complying with applicable laws, and paying taxes on gains.',
        },
        {
          title: 'Governing Law',
          body: 'These Terms are governed by the laws of the Republic of Cyprus. Jurisdiction: Limassol, Cyprus.',
        },
        {
          title: 'Contact',
          body: 'support@aura-trading.app',
          isContact: true,
        },
      ]
    : [
        {
          title: 'Αποδοχή Όρων',
          body: 'Χρησιμοποιώντας την εφαρμογή AURA Trading Assistant, αποδέχεστε πλήρως τους παρόντες Όρους Χρήσης.',
        },
        {
          title: 'ΔΕΝ ΑΠΟΤΕΛΕΙ ΕΠΕΝΔΥΤΙΚΗ ΣΥΜΒΟΥΛΗ',
          body: 'Η εφαρμογή AURA παρέχει αποκλειστικά εργαλεία τεχνολογικής ανάλυσης. Δεν αποτελεί επενδυτική υπηρεσία και δεν παρέχει επενδυτικές συμβουλές. Οι προβλέψεις βασίζονται σε αλγοριθμικά μοντέλα που δεν εγγυώνται ακρίβεια ή αποδόσεις.',
        },
        {
          title: 'Κίνδυνοι',
          body: 'Οι επενδύσεις σε κρυπτονομίσματα ενέχουν υψηλό κίνδυνο. Ενδέχεται να χάσετε μέρος ή το σύνολο των επενδυμένων κεφαλαίων σας. Το Auto Trading εκτελεί πραγματικές εντολές με πραγματικά χρήματα όταν ενεργοποιηθεί.',
        },
        {
          title: 'Αποποίηση Ευθύνης',
          body: 'Στο μέγιστο βαθμό που επιτρέπεται από το εφαρμοστέο δίκαιο, αποποιόμαστε κάθε ευθύνης για ζημίες από χρήση της εφαρμογής, λανθασμένες προβλέψεις, τεχνικές βλάβες ή αστοχία τρίτων υπηρεσιών (Binance, Bybit κτλ).',
        },
        {
          title: 'Υποχρεώσεις Χρήστη',
          body: 'Ο χρήστης φέρει αποκλειστική ευθύνη για τη διαφύλαξη κωδικών και API keys, τη συμμόρφωση με την ισχύουσα νομοθεσία και την καταβολή φόρων επί κερδών.',
        },
        {
          title: 'Εφαρμοστέο Δίκαιο',
          body: 'Οι παρόντες Όροι διέπονται από το δίκαιο της Κυπριακής Δημοκρατίας. Αρμόδια δικαστήρια: Λεμεσός, Κύπρος.',
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
