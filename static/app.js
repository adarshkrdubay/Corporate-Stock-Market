// Global State
let activeStockId = null;
let chartInstance = null;
let userBalance = 0;
let myPortfolio = [];

// Configuration
const POLL_INTERVAL_MS = 5000; // 5 seconds polling

// DOM Elements
const elStockList = document.getElementById('stock-list');
const elNewsFeed = document.getElementById('news-feed');
const elLeaderboardList = document.getElementById('leaderboard-list');
const elPortfolioList = document.getElementById('portfolio-list');
const elUserBalance = document.getElementById('user-balance');
const elPortfolioValue = document.getElementById('portfolio-value');
const elTotalNetWorth = document.getElementById('total-net-worth');
const elChartCanvas = document.getElementById('stockChart');
const elActiveStockName = document.getElementById('active-stock-name');
const elActiveStockPrice = document.getElementById('active-stock-price');
const btnBuy = document.getElementById('btn-buy');
const btnSell = document.getElementById('btn-sell');
const btnMaximize = document.getElementById('btn-maximize');
const elChartContainer = document.querySelector('.chart-container');
const inputQuantity = document.getElementById('trade-quantity');
const elTradeCostPreview = document.getElementById('trade-cost-preview');
const tradeFeedback = document.getElementById('trade-feedback');
const navUsername = document.getElementById('nav-username');
const navAdmin = document.getElementById('nav-admin');
const modalOverlay = document.getElementById('profile-modal');
const modalUsername = document.getElementById('modal-username');
const modalPortfolioList = document.getElementById('modal-portfolio-list');

// Application Core
async function initApp() {
    initChart();
    await fetchInitialData();
    setupEventListeners();

    // Start polling loop
    setInterval(pollData, POLL_INTERVAL_MS);
}

