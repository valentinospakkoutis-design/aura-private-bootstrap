import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { theme } from '../mobile/src/constants/theme';

export default function ChangePasswordScreen() {
  const router = useRouter();
  const { user, setUser, showToast } = useAppStore();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async () => {
    if (!currentPassword.trim()) {
      showToast('Συμπλήρωσε τον τρέχοντα κωδικό', 'error');
      return;
    }
    if (newPassword.length < 8) {
      showToast('Ο νέος κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες', 'error');
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast('Οι κωδικοί δεν ταιριάζουν', 'error');
      return;
    }

    setLoading(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      // Re-login with new password to get a fresh token
      const updatedUser = await api.login(user?.email || '', newPassword);
      setUser(updatedUser as any);
      showToast('Ο κωδικός άλλαξε επιτυχώς', 'success');
      router.back();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Αποτυχία αλλαγής κωδικού';
      showToast(typeof msg === 'string' ? msg : msg.message || 'Αποτυχία', 'error');
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
        <Text style={styles.title}>Αλλαγή Κωδικού</Text>
        <Text style={styles.subtitle}>Εισήγαγε τον τρέχοντα και τον νέο κωδικό</Text>

        <View style={styles.form}>
          <Text style={styles.label}>Τρέχων κωδικός</Text>
          <TextInput
            style={styles.input}
            placeholder="Τρέχων κωδικός"
            placeholderTextColor={theme.colors.text.secondary}
            value={currentPassword}
            onChangeText={setCurrentPassword}
            secureTextEntry
          />

          <Text style={styles.label}>Νέος κωδικός</Text>
          <TextInput
            style={styles.input}
            placeholder="Τουλάχιστον 8 χαρακτήρες"
            placeholderTextColor={theme.colors.text.secondary}
            value={newPassword}
            onChangeText={setNewPassword}
            secureTextEntry
          />

          <Text style={styles.label}>Επιβεβαίωση νέου κωδικού</Text>
          <TextInput
            style={styles.input}
            placeholder="Επανάλαβε τον νέο κωδικό"
            placeholderTextColor={theme.colors.text.secondary}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry
          />

          <AnimatedButton
            title={loading ? 'Αποθήκευση...' : 'Αποθήκευση'}
            onPress={handleChangePassword}
            variant="primary"
            size="large"
            fullWidth
            disabled={loading}
          />
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
    padding: theme.spacing.xl,
    paddingTop: theme.spacing.xl * 2,
  },
  title: {
    fontSize: theme.typography.sizes['2xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.secondary,
    marginBottom: theme.spacing.xl,
  },
  form: {
    gap: theme.spacing.sm,
  },
  label: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginTop: theme.spacing.sm,
  },
  input: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
  },
});

