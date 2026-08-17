const API_BASE = "/api/v1";
let currentWallet = null;
let rawTransactions = [];
let activeFilter = 'ALL';
let isBalanceHidden = false;

// Toast Notification System
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Tab Switcher
function switchTab(tab) {
    const loginForm = document.getElementById("login-form");
    const regForm = document.getElementById("register-form");
    const loginBtn = document.getElementById("tab-login-btn");
    const regBtn = document.getElementById("tab-register-btn");

    if (tab === "login") {
        loginForm.classList.remove("hidden");
        regForm.classList.add("hidden");
        loginBtn.classList.add("active");
        regBtn.classList.remove("active");
    } else {
        loginForm.classList.add("hidden");
        regForm.classList.remove("hidden");
        loginBtn.classList.remove("active");
        regBtn.classList.add("active");
    }
}

// Generate UUID for Idempotency Key
function generateUUID() {
    return 'idemp-' + 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Balance Visibility Toggle
function toggleBalanceVisibility() {
    isBalanceHidden = !isBalanceHidden;
    const balanceEl = document.getElementById("wallet-balance-display");
    const eyeIcon = document.getElementById("eye-icon");

    if (isBalanceHidden) {
        balanceEl.innerText = "••••••••";
        eyeIcon.innerText = "🙈";
    } else {
        eyeIcon.innerText = "👁️";
        if (currentWallet) {
            balanceEl.innerText = new Intl.NumberFormat('id-ID').format(currentWallet.balance);
        }
    }
}

// Preset Amount Helpers
function setTopupAmount(amount) {
    document.getElementById("topup-amount").value = amount;
}

function setTransferAmount(amount) {
    document.getElementById("transfer-amount").value = amount;
}

// Modal Backdrop Click
function closeModalOnBackdrop(event, modalId) {
    if (event.target.id === modalId) {
        closeModal(modalId);
    }
}

// Handle Register
async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById("reg-name").value;
    const email = document.getElementById("reg-email").value;
    const password = document.getElementById("reg-password").value;

    try {
        const res = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, full_name: name })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Gagal melakukan registrasi");

        showToast("Registrasi berhasil! Silakan masuk.", "success");
        switchTab("login");
        document.getElementById("login-email").value = email;
    } catch (err) {
        showToast(err.message, "error");
    }
}

// Handle Login
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Email atau kata sandi salah");

        localStorage.setItem("access_token", data.access_token);
        showToast("Login berhasil! Selamat datang.", "success");
        initDashboard();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// Handle Logout
function handleLogout() {
    localStorage.removeItem("access_token");
    document.getElementById("dashboard-section").classList.add("hidden");
    document.getElementById("auth-section").classList.remove("hidden");
    showToast("Anda telah keluar.", "success");
}

