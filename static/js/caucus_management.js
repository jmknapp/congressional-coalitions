// Caucus Management JavaScript

let currentCaucus = null;
let allMembers = [];

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    loadCaucuses();
    loadAllMembers();
    
    // Set up event listeners
    document.getElementById('caucusSelect').addEventListener('change', onCaucusSelect);
    document.getElementById('memberSearch').addEventListener('input', filterMembers);
    
    // Start date is optional - no default value
});

// Load all available caucuses
async function loadCaucuses() {
    try {
        const response = await fetch('/api/caucuses');
        const caucuses = await response.json();
        
        const select = document.getElementById('caucusSelect');
        select.innerHTML = '<option value="">Choose a caucus...</option>';
        
        caucuses.forEach(caucus => {
            const option = document.createElement('option');
            option.value = caucus.id;
            option.textContent = caucus.name;
            select.appendChild(option);
        });
        
        // Add "Add Caucus" option
        const addOption = document.createElement('option');
        addOption.value = 'add_new';
        addOption.textContent = '+ Add New Caucus';
        addOption.style.fontStyle = 'italic';
        addOption.style.color = '#6c757d';
        select.appendChild(addOption);
    } catch (error) {
        console.error('Error loading caucuses:', error);
        showAlert('Error loading caucuses', 'danger');
    }
}

