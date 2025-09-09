// Developer Mode Configuration
const DEV_MODE_CONFIG = {
    sessionTimeout: 24 * 60 * 60 * 1000, // 24 hours in milliseconds
    maxAttempts: 3 // Maximum failed attempts before temporary lockout
};

// Function to verify developer password with server
async function verifyDeveloperPassword(password) {
    try {
        const response = await fetch('/api/verify-dev-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ password: password })
        });
        
        const result = await response.json();
        return result.success;
    } catch (error) {
        console.error('Error verifying password:', error);
        return false;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DEV_MODE_CONFIG, verifyDeveloperPassword };
}
