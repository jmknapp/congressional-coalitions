// Developer Mode Configuration - Enhanced Security
const DEV_MODE_CONFIG = {
    sessionCheckInterval: 5 * 60 * 1000, // Check session every 5 minutes
    maxAttempts: 3 // Maximum failed attempts before temporary lockout
};

// Check if developer mode session is still valid (server-side)
async function isDeveloperModeSessionValid() {
    try {
        const response = await fetch('/api/dev-session-status', {
            method: 'GET',
            credentials: 'include' // Include cookies for session
        });
        
        if (response.ok) {
            const result = await response.json();
            return result.success && result.dev_mode === true;
        }
        
        return false;
    } catch (error) {
        console.error('Error checking dev session:', error);
        return false;
    }
}

// Set developer mode session (now handled server-side)
function setDeveloperModeSession(enabled) {
    // Session is now managed server-side, this is just for UI state
    if (enabled) {
        console.log('Developer mode enabled - session managed server-side');
    } else {
        console.log('Developer mode disabled - session managed server-side');
    }
}

// Clear developer mode session (server-side)
async function clearDeveloperModeSession() {
    try {
        const response = await fetch('/api/dev-logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Dev session cleared:', result.message);
        }
    } catch (error) {
        console.error('Error clearing dev session:', error);
    }
}

// Function to verify developer password with server (enhanced security)
async function verifyDeveloperPassword(password) {
    try {
        // Validate password length client-side before sending
        if (!password || password.length < 8 || password.length > 128) {
            console.error('Invalid password format');
            return false;
        }
        
        const response = await fetch('/api/verify-dev-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include', // Include cookies for session
            body: JSON.stringify({ password: password.trim() })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('Password verified successfully');
            return true;
        } else {
            console.error('Password verification failed:', result.error);
            return false;
        }
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
