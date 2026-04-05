import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, KeyboardAvoidingView, Platform, TouchableOpacity, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { theme } from '../mobile/src/constants/theme';

export default function RegisterScreen() {
  const router = useRouter();
  const { showToast } = useAppStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (!email.trim() || !password.trim()) {
      showToast('Συμπλήρωσε όλα τα πεδία', 'error');
      return;
    }
    if (password.length < 8) {
      showToast('Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες', 'error');
      return;
    }
    if (password !== confirmPassword) {
      showToast('Οι κωδικοί δεν ταιριάζουν', 'error');
      return;
    }

    setLoading(true);
    try {
      await api.register(email.trim().toLowerCase(), password);
      showToast('Επιτυχής εγγραφή! Μπορείς να συνδεθείς.', 'success');
      router.replace('/login');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.message || 'Αποτυχία εγγραφής';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.logo}>AURA</Text>
        <Text style={styles.subtitle}>Δημιουργία Λογαριασμού</Text>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor={theme.colors.text.secondary}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={styles.input}
            placeholder="Κωδικός (τουλάχιστον 8 χαρακτήρες)"
            placeholderTextColor={theme.colors.text.secondary}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          <TextInput
            style={styles.input}
            placeholder="Επιβεβαίωση κωδικού"
            placeholderTextColor={theme.colors.text.secondary}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry
          />
          <AnimatedButton
            title={loading ? 'Εγγραφή...' : 'Εγγραφή'}
            onPress={handleRegister}
            variant="primary"
            size="large"
            fullWidth
            disabled={loading}
          />

          <TouchableOpacity onPress={() => router.replace('/login')} style={styles.linkContainer}>
            <Text style={styles.linkText}>Έχεις ήδη λογαριασμό; </Text>
            <Text style={styles.linkTextBold}>Σύνδεση</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.xl,
  },
  logo: {
    fontSize: 48,
    fontWeight: '800',
    color: theme.colors.brand.primary,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontSize: theme.typography.sizes.lg,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xl * 2,
  },
  form: {
    width: '100%',
    gap: theme.spacing.md,
  },
  input: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.large,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
  },
  linkContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: theme.spacing.md,
  },
  linkText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  linkTextBold: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.brand.primary,
    fontWeight: '600',
  },
});
