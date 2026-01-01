import React, { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { useAppStore } from '@/stores/appStore';
import { Toast } from './Toast';
import { Modal } from './Modal';

interface GlobalProviderProps {
  children: React.ReactNode;
}

export const GlobalProvider: React.FC<GlobalProviderProps> = ({ children }) => {
  const { toast, hideToast, modal, hideModal } = useAppStore();

  return (
    <View style={styles.container}>
      {children}
      
      {/* Global Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onHide={hideToast}
        />
      )}

      {/* Global Modal */}
      {modal && (
        <Modal
          visible={modal.visible}
          title={modal.title}
          message={modal.message}
          onClose={hideModal}
          onConfirm={modal.onConfirm}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});

