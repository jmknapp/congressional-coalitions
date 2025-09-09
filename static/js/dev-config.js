// Developer Mode Configuration
const DEV_MODE_CONFIG = {
    sessionTimeout: 24 * 60 * 60 * 1000, // 24 hours in milliseconds
    maxAttempts: 3 // Maximum failed attempts before temporary lockout
};

// Check if developer mode session is still valid
function isDeveloperModeSessionValid() {
    const devModeData = localStorage.getItem('developerMode');
    if (!devModeData) {
        return false;
    }
    
    try {
        const data = JSON.parse(devModeData);
        const now = Date.now();
        const sessionExpiry = data.sessionExpiry;
        
        // Check if session has expired
        if (now > sessionExpiry) {
            // Session expired, clear the data
            localStorage.removeItem('developerMode');
            return false;
        }
        
        return data.enabled === true;
    } catch (error) {
        // Invalid data format, clear it
        localStorage.removeItem('developerMode');
        return false;
    }
}

// Set developer mode with session expiry
function setDeveloperModeSession(enabled) {
    const now = Date.now();
    const sessionExpiry = now + DEV_MODE_CONFIG.sessionTimeout;
    
    const data = {
        enabled: enabled,
        sessionExpiry: sessionExpiry,
        timestamp: now
    };
    
    localStorage.setItem('developerMode', JSON.stringify(data));
}

// Clear developer mode session
function clearDeveloperModeSession() {
    localStorage.removeItem('developerMode');
}

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
    module.exports = { 
        DEV_MODE_CONFIG, 
        verifyDeveloperPassword, 
        isDeveloperModeSessionValid, 
        setDeveloperModeSession, 
        clearDeveloperModeSession 
    };
}
