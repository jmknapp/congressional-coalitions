// Congressional Coalition Analysis Dashboard JavaScript - Updated for Pink FC Badges v2024

// Global variables
let currentData = {
    membersById: {},
    allMembers: []
};

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadSummary();
    loadMembers();
    loadBills();
    loadRollcalls();
    loadCrossPartyVoters();
});

// Helper to format member chip text
function formatMemberChip(member) {
    if (!member) return '';
    const last = (member.name || '').split(' ').slice(-1)[0] || '';
    const party = member.party || '';
    const state = member.state || '';
    return `${last} (${party}${state ? '-' + state : ''})`;
}

// Load summary statistics
async function loadSummary() {
    try {
        const response = await fetch('/api/summary');
        const data = await response.json();
        
        document.getElementById('total-members').textContent = data.total_members;
        document.getElementById('total-bills').textContent = data.total_bills;
        document.getElementById('total-rollcalls').textContent = data.total_rollcalls;
        document.getElementById('total-cosponsors').textContent = data.total_cosponsors;
        
        // Update time period information
        if (data.time_period) {
            const timePeriodText = `Data from ${data.time_period.description} (${data.time_period.days_covered} days)`;
            document.getElementById('time-period-text').textContent = timePeriodText;
        } else {
            document.getElementById('time-period-text').textContent = 'Current session data';
        }
        
    } catch (error) {
        console.error('Error loading summary:', error);
        document.getElementById('time-period-text').textContent = 'Error loading time period';
    }
}

// Load members data
async function loadMembers() {
    try {
        const response = await fetch('/api/members');
        const members = await response.json();
        
        // Store all members and build quick lookup by bioguide id
        currentData.allMembers = members;
        currentData.membersById = {};
        members.forEach(m => {
            currentData.membersById[m.id] = m;
        });
        
        // Update party counts
        updatePartyCounts(members);
        
        // Display all members initially
        displayMembers(members);
        
    } catch (error) {
        console.error('Error loading members:', error);
    }
}

// Update party counts in tab labels
function updatePartyCounts(members) {
    const allCount = members.length;
    const demCount = members.filter(m => m.party === 'D').length;
    const repCount = members.filter(m => m.party === 'R').length;
    
    document.getElementById('all-count').textContent = allCount;
    document.getElementById('dem-count').textContent = demCount;
    document.getElementById('rep-count').textContent = repCount;
}

