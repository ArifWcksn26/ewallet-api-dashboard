# E-Wallet RESTful API & PaySphere Dashboard

Sistem backend E-Wallet REST API dan Antarmuka Frontend Dashboard modern yang dibangun menggunakan FastAPI, PostgreSQL, Redis, dan Docker untuk transaksi keuangan yang aman, akurat, dan real-time.

## Live Demo & Deployment

- **PaySphere Dashboard (Web App):** [https://ewallet-api-dashboard-production.up.railway.app/](https://ewallet-api-dashboard-production.up.railway.app/)
- **Interactive Swagger API Docs:** [https://ewallet-api-dashboard-production.up.railway.app/docs](https://ewallet-api-dashboard-production.up.railway.app/docs)

## Fitur Utama

- Double-Entry Accounting: Pencatatan mutasi berpasangan (DEBIT & CREDIT) untuk menjamin transparansi data ledger.
- Anti-Race Condition & Anti-Deadlock: Menggunakan Pessimistic Locking (SELECT FOR UPDATE) dengan urutan ID yang konsisten.
- Mekanisme Idempotency: Validasi header Idempotency-Key via Redis (TTL 24 jam) untuk mencegah eksekusi ganda pada Top-up dan Transfer.
- Keamanan Otentikasi & PIN Keuangan: Hashing password Argon2id, token JWT (Access & Refresh), dan otorisasi PIN 6-digit untuk transfer dana.
- Manajemen Kontak Favorit: Menyimpan, melihat, dan menghapus daftar penerima transfer (Saved Beneficiaries).
- UI Dashboard Glassmorphism: Dashboard interaktif dengan fitur pencarian mutasi, filter tipe transaksi, preset nominal cepat, dan toggle visibilitas saldo.
- Performa Tinggi: Operasi database berbasis Asynchronous I/O (SQLAlchemy 2.0 & asyncpg).
- Pengujian Otomatis: Integration test utuh menggunakan Pytest & HTTPX.

## Tech Stack

- Backend: Python 3.13+, FastAPI, SQLAlchemy 2.0 (Async), asyncpg, Argon2-cffi, PyJWT
- Frontend: HTML5, Modern CSS3 (Glassmorphism Dark Mode), Vanilla JavaScript (Fetch API)
- Database: PostgreSQL 16
- Cache / Idempotency: Redis 7
- Containerization: Docker & Docker Compose
- Deployment: Railway Cloud (Production)
- Testing: Pytest & Pytest-Asyncio

## Daftar Endpoint API

- POST /api/v1/auth/register : Pendaftaran akun pengguna baru
- POST /api/v1/auth/login : Autentikasi pengguna & pengambilan token JWT
- POST /api/v1/auth/pin : Setel atau perbarui 6-digit PIN Keuangan
- GET /api/v1/wallets/me : Cek saldo & profil dompet (cached via Redis)
- POST /api/v1/wallets/topup : Penambahan saldo dompet (wajib header Idempotency-Key)
- POST /api/v1/wallets/transfer : Transfer dana antar pengguna (wajib PIN Keuangan & Idempotency-Key)
- GET /api/v1/wallets/history : Riwayat mutasi saldo (dilengkapi pagination & filter tanggal)
- GET /api/v1/beneficiaries : Dapatkan daftar kontak favorit penerima
- POST /api/v1/beneficiaries : Tambah kontak favorit penerima baru
- DELETE /api/v1/beneficiaries/{id} : Hapus kontak favorit penerima
- GET /health : Cek status kesehatan sistem & koneksi database/Redis

## Cara Menjalankan Secara Lokal

1. Jalankan PostgreSQL dan Redis di Docker:
   docker compose up -d postgres redis

2. Aktifkan virtual environment dan install dependensi:
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt

3. Jalankan server aplikasi:
   uvicorn app.main:app --reload

4. Akses Dashboard Frontend Lokal di Browser:
   http://localhost:8000

5. Akses Swagger UI Dokumentasi API Lokal:
   http://localhost:8000/docs

6. Jalankan pengujian otomatis:
   python -m pytest -v
