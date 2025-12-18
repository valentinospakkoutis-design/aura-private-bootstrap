// Validation Utilities
// Comprehensive form validation functions

/**
 * Validates email format
 */
export function validateEmail(email) {
  if (!email || typeof email !== 'string') {
    return { valid: false, message: 'Το email είναι υποχρεωτικό' };
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { valid: false, message: 'Μη έγκυρη διεύθυνση email' };
  }
  
  return { valid: true };
}

/**
 * Validates password strength
 */
export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return { valid: false, message: 'Το password είναι υποχρεωτικό' };
  }
  
  if (password.length < 8) {
    return { valid: false, message: 'Τουλάχιστον 8 χαρακτήρες' };
  }
  
  if (!/[A-Z]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 κεφαλαίο γράμμα' };
  }
  
  if (!/[a-z]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 πεζό γράμμα' };
  }
  
  if (!/[0-9]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 αριθμό' };
  }
  
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 ειδικό χαρακτήρα' };
  }
  
  return { valid: true, message: 'Ισχυρό password' };
}

/**
 * Validates API key format
 */
export function validateApiKey(apiKey) {
  if (!apiKey || typeof apiKey !== 'string') {
    return { valid: false, message: 'Μη έγκυρο API key' };
  }
  
  if (apiKey.length < 20) {
    return { valid: false, message: 'Το API key πρέπει να είναι τουλάχιστον 20 χαρακτήρες' };
  }
  
  if (apiKey.length > 200) {
    return { valid: false, message: 'Το API key είναι πολύ μεγάλο' };
  }
  
  // Check for valid characters (alphanumeric, dashes, underscores)
  if (!/^[a-zA-Z0-9_-]+$/.test(apiKey)) {
    return { valid: false, message: 'Το API key περιέχει μη έγκυρους χαρακτήρες' };
  }
  
  return { valid: true };
}

/**
 * Validates trading quantity
 */
export function validateQuantity(quantity, minQuantity = 0.0001, maxQuantity = 1000000) {
  if (!quantity || quantity === '') {
    return { valid: false, message: 'Η ποσότητα είναι υποχρεωτική' };
  }
  
  const num = parseFloat(quantity);
  
  if (isNaN(num)) {
    return { valid: false, message: 'Η ποσότητα πρέπει να είναι αριθμός' };
  }
  
  if (num <= 0) {
    return { valid: false, message: 'Η ποσότητα πρέπει να είναι μεγαλύτερη από 0' };
  }
  
  if (num < minQuantity) {
    return { valid: false, message: `Η ελάχιστη ποσότητα είναι ${minQuantity}` };
  }
  
  if (num > maxQuantity) {
    return { valid: false, message: `Η μέγιστη ποσότητα είναι ${maxQuantity}` };
  }
  
  return { valid: true };
}

/**
 * Validates price
 */
export function validatePrice(price, minPrice = 0.0001) {
  if (!price || price === '') {
    return { valid: false, message: 'Η τιμή είναι υποχρεωτική' };
  }
  
  const num = parseFloat(price);
  
  if (isNaN(num)) {
    return { valid: false, message: 'Η τιμή πρέπει να είναι αριθμός' };
  }
  
  if (num <= 0) {
    return { valid: false, message: 'Η τιμή πρέπει να είναι μεγαλύτερη από 0' };
  }
  
  if (num < minPrice) {
    return { valid: false, message: `Η ελάχιστη τιμή είναι ${minPrice}` };
  }
  
  return { valid: true };
}

/**
 * Validates percentage (0-100)
 */
export function validatePercentage(percentage) {
  if (percentage === '' || percentage === null || percentage === undefined) {
    return { valid: false, message: 'Το ποσοστό είναι υποχρεωτικό' };
  }
  
  const num = parseFloat(percentage);
  
  if (isNaN(num)) {
    return { valid: false, message: 'Το ποσοστό πρέπει να είναι αριθμός' };
  }
  
  if (num < 0 || num > 100) {
    return { valid: false, message: 'Το ποσοστό πρέπει να είναι μεταξύ 0 και 100' };
  }
  
  return { valid: true };
}

/**
 * Validates symbol/ticker format
 */
export function validateSymbol(symbol) {
  if (!symbol || typeof symbol !== 'string') {
    return { valid: false, message: 'Το σύμβολο είναι υποχρεωτικό' };
  }
  
  if (symbol.length < 2 || symbol.length > 20) {
    return { valid: false, message: 'Το σύμβολο πρέπει να είναι 2-20 χαρακτήρες' };
  }
  
  // Allow alphanumeric and common trading symbols
  if (!/^[A-Z0-9]+$/.test(symbol.toUpperCase())) {
    return { valid: false, message: 'Το σύμβολο περιέχει μη έγκυρους χαρακτήρες' };
  }
  
  return { valid: true };
}

/**
 * Validates date range
 */
export function validateDateRange(startDate, endDate) {
  if (!startDate || !endDate) {
    return { valid: false, message: 'Οι ημερομηνίες είναι υποχρεωτικές' };
  }
  
  const start = new Date(startDate);
  const end = new Date(endDate);
  
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return { valid: false, message: 'Μη έγκυρες ημερομηνίες' };
  }
  
  if (start > end) {
    return { valid: false, message: 'Η αρχική ημερομηνία πρέπει να είναι πριν την τελική' };
  }
  
  return { valid: true };
}

/**
 * Validates required field
 */
export function validateRequired(value, fieldName = 'Το πεδίο') {
  if (value === null || value === undefined || value === '') {
    return { valid: false, message: `${fieldName} είναι υποχρεωτικό` };
  }
  
  if (typeof value === 'string' && value.trim() === '') {
    return { valid: false, message: `${fieldName} είναι υποχρεωτικό` };
  }
  
  return { valid: true };
}

/**
 * Validates number range
 */
export function validateNumberRange(value, min, max, fieldName = 'Η τιμή') {
  const num = parseFloat(value);
  
  if (isNaN(num)) {
    return { valid: false, message: `${fieldName} πρέπει να είναι αριθμός` };
  }
  
  if (num < min || num > max) {
    return { valid: false, message: `${fieldName} πρέπει να είναι μεταξύ ${min} και ${max}` };
  }
  
  return { valid: true };
}

/**
 * Validates multiple fields at once
 */
export function validateForm(fields) {
  const errors = {};
  let isValid = true;
  
  for (const [fieldName, value] of Object.entries(fields)) {
    const result = validateRequired(value, fieldName);
    if (!result.valid) {
      errors[fieldName] = result.message;
      isValid = false;
    }
  }
  
  return {
    valid: isValid,
    errors
  };
}

