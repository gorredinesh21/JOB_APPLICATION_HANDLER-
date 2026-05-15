/**
 * ===================================
 * Job Application Dashboard - JavaScript
 * ===================================
 */

// Global Variables
let allJobs = [];
let filteredJobs = [];
let isAnimating = false;
let currentFilters = {
    search: '',
    score: '',
    source: '',
    resume: ''
};

// Dashboard Configuration
const CONFIG = {
    ANIMATION_DURATION: 1000,
    DEBOUNCE_DELAY: 300,
    PARTICLE_COUNT: 8, // Reduced from 20 for performance
    API_ENDPOINTS: {
        JOBS: '/api/jobs',
        STATS: '/api/stats',
        JOB_DETAIL: '/api/job/'
    },
    KEYBOARD_SHORTCUTS: {
        SEARCH: 'ctrl+k',
        CLEAR: 'escape',
        REFRESH: 'ctrl+r'
    }
};

/**
 * Initialize Dashboard
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
});

function initializeDashboard() {
    console.log('🚀 Initializing Job Application Dashboard...');
    
    // Initialize AOS (Animate On Scroll)
    initializeAOS();
    
    // Add entrance animations
    animateEntrance();
    
    // Load initial data
    loadInitialData();
    
    // Setup event listeners
    setupEventListeners();
    
    // Add visual effects
    createParticles();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Setup periodic updates
    setupPeriodicUpdates();
    
    console.log('✅ Dashboard initialized successfully!');
}

/**
 * Initialize AOS Library
 */
function initializeAOS() {
    AOS.init({
        duration: 600, // Reduced from 1000
        once: true,
        offset: 50, // Reduced from 100
        easing: 'ease-out-cubic',
        throttleDelay: 50, // Add throttling
        debounceDelay: 50 // Add debouncing
    });
}

/**
 * Load Initial Data
 */
async function loadInitialData() {
    try {
        await Promise.all([
            loadStats(),
            loadJobs()
        ]);
        updateLastUpdated();
    } catch (error) {
        console.error('❌ Error loading initial data:', error);
        showErrorState('Failed to load dashboard data. Please refresh the page.');
    }
}

/**
 * Setup Event Listeners
 */
function setupEventListeners() {
    console.log('🔧 Setting up event listeners...');
    
    // Search and filter inputs
    const searchInput = document.getElementById('search-input');
    const scoreFilter = document.getElementById('score-filter');
    const sourceFilter = document.getElementById('source-filter');
    const resumeFilter = document.getElementById('resume-filter');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterJobs, CONFIG.DEBOUNCE_DELAY));
    }
    
    if (scoreFilter) {
        scoreFilter.addEventListener('change', filterJobs);
    }
    
    if (sourceFilter) {
        sourceFilter.addEventListener('change', filterJobs);
    }
    
    if (resumeFilter) {
        resumeFilter.addEventListener('change', filterJobs);
    }
    
    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshData);
    }
    
    // Window resize
    window.addEventListener('resize', handleResize);
    
    console.log('✅ Event listeners setup complete');
}

/**
 * Keyboard Shortcuts
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        const ctrl = e.ctrlKey || e.metaKey;
        
        // Ctrl/Cmd + K for search focus
        if (ctrl && key === 'k') {
            e.preventDefault();
            focusSearch();
        }
        
        // Escape to clear search
        if (key === 'escape') {
            clearSearch();
        }
        
        // Ctrl/Cmd + R for refresh
        if (ctrl && key === 'r') {
            e.preventDefault();
            refreshData();
        }
        
        // Number keys for quick score filtering
        if (key >= '1' && key <= '3' && !ctrl) {
            const scoreMap = { '1': '90-100', '2': '80-89', '3': '60-79' };
            const scoreFilter = document.getElementById('score-filter');
            if (scoreFilter) {
                scoreFilter.value = scoreMap[key];
                filterJobs();
            }
        }
    });
}

/**
 * Load Statistics
 */
