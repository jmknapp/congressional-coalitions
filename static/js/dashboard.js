// Congressional Coalition Analysis Dashboard JavaScript

// Global variables
let currentData = {
    membersById: {}
};

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadSummary();
    loadMembers();
    loadBills();
    loadRollcalls();
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
        
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

// Load members data
async function loadMembers() {
    try {
        const response = await fetch('/api/members');
        const members = await response.json();
        
        // Build quick lookup by bioguide id
        currentData.membersById = {};
        members.forEach(m => {
            currentData.membersById[m.id] = m;
        });
        
        const tbody = document.getElementById('members-tbody');
        tbody.innerHTML = '';
        
        members.forEach(member => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><a href="/member/${member.id}" target="_blank" rel="noopener noreferrer">${member.name}</a></td>
                <td><span class="party-badge party-${member.party.toLowerCase()}">${member.party}</span></td>
                <td>${member.state}</td>
                <td>${member.chamber}</td>
                <td>${member.vote_count}</td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        console.error('Error loading members:', error);
    }
}

// Load bills data
async function loadBills() {
    try {
        const response = await fetch('/api/bills');
        const bills = await response.json();
        
        console.log('Bills loaded:', bills.length, 'bills');
        
        const tbody = document.getElementById('bills-tbody');
        if (!tbody) {
            console.error('Bills tbody element not found');
            return;
        }
        tbody.innerHTML = '';
        
        bills.forEach((bill, index) => {
            if (index < 10) { // Only log first 10 for debugging
                console.log('Processing bill:', bill);
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
            
            row.innerHTML = `
                <td><strong><a href="${billHref}" target="_blank" rel="noopener noreferrer">${bill.type} ${bill.number}</a></strong></td>
                <td>${(bill.title || '').substring(0, 50)}${(bill.title || '').length > 50 ? '...' : ''}</td>
                <td>${bill.sponsor}</td>
                <td>${bill.chamber}</td>
                <td>${bill.cosponsor_count}</td>
                <td>${lastActionDisplay}</td>
            `;
            tbody.appendChild(row);
        });
        
        console.log('Bills table populated with', bills.length, 'rows');
        
    } catch (error) {
        console.error('Error loading bills:', error);
    }
}

// Load roll calls data
async function loadRollcalls() {
    try {
        const response = await fetch('/api/rollcalls');
        const rollcalls = await response.json();
        
        const tbody = document.getElementById('rollcalls-tbody');
        tbody.innerHTML = '';
        
        // Sort rollcalls by date ascending (oldest first)
        rollcalls.sort((a, b) => {
            const dateA = a.date ? new Date(a.date) : new Date(0);
            const dateB = b.date ? new Date(b.date) : new Date(0);
            return dateA - dateB;
        });
        
        rollcalls.forEach(rollcall => {
            const date = rollcall.date ? new Date(rollcall.date).toLocaleDateString() : '';
            const row = document.createElement('tr');
            const billLink = rollcall.bill_id ? `<a href="/bill/${rollcall.bill_id}" target="_blank" rel="noopener noreferrer">Bill</a>` : '';
            
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
                    ${billLink ? `<a class="btn btn-sm btn-outline-secondary" href="/bill/${rollcall.bill_id}" target="_blank" rel="noopener noreferrer">Bill</a>` : ''}
                </td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        console.error('Error loading roll calls:', error);
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
    
    // Display most partisan votes
    const mostPartisanVotes = votingAnalysis.most_partisan_votes || [];
    if (mostPartisanVotes.length > 0) {
        html += '<h5 class="mt-4 mb-3"><i class="fas fa-vote-yea me-2"></i>Most Partisan Votes</h5>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-striped">';
        html += '<thead><tr><th>Roll Call</th><th>Question</th><th>Party Line Score</th></tr></thead>';
        html += '<tbody>';
        
        mostPartisanVotes.slice(0, 10).forEach(vote => {
            // Create bill title display if bill_id exists
            let billDisplay = '';
            if (vote.bill_id) {
                if (vote.bill_title) {
                    // Use the actual bill title if available
                    billDisplay = `<div class="mb-1"><strong><a href="/bill/${vote.bill_id}" target="_blank" rel="noopener noreferrer">${vote.bill_title}</a></strong></div>`;
                } else {
                    // Fallback to bill code if title not available
                    const billParts = vote.bill_id.split('-');
                    if (billParts.length >= 2) {
                        const billType = billParts[0].toUpperCase();
                        const billNumber = billParts[1];
                        const billTypeDisplay = billType === 'HR' ? 'H.R.' : billType === 'S' ? 'S.' : billType === 'HJRES' ? 'H.J.Res.' : billType === 'SJRES' ? 'S.J.Res.' : billType === 'HCONRES' ? 'H.Con.Res.' : billType === 'SCONRES' ? 'S.Con.Res.' : billType;
                        billDisplay = `<div class="mb-1"><strong><a href="/bill/${vote.bill_id}" target="_blank" rel="noopener noreferrer">${billTypeDisplay} ${billNumber}</a></strong></div>`;
                    }
                }
            }
            
            html += `
                <tr>
                    <td><strong><a href="/vote/${vote.rollcall_id}" target="_blank" rel="noopener noreferrer">${vote.rollcall_id}</a></strong></td>
                    <td>
                        ${billDisplay}
                        <div>${vote.question || 'N/A'}</div>
                    </td>
                    <td><span class="badge bg-danger">${vote.party_line_score.toFixed(1)}%</span></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
    }
    
    // Display most similar voters
    const mostSimilarVoters = memberAnalysis.most_similar_voters || [];
    if (mostSimilarVoters.length > 0) {
        html += '<h5 class="mt-4 mb-3"><i class="fas fa-users me-2"></i>Most Similar Voters</h5>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-striped">';
        html += '<thead><tr><th>Member 1</th><th>Member 2</th><th>Agreement %</th></tr></thead>';
        html += '<tbody>';
        
        mostSimilarVoters.slice(0, 10).forEach(pair => {
            const party1Class = pair.party1 ? `party-${pair.party1.toLowerCase()}` : '';
            const party2Class = pair.party2 ? `party-${pair.party2.toLowerCase()}` : '';
            
            html += `
                <tr>
                    <td><span class="member-chip ${party1Class}">${pair.member1} (${pair.party1})</span></td>
                    <td><span class="member-chip ${party2Class}">${pair.member2} (${pair.party2})</span></td>
                    <td><span class="badge bg-success">${pair.agreement.toFixed(1)}%</span></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
    }
    
    // Display cross-party voters
    const crossPartyVoters = memberAnalysis.cross_party_voters || [];
    if (crossPartyVoters.length > 0) {
        html += '<h5 class="mt-4 mb-3"><i class="fas fa-exchange-alt me-2"></i>Cross-Party Voters</h5>';
        html += '<div class="table-responsive">';
        html += '<table class="table table-striped">';
        html += '<thead><tr><th>Member</th><th>Party</th><th>State</th><th>Cross-Party %</th><th>Cross-Party Votes</th><th>Total Votes</th></tr></thead>';
        html += '<tbody>';
        
        crossPartyVoters.slice(0, 15).forEach(member => {
            const partyClass = member.party ? `party-${member.party.toLowerCase()}` : '';
            const percentageClass = member.cross_party_percentage > 20 ? 'bg-warning' : 'bg-info';
            
            html += `
                <tr>
                    <td><span class="member-chip ${partyClass}">${member.name}</span></td>
                    <td><span class="party-badge party-${member.party.toLowerCase()}">${member.party}</span></td>
                    <td>${member.state}</td>
                    <td><span class="badge ${percentageClass}">${member.cross_party_percentage.toFixed(1)}%</span></td>
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
                    <td>${name}</td>
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
                    <td>${name}</td>
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
