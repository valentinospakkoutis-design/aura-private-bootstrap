import React, { useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { type ModalState, type ToastState, useAppStore } from '../stores/appStore';
import { Toast } from './Toast';
import { Modal } from './Modal';

interface GlobalProviderProps {
  children: React.ReactNode;
}

// Stable Toast wrapper — prevents re-renders from affecting sibling TextInputs
const StableToast = React.memo(({ toast, onHide }: { toast: ToastState | null; onHide: () => void }) => {
  if (!toast) return null;
  return (
    <Toast
      message={toast.message}
      type={toast.type}
      onHide={onHide}
    />
  );
});

// Stable Modal wrapper
const StableModal = React.memo(({ modal, onHide }: { modal: ModalState | null; onHide: () => void }) => {
  if (!modal) return null;
  return (
    <Modal
      visible={modal.visible}
      title={modal.title}
      message={modal.message}
      onClose={onHide}
      onConfirm={modal.onConfirm}
    />
  );
});

export const GlobalProvider: React.FC<GlobalProviderProps> = ({ children }) => {
  const toast = useAppStore((s) => s.toast);
  const hideToast = useAppStore((s) => s.hideToast);
  const modal = useAppStore((s) => s.modal);
  const hideModal = useAppStore((s) => s.hideModal);

  const stableHideToast = useCallback(() => hideToast(), [hideToast]);
  const stableHideModal = useCallback(() => hideModal(), [hideModal]);

  return (
    <View style={styles.container}>
      {children}
      <StableToast toast={toast} onHide={stableHideToast} />
      <StableModal modal={modal} onHide={stableHideModal} />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