async function loadStats() {
    console.log('📊 Loading statistics...');
    
    try {
        const response = await fetch(CONFIG.API_ENDPOINTS.STATS);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const stats = await response.json();
        
        // Animate number counting
        animateNumber('total-jobs', stats.total_jobs, 1000);
        animateNumber('avg-score', stats.avg_score, 1200);
        animateNumber('resume-count', stats.resume_count, 1400);
        
        // Calculate high score jobs
        const highScoreJobs = stats.score_distribution
            .filter(item => item.score_range === '90-100' || item.score_range === '80-89')
            .reduce((sum, item) => sum + item.count, 0);
        animateNumber('high-score-jobs', highScoreJobs, 1600);
        
        console.log('✅ Statistics loaded successfully');
        
    } catch (error) {
        console.error('❌ Error loading statistics:', error);
        throw error;
    }
}

/**
 * Load Jobs
 */
async function loadJobs() {
    console.log('💼 Loading jobs...');
    
    const loadingElement = document.getElementById('loading');
    const jobsContainer = document.getElementById('jobs-container');
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (jobsContainer) jobsContainer.style.opacity = '0';
    
    try {
        const response = await fetch(CONFIG.API_ENDPOINTS.JOBS);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        allJobs = await response.json();
        filteredJobs = [...allJobs];
        
        console.log(`✅ Loaded ${allJobs.length} jobs`);
        
        // Fade out loading, fade in jobs
        if (loadingElement) {
            loadingElement.style.opacity = '0';
            setTimeout(() => {
                loadingElement.style.display = 'none';
            }, 300);
        }
        
        if (jobsContainer) {
            jobsContainer.style.opacity = '1';
            renderJobs();
        }
        
    } catch (error) {
        console.error('❌ Error loading jobs:', error);
        
        if (loadingElement) {
            loadingElement.innerHTML = `
                <div class="alert alert-danger" style="background: rgba(239, 68, 68, 0.1); border: 2px solid rgba(239, 68, 68, 0.3); color: white;">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error loading job data. Please try refreshing.
                </div>
            `;
        }
        
        throw error;
    }
}

/**
 * Filter Jobs
 */
function filterJobs() {
    console.log('🔍 Filtering jobs...');
    
    const searchTerm = document.getElementById('search-input')?.value.toLowerCase() || '';
    const scoreFilter = document.getElementById('score-filter')?.value || '';
    const sourceFilter = document.getElementById('source-filter')?.value || '';
    const resumeFilter = document.getElementById('resume-filter')?.value || '';
    
    // Update current filters
    currentFilters = { search: searchTerm, score: scoreFilter, source: sourceFilter, resume: resumeFilter };
    
    filteredJobs = allJobs.filter(job => {
        // Search filter
        if (searchTerm) {
            const searchableText = `${job.job_title} ${job.company_name} ${job.location}`.toLowerCase();
            if (!searchableText.includes(searchTerm)) return false;
        }
        
        // Score filter
        if (scoreFilter) {
            const score = job.score || 0;
            if (scoreFilter === '90-100' && score < 90) return false;
            if (scoreFilter === '80-89' && (score < 80 || score >= 90)) return false;
            if (scoreFilter === '60-79' && (score < 60 || score >= 80)) return false;
            if (scoreFilter === '0-59' && score >= 60) return false;
        }
        
        // Source filter
        if (sourceFilter && job.source !== sourceFilter) return false;
        
        // Resume filter
        if (resumeFilter === 'available' && !job.resume_exists) return false;
        if (resumeFilter === 'unavailable' && job.resume_exists) return false;
        
        return true;
    });
    
    console.log(`📋 Filtered ${filteredJobs.length} jobs from ${allJobs.length} total`);
    renderJobs();
}

/**
 * Render Jobs
 */
function renderJobs() {
    console.log('🎨 Rendering jobs...');
    
    const container = document.getElementById('jobs-container');
    if (!container) return;
    
    if (filteredJobs.length === 0) {
        renderEmptyState(container);
        return;
    }
    
    // Use document fragment for better performance
    const fragment = document.createDocumentFragment();
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = filteredJobs.map((job, index) => createJobCard(job, index)).join('');
    
    while (tempDiv.firstChild) {
        fragment.appendChild(tempDiv.firstChild);
    }
    
    // Clear and append efficiently
    container.innerHTML = '';
    container.appendChild(fragment);
    
    // Re-initialize AOS for new elements
    AOS.refresh();
    
    console.log(`✅ Rendered ${filteredJobs.length} job cards`);
}

/**
 * Create Job Card HTML
 */