// Load all members for the member selection dropdown
async function loadAllMembers() {
    try {
        const response = await fetch('/api/members');
        allMembers = await response.json();
        
        const select = document.getElementById('memberSelect');
        select.innerHTML = '<option value="">Search and select a member...</option>';
        
        allMembers.forEach(member => {
            const option = document.createElement('option');
            option.value = member.id;
            option.textContent = `${member.name} (${member.party}-${member.state}${member.district ? '-' + member.district : ''})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading members:', error);
        showAlert('Error loading members', 'danger');
    }
}

// Handle caucus selection
async function onCaucusSelect(event) {
    const caucusId = event.target.value;
    if (!caucusId) {
        hideCaucusInfo();
        return;
    }
    
    // Handle "Add New Caucus" selection
    if (caucusId === 'add_new') {
        showAddCaucusModal();
        // Reset dropdown to default
        event.target.value = '';
        return;
    }
    
    try {
        const response = await fetch(`/api/caucuses/${caucusId}`);
        const caucus = await response.json();
        
        if (caucus.error) {
            showAlert(caucus.error, 'danger');
            return;
        }
        
        currentCaucus = caucus;
        displayCaucusInfo(caucus);
        loadCaucusMembers(caucusId);
    } catch (error) {
        console.error('Error loading caucus:', error);
        showAlert('Error loading caucus information', 'danger');
    }
}

// Display caucus information
function displayCaucusInfo(caucus) {
    document.getElementById('caucusName').textContent = caucus.name;
    document.getElementById('caucusDescription').textContent = caucus.description || 'No description available';
    document.getElementById('memberCount').textContent = caucus.member_count || 0;
    document.getElementById('caucusColor').textContent = caucus.color;
    document.getElementById('caucusIcon').className = caucus.icon;
    
    document.getElementById('caucusInfo').style.display = 'block';
    document.getElementById('membersTable').style.display = 'block';
}

// Hide caucus information
function hideCaucusInfo() {
    document.getElementById('caucusInfo').style.display = 'none';
    document.getElementById('membersTable').style.display = 'none';
    currentCaucus = null;
}

// Load members for a specific caucus
async function loadCaucusMembers(caucusId) {
    try {
        const response = await fetch(`/api/caucuses/${caucusId}/members`);
        const members = await response.json();
        
        if (members.error) {
            showAlert(members.error, 'danger');
            return;
        }
        
        displayCaucusMembers(members);
        document.getElementById('memberCount').textContent = members.length;
    } catch (error) {
        console.error('Error loading caucus members:', error);
        showAlert('Error loading caucus members', 'danger');
    }
}

// Display caucus members in the table
function displayCaucusMembers(members) {
    const tbody = document.getElementById('membersTableBody');
    tbody.innerHTML = '';
    
    if (members.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No members in this caucus</td></tr>';
        return;
    }
    
    members.forEach(membership => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${membership.member_name}</td>
            <td><span class="badge bg-${membership.party === 'D' ? 'primary' : 'danger'}">${membership.party}</span></td>
            <td>${membership.state}</td>
            <td>${membership.district || 'N/A'}</td>
            <td>${formatDate(membership.start_date)}</td>
            <td>${membership.notes || ''}</td>
            <td>
                <button class="btn btn-sm btn-outline-danger" onclick="removeMember(${membership.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Filter members in the search box
function filterMembers(event) {
    const searchTerm = event.target.value.toLowerCase();
    const select = document.getElementById('memberSelect');
    
    // Reset to show all members
    Array.from(select.options).forEach(option => {
        if (option.value === '') return; // Skip the placeholder
        
        const memberText = option.textContent.toLowerCase();
        option.style.display = memberText.includes(searchTerm) ? '' : 'none';
    });
}

// Show bulk member management modal
function addMemberModal() {
    if (!currentCaucus) {
        showAlert('Please select a caucus first', 'warning');
        return;
    }
    
    // Load all members organized by party
    loadMembersForBulkManagement();
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('addMemberModal'));
    modal.show();
}

// Load members organized by party for bulk management
async function loadMembersForBulkManagement() {
    try {
        // Get current caucus members
        const currentMembersResponse = await fetch(`/api/caucuses/${currentCaucus.id}/members`);
        const currentMembers = await currentMembersResponse.json();
        const currentMemberIds = new Set(currentMembers.map(m => m.member_id_bioguide));
        
        // Organize all members by party
        const republicans = [];
        const democrats = [];
        const others = [];
        
        allMembers.forEach(member => {
            const memberData = {
                ...member,
                isCurrentMember: currentMemberIds.has(member.id)
            };
            
            if (member.party === 'R') {
                republicans.push(memberData);
            } else if (member.party === 'D') {
                democrats.push(memberData);
            } else {
                others.push(memberData);
            }
        });
        
        // Render member lists
        renderMemberList('republicanMembers', republicans);
        renderMemberList('democratMembers', democrats);
        renderMemberList('otherMembers', others);
        
    } catch (error) {
        console.error('Error loading members for bulk management:', error);
        showAlert('Error loading members', 'danger');
    }
}

// Render a member list with checkboxes
function renderMemberList(containerId, members) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    if (members.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No members in this party</p>';
        return;
    }
    
            members.forEach(member => {
            const memberDiv = document.createElement('div');
            memberDiv.className = `member-item ${member.isCurrentMember ? 'current-member' : ''}`;
            
            // Create abbreviated entry like "BEATTY OH03"
            const lastName = member.name.split(' ').pop().toUpperCase();
            const state = member.state;
            const district = member.district ? String(member.district).padStart(2, '0') : '';
            const abbreviatedEntry = `${lastName} ${state}${district}`;
            
            memberDiv.innerHTML = `
                <input type="checkbox" class="member-checkbox" 
                       id="member_${member.id}" 
                       value="${member.id}" 
                       ${member.isCurrentMember ? 'checked' : ''}
                       ${member.isCurrentMember ? 'data-was-current="true"' : ''}>
                <div class="member-info" title="${member.name} (${member.party}-${member.state}${member.district ? '-' + member.district : ''})">
                    <div class="member-name">${abbreviatedEntry}</div>
                </div>
            `;
            
            container.appendChild(memberDiv);
        });
}

// Bulk update caucus members
async function bulkUpdateCaucusMembers() {
    const startDate = document.getElementById('bulkStartDate').value;
    const notes = document.getElementById('bulkNotes').value;
    
    // Get all checked members
    const checkedMembers = [];
    const uncheckedMembers = [];
    
    // Check all party tabs for checked/unchecked members
    ['republican', 'democrat', 'other'].forEach(party => {
        const container = document.getElementById(party + 'Members');
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        
        checkboxes.forEach(checkbox => {
            const memberId = checkbox.value;
            const wasCurrentMember = checkbox.hasAttribute('data-was-current');
            
            if (checkbox.checked && !wasCurrentMember) {
                // New member to add
                checkedMembers.push(memberId);
            } else if (!checkbox.checked && wasCurrentMember) {
                // Current member to remove
                uncheckedMembers.push(memberId);
            }
        });
    });
    
    if (checkedMembers.length === 0 && uncheckedMembers.length === 0) {
        showAlert('No changes detected', 'info');
        return;
    }
    
    try {
        // Process additions
        for (const memberId of checkedMembers) {
            await addMemberToCaucus(memberId, startDate, notes);
        }
        
        // Process removals
        for (const memberId of uncheckedMembers) {
            await removeMemberFromCaucus(memberId);
        }
        
        showAlert(`Updated caucus: ${checkedMembers.length} added, ${uncheckedMembers.length} removed`, 'success');
        
        // Close modal and refresh
        const modal = bootstrap.Modal.getInstance(document.getElementById('addMemberModal'));
        modal.hide();
        
        // Refresh the members list
        loadCaucusMembers(currentCaucus.id);
        
    } catch (error) {
        console.error('Error updating caucus:', error);
        showAlert('Error updating caucus', 'danger');
    }
}

// Helper function to add a single member
async function addMemberToCaucus(memberId, startDate, notes) {
    try {
        const response = await fetch('/api/caucus-memberships', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                member_id_bioguide: memberId,
                caucus_id: currentCaucus.id,
                start_date: startDate || null,
                notes: notes || ''
            })
        });
        
        const result = await response.json();
        
        if (result.error) {
            throw new Error(result.error);
        }
        
    } catch (error) {
        console.error('Error adding member:', error);
        throw error;
    }
}

// Helper function to remove a single member
async function removeMemberFromCaucus(memberId) {
    try {
        // Find the membership ID for this member
        const currentMembersResponse = await fetch(`/api/caucuses/${currentCaucus.id}/members`);
        const currentMembers = await currentMembersResponse.json();
        const membership = currentMembers.find(m => m.member_id_bioguide === memberId);
        
        if (membership) {
            const response = await fetch(`/api/caucus-memberships/${membership.id}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.error) {
                throw new Error(result.error);
            }
        }
        
    } catch (error) {
        console.error('Error removing member:', error);
        throw error;
    }
}

