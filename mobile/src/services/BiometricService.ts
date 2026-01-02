import * as LocalAuthentication from 'expo-local-authentication';
import { Platform } from 'react-native';
import { logger } from '../utils/Logger';
import { SecureStorage, STORAGE_KEYS } from '../utils/SecureStorage';

export class BiometricService {
  // Check if biometrics are available
  async isAvailable(): Promise<boolean> {
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      return hasHardware && isEnrolled;
    } catch (error) {
      logger.error('Failed to check biometric availability:', error);
      return false;
    }
  }

  // Get supported biometric types
  async getSupportedTypes(): Promise<LocalAuthentication.AuthenticationType[]> {
    try {
      return await LocalAuthentication.supportedAuthenticationTypesAsync();
    } catch (error) {
      logger.error('Failed to get supported biometric types:', error);
      return [];
    }
  }

  // Get biometric type name
  async getBiometricTypeName(): Promise<string> {
    const types = await this.getSupportedTypes();
    
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return Platform.OS === 'ios' ? 'Face ID' : 'Face Recognition';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return Platform.OS === 'ios' ? 'Touch ID' : 'Fingerprint';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      return 'Iris Recognition';
    }
    return 'Biometric Authentication';
  }

  // Authenticate with biometrics
  async authenticate(reason?: string): Promise<{ success: boolean; error?: string }> {
    try {
      const isAvailable = await this.isAvailable();
      
      if (!isAvailable) {
        return {
          success: false,
          error: 'Biometric authentication is not available on this device',
        };
      }

      const biometricName = await this.getBiometricTypeName();
      const promptMessage = reason || `Authenticate with ${biometricName}`;

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage,
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
        fallbackLabel: 'Use Passcode',
      });

      if (result.success) {
        logger.info('Biometric authentication successful');
        return { success: true };
      } else {
        logger.warn('Biometric authentication failed:', result.error);
        return {
          success: false,
          error: result.error || 'Authentication failed',
        };
      }
    } catch (error) {
      logger.error('Biometric authentication error:', error);
      return {
        success: false,
        error: 'An error occurred during authentication',
      };
    }
  }

  // Check if biometrics are enabled in app settings
  async isEnabled(): Promise<boolean> {
    const enabled = await SecureStorage.get(STORAGE_KEYS.BIOMETRICS_ENABLED);
    return enabled === 'true';
  }

  // Enable biometrics
  async enable(): Promise<boolean> {
    const isAvailable = await this.isAvailable();
    
    if (!isAvailable) {
      return false;
    }

    // Test authentication before enabling
    const result = await this.authenticate('Enable biometric authentication');
    
    if (result.success) {
      await SecureStorage.set(STORAGE_KEYS.BIOMETRICS_ENABLED, 'true');
      logger.info('Biometrics enabled');
      return true;
    }

    return false;
  }

  // Disable biometrics
  async disable(): Promise<void> {
    await SecureStorage.set(STORAGE_KEYS.BIOMETRICS_ENABLED, 'false');
    logger.info('Biometrics disabled');
  }
}

// Create singleton instance
export const biometricService = new BiometricService();

