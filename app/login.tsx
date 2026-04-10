import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, KeyboardAvoidingView, Platform, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { theme } from '../mobile/src/constants/theme';

export default function LoginScreen() {
  const router = useRouter();
  const { setUser, showToast } = useAppStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      showToast('Συμπλήρωσε email και κωδικό', 'error');
      return;
    }

    setLoading(true);
    try {
      const user = await api.login(email.trim().toLowerCase(), password);
      console.log('[Login] Success, user:', user?.email);
      console.log('[Login] Token saved:', typeof localStorage !== 'undefined' ? (localStorage.getItem('auth_token') ? 'yes' : 'no') : 'N/A (mobile)');
      setUser(user as any);
      router.replace('/(tabs)');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Λάθος email ή κωδικός';
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
      <View style={styles.content}>
        <Text style={styles.logo}>AURA</Text>
        <Text style={styles.subtitle}>AI Trading Assistant</Text>

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
            placeholder="Κωδικός"
            placeholderTextColor={theme.colors.text.secondary}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          <AnimatedButton
            title={loading ? 'Σύνδεση...' : 'Σύνδεση'}
            onPress={handleLogin}
            variant="primary"
            size="large"
            fullWidth
            disabled={loading}
          />

          <TouchableOpacity onPress={() => router.push('/register')} style={styles.linkContainer}>
            <Text style={styles.linkText}>Δεν έχεις λογαριασμό; </Text>
            <Text style={styles.linkTextBold}>Δημιουργία λογαριασμού</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    flex: 1,
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
