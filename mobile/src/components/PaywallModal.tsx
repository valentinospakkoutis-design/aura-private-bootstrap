import React from 'react';

import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Modal } from './Modal';
import { Button } from './Button';
import { theme } from '../constants/theme';
import { useLanguage } from '../hooks/useLanguage';

interface PaywallModalProps {
  visible: boolean;
  requiredTier: 'pro' | 'elite';
  feature?: string;
  onClose: () => void;
}

export function PaywallModal({ visible, requiredTier, feature, onClose }: PaywallModalProps) {
  const router = useRouter();
  const { t } = useLanguage();

  const featureLabel = feature ? t(feature) : t('premiumFeature');

  return (
    <Modal visible={visible} title={t('paywallTitle')} type="warning" onClose={onClose} cancelText={t('maybeLater')}>
      <View style={styles.content}>
        <Text style={styles.message}>
          {t('paywallMessage', { feature: featureLabel, tier: requiredTier.toUpperCase() })}
        </Text>

        <Button
          title={t('viewPlans')}
          fullWidth
          onPress={() => {
            onClose();
            router.push({ pathname: '/subscription' } as any);
          }}
        />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  content: {
    width: '100%',
    gap: theme.spacing.md,
  },
  message: {
    fontSize: theme.typography.sizes.md,
    lineHeight: 22,
    color: theme.colors.text.secondary,
    textAlign: 'center',
  },
});