// Chart.js Setup
function initChart() {
    const ctx = elChartCanvas.getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Stock Price',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    display: false // Hide x-axis labels for clean look
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// Fetchers
async function fetchInitialData() {
    await fetchUser();
    const stocks = await fetchStocks();
    if (stocks.length > 0 && !activeStockId) {
        selectStock(stocks[0].id, stocks[0].name, stocks[0].symbol);
    }
    await fetchNews();
    await fetchPortfolio();
}

async function pollData() {
    await fetchUser();
    await fetchStocks();
    await fetchNews();
    await fetchPortfolio();
    await fetchLeaderboard();
    if (activeStockId) {
        await updateChartExtrema(activeStockId);
    }
}

// API Calls & Rendering
async function fetchUser() {
    try {
        const res = await fetch('/api/user');
        const user = await res.json();
        userBalance = user.balance;
        elUserBalance.textContent = `& ${userBalance.toFixed(2)}`;

        if (navUsername) navUsername.textContent = user.username;
        if (navAdmin && user.is_admin) {
            navAdmin.style.display = 'inline';
        }
    } catch (e) {
        console.error("Error fetching user data", e);
    }
}

async function fetchStocks() {
    try {
        const res = await fetch('/api/stocks');
        const stocks = await res.json();
        renderStockList(stocks);
        return stocks;
    } catch (e) {
        console.error("Error fetching stocks", e);
        return [];
    }
}

async function fetchPortfolio() {
    try {
        const res = await fetch('/api/portfolio');
        myPortfolio = await res.json();
        renderPortfolio(myPortfolio);
    } catch (e) {
        console.error("Error fetching portfolio", e);
    }
}

async function fetchNews() {
    try {
        const res = await fetch('/api/news');
        const news = await res.json();
        renderNewsAndAlerts(news);
    } catch (e) {
        console.error("Error fetching news", e);
    }
}

async function fetchLeaderboard() {
    try {
        const res = await fetch('/api/leaderboard');
        const data = await res.json();
        renderLeaderboard(data);
    } catch (e) {
        console.error("Error fetching leaderboard", e);
    }
}

async function updateChartExtrema(stockId) {
    try {
        const res = await fetch(`/api/stocks/${stockId}/history`);
        const history = await res.json();

        // Update Chart Data
        const labelsDate = history.map(h => new Date(h.timestamp));
        const labels = labelsDate.map(d => d.toLocaleString());
        const data = history.map(h => h.price);

        chartInstance.data.labels = labels;
        chartInstance.data.datasets[0].data = data;

        let txData = Array(labels.length).fill(null);
        try {
            const txRes = await fetch(`/api/transactions/${stockId}`);
            if(txRes.ok) {
                const txs = await txRes.json();
                txs.forEach(tx => {
                    if(tx.type === 'BUY') {
                        const txTime = new Date(tx.timestamp).getTime();
                        let closestIdx = -1;
                        let minDiff = Infinity;
                        labelsDate.forEach((ld, idx) => {
                            const diff = Math.abs(ld.getTime() - txTime);
                            if(diff < minDiff) { minDiff = diff; closestIdx = idx; }
                        });
                        if(closestIdx !== -1) {
                            txData[closestIdx] = tx.price;
                        }
                    }
                });
            }
        } catch(e) { }

        // Remove old buy markers if exist
        if(chartInstance.data.datasets.length > 1) {
            chartInstance.data.datasets.pop();
        }

        // Push the scatter pin points dataset
        if(txData.some(val => val !== null)) {
            chartInstance.data.datasets.push({
                type: 'line',
                label: 'Bought At',
                data: txData,
                backgroundColor: '#f59e0b',
                borderColor: '#f59e0b',
                borderWidth: 0,
                pointStyle: 'triangle',
                pointRadius: 10,
                pointHoverRadius: 12,
                showLine: false,
                fill: false
            });
        }

        // Color based on trend
        if (data.length >= 2) {
            const first = data[0];
            const last = data[data.length - 1];
            if (last >= first) {
                chartInstance.data.datasets[0].borderColor = '#10b981'; // Green
                chartInstance.data.datasets[0].backgroundColor = 'rgba(16, 185, 129, 0.1)';
            } else {
                chartInstance.data.datasets[0].borderColor = '#ef4444'; // Red
                chartInstance.data.datasets[0].backgroundColor = 'rgba(239, 68, 68, 0.1)';
            }
        }
        // Enable horizontal history sliding if data gets too dense
        const chartInner = document.getElementById('chart-inner');
        if (chartInner) {
            const pxPerPoint = window.innerWidth <= 768 ? 15 : 10; // 15px per point on mobile
            const targetWidth = data.length * pxPerPoint;

            // Only force widen if the data requires more space than the container provides
            chartInner.style.minWidth = `max(100%, ${targetWidth}px)`;

            // Scroll to the newest data point (far right) if this is a newly opened stock or we are already scrolled to the right
            const wrapper = document.querySelector('.chart-wrapper');
            const distFromRight = wrapper.scrollWidth - wrapper.scrollLeft - wrapper.clientWidth;
            if (wrapper.scrollLeft === 0 || distFromRight < 50) {
                setTimeout(() => { wrapper.scrollLeft = wrapper.scrollWidth; }, 10);
            }
        }

        chartInstance.update();

        const boughtStock = myPortfolio.find(p => p.stock_id === stockId);
        let qtyStr = boughtStock ? ` | Holding: ${boughtStock.quantity}` : '';
        if (data.length > 0) {
            elActiveStockPrice.textContent = `& ${data[data.length - 1].toFixed(2)}${qtyStr}`;
            updateCostPreview();
        }
    } catch (e) {
        console.error("Error fetching chart history", e);
    }
}

// Render Functions
function renderStockList(stocks) {
    // Check if empty
    if(stocks.length === 0) return;

    // Rebuild or update
    elStockList.innerHTML = '';

    stocks.forEach(stock => {
        const item = document.createElement('div');
        item.className = `stock-item ${stock.id === activeStockId ? 'active' : ''}`;
        item.onclick = () => selectStock(stock.id, stock.name, stock.symbol);

        // Simple percent diff calculation (approx)
        const diff = stock.current_price - stock.base_price;
        const pct = (diff / stock.base_price) * 100;
        const trendClass = pct >= 0 ? 'text-up' : 'text-down';
        const trendSign = pct >= 0 ? '+' : '';

        item.innerHTML = `
            <div class="stock-info">
                <span class="stock-symbol">${stock.symbol}</span>
                <span class="stock-name" title="${stock.name}">${stock.name}</span>
            </div>
            <div class="stock-price-info">
                <div class="stock-current-price">& ${stock.current_price.toFixed(2)}</div>
                <div class="stock-trend ${trendClass}">${trendSign}${pct.toFixed(2)}%</div>
            </div>
        `;
        elStockList.appendChild(item);
    });
}

function renderPortfolio(portfolio) {
    if (portfolio.length === 0) {
        elPortfolioList.innerHTML = '<div class="empty-state">No stocks in your portfolio yet.</div>';
        elPortfolioValue.textContent = '& 0.00';
        elTotalNetWorth.textContent = `& ${userBalance.toFixed(2)}`;
        return;
    }

    elPortfolioList.innerHTML = '';
    let totalPortfolioValue = 0;

    portfolio.forEach(item => {
        const currentVal = item.quantity * item.current_price;
        const totalCost = item.quantity * item.avg_buy_price;
        const pl = currentVal - totalCost;
        const plPct = (pl / totalCost) * 100;
        const trendClass = pl >= 0 ? 'text-up' : 'text-down';
        const trendSign = pl >= 0 ? '+' : '';
        const btnColor = pl >= 0 ? 'var(--color-up)' : 'var(--color-down)';
        const borderColor = pl >= 0 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)';

        totalPortfolioValue += currentVal;

        const div = document.createElement('div');
        div.className = 'portfolio-item';
        div.innerHTML = `
            <div class="port-header">
                <span>${item.symbol} (${item.quantity} Qty)</span>
                <span class="${trendClass}">${trendSign}& ${Math.abs(pl).toFixed(2)} (${plPct.toFixed(2)}%)</span>
            </div>
            <div class="port-details" style="grid-template-columns: 1fr; gap: 4px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Invested:</span>
                    <span style="color: white;">& ${totalCost.toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Current Value:</span>
                    <span style="color: white;">& ${currentVal.toFixed(2)}</span>
                </div>
            </div>
            <div class="quick-sell-bar" style="display:flex; align-items:center; justify-content:space-between; margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05);">
                <div style="display:flex; align-items:center; background: rgba(0,0,0,0.4); border-radius: 4px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">
                    <input type="number" id="qs-qty-${item.stock_id}" value="${item.quantity}" min="1" max="${item.quantity}"
                        style="width: 50px; text-align: center; padding: 6px; border: none; background: transparent; color: white; outline: none; font-family: inherit;"
                        oninput="document.getElementById('qs-prev-${item.stock_id}').textContent = '& ' + (this.value * ${item.current_price}).toFixed(2)">
                    <button class="btn btn-sell" style="padding: 6px 14px; font-size: 0.75rem; border-radius: 0; border: none; font-weight: 600; margin: 0; box-shadow: none; background: ${btnColor}; color: white; transition: 0.2s;" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'" onclick="executePortfolioSell(${item.stock_id})">SELL</button>
                </div>
                <div style="text-align: right;">
                    <span style="display: block; font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase;">Est. Return</span>
                    <span id="qs-prev-${item.stock_id}" style="font-size: 0.85rem; color: ${btnColor}; font-weight: 600;">& ${currentVal.toFixed(2)}</span>
                </div>
            </div>
        `;
        elPortfolioList.appendChild(div);
    });

    elPortfolioValue.textContent = `& ${totalPortfolioValue.toFixed(2)}`;
    elTotalNetWorth.textContent = `& ${(userBalance + totalPortfolioValue).toFixed(2)}`;
}

