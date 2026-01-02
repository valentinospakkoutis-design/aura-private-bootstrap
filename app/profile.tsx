import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, Image, TouchableOpacity, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppStore } from '../mobile/src/stores/appStore';
import { useApi } from '../mobile/src/hooks/useApi';
import { api } from '../mobile/src/services/apiClient';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { Button } from '../mobile/src/components/Button';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';
import { Validator } from '../mobile/src/utils/Validator';
import * as ImagePicker from 'expo-image-picker';
import * as Haptics from 'expo-haptics';

interface ProfileData {
  name: string;
  email: string;
  phone: string;
  avatar?: string;
}

interface PasswordData {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export default function ProfileScreen() {
  const router = useRouter();
  const { user, setUser, showToast } = useAppStore();
  
  const [profile, setProfile] = useState<ProfileData>({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    avatar: user?.avatar,
  });

  const [password, setPassword] = useState<PasswordData>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [hasChanges, setHasChanges] = useState(false);

  const {
    loading: updatingProfile,
    execute: updateProfile,
  } = useApi(api.updateProfile, { showLoading: false });

  const {
    loading: updatingPassword,
    execute: updatePassword,
  } = useApi((data: { currentPassword: string; newPassword: string }) => 
    api.updatePassword(data.currentPassword, data.newPassword), 
    { showLoading: false }
  );

  useEffect(() => {
    const changed = 
      profile.name !== user?.name ||
      profile.email !== user?.email ||
      profile.phone !== user?.phone ||
      profile.avatar !== user?.avatar;
    setHasChanges(changed);
  }, [profile, user]);

  const validateProfile = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (Validator.isEmpty(profile.name)) {
      newErrors.name = 'Το όνομα είναι υποχρεωτικό';
    }

    if (!Validator.isValidEmail(profile.email)) {
      newErrors.email = 'Μη έγκυρο email';
    }