// Remove member from caucus
async function removeMember(membershipId) {
    if (!confirm('Are you sure you want to remove this member from the caucus?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/caucus-memberships/${membershipId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.error) {
            showAlert(result.error, 'danger');
            return;
        }
        
        showAlert('Member removed from caucus successfully', 'success');
        
        // Refresh the members list
        loadCaucusMembers(currentCaucus.id);
        
    } catch (error) {
        console.error('Error removing member:', error);
        showAlert('Error removing member from caucus', 'danger');
    }
}

// Format date for display
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
}

// Show alert message
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Show the Add Caucus modal
function showAddCaucusModal() {
    const modal = document.getElementById('addCaucusModal');
    if (modal) {
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
}

// Handle caucus creation
async function createCaucus() {
    const form = document.getElementById('addCaucusForm');
    const formData = new FormData(form);
    
    const caucusData = {
        name: formData.get('name'),
        short_name: formData.get('short_name'),
        description: formData.get('description'),
        color: formData.get('color'),
        icon: formData.get('icon'),
        is_active: true
    };
    
    // Validate required fields
    if (!caucusData.name || !caucusData.short_name) {
        showAlert('Name and Short Name are required', 'danger');
        return;
    }
    
    try {
        const response = await fetch('/api/caucuses', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(caucusData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Caucus created successfully!', 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addCaucusModal'));
            modal.hide();
            
            // Reset form
            form.reset();
            
            // Reload caucuses dropdown
            await loadCaucuses();
            
            // Select the newly created caucus
            const select = document.getElementById('caucusSelect');
            select.value = result.id;
            onCaucusSelect({ target: select });
            
        } else {
            showAlert(result.error || 'Error creating caucus', 'danger');
        }
    } catch (error) {
        console.error('Error creating caucus:', error);
        showAlert('Error creating caucus', 'danger');
    }
}