function createJobCard(job, index) {
    const scoreClass = getScoreClass(job.score);
    const applyUrl = job.apply_url?.trim() || null;
    
    return `
        <div class="job-card" 
             data-aos="fade-up" 
             data-aos-delay="${index * 50}" 
             data-job-id="${job.job_unique_id}"
             onclick="handleJobCardClick(event, '${job.job_unique_id}')">
            <div class="row align-items-center">
                <div class="col-md-1">
                    <div class="company-logo" onclick="animateCompanyLogo(event, this)">
                        ${job.company_name.charAt(0).toUpperCase()}
                    </div>
                </div>
                <div class="col-md-7">
                    <h5 class="fw-bold mb-2 job-title" onclick="highlightText(event, this)">
                        ${job.job_title}
                    </h5>
                    <p class="text-muted mb-2">
                        <i class="fas fa-building me-2"></i>${job.company_name}
                        ${job.location && job.location !== 'Not specified' ? 
                            `<i class="fas fa-map-marker-alt ms-3 me-2"></i>${job.location}` : ''}
                    </p>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="source-badge" onclick="animateBadge(event, this)">${job.source}</span>
                        ${job.resume_exists ? 
                            '<span class="resume-badge" onclick="animateBadge(event, this)"><i class="fas fa-file-pdf me-1"></i>Resume Ready</span>' : 
                            '<span class="badge bg-secondary">No Resume</span>'}
                        ${job.experience_required?.trim() ? 
                            `<span class="badge bg-info">${job.experience_required}</span>` : ''}
                    </div>
                </div>
                <div class="col-md-2 text-center">
                    <div class="score-badge ${scoreClass} mb-2" onclick="animateScore(event, this)">
                        ${job.score || 'N/A'}
                    </div>
                    <small class="text-muted">Match Score</small>
                </div>
                <div class="col-md-2 text-end">
                    <div class="btn-group-vertical" role="group">
                        <a href="/job/${job.job_unique_id}" 
                           class="btn btn-outline-primary btn-sm mb-2" 
                           onclick="animateButton(event, this)">
                            <i class="fas fa-eye me-1"></i>View Details
                        </a>
                        ${applyUrl ? 
                            `<a href="${applyUrl}" target="_blank" class="btn btn-outline-success btn-sm mb-2" onclick="animateButton(event, this)">
                                <i class="fas fa-external-link-alt me-1"></i>Apply
                            </a>` : ''}
                        ${job.resume_exists ? 
                            `<a href="/download/resume/${job.resume_filename}" class="btn btn-outline-danger btn-sm" onclick="animateButton(event, this)">
                                <i class="fas fa-download me-1"></i>Resume
                            </a>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Empty State
 */
function renderEmptyState(container) {
    container.innerHTML = `
        <div class="text-center py-5" data-aos="fade-up">
            <div class="empty-state">
                <i class="fas fa-search fa-4x mb-3"></i>
                <h4>No jobs found</h4>
                <p>Try adjusting your filters or search terms</p>
                <button onclick="clearFilters()" class="btn btn-primary-custom mt-3">
                    <i class="fas fa-redo me-2"></i>Clear Filters
                </button>
            </div>
        </div>
    `;
}

/**
 * Get Score Class
 */
function getScoreClass(score) {
    if (score >= 80) return 'score-high';
    if (score >= 60) return 'score-medium';
    return 'score-low';
}

/**
 * Animation Functions
 */
function animateNumber(elementId, targetValue, duration) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const startValue = 0;
    const startTime = performance.now();
    
    function updateNumber(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const currentValue = Math.floor(startValue + (targetValue - startValue) * easeOutQuart);
        
        element.textContent = currentValue;
        
        if (progress < 1) {
            requestAnimationFrame(updateNumber);
        }
    }
    
    requestAnimationFrame(updateNumber);
}