let lastNewsIdFrame = [];
function renderNewsAndAlerts(news) {
    if (news.length === 0) {
        elNewsFeed.innerHTML = '<div class="empty-state">No recent news.</div>';
        return;
    }

    const currentListStr = news.map(n=>n.id).join(',');
    const prevListStr = lastNewsIdFrame.join(',');

    // Only rebuild DOM if new news arrived, saves continuous repaints
    if(currentListStr !== prevListStr) {
        elNewsFeed.innerHTML = '';
        news.forEach(n => {
            const time = new Date(n.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const div = document.createElement('div');
            div.className = 'news-item';
            div.innerHTML = `
                <div class="news-meta">
                    <span style="font-weight:600; color:var(--accent-primary)">${n.symbol}</span>
                    <span>${time}</span>
                </div>
                <div class="news-headline">${n.headline}</div>
            `;
            elNewsFeed.appendChild(div);
        });
        lastNewsIdFrame = news.map(n=>n.id);
    }
}

function renderLeaderboard(data) {
    if(data.length === 0) {
        elLeaderboardList.innerHTML = '<div class="empty-state">No ranked players.</div>';
        return;
    }

    elLeaderboardList.innerHTML = '';
    data.forEach((player, idx) => {
        const rank = idx + 1;
        let rankClass = rank <= 3 ? `rank-${rank}` : '';

        const isMe = navUsername && navUsername.textContent === player.username;
        const myStyle = isMe ? 'background: rgba(255,255,255,0.05); border-color: var(--accent-primary); cursor: pointer;' : 'cursor: pointer;';

        const div = document.createElement('div');
        div.className = 'leaderboard-item';
        div.style = myStyle;
        div.onclick = () => openProfileModal(player.username);
        div.innerHTML = `
            <div class="rank-badge ${rankClass}">${rank}</div>
            <div class="player-info">
                <div class="player-name">${player.username} ${isMe ? '(You)' : ''}</div>
            </div>
            <div class="player-worth">& ${player.profit.toFixed(2)}</div>
        `;
        elLeaderboardList.appendChild(div);
    });
}

// Modal Logic
async function openProfileModal(username) {
    modalOverlay.style.display = 'flex';
    modalUsername.textContent = `${username}'s Portfolio`;
    modalPortfolioList.innerHTML = '<div class="loading">Loading holdings...</div>';

    try {
        const res = await fetch(`/api/user/${username}/portfolio`);
        if(!res.ok) {
            modalPortfolioList.innerHTML = '<div class="empty-state">Could not fetch portfolio.</div>';
            return;
        }
        const portfolio = await res.json();

        if (portfolio.length === 0) {
            modalPortfolioList.innerHTML = '<div class="empty-state">No stocks in portfolio yet.</div>';
            return;
        }

        modalPortfolioList.innerHTML = '';
        portfolio.forEach(item => {
            const currentVal = item.quantity * item.current_price;
            const totalCost = item.quantity * item.avg_buy_price;
            const pl = currentVal - totalCost;
            const trendClass = pl >= 0 ? 'text-up' : 'text-down';
            const trendSign = pl >= 0 ? '+' : '';

            const div = document.createElement('div');
            div.className = 'portfolio-item';
            div.innerHTML = `
                <div class="port-header">
                    <span>${item.symbol}</span>
                    <span class="${trendClass}">${trendSign}& ${Math.abs(pl).toFixed(2)}</span>
                </div>
                <div class="port-details">
                    <span>Qty: ${item.quantity}</span>
                    <span>Val: <span class="port-val">& ${currentVal.toFixed(2)}</span></span>
                </div>
            `;
            modalPortfolioList.appendChild(div);
        });
    } catch (e) {
        modalPortfolioList.innerHTML = '<div class="empty-state">Error fetching portfolio.</div>';
    }
}

function closeProfileModal() {
    modalOverlay.style.display = 'none';
}

function switchTab(tabId) {
    const tabNews = document.getElementById('tab-news');
    const tabLeader = document.getElementById('tab-leader');
    const panelNews = document.getElementById('news-feed');
    const panelLeader = document.getElementById('leaderboard-list');

    if(tabId === 'news') {
        tabNews.classList.add('active');
        tabLeader.classList.remove('active');
        panelNews.style.display = 'block';
        panelLeader.style.display = 'none';
    } else {
        tabLeader.classList.add('active');
        tabNews.classList.remove('active');
        panelLeader.style.display = 'block';
        panelNews.style.display = 'none';
    }
}

// Interactions
function updateCostPreview() {
    if (!activeStockId) return;
    const qty = parseInt(inputQuantity.value) || 0;
    if (chartInstance && chartInstance.data.datasets[0].data.length > 0) {
        const dataArr = chartInstance.data.datasets[0].data;
        const currentPrice = dataArr[dataArr.length - 1];
        const total = (currentPrice * qty).toFixed(2);
        elTradeCostPreview.textContent = `Total Est: & ${total}`;
    }
}

function selectStock(id, name, symbol) {
    activeStockId = id;
    elActiveStockName.textContent = `${name} (${symbol})`;
    // Force a chart update immediately
    updateChartExtrema(id);
    // Refresh stock list for active style
    fetchStocks();

    // Mobile Tab Auto-Switch
    if (window.innerWidth <= 768) {
        const tradeBtn = document.querySelector('.bottom-tab-btn:nth-child(2)');
        if (typeof switchMobileTab === 'function') {
            switchMobileTab('trade', tradeBtn);
        }
    }
}

function setupEventListeners() {
    btnBuy.addEventListener('click', () => executeTrade('buy'));
    btnSell.addEventListener('click', () => executeTrade('sell'));
    inputQuantity.addEventListener('input', updateCostPreview);

    if(btnMaximize) {
        btnMaximize.addEventListener('click', () => {
            elChartContainer.classList.toggle('chart-maximized');
            if(elChartContainer.classList.contains('chart-maximized')) {
                btnMaximize.textContent = '✖';
                btnMaximize.title = 'Minimize Chart';
            } else {
                btnMaximize.textContent = '⛶';
                btnMaximize.title = 'Toggle Fullscreen';
            }
            if (chartInstance) chartInstance.resize();
        });
    }
}

async function executeTrade(type) {
    if (!activeStockId) return showFeedback('Select a stock first', 'error');

    const qty = parseInt(inputQuantity.value);
    if (isNaN(qty) || qty <= 0) return showFeedback('Invalid quantity', 'error');

    try {
        // Disable buttons
        btnBuy.disabled = true; btnSell.disabled = true;

        const res = await fetch(`/api/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_id: activeStockId, quantity: qty })
        });

        const data = await res.json();

        if (res.ok) {
            const verb = type === 'buy' ? 'Bought' : 'Sold';
            showFeedback(`${verb} ${qty} shares!`, 'success');
            // Force quick visual update
            pollData();
        } else {
            showFeedback(data.error || 'Trade failed', 'error');
        }
    } catch (e) {
        showFeedback('Network error', 'error');
    } finally {
        btnBuy.disabled = false; btnSell.disabled = false;
        inputQuantity.value = '1';
    }
}

function showFeedback(msg, type) {
    tradeFeedback.textContent = msg;
    tradeFeedback.className = `feedback-msg feedback-${type}`;
    setTimeout(() => { tradeFeedback.textContent = ''; }, 3000);
}

async function executePortfolioSell(stockId) {
    const qtyInput = document.getElementById(`qs-qty-${stockId}`);
    const qty = parseInt(qtyInput.value);
    if (isNaN(qty) || qty <= 0) return showFeedback('Invalid quantity', 'error');

    try {
        const res = await fetch(`/api/sell`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_id: stockId, quantity: qty })
        });

        const data = await res.json();

        if (res.ok) {
            showFeedback(`Quick Sold ${qty} shares!`, 'success');
            pollData();
        } else {
            showFeedback(data.error || 'Trade failed', 'error');
        }
    } catch (e) {
        showFeedback('Network error', 'error');
    }
}

// Start
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    if (window.innerWidth <= 768) {
        const leftSidebar = document.querySelector('.left-sidebar');
        if (leftSidebar) leftSidebar.classList.add('active-mobile-view');
    }
});

// Mobile Bottom Nav Control
function switchMobileTab(view, btnEl) {
    const leftSidebar = document.querySelector('.left-sidebar');
    const centerContent = document.querySelector('.center-content');
    const rightSidebar = document.querySelector('.right-sidebar');

    if (leftSidebar) leftSidebar.classList.remove('active-mobile-view');
    if (centerContent) centerContent.classList.remove('active-mobile-view');
    if (rightSidebar) rightSidebar.classList.remove('active-mobile-view');

    const allBtns = document.querySelectorAll('.bottom-tab-btn');
    allBtns.forEach(b => b.classList.remove('active'));

    if(btnEl) btnEl.classList.add('active');

    if (view === 'market' && leftSidebar) {
        leftSidebar.classList.add('active-mobile-view');
    } else if (view === 'trade' && centerContent) {
        centerContent.classList.add('active-mobile-view');
    } else if (view === 'news' && rightSidebar) {
        rightSidebar.classList.add('active-mobile-view');
    }
}

fetch('/api/market-status')
  .then(res => res.json())
  .then(data => {
    console.log(data.status);

    if (data.status === "CLOSED") {
        alert("Market Closed 🚫");
        // disable buttons
    }
  });