// Display members in the table
function displayMembers(members) {
    const tbody = document.getElementById('members-tbody');
    const spinner = document.getElementById('members-loading-spinner');
    const tableContainer = document.getElementById('members-table-container');
    
    // Hide spinner, show table
    if (spinner) spinner.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';
    
    tbody.innerHTML = '';
    
    members.forEach(member => {
        const row = document.createElement('tr');
        
        // Create caucus badges with clickable links to caucus info pages
        const freedomCaucusBadge = member.is_freedom_caucus ? 
            '<a href="/caucus/1" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge fc-pink-badge ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Freedom Caucus information"><i class="fas fa-scale-unbalanced me-1"></i>FC</span></a>' : '';
        const progressiveCaucusBadge = member.is_progressive_caucus ? 
            '<a href="/caucus/2" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-info text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Progressive Caucus information"><i class="fas fa-arrow-trend-up me-1"></i>PC</span></a>' : '';
        const blueDogCoalitionBadge = member.is_blue_dog_coalition ? 
            '<a href="/caucus/3" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-info text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Blue Dog Coalition information"><i class="fas fa-dog me-1"></i>BD</span></a>' : '';
        const magaRepublicanBadge = member.is_maga_republican ? 
            '<a href="/caucus/5" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-danger text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view MAGA Republicans information"><i class="fas fa-biohazard me-1"></i>MAGA</span></a>' : '';
        const congressionalBlackCaucusBadge = member.is_congressional_black_caucus ? 
            '<a href="/caucus/4" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #1a237e;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Congressional Black Caucus information"><i class="fas fa-users me-1"></i>CBC</span></a>' : '';
        const trueBlueDemocratsBadge = member.is_true_blue_democrat ? 
            '<a href="/caucus/6" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-primary text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view True Blue Democrats information"><i class="fas fa-heart me-1"></i>TB</span></a>' : '';
        const hispanicCaucusBadge = member.is_hispanic_caucus ? 
            '<a href="/caucus/7" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #2e7d32;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Congressional Hispanic Caucus information"><i class="fas fa-flag me-1"></i>CHC</span></a>' : '';
        const newDemocratCoalitionBadge = member.is_new_democrat_coalition ? 
            '<a href="/caucus/8" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #1976d2;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view New Democrat Coalition information"><i class="fas fa-chart-line me-1"></i>NDC</span></a>' : '';

        row.innerHTML = `
            <td>
                <a href="/member/${member.id}" 
                   target="_blank" 
                   rel="noopener noreferrer"
                   data-bs-toggle="tooltip" 
                   data-bs-placement="right"
                   data-bs-html="true"
                   data-bs-title="<img src='/api/member-image/${member.id}' alt='${member.name}' style='width: 120px; height: 120px; object-fit: cover; border-radius: 8px;'><br><strong>${member.name}</strong><br><small>${member.party} - ${member.state}${member.district ? ' District ' + member.district : ''}</small>">${member.name}</a>
                ${freedomCaucusBadge}
                ${progressiveCaucusBadge}
                ${blueDogCoalitionBadge}
                ${magaRepublicanBadge}
                ${congressionalBlackCaucusBadge}
                ${trueBlueDemocratsBadge}
                ${hispanicCaucusBadge}
                ${newDemocratCoalitionBadge}
            </td>
            <td><span class="party-badge party-${member.party.toLowerCase()}">${member.party}</span></td>
            <td>${member.state}</td>
            <td>${member.vote_count}</td>
        `;
        tbody.appendChild(row);
    });
    
    // Initialize tooltips for caucus badges
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Filter members by party
function filterMembersByParty(party) {
    let filteredMembers;
    
    if (party === 'all') {
        filteredMembers = currentData.allMembers;
    } else {
        filteredMembers = currentData.allMembers.filter(member => member.party === party);
    }
    
    displayMembers(filteredMembers);
}

// Load bills data
async function loadBills() {
    try {
        // Show spinner, hide table
        const spinner = document.getElementById('bills-loading-spinner');
        const tableContainer = document.getElementById('bills-table-container');
        
        if (spinner) spinner.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
        
        const response = await fetch('/api/bills');
        const data = await response.json();
        
        // Handle new response format with cache metadata
        let bills;
        if (data.bills) {
            bills = data.bills;
            // console.log(`Bills loaded: ${data.count} bills (cached: ${data.cached}, cache_time: ${data.cache_time})`);
        } else {
            // Fallback for old format
            bills = data;
            // console.log('Bills loaded:', bills.length, 'bills');
        }
        
        const tbody = document.getElementById('bills-tbody');
        if (!tbody) {
            console.error('Bills tbody element not found');
            return;
        }
        tbody.innerHTML = '';
        
        bills.forEach((bill, index) => {
            if (index < 10) { // Only log first 10 for debugging
                // console.log('Processing bill:', bill);
            }
            const row = document.createElement('tr');
            const billHref = `/bill/${bill.id}`;
            // Format last action date
            let lastActionDisplay = 'N/A';
            if (bill.last_action_date) {
                const actionDate = new Date(bill.last_action_date).toLocaleDateString();
                if (bill.last_action_code && bill.last_action_code !== 'UNKNOWN') {
                    lastActionDisplay = `<div><strong>${actionDate}</strong></div><div class="text-muted small">${bill.last_action_code}</div>`;
                } else {
                    lastActionDisplay = actionDate;
                }
            }
            
            // Format sponsor with link to member page if bioguide ID is available
            let sponsorDisplay = bill.sponsor;
            if (bill.sponsor_bioguide && bill.sponsor !== 'Unknown') {
                const memberHref = `/member/${bill.sponsor_bioguide}`;
                sponsorDisplay = `<a href="${memberHref}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${bill.sponsor}</a>`;
            }
            
            row.innerHTML = `
                <td>${lastActionDisplay}</td>
                <td><strong><a href="${billHref}" target="_blank" rel="noopener noreferrer">${bill.type} ${bill.number}</a></strong></td>
                <td>${(bill.title || '').substring(0, 50)}${(bill.title || '').length > 50 ? '...' : ''}</td>
                <td>${sponsorDisplay}</td>
                <td>${bill.cosponsor_count}</td>
            `;
            tbody.appendChild(row);
        });
        
        // console.log('Bills table populated with', bills.length, 'rows');
        
        // Hide spinner, show table
        if (spinner) spinner.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading bills:', error);
        
        // Hide spinner on error and show error message
        const spinner = document.getElementById('bills-loading-spinner');
        const tableContainer = document.getElementById('bills-table-container');
        
        if (spinner) {
            spinner.innerHTML = `
                <div class="text-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error loading bills: ${error.message}
                </div>
            `;
        }
    }
}

// Load roll calls data
async function loadRollcalls() {
    try {
        const response = await fetch('/api/rollcalls');
        const rollcalls = await response.json();
        
        const tbody = document.getElementById('rollcalls-tbody');
        const spinner = document.getElementById('rollcalls-loading-spinner');
        const tableContainer = document.getElementById('rollcalls-table-container');
        
        // Hide spinner, show table
        if (spinner) spinner.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
        
        tbody.innerHTML = '';
        
        // Roll calls are already sorted by the backend (date desc, then roll call number desc)
        
        rollcalls.forEach(rollcall => {
            const date = rollcall.date ? new Date(rollcall.date).toLocaleDateString() : '';
            const row = document.createElement('tr');
            // Removed redundant "Bill" button; bill titles are already hyperlinked in the question column.
            
            // Create question display with bill info on first line if available
            let questionDisplay = '';
            if (rollcall.bill_id && rollcall.bill_title) {
                const billTitle = rollcall.bill_title.length > 50 ? rollcall.bill_title.substring(0, 50) + '...' : rollcall.bill_title;
                const billHref = `/bill/${rollcall.bill_id}`;
                questionDisplay = `<div><strong><a href="${billHref}" target="_blank" rel="noopener noreferrer">${billTitle}</a></strong></div>`;
            }
            if (rollcall.question) {
                const questionText = rollcall.question.length > 80 ? rollcall.question.substring(0, 80) + '...' : rollcall.question;
                questionDisplay += `<div>${questionText}</div>`;
            }
            
            row.innerHTML = `
                <td><strong><a href="/vote/${rollcall.id}" target="_blank" rel="noopener noreferrer">${rollcall.id}</a></strong></td>
                <td>${questionDisplay}</td>
                <td>${date}</td>
                <td><span class="vote-badge vote-yea">${rollcall.yea_count}</span></td>
                <td><span class="vote-badge vote-nay">${rollcall.nay_count}</span></td>
                <td><span class="vote-badge vote-present">${rollcall.present_count}</span></td>
                <td>
                    <a class="btn btn-sm btn-outline-primary me-2" href="/vote/${rollcall.id}" target="_blank" rel="noopener noreferrer">
                        <i class="fas fa-eye"></i> View Votes
                    </a>
                </td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        console.error('Error loading roll calls:', error);
    }
}

// Load cross-party voters data
async function loadCrossPartyVoters() {
    try {
        // Show spinner, hide table
        const spinner = document.getElementById('crossparty-loading-spinner');
        const tableContainer = document.getElementById('crossparty-table-container');
        
        if (spinner) spinner.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
        
        // Fetch both analysis data and member data in parallel
        const [analysisResponse, membersResponse] = await Promise.all([
            fetch('/api/analysis/119/house'),
            fetch('/api/members')
        ]);
        
        const analysisData = await analysisResponse.json();
        const membersData = await membersResponse.json();
        
        // console.log('Members data structure:', Object.keys(membersData));
        
        const crossPartyVoters = (analysisData.member_analysis && analysisData.member_analysis.cross_party_voters) || [];
        
        // Create member lookup by bioguide ID
        const memberLookup = {};
        let members;
        
        // Handle different response formats more robustly
        if (membersData.members) {
            members = membersData.members;
        } else if (Array.isArray(membersData)) {
            members = membersData;
        } else {
            console.error('Unexpected members data format:', membersData);
            members = [];
        }
        
        members.forEach(member => {
            if (member && member.id) {
                memberLookup[member.id] = member;
            }
        });
        
        // Debug logging
        // console.log('Member lookup created with', Object.keys(memberLookup).length, 'members');
        // console.log('Sample member IDs:', Object.keys(memberLookup).slice(0, 5));
        // console.log('Sample cross-party voter IDs:', crossPartyVoters.slice(0, 5).map(v => v.member_id));
        
        if (spinner) spinner.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
        
        const tbody = document.getElementById('crossparty-tbody');
        if (!tbody) {
            console.error('Cross-party tbody element not found');
            return;
        }
        tbody.innerHTML = '';
        
        if (crossPartyVoters.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No cross-party voting data available</td></tr>';
            return;
        }
        
        // Display top 15 cross-party voters
        crossPartyVoters.slice(0, 15).forEach((voter, index) => {
            const percentageClass = voter.cross_party_percentage > 20 ? 'bg-warning' : 'bg-info';
            const bioguideId = voter.member_id;
            const member = memberLookup[bioguideId];
            
            // Debug logging for first few members
            if (index < 3) {
                // console.log(`Voter ${index}:`, voter.name, 'ID:', bioguideId, 'Member found:', !!member);
                if (member) {
                    // console.log('  Caucus memberships:', {
                    //     freedom: member.is_freedom_caucus,
                    //     progressive: member.is_progressive_caucus,
                    //     blue_dog: member.is_blue_dog_coalition,
                    //     maga: member.is_maga_republican,
                    //     cbc: member.is_congressional_black_caucus,
                    //     true_blue: member.is_true_blue_democrat
                    // });
                }
            }
            
            // Generate caucus badges
            let badges = '';
            if (member) {
                const freedomCaucusBadge = member.is_freedom_caucus ? 
                    '<a href="/caucus/1" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge fc-pink-badge ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Freedom Caucus information"><i class="fas fa-scale-unbalanced me-1"></i>FC</span></a>' : '';
                const progressiveCaucusBadge = member.is_progressive_caucus ? 
                    '<a href="/caucus/2" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-info text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Progressive Caucus information"><i class="fas fa-arrow-trend-up me-1"></i>PC</span></a>' : '';
                const blueDogBadge = member.is_blue_dog_coalition ? 
                    '<a href="/caucus/3" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-info text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Blue Dog Coalition information"><i class="fas fa-dog me-1"></i>BD</span></a>' : '';
                const magaBadge = member.is_maga_republican ? 
                    '<a href="/caucus/5" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-danger text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view MAGA Republicans information"><i class="fas fa-biohazard me-1"></i>MAGA</span></a>' : '';
                const congressionalBlackCaucusBadge = member.is_congressional_black_caucus ? 
                    '<a href="/caucus/4" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #1a237e;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Congressional Black Caucus information"><i class="fas fa-users me-1"></i>CBC</span></a>' : '';
                const trueBlueBadge = member.is_true_blue_democrat ? 
                    '<a href="/caucus/6" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge bg-primary text-white ms-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view True Blue Democrats information"><i class="fas fa-heart me-1"></i>TB</span></a>' : '';
                const hispanicCaucusBadge = member.is_hispanic_caucus ? 
                    '<a href="/caucus/7" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #2e7d32;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view Congressional Hispanic Caucus information"><i class="fas fa-flag me-1"></i>CHC</span></a>' : '';
                const newDemocratCoalitionBadge = member.is_new_democrat_coalition ? 
                    '<a href="/caucus/8" target="_blank" rel="noopener noreferrer" class="text-decoration-none"><span class="badge text-white ms-2" style="background-color: #1976d2;" data-bs-toggle="tooltip" data-bs-placement="top" title="Click to view New Democrat Coalition information"><i class="fas fa-chart-line me-1"></i>NDC</span></a>' : '';
                
                badges = freedomCaucusBadge + progressiveCaucusBadge + blueDogBadge + magaBadge + congressionalBlackCaucusBadge + trueBlueBadge + hispanicCaucusBadge + newDemocratCoalitionBadge;
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <a href="/member/${bioguideId}" 
                       target="_blank" 
                       rel="noopener noreferrer" 
                       class="text-decoration-none"
                       data-bs-toggle="tooltip" 
                       data-bs-placement="right"
                       data-bs-html="true"
                       data-bs-title="<img src='/api/member-image/${bioguideId}' alt='${voter.name}' style='width: 120px; height: 120px; object-fit: cover; border-radius: 8px;'><br><strong>${voter.name}</strong><br><small>${voter.party} - ${voter.state}</small>">
                        ${voter.name}
                    </a>
                    ${badges}
                </td>
                <td><span class="party-badge party-${voter.party.toLowerCase()}">${voter.party}</span></td>
                <td>${voter.state}</td>
                <td><span class="badge ${percentageClass}" data-bs-toggle="tooltip" data-bs-placement="top" title="Cross-party voting percentage">${voter.cross_party_percentage.toFixed(1)}%</span></td>
                <td>${voter.cross_party_votes}</td>
                <td>${voter.total_votes}</td>
            `;
            tbody.appendChild(row);
        });
        
        // Initialize tooltips for this section
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('#crossparty-table [data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        // console.log(`Cross-party voters loaded: ${crossPartyVoters.length} members (showing top 15)`);
        
    } catch (error) {
        console.error('Error loading cross-party voters:', error);
        const spinner = document.getElementById('crossparty-loading-spinner');
        if (spinner) {
            spinner.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    Failed to load cross-party voting data: ${error.message}
                </div>
            `;
        }
    }
}

// Run coalition analysis
async function runAnalysis() {
    const congress = document.getElementById('congress-select').value;
    const chamber = 'house'; // Force House-only analysis
    const window = document.getElementById('window-select').value;
    
    // Show loading state
    const analysisContent = document.getElementById('analysis-content');
    analysisContent.innerHTML = `
        <div class="loading">
            <i class="fas fa-spinner"></i>
            <p>Running coalition analysis...</p>
        </div>
    `;
    
    document.getElementById('analysis-results').style.display = 'block';
    
    try {
        const response = await fetch(`/api/analysis/${congress}/${chamber}`);
        const data = await response.json();
        
        displayAnalysisResults(data, congress, chamber, window);
        
    } catch (error) {
        console.error('Error running analysis:', error);
        analysisContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Error running analysis: ${error.message}
            </div>
        `;
    }
}

// Display analysis results
function displayAnalysisResults(data, congress, chamber, window) {
    const analysisContent = document.getElementById('analysis-content');
    
    const summary = (data && data.summary) || {};
    const votingAnalysis = (data && data.voting_analysis) || {};
    const memberAnalysis = (data && data.member_analysis) || {};
    const recentBills = (data && data.recent_bills) || [];
    
    if (!data || data.error) {
        analysisContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                ${data && data.error ? data.error : 'Analysis failed.'}
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="analysis-summary">
            <h4>House Analysis Summary - Congress ${congress}</h4>
            <div class="row">
                <div class="col-md-3">
                    <div class="analysis-metric">
                        <h3>${summary.total_members || '-'}</h3>
                        <p>Members Analyzed</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-metric">
                        <h3>${summary.total_rollcalls || '-'}</h3>
                        <p>Roll Calls</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-metric">
                        <h3>${summary.total_votes || '-'}</h3>
                        <p>Total Votes</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-metric">
                        <h3>${summary.recent_bills || '-'}</h3>
                        <p>Recent Bills</p>
                    </div>
                </div>
            </div>
            <p class="text-muted mt-2">Analysis Period: ${summary.analysis_period || 'N/A'}</p>
        </div>
    `;
    

    
    // Display cross-party voters
    const crossPartyVoters = memberAnalysis.cross_party_voters || [];
    if (crossPartyVoters.length > 0) {
        html += '<h5 class="mt-4 mb-3"><i class="fas fa-exchange-alt me-2"></i>Cross-Party Voters</h5>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-striped">';
        html += '<thead><tr><th>Member</th><th>Party</th><th>State</th><th>Cross-Party %</th><th>Cross-Party Votes</th><th>Total Votes</th></tr></thead>';
        html += '<tbody>';
        
        crossPartyVoters.slice(0, 15).forEach(member => {
            const percentageClass = member.cross_party_percentage > 20 ? 'bg-warning' : 'bg-info';
            // Use member_id as bioguide_id (they're the same in this context)
            const bioguideId = member.member_id;
            
            html += `
                <tr>
                    <td>
                        <a href="/member/${bioguideId}" 
                           target="_blank" 
                           rel="noopener noreferrer" 
                           class="text-decoration-none"
                           data-bs-toggle="tooltip" 
                           data-bs-placement="right"
                           data-bs-html="true"
                           data-bs-title="<img src='/api/member-image/${bioguideId}' alt='${member.name}' style='width: 120px; height: 120px; object-fit: cover; border-radius: 8px;'><br><strong>${member.name}</strong><br><small>${member.party} - ${member.state}</small>">
                            ${member.name}
                        </a>
                    </td>
                    <td><span class="party-badge party-${member.party.toLowerCase()}">${member.party}</span></td>
                    <td>${member.state}</td>
                    <td><span class="badge ${percentageClass}" data-bs-toggle="tooltip" data-bs-placement="top" title="Cross-party voting percentage">${member.cross_party_percentage.toFixed(1)}%</span></td>
                    <td>${member.cross_party_votes}</td>
                    <td>${member.total_votes}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
    }
    
    // Display recent bills
    if (recentBills.length > 0) {
        html += '<h5 class="mt-4 mb-3"><i class="fas fa-file-alt me-2"></i>Recent House Bills</h5>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-striped">';
        html += '<thead><tr><th>Bill ID</th><th>Title</th><th>Introduced Date</th></tr></thead>';
        html += '<tbody>';
        
        recentBills.slice(0, 10).forEach(bill => {
            html += `
                <tr>
                    <td><strong><a href="/bill/${bill.bill_id}" target="_blank">${bill.bill_id}</a></strong></td>
                    <td>${bill.title || 'N/A'}</td>
                    <td>${bill.introduced_date || 'N/A'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
    }
    
    analysisContent.innerHTML = html;
    
    // Initialize tooltips for analysis results
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Show vote details modal
async function showVoteDetails(rollcallId) {
    try {
        const response = await fetch(`/api/votes/${rollcallId}`);
        const votes = await response.json();
        
        const voteDetails = document.getElementById('vote-details');
        let html = `
            <h6>Vote Details for ${rollcallId}</h6>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Member</th>
                            <th>Party</th>
                            <th>State</th>
                            <th>Vote</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        votes.forEach(vote => {
            const m = currentData.membersById[vote.member_id] || null;
            const name = formatMemberChip(m) || vote.member_name || '';
            const voteClass = (vote.vote_code || '').toLowerCase().replace(' ', '-');
            html += `
                <tr>
                    <td><a href="/member/${vote.member_id}" target="_blank" rel="noopener noreferrer">${name}</a></td>
                    <td><span class="party-badge party-${(vote.party || '').toLowerCase()}">${vote.party || ''}</span></td>
                    <td>${vote.state || ''}</td>
                    <td><span class="vote-badge vote-${voteClass}">${vote.vote_code || ''}</span></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        voteDetails.innerHTML = html;
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('voteModal'));
        modal.show();
        
    } catch (error) {
        console.error('Error loading vote details:', error);
    }
}

// Show cosponsor details modal
async function showCosponsorDetails(billId) {
    try {
        const response = await fetch(`/api/cosponsors/${billId}`);
        const cosponsors = await response.json();
        
        const cosponsorDetails = document.getElementById('cosponsor-details');
        let html = `
            <h6>Cosponsors for ${billId}</h6>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Member</th>
                            <th>Party</th>
                            <th>State</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        cosponsors.forEach(cosponsor => {
            const m = currentData.membersById[cosponsor.member_id] || null;
            const name = formatMemberChip(m) || cosponsor.member_name || '';
            const date = cosponsor.date ? new Date(cosponsor.date).toLocaleDateString() : 'N/A';
            html += `
                <tr>
                    <td><a href="/member/${cosponsor.member_id}" target="_blank" rel="noopener noreferrer">${name}</a></td>
                    <td><span class="party-badge party-${(cosponsor.party || '').toLowerCase()}">${cosponsor.party || ''}</span></td>
                    <td>${cosponsor.state || ''}</td>
                    <td>${date}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        cosponsorDetails.innerHTML = html;
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('cosponsorModal'));
        modal.show();
        
    } catch (error) {
        console.error('Error loading cosponsor details:', error);
    }
}