function animateEntrance() {
    const elements = document.querySelectorAll('.stat-card, .filter-section');
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        setTimeout(() => {
            el.style.transition = 'all 0.6s ease';
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

function createParticles() {
    const container = document.querySelector('.dashboard-container');
    if (!container) return;
    
    // Create particles efficiently with requestAnimationFrame
    const fragment = document.createDocumentFragment();
    
    for (let i = 0; i < CONFIG.PARTICLE_COUNT; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.cssText = `
            position: absolute;
            width: 3px;
            height: 3px;
            background: linear-gradient(135deg, #8B0000, #DC143C);
            border-radius: 50%;
            pointer-events: none;
            opacity: 0.2;
            animation: float ${10 + Math.random() * 15}s infinite ease-in-out;
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            animation-delay: ${Math.random() * 5}s;
        `;
        fragment.appendChild(particle);
    }
    
    container.appendChild(fragment);
}

// Interactive Animation Functions
function animateCompanyLogo(event, element) {
    event.stopPropagation();
    element.style.transform = 'rotate(360deg) scale(1.2)';
    element.style.transition = 'transform 0.6s ease';
    setTimeout(() => {
        element.style.transform = 'rotate(0deg) scale(1)';
    }, 600);
}

function animateBadge(event, element) {
    event.stopPropagation();
    element.style.transform = 'scale(1.2)';
    element.style.transition = 'transform 0.2s ease';
    setTimeout(() => {
        element.style.transform = 'scale(1)';
    }, 200);
}

function animateScore(event, element) {
    event.stopPropagation();
    element.style.transform = 'scale(1.1) rotate(5deg)';
    element.style.transition = 'transform 0.3s ease';
    setTimeout(() => {
        element.style.transform = 'scale(1) rotate(0deg)';
    }, 300);
}

function animateButton(event, element) {
    event.stopPropagation();
    element.style.transform = 'scale(0.95)';
    element.style.transition = 'transform 0.1s ease';
    setTimeout(() => {
        element.style.transform = 'scale(1)';
    }, 100);
}

function highlightText(event, element) {
    event.stopPropagation();
    element.style.color = '#DC143C';
    element.style.transition = 'color 0.3s ease';
    setTimeout(() => {
        element.style.color = '';
    }, 1000);
}

/**
 * Event Handlers
 */
function handleJobCardClick(event, jobId) {
    // Optional: Handle card click (e.g., navigate to details)
    console.log('Job card clicked:', jobId);
}

function focusSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.focus();
        searchInput.select();
    }
}

function clearSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
        filterJobs();
    }
}

function clearFilters() {
    document.getElementById('search-input').value = '';
    document.getElementById('score-filter').value = '';
    document.getElementById('source-filter').value = '';
    document.getElementById('resume-filter').value = '';
    filterJobs();
}

async function refreshData() {
    console.log('🔄 Refreshing data...');
    
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Refreshing...';
    }
    
    try {
        await loadInitialData();
        showNotification('Data refreshed successfully!', 'success');
    } catch (error) {
        showNotification('Failed to refresh data', 'error');
    } finally {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt me-2"></i>Refresh';
        }
    }
}

/**
 * Utility Functions
 */
function updateLastUpdated() {
    const now = new Date();
    const element = document.getElementById('last-updated');
    if (element) {
        element.textContent = now.toLocaleString();
    }
}

function handleResize() {
    // Handle responsive layout changes
    clearTimeout(window.resizeTimer);
    window.resizeTimer = setTimeout(() => {
        AOS.refresh();
    }, 250);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        animation: slideInRight 0.3s ease;
    `;
    notification.innerHTML = `
        <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
        ${message}
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

function showErrorState(message) {
    const container = document.getElementById('jobs-container');
    if (container) {
        container.innerHTML = `
            <div class="text-center py-5">
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle fa-4x mb-3" style="color: rgba(239, 68, 68, 0.7);"></i>
                    <h4 style="color: rgba(239, 68, 68, 0.9);">Error</h4>
                    <p style="color: rgba(239, 68, 68, 0.7);">${message}</p>
                    <button onclick="refreshData()" class="btn btn-primary-custom mt-3">
                        <i class="fas fa-redo me-2"></i>Try Again
                    </button>
                </div>
            </div>
        `;
    }
}

/**
 * Periodic Updates
 */
function setupPeriodicUpdates() {
    // Update last updated time every minute
    setInterval(updateLastUpdated, 60000);
    
    // Optional: Auto-refresh data every 5 minutes
    // setInterval(refreshData, 300000);
}

/**
 * Add slide animations
 */
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Export functions for global access
window.dashboardFunctions = {
    animateCompanyLogo,
    animateBadge,
    animateScore,
    animateButton,
    highlightText,
    clearFilters,
    refreshData,
    filterJobs
};