// Fetch Wallet Profile
async function fetchWalletProfile() {
    const token = localStorage.getItem("access_token");
    if (!token) return handleLogout();

    try {
        const res = await fetch(`${API_BASE}/wallets/me`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        currentWallet = data;
        
        // Initials
        const initials = data.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        document.getElementById("avatar-initials").innerText = initials;
        document.getElementById("user-display-name").innerText = data.full_name;
        document.getElementById("card-holder-name").innerText = data.full_name.toUpperCase();
        document.getElementById("card-wallet-id").innerText = data.wallet_id;

        if (!isBalanceHidden) {
            document.getElementById("wallet-balance-display").innerText = new Intl.NumberFormat('id-ID').format(data.balance);
        }

        fetchBeneficiaries();
        fetchTransactionHistory();
    } catch (err) {
        handleLogout();
    }
}

// Fetch History & Calculate Analytics
async function fetchTransactionHistory() {
    const token = localStorage.getItem("access_token");

    try {
        const res = await fetch(`${API_BASE}/wallets/history?page=1&limit=50`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (!res.ok) return;

        rawTransactions = data.items;
        calculateAnalytics(rawTransactions);
        renderHistoryTable();
    } catch (err) {
        console.error("Gagal memuat riwayat", err);
    }
}

// Calculate Stats (Inflow, Outflow, Count)
function calculateAnalytics(items) {
    let totalInflow = 0;
    let totalOutflow = 0;

    items.forEach(item => {
        const entryType = item.ledger_entry ? item.ledger_entry.entry_type : item.type;
        const amount = parseFloat(item.amount);

        if (entryType === "CREDIT" || item.type === "TOPUP") {
            totalInflow += amount;
        } else if (entryType === "DEBIT") {
            totalOutflow += amount;
        }
    });

    document.getElementById("stat-total-inflow").innerText = new Intl.NumberFormat('id-ID', {
        style: 'currency', currency: 'IDR', maximumFractionDigits: 0
    }).format(totalInflow);

    document.getElementById("stat-total-outflow").innerText = new Intl.NumberFormat('id-ID', {
        style: 'currency', currency: 'IDR', maximumFractionDigits: 0
    }).format(totalOutflow);

    document.getElementById("stat-total-count").innerText = `${items.length} Mutasi`;
}

// Filter Type Pills
function setFilterType(type, element) {
    activeFilter = type;
    document.querySelectorAll('.filter-pills .pill').forEach(p => p.classList.remove('active'));
    element.classList.add('active');
    renderHistoryTable();
}

// Search & Filter render
function filterHistory() {
    renderHistoryTable();
}

function renderHistoryTable() {
    const searchQuery = document.getElementById("search-input").value.toLowerCase();
    const tbody = document.getElementById("history-table-body");

    const filtered = rawTransactions.filter(item => {
        const entryType = item.ledger_entry ? item.ledger_entry.entry_type : item.type;
        
        // Filter type
        if (activeFilter === 'TOPUP' && item.type !== 'TOPUP') return false;
        if (activeFilter === 'DEBIT' && entryType !== 'DEBIT') return false;
        if (activeFilter === 'CREDIT' && entryType !== 'CREDIT' && item.type !== 'TOPUP') return false;

        // Search query
        const descMatch = (item.description || '').toLowerCase().includes(searchQuery);
        const refMatch = (item.reference_id || '').toLowerCase().includes(searchQuery);
        return descMatch || refMatch;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">Tidak ada transaksi ditemukan.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(item => {
        const dateStr = new Date(item.created_at).toLocaleString('id-ID');
        const entryType = item.ledger_entry ? item.ledger_entry.entry_type : item.type;
        const isCredit = entryType === "CREDIT" || item.type === "TOPUP";
        const badgeClass = item.type === "TOPUP" ? "badge-topup" : (isCredit ? "badge-credit" : "badge-debit");
        const amountClass = isCredit ? "amount-green" : "amount-red";
        const amountPrefix = isCredit ? "+" : "-";

        const formattedAmount = new Intl.NumberFormat('id-ID', {
            style: 'currency', currency: 'IDR', maximumFractionDigits: 0
        }).format(item.amount);

        const balanceAfter = item.ledger_entry ? new Intl.NumberFormat('id-ID', {
            style: 'currency', currency: 'IDR', maximumFractionDigits: 0
        }).format(item.ledger_entry.balance_after) : "-";

        return `
            <tr>
                <td>${dateStr}</td>
                <td><small style="font-family: monospace; opacity: 0.8;">${item.reference_id}</small></td>
                <td><span class="badge-pill ${badgeClass}">${entryType}</span></td>
                <td class="${amountClass}">${amountPrefix} ${formattedAmount}</td>
                <td><strong>${balanceAfter}</strong></td>
                <td>${item.description || '-'}</td>
            </tr>
        `;
    }).join('');
}

// Handle Topup
async function handleTopup(e) {
    e.preventDefault();
    const token = localStorage.getItem("access_token");
    const amount = parseFloat(document.getElementById("topup-amount").value);
    const description = document.getElementById("topup-desc").value;

    try {
        const res = await fetch(`${API_BASE}/wallets/topup`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
                "Idempotency-Key": generateUUID()
            },
            body: JSON.stringify({ amount, description })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        closeModal("topup-modal");
        showToast("Top-Up Berhasil Diproses!", "success");
        fetchWalletProfile();
    } catch (err) {
        showToast("Top-Up Gagal: " + err.message, "error");
    }
}

let pendingTransferData = null;

// Fetch Beneficiaries
async function fetchBeneficiaries() {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    try {
        const res = await fetch(`${API_BASE}/beneficiaries`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();
        if (!res.ok) return;

        const listEl = document.getElementById("beneficiaries-list");
        if (data.length === 0) {
            listEl.innerHTML = `<span class="text-muted" style="font-size: 13px;">Belum ada kontak favorit tersimpan.</span>`;
            return;
        }

        listEl.innerHTML = data.map(b => `
            <div class="contact-chip" onclick="selectBeneficiary('${b.target_wallet_id}')">
                <span>👤 ${b.nickname}</span>
                <button class="contact-delete-btn" onclick="event.stopPropagation(); deleteBeneficiary('${b.id}')" title="Hapus Kontak">&times;</button>
            </div>
        `).join('');
    } catch (err) {
        console.error("Gagal memuat kontak", err);
    }
}

function selectBeneficiary(walletId) {
    openModal('transfer-modal');
    document.getElementById("transfer-receiver").value = walletId;
    showToast("ID Dompet kontak dipilih!", "success");
}

async function handleAddContact(e) {
    e.preventDefault();
    const token = localStorage.getItem("access_token");
    const nickname = document.getElementById("contact-nickname").value;
    const target_wallet_id = document.getElementById("contact-wallet-id").value.trim();

    try {
        const res = await fetch(`${API_BASE}/beneficiaries`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ nickname, target_wallet_id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        closeModal("add-contact-modal");
        document.getElementById("contact-nickname").value = "";
        document.getElementById("contact-wallet-id").value = "";
        showToast("Kontak favorit tersimpan!", "success");
        fetchBeneficiaries();
    } catch (err) {
        showToast("Gagal menyimpan kontak: " + err.message, "error");
    }
}

async function deleteBeneficiary(id) {
    const token = localStorage.getItem("access_token");
    try {
        const res = await fetch(`${API_BASE}/beneficiaries/${id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Gagal menghapus kontak");
        showToast("Kontak berhasil dihapus.", "success");
        fetchBeneficiaries();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// Transfer Submit -> Triggers PIN Modal
function handleTransferSubmit(e) {
    e.preventDefault();
    const receiver_wallet_id = document.getElementById("transfer-receiver").value.trim();
    const amount = parseFloat(document.getElementById("transfer-amount").value);
    const description = document.getElementById("transfer-desc").value;

    pendingTransferData = { receiver_wallet_id, amount, description };
    closeModal("transfer-modal");

    // Check if user has PIN
    if (!currentWallet || !currentWallet.has_pin) {
        document.getElementById("pin-modal-title").innerText = "Buat PIN 6-Digit";
        document.getElementById("pin-modal-desc").innerText = "Akun Anda belum memiliki PIN Keuangan. Masukkan 6-digit angka untuk membuat PIN baru.";
    } else {
        document.getElementById("pin-modal-title").innerText = "Masukkan PIN Keuangan";
        document.getElementById("pin-modal-desc").innerText = "Masukkan 6-digit PIN Keuangan Anda untuk memproses transfer.";
    }

    document.getElementById("pin-input").value = "";
    openModal("pin-modal");
}

// Open Direct Set PIN Modal
function openSetPinModal() {
    document.getElementById("direct-pin-input").value = "";
    openModal("set-pin-modal");
}

async function handleDirectPinSubmit(e) {
    e.preventDefault();
    const pin = document.getElementById("direct-pin-input").value;
    const token = localStorage.getItem("access_token");

    try {
        const resPin = await fetch(`${API_BASE}/auth/pin`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ pin })
        });
        const pinData = await resPin.json();
        if (!resPin.ok) throw new Error(pinData.detail);
        
        if (currentWallet) currentWallet.has_pin = true;
        closeModal("set-pin-modal");
        showToast("PIN Keuangan 6-digit berhasil disimpan!", "success");
    } catch (err) {
        showToast("Gagal menyimpan PIN: " + err.message, "error");
    }
}

// PIN Submit
async function handlePinSubmit(e) {
    e.preventDefault();
    const pin = document.getElementById("pin-input").value;
    const token = localStorage.getItem("access_token");

    // If user hasn't set PIN, save it first
    if (!currentWallet.has_pin) {
        try {
            const resPin = await fetch(`${API_BASE}/auth/pin`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ pin })
            });
            const pinData = await resPin.json();
            if (!resPin.ok) throw new Error(pinData.detail);
            currentWallet.has_pin = true;
            showToast("PIN Keuangan 6-digit berhasil dibuat!", "success");
        } catch (err) {
            showToast("Gagal membuat PIN: " + err.message, "error");
            return;
        }
    }

    // Now execute transfer with PIN
    if (pendingTransferData) {
        executeTransfer(pendingTransferData, pin);
    }
}

async function executeTransfer(transferData, pin) {
    const token = localStorage.getItem("access_token");

    try {
        const res = await fetch(`${API_BASE}/wallets/transfer`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
                "Idempotency-Key": generateUUID()
            },
            body: JSON.stringify({ ...transferData, pin })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        closeModal("pin-modal");
        pendingTransferData = null;
        showToast("Transfer Dana Berhasil Dikirim!", "success");
        fetchWalletProfile();
    } catch (err) {
        showToast("Gagal Transfer: " + err.message, "error");
    }
}

// Copy Wallet ID
function copyWalletId() {
    if (!currentWallet) return;
    navigator.clipboard.writeText(currentWallet.wallet_id);
    showToast("ID Dompet disalin ke clipboard!", "success");
}

// Modal Helpers
function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

// Initialize Dashboard
function initDashboard() {
    const token = localStorage.getItem("access_token");
    if (token) {
        document.getElementById("auth-section").classList.add("hidden");
        document.getElementById("dashboard-section").classList.remove("hidden");
        fetchWalletProfile();
    } else {
        document.getElementById("auth-section").classList.remove("hidden");
        document.getElementById("dashboard-section").classList.add("hidden");
    }
}

// Run on page load
document.addEventListener("DOMContentLoaded", initDashboard);
