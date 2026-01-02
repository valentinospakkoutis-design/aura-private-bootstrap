import React from 'react';
import { View, Text, StyleSheet, Modal as RNModal, TouchableOpacity, Dimensions } from 'react-native';
import { BlurView } from 'expo-blur';
import { theme } from '../constants/theme';
import { Button } from './Button';

interface ModalProps {
  visible: boolean;
  title: string;
  message?: string;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  cancelText?: string;
  type?: 'info' | 'warning' | 'danger';
  children?: React.ReactNode;
}

const { width } = Dimensions.get('window');

export const Modal: React.FC<ModalProps> = ({
  visible,
  title,
  message,
  onClose,
  onConfirm,
  confirmText = 'Επιβεβαίωση',
  cancelText = 'Ακύρωση',
  type = 'info',
  children,
}) => {
  const getIconColor = () => {
    switch (type) {
      case 'warning':
        return theme.colors.semantic.warning;
      case 'danger':
        return theme.colors.semantic.error;
      default:
        return theme.colors.brand.primary;
    }
  };

  return (
    <RNModal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <BlurView intensity={20} style={styles.overlay}>
        <TouchableOpacity
          style={styles.backdrop}
          activeOpacity={1}
          onPress={onClose}
        />
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            {/* Icon */}
            <View style={[styles.iconContainer, { backgroundColor: getIconColor() + '20' }]}>
              <Text style={[styles.icon, { color: getIconColor() }]}>
                {type === 'danger' ? '⚠' : type === 'warning' ? '⚠' : 'ℹ'}
              </Text>
            </View>

            {/* Title */}
            <Text style={styles.title}>{title}</Text>

            {/* Message */}
            {message && <Text style={styles.message}>{message}</Text>}

            {/* Custom Content */}
            {children && <View style={styles.children}>{children}</View>}

            {/* Buttons */}
            <View style={styles.buttonContainer}>
              <Button
                title={cancelText}
                onPress={onClose}
                variant="ghost"
                size="medium"
                style={styles.button}
              />
              {onConfirm && (
                <Button
                  title={confirmText}
                  onPress={() => {
                    onConfirm();
                    onClose();
                  }}
                  variant={type === 'danger' ? 'danger' : 'primary'}
                  size="medium"
                  style={styles.button}
                />
              )}
            </View>
          </View>
        </View>
      </BlurView>
    </RNModal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  modalContainer: {
    width: width - theme.spacing.xl * 2,
    maxWidth: 400,
  },
  modalContent: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.xl,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 10,
  },
  iconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  icon: {
    fontSize: 32,
  },
  title: {
    fontSize: theme.typography.sizes.xl,
    fontFamily: theme.typography.fontFamily.primary,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.sm,
    textAlign: 'center',
  },
  message: {
    fontSize: theme.typography.sizes.md,
    fontFamily: theme.typography.fontFamily.primary,
    color: theme.colors.text.secondary,
    textAlign: 'center',
    marginBottom: theme.spacing.lg,
    lineHeight: 20,
  },
  children: {
    width: '100%',
    marginBottom: theme.spacing.lg,
  },
  buttonContainer: {
    flexDirection: 'row',
    width: '100%',
    gap: theme.spacing.md,
  },
  button: {
    flex: 1,
  },
});

