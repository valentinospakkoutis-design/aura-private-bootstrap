// AURA Security Utilities - Test Suite
// Tests for encryption/decryption functions

import { encryptData, decryptData, storeApiKey, getApiKey, deleteApiKey } from '../security';

describe('Security Utilities', () => {
  describe('encryptData / decryptData', () => {
    it('should encrypt and decrypt simple data', async () => {
      const originalData = { apiKey: 'test-api-key-12345' };
      
      const encrypted = await encryptData(originalData);
      expect(encrypted).toBeDefined();
      expect(typeof encrypted).toBe('string');
      expect(encrypted).not.toBe(JSON.stringify(originalData));
      
      const decrypted = await decryptData(encrypted);
      expect(decrypted).toEqual(originalData);
    });

    it('should encrypt and decrypt complex data', async () => {
      const originalData = {
        apiKey: 'test-api-key-12345',
        apiSecret: 'test-secret-67890',
        broker: 'binance',
        testnet: true,
        timestamp: Date.now()
      };
      
      const encrypted = await encryptData(originalData);
      const decrypted = await decryptData(encrypted);
      
      expect(decrypted).toEqual(originalData);
    });

    it('should produce different encrypted output for same data (due to IV)', async () => {
      const originalData = { apiKey: 'test-key' };
      
      const encrypted1 = await encryptData(originalData);
      const encrypted2 = await encryptData(originalData);
      
      // Should be different due to random IV
      expect(encrypted1).not.toBe(encrypted2);
      
      // But both should decrypt to same data
      const decrypted1 = await decryptData(encrypted1);
      const decrypted2 = await decryptData(encrypted2);
      
      expect(decrypted1).toEqual(originalData);
      expect(decrypted2).toEqual(originalData);
    });

    it('should detect tampered data (HMAC verification)', async () => {
      const originalData = { apiKey: 'test-key' };
      const encrypted = await encryptData(originalData);
      
      // Tamper with encrypted data
      const tampered = Buffer.from(encrypted, 'base64').toString();
      const tamperedBase64 = Buffer.from(tampered + 'tampered').toString('base64');
      
      // Should fail to decrypt or return null
      const decrypted = await decryptData(tamperedBase64);
      expect(decrypted).not.toEqual(originalData);
    });
  });

  describe('storeApiKey / getApiKey', () => {
    const testService = 'test_broker';
    const testApiKey = 'test-api-key-1234567890';

    afterEach(async () => {
      // Cleanup
      await deleteApiKey(testService);
    });

    it('should store and retrieve API key', async () => {
      const stored = await storeApiKey(testService, testApiKey);
      expect(stored).toBe(true);
      
      const retrieved = await getApiKey(testService);
      expect(retrieved).toBe(testApiKey);
    });

    it('should return null for non-existent key', async () => {
      const retrieved = await getApiKey('non_existent_service');
      expect(retrieved).toBeNull();
    });

    it('should delete stored API key', async () => {
      await storeApiKey(testService, testApiKey);
      const deleted = await deleteApiKey(testService);
      expect(deleted).toBe(true);
      
      const retrieved = await getApiKey(testService);
      expect(retrieved).toBeNull();
    });
  });
});

