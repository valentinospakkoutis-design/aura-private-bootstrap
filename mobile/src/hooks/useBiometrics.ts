import { useState, useEffect } from 'react';
import { biometricService } from '../services/BiometricService';
import { useAppStore } from '../stores/appStore';
import { logger } from '../utils/Logger';

export function useBiometrics() {
  const [isAvailable, setIsAvailable] = useState(false);
  const [isEnabled, setIsEnabled] = useState(false);
  const [biometricType, setBiometricType] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const { showToast } = useAppStore();

  useEffect(() => {
    checkAvailability();
  }, []);

  const checkAvailability = async () => {
    const available = await biometricService.isAvailable();
    setIsAvailable(available);

    if (available) {
      const type = await biometricService.getBiometricTypeName();
      setBiometricType(type);

      const enabled = await biometricService.isEnabled();
      setIsEnabled(enabled);
    }
  };

  const authenticate = async (reason?: string): Promise<boolean> => {
    setLoading(true);
    try {
      const result = await biometricService.authenticate(reason);
      
      if (result.success) {
        showToast('Authentication successful', 'success');
        return true;
      } else {
        showToast(result.error || 'Authentication failed', 'error');
        return false;
      }
    } catch (error) {
      logger.error('Authentication error:', error);
      showToast('Authentication error', 'error');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const enable = async (): Promise<boolean> => {
    setLoading(true);
    try {
      const success = await biometricService.enable();
      
      if (success) {
        setIsEnabled(true);
        showToast(`${biometricType} enabled`, 'success');
        return true;
      } else {
        showToast('Failed to enable biometrics', 'error');
        return false;
      }
    } catch (error) {
      logger.error('Enable biometrics error:', error);
      showToast('Failed to enable biometrics', 'error');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const disable = async () => {
    setLoading(true);
    try {
      await biometricService.disable();
      setIsEnabled(false);
      showToast(`${biometricType} disabled`, 'success');
    } catch (error) {
      logger.error('Disable biometrics error:', error);
      showToast('Failed to disable biometrics', 'error');
    } finally {
      setLoading(false);
    }
  };

  return {
    isAvailable,
    isEnabled,
    biometricType,
    loading,
    authenticate,
    enable,
    disable,
  };
}

