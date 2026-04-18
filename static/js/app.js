function formatVersion(v) {
    if (!v || v === 'Unchecked') return '';
    return /^\d/.test(v) ? 'v' + v : v;
}

function f95tracker() {
    return {
        searchQuery: '',
        filter: 'all',
        activeTab: 0,
        tabs: [],
        sortBy: localStorage.getItem('f95tracker_sortBy') || 'added_on',
        sortDir: localStorage.getItem('f95tracker_sortDir') || 'desc',
        viewMode: localStorage.getItem('f95tracker_view') || 'grid',
        showAddModal: false,
        refreshing: false,
        games: window.__GAMES__ || [],
        gameIds: new Set(window.__GAME_IDS__ || []),
        toasts: [],
        stats: {
            total: 0,
            updated: 0,
            installed: 0,
            finished: 0,
        },
        addTab: 'url',
        addUrl: '',
        addLoading: false,
        addError: '',
        searchQ: '',
        searchCategory: 'games',
        searchResults: [],
        searchLoading: false,
        customName: 'Custom game',

        get filteredGames() {
            let g = [...this.games];
            if (this.activeTab !== 0) {
                g = g.filter(x => x.tab === this.activeTab);
            }
            if (this.filter === 'updated') g = g.filter(x => x.updated);
            else if (this.filter === 'installed') g = g.filter(x => x.installed);
            else if (this.filter === 'finished') g = g.filter(x => x.finished);
            else if (this.filter === 'archived') g = g.filter(x => x.archived);
            else if (this.filter.startsWith('status:')) {
                const s = parseInt(this.filter.split(':')[1]);
                g = g.filter(x => x.status === s);
            }
            else if (this.filter.startsWith('type:')) {
                const t = parseInt(this.filter.split(':')[1]);
                g = g.filter(x => x.type === t);
            }
            if (this.searchQuery) {
                const q = this.searchQuery.toLowerCase();
                g = g.filter(x => q.includes(x.name.toLowerCase()) || x.name.toLowerCase().includes(q) || (x.developer && x.developer.toLowerCase().includes(q)));
            }
            const dir = this.sortDir === 'desc' ? -1 : 1;
            g.sort((a, b) => {
                let va, vb;
                if (this.sortBy === 'name') { va = a.name.toLowerCase(); vb = b.name.toLowerCase(); }
                else if (this.sortBy === 'score') { va = a.score; vb = b.score; }
                else if (this.sortBy === 'last_updated') { va = a.last_updated; vb = b.last_updated; }
                else { va = a.added_on; vb = b.added_on; }
                return va < vb ? -1 * dir : va > vb ? 1 * dir : 0;
            });
            return g;
        },

        init() {
            this.loadTabs();
            this.updateStats();
            this.pollRefreshStatus();

            document.addEventListener('keydown', (e) => {
                if (e.key === 'n' && !e.ctrlKey && !e.altKey && !e.metaKey && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                    this.showAddModal = true;
                }
                if (e.key === 'Escape') {
                    this.showAddModal = false;
                }
            });
        },

        async loadTabs() {
            try {
                const resp = await fetch('/tabs');
                this.tabs = await resp.json();
            } catch (e) { }
        },

        setTab(tabId) {
            this.activeTab = tabId;
        },

        updateStats() {
            this.stats = {
                total: this.games.length,
                updated: this.games.filter(g => g.updated).length,
                installed: this.games.filter(g => g.installed).length,
                finished: this.games.filter(g => g.finished).length,
            };
        },

        setFilter(f) {
            this.filter = f;
        },

        savePrefs() {
            localStorage.setItem('f95tracker_view', this.viewMode);
            localStorage.setItem('f95tracker_sortBy', this.sortBy);
            localStorage.setItem('f95tracker_sortDir', this.sortDir);
        },

        debouncedSearch: debounce(function() {
        }, 300),

        async refreshAll() {
            if (this.refreshing) return;
            this.refreshing = true;
            this.toast('Starting refresh...', 'info');
            try {
                const resp = await fetch('/refresh', { method: 'POST' });
                const data = await resp.json();
                if (data.ok) {
                    this.toast('Refresh started!', 'success');
                } else {
                    this.toast('Failed to start refresh', 'error');
                }
            } catch (e) {
                this.toast('Error starting refresh', 'error');
            }
            this.refreshing = false;
        },

        async pollRefreshStatus() {
            try {
                const resp = await fetch('/refresh/status');
                const data = await resp.json();
                if (data.status === 'running') {
                    this.refreshing = true;
                    const progress = data.total > 0 ? Math.round((data.done / data.total) * 100) : 0;
                    this.toast(`Refreshing: ${data.done}/${data.total} (${progress}%)`, 'info');
                } else if (data.status === 'done' && data.updated && data.updated.length > 0) {
                    this.refreshing = false;
                    this.toast(`${data.updated.length} game(s) updated!`, 'success');
                    this.reloadGames();
                    return;
                } else if (data.status.startsWith('error')) {
                    this.refreshing = false;
                    this.toast('Refresh error: ' + data.status, 'error');
                    return;
                } else {
                    this.refreshing = false;
                }
            } catch (e) { }

            if (this.refreshing) {
                setTimeout(() => this.pollRefreshStatus(), 2000);
            }
        },

        async reloadGames() {
            try {
                const resp2 = await fetch('/api/games');
                if (resp2.ok) {
                    this.games = await resp2.json();
                    this.gameIds = new Set(this.games.map(g => g.id));
                    this.updateStats();
                }
            } catch (e) { }
        },

        async addByUrl() {
            if (!this.addUrl) return;
            this.addLoading = true;
            this.addError = '';
            try {
                const resp = await fetch('/games/add-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'url=' + encodeURIComponent(this.addUrl)
                });
                const data = await resp.json();
                if (data.ok) {
                    this.toast('Game added!', 'success');
                    this.showAddModal = false;
                    this.addUrl = '';
                    this.searchQuery = '';
                    await this.reloadGames();
                } else {
                    this.addError = data.error || 'Failed to add game';
                }
            } catch (e) {
                this.addError = 'Error adding game';
            }
            this.addLoading = false;
        },

        async addByUrlUrl(url) {
            this.addLoading = true;
            try {
                const resp = await fetch('/games/add-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'url=' + encodeURIComponent(url)
                });
                const data = await resp.json();
                if (data.ok) {
                    this.toast('Game added!', 'success');
                    this.showAddModal = false;
                    this.addUrl = '';
                    this.searchQuery = '';
                    await this.reloadGames();
                } else {
                    this.toast(data.error || 'Failed to add game', 'error');
                }
            } catch (e) {
                this.toast('Error adding game', 'error');
            }
            this.addLoading = false;
        },

        async addCustom() {
            this.addLoading = true;
            try {
                const resp = await fetch('/games/add-custom', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'name=' + encodeURIComponent(this.customName)
                });
                const data = await resp.json();
                if (data.ok) {
                    this.toast('Custom game added!', 'success');
                    this.showAddModal = false;
                    this.customName = 'Custom game';
                    await this.reloadGames();
                }
            } catch (e) {
                this.toast('Error adding game', 'error');
            }
            this.addLoading = false;
        },

        async searchF95() {
            if (!this.searchQ) return;
            this.searchLoading = true;
            this.searchResults = [];
            try {
                const resp = await fetch(`/games/search?q=${encodeURIComponent(this.searchQ)}&category=${this.searchCategory}`);
                const data = await resp.json();
                this.searchResults = data.results || [];
                if (this.searchResults.length === 0) {
                    this.toast('No results found', 'warning');
                }
            } catch (e) {
                this.toast('Search error', 'error');
            }
            this.searchLoading = false;
        },

        async searchHeader() {
            if (this.searchQuery.length >= 3) {
                this.searchQ = this.searchQuery;
                this.searchCategory = 'games';
                this.addTab = 'search';
                this.showAddModal = true;
                await this.searchF95();
            }
        },

        toast(message, type = 'info') {
            const t = { message, type };
            this.toasts.push(t);
            setTimeout(() => {
                const idx = this.toasts.indexOf(t);
                if (idx !== -1) this.toasts.splice(idx, 1);
            }, 4000);
        },
    };
}