    if (profile.phone && !Validator.isValidPhone(profile.phone)) {
      newErrors.phone = 'Μη έγκυρος αριθμός τηλεφώνου';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validatePassword = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (Validator.isEmpty(password.currentPassword)) {
      newErrors.currentPassword = 'Εισάγετε το τρέχον password';
    }

    if (!Validator.isValidPassword(password.newPassword)) {
      newErrors.newPassword = 'Το password πρέπει να έχει τουλάχιστον 8 χαρακτήρες, 1 κεφαλαίο, 1 πεζό και 1 αριθμό';
    }

    if (password.newPassword !== password.confirmPassword) {
      newErrors.confirmPassword = 'Τα passwords δεν ταιριάζουν';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handlePickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    
    if (status !== 'granted') {
      showToast('Χρειαζόμαστε άδεια για πρόσβαση στις φωτογραφίες', 'error');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      setProfile({ ...profile, avatar: result.assets[0].uri });
      setHasChanges(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  };

  const handleSaveProfile = async () => {
    if (!validateProfile()) {
      showToast('Παρακαλώ διορθώστε τα σφάλματα', 'error');
      return;
    }

    try {
      await updateProfile(profile);
      setUser({ ...user, ...profile });
      showToast('Το προφίλ ενημερώθηκε επιτυχώς!', 'success');
      setHasChanges(false);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (err) {
      showToast('Αποτυχία ενημέρωσης προφίλ', 'error');
    }
  };

  const handleChangePassword = async () => {
    if (!validatePassword()) {
      showToast('Παρακαλώ διορθώστε τα σφάλματα', 'error');
      return;
    }

    try {
      await updatePassword({
        currentPassword: password.currentPassword,
        newPassword: password.newPassword,
      });
      showToast('Το password άλλαξε επιτυχώς!', 'success');
      setPassword({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (err) {
      showToast('Αποτυχία αλλαγής password', 'error');
    }
  };

  const handleCancel = () => {
    if (hasChanges) {
      Alert.alert(
        'Ακύρωση Αλλαγών',
        'Έχεις μη αποθηκευμένες αλλαγές. Θέλεις να τις απορρίψεις;',
        [
          { text: 'Συνέχεια Επεξεργασίας', style: 'cancel' },
          {
            text: 'Απόρριψη',
            style: 'destructive',
            onPress: () => {
              setProfile({
                name: user?.name || '',
                email: user?.email || '',
                phone: user?.phone || '',
                avatar: user?.avatar,
              });
              setHasChanges(false);
              router.back();
            },
          },
        ]
      );
    } else {
      router.back();
    }
  };

  return (
    <PageTransition type="fade">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Profile Picture */}
        <AnimatedCard delay={0} animationType="scale">
          <View style={styles.avatarContainer}>
            <TouchableOpacity onPress={handlePickImage} activeOpacity={0.7}>
              {profile.avatar ? (
                <Image source={{ uri: profile.avatar }} style={styles.avatar} />
              ) : (
                <View style={styles.avatarPlaceholder}>
                  <Text style={styles.avatarPlaceholderText}>
                    {profile.name.charAt(0).toUpperCase() || '?'}
                  </Text>
                </View>
              )}
              <View style={styles.avatarEditBadge}>
                <Text style={styles.avatarEditIcon}>📷</Text>
              </View>
            </TouchableOpacity>
            <Text style={styles.avatarHint}>Πάτησε για αλλαγή φωτογραφίας</Text>
          </View>
        </AnimatedCard>

        {/* Profile Information */}
        <AnimatedCard delay={100} animationType="slideUp">
          <Text style={styles.sectionTitle}>Προσωπικές Πληροφορίες</Text>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Όνομα *</Text>
            <TextInput
              style={[styles.input, errors.name && styles.inputError]}
              value={profile.name}
              onChangeText={(text) => {
                setProfile({ ...profile, name: text });
                if (errors.name) setErrors({ ...errors, name: '' });
              }}
              placeholder="Το όνομά σου"
              placeholderTextColor={theme.colors.text.secondary}
            />
            {errors.name && <Text style={styles.errorText}>{errors.name}</Text>}
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Email *</Text>
            <TextInput
              style={[styles.input, errors.email && styles.inputError]}
              value={profile.email}
              onChangeText={(text) => {
                setProfile({ ...profile, email: text });
                if (errors.email) setErrors({ ...errors, email: '' });
              }}
              placeholder="email@example.com"
              placeholderTextColor={theme.colors.text.secondary}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            {errors.email && <Text style={styles.errorText}>{errors.email}</Text>}
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Τηλέφωνο</Text>
            <TextInput
              style={[styles.input, errors.phone && styles.inputError]}
              value={profile.phone}
              onChangeText={(text) => {
                setProfile({ ...profile, phone: text });
                if (errors.phone) setErrors({ ...errors, phone: '' });
              }}
              placeholder="+357 99 123456"
              placeholderTextColor={theme.colors.text.secondary}
              keyboardType="phone-pad"
            />
            {errors.phone && <Text style={styles.errorText}>{errors.phone}</Text>}
          </View>

          <View style={styles.buttonRow}>
            <Button
              title="Ακύρωση"
              onPress={handleCancel}
              variant="secondary"
              size="medium"
              style={styles.button}
            />
            <Button
              title="Αποθήκευση"
              onPress={handleSaveProfile}
              variant="primary"
              size="medium"
              loading={updatingProfile}
              disabled={!hasChanges}
              style={styles.button}
            />
          </View>
        </AnimatedCard>

        {/* Change Password */}
        <AnimatedCard delay={200} animationType="slideUp">
          <Text style={styles.sectionTitle}>Αλλαγή Password</Text>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Τρέχον Password *</Text>
            <TextInput
              style={[styles.input, errors.currentPassword && styles.inputError]}
              value={password.currentPassword}
              onChangeText={(text) => {
                setPassword({ ...password, currentPassword: text });
                if (errors.currentPassword) setErrors({ ...errors, currentPassword: '' });
              }}
              placeholder="••••••••"
              placeholderTextColor={theme.colors.text.secondary}
              secureTextEntry
            />
            {errors.currentPassword && <Text style={styles.errorText}>{errors.currentPassword}</Text>}
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Νέο Password *</Text>
            <TextInput
              style={[styles.input, errors.newPassword && styles.inputError]}
              value={password.newPassword}
              onChangeText={(text) => {
                setPassword({ ...password, newPassword: text });
                if (errors.newPassword) setErrors({ ...errors, newPassword: '' });
              }}
              placeholder="••••••••"
              placeholderTextColor={theme.colors.text.secondary}
              secureTextEntry
            />
            {errors.newPassword && <Text style={styles.errorText}>{errors.newPassword}</Text>}
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Επιβεβαίωση Password *</Text>
            <TextInput
              style={[styles.input, errors.confirmPassword && styles.inputError]}
              value={password.confirmPassword}
              onChangeText={(text) => {
                setPassword({ ...password, confirmPassword: text });
                if (errors.confirmPassword) setErrors({ ...errors, confirmPassword: '' });
              }}
              placeholder="••••••••"
              placeholderTextColor={theme.colors.text.secondary}
              secureTextEntry
            />
            {errors.confirmPassword && <Text style={styles.errorText}>{errors.confirmPassword}</Text>}
          </View>

          <Button
            title="Αλλαγή Password"
            onPress={handleChangePassword}
            variant="primary"
            size="medium"
            loading={updatingPassword}
            fullWidth
          />
        </AnimatedCard>

        <View style={styles.bottomPadding} />
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
    padding: theme.spacing.md,
    paddingBottom: theme.spacing.xl * 2,
  },
  avatarContainer: {
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  avatar: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: theme.colors.ui.border,
  },
  avatarPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: theme.colors.brand.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarPlaceholderText: {
    fontSize: 48,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  avatarEditBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: theme.colors.brand.primary,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: theme.colors.ui.background,
  },
  avatarEditIcon: {
    fontSize: 16,
  },
  avatarHint: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    marginTop: theme.spacing.sm,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.lg,
  },
  inputGroup: {
    marginBottom: theme.spacing.md,
  },
  inputLabel: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '600',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  input: {
    backgroundColor: theme.colors.ui.background,
    borderWidth: 1,
    borderColor: theme.colors.ui.border,
    borderRadius: theme.borderRadius.medium,
    padding: theme.spacing.md,
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
  },
  inputError: {
    borderColor: theme.colors.semantic.error,
  },
  errorText: {
    fontSize: theme.typography.sizes.xs,
    color: theme.colors.semantic.error,
    marginTop: theme.spacing.xs,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginTop: theme.spacing.md,
  },
  button: {
    flex: 1,
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
});