function gameDetail(game, timeline) {
    return {
        game: game,
        timeline: timeline,
        refreshing: false,
        tabs: [],

        async init() {
            try {
                const resp = await fetch('/tabs');
                this.tabs = await resp.json();
            } catch (e) { }
        },

        async updateTab() {
            await fetch(`/game/${this.game.id}/update-field`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `field=tab&value=${this.game.tab || ''}`
            });
        },

        async refreshGame() {
            this.refreshing = true;
            try {
                const resp = await fetch(`/game/${this.game.id}/refresh`, { method: 'POST' });
                const data = await resp.json();
                if (data.ok) {
                    this.toast('Game updated!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    this.toast('No updates found or error occurred', 'warning');
                }
            } catch (e) {
                this.toast('Error checking for updates', 'error');
            }
            this.refreshing = false;
        },

        async toggleField(field, event) {
            const val = event.target.checked;
            await fetch(`/game/${this.game.id}/update-field`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `field=${field}&value=${val}`
            });
            if (field === 'installed' && val) {
                this.game.installed = this.game.version;
            } else if (field === 'installed') {
                this.game.installed = '';
            }
            if (field === 'finished' && val) {
                this.game.finished = this.game.version;
            } else if (field === 'finished') {
                this.game.finished = '';
            }
        },

        async setRating(r) {
            this.game.rating = r;
            await fetch(`/game/${this.game.id}/update-field`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `field=rating&value=${r}`
            });
        },

        async saveNotes() {
            await fetch(`/game/${this.game.id}/update-field`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `field=notes&value=${encodeURIComponent(this.game.notes)}`
            });
        },

        async confirmDelete() {
            if (confirm(`Remove "${this.game.name}" from your library?`)) {
                try {
                    const resp = await fetch(`/game/${this.game.id}/delete`, { method: 'POST' });
                    const data = await resp.json();
                    if (data.ok) {
                        window.location.href = '/';
                    } else {
                        this.toast('Delete failed: ' + (data.error || 'Unknown error'), 'error');
                    }
                } catch (e) {
                    this.toast('Delete failed: ' + e.message, 'error');
                }
            }
        },

        toast(message, type = 'info') {
            // Reuse the main app's toast system
            const container = document.querySelector('.toast-container');
            if (!container) return;
            const div = document.createElement('div');
            div.className = `toast ${type}`;
            div.textContent = message;
            container.appendChild(div);
            setTimeout(() => div.remove(), 4000);
        },
    };
}

function settingsPage() {
    return {
        labels: [],

        async init() {
            await this.loadLabels();
        },

        async loadLabels() {
            try {
                const resp = await fetch('/labels');
                this.labels = await resp.json();
            } catch (e) { }
        },

        async createLabel() {
            await fetch('/labels/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'name=&color=%23696969'
            });
            await this.loadLabels();
        },

        async updateLabel(label) {
            await fetch(`/labels/${label.id}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${encodeURIComponent(label.name)}&color=${encodeURIComponent(label.color)}`
            });
        },

        async deleteLabel(id) {
            if (confirm('Delete this label?')) {
                await fetch(`/labels/${id}/delete`, { method: 'POST' });
                await this.loadLabels();
            }
        },
    };
}

function labelsManager() {
    return {
        labels: [],

        async init() {
            await this.loadLabels();
        },

        async loadLabels() {
            try {
                const resp = await fetch('/labels');
                this.labels = await resp.json();
            } catch (e) { }
        },

        async createLabel() {
            await fetch('/labels/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'name=&color=%23696969'
            });
            await this.loadLabels();
        },

        async updateLabel(label) {
            await fetch(`/labels/${label.id}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${encodeURIComponent(label.name)}&color=${encodeURIComponent(label.color)}`
            });
        },

        async deleteLabel(id) {
            if (confirm('Delete this label?')) {
                await fetch(`/labels/${id}/delete`, { method: 'POST' });
                await this.loadLabels();
            }
        },
    };
}

function tabsManager() {
    return {
        tabs: [],
        newTabName: '',
        newTabIcon: '📁',

        async init() {
            await this.loadTabs();
        },

        async loadTabs() {
            try {
                const resp = await fetch('/tabs');
                this.tabs = await resp.json();
            } catch (e) { }
        },

        async createTab() {
            const name = this.newTabName.trim() || 'New Tab';
            const resp = await fetch('/tabs/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${encodeURIComponent(name)}&icon=${encodeURIComponent(this.newTabIcon)}`
            });
            const data = await resp.json();
            if (data.ok) {
                this.newTabName = '';
                this.newTabIcon = '📁';
                await this.loadTabs();
            }
        },

        async deleteTab(id) {
            if (confirm('Delete this tab? Games in this tab will be unassigned.')) {
                await fetch(`/tabs/${id}/delete`, { method: 'POST' });
                await this.loadTabs();
            }
        },
    };
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}