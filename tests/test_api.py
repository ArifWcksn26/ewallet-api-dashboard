import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base
import uuid


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_ewallet_full_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        # 2. Register User 1 & User 2
        email1 = f"user1_{uuid.uuid4().hex[:6]}@example.com"
        email2 = f"user2_{uuid.uuid4().hex[:6]}@example.com"

        reg1 = await client.post("/api/v1/auth/register", json={
            "email": email1,
            "password": "password123",
            "full_name": "Pengguna Pertama"
        })
        assert reg1.status_code == 201, reg1.text

        reg2 = await client.post("/api/v1/auth/register", json={
            "email": email2,
            "password": "password123",
            "full_name": "Pengguna Kedua"
        })
        assert reg2.status_code == 201, reg2.text

        # 3. Login User 1 & User 2
        login1 = await client.post("/api/v1/auth/login", json={
            "email": email1,
            "password": "password123"
        })
        assert login1.status_code == 200
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        login2 = await client.post("/api/v1/auth/login", json={
            "email": email2,
            "password": "password123"
        })
        assert login2.status_code == 200
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # 4. Get Profile User 1 & User 2
        me1 = await client.get("/api/v1/wallets/me", headers=headers1)
        assert me1.status_code == 200
        wallet_id1 = me1.json()["wallet_id"]
        assert float(me1.json()["balance"]) == 0.0

        me2 = await client.get("/api/v1/wallets/me", headers=headers2)
        assert me2.status_code == 200
        wallet_id2 = me2.json()["wallet_id"]
        assert float(me2.json()["balance"]) == 0.0

        # 5. Topup User 1 with Idempotency Key
        topup_idem_key = f"topup-{uuid.uuid4().hex}"
        topup_headers = {**headers1, "Idempotency-Key": topup_idem_key}

        topup_res = await client.post(
            "/api/v1/wallets/topup",
            headers=topup_headers,
            json={"amount": 500000.00, "description": "Top-up Awal"}
        )
        assert topup_res.status_code == 201, topup_res.text
        assert float(topup_res.json()["amount"]) == 500000.00
        tx_id_topup = topup_res.json()["id"]

        # 5b. Test Idempotency: Repeat topup with SAME Idempotency-Key
        topup_repeat = await client.post(
            "/api/v1/wallets/topup",
            headers=topup_headers,
            json={"amount": 500000.00, "description": "Top-up Awal"}
        )
        assert topup_repeat.status_code == 201
        assert topup_repeat.json()["id"] == tx_id_topup  # Must return cached result!

        # 6. Test PIN Setup & Transfer with PIN
        pin_res = await client.post("/api/v1/auth/pin", headers=headers1, json={"pin": "123456"})
        assert pin_res.status_code == 200

        # Attempt Transfer with WRONG PIN -> Should fail 401
        trf_wrong_pin = await client.post(
            "/api/v1/wallets/transfer",
            headers={**headers1, "Idempotency-Key": f"trf-fail-{uuid.uuid4().hex}"},
            json={"receiver_wallet_id": wallet_id2, "amount": 100000.00, "description": "Fail PIN", "pin": "999999"}
        )
        assert trf_wrong_pin.status_code == 401

        # Transfer with CORRECT PIN -> Should succeed
        transfer_idem_key = f"trf-{uuid.uuid4().hex}"
        trf_headers = {**headers1, "Idempotency-Key": transfer_idem_key}
        trf_res = await client.post(
            "/api/v1/wallets/transfer",
            headers=trf_headers,
            json={
                "receiver_wallet_id": wallet_id2,
                "amount": 150000.00,
                "description": "Beli Kopi",
                "pin": "123456"
            }
        )
        assert trf_res.status_code == 200, trf_res.text

        # 7. Test Beneficiary Contacts API
        add_b = await client.post(
            "/api/v1/beneficiaries",
            headers=headers1,
            json={"nickname": "User 2 Fav", "target_wallet_id": wallet_id2}
        )
        assert add_b.status_code == 201
        b_id = add_b.json()["id"]

        list_b = await client.get("/api/v1/beneficiaries", headers=headers1)
        assert list_b.status_code == 200
        assert len(list_b.json()) == 1

        del_b = await client.delete(f"/api/v1/beneficiaries/{b_id}", headers=headers1)
        assert del_b.status_code == 200

        # Check balance User 1 (should be 350,000) & User 2 (should be 150,000)
        me1_after_trf = await client.get("/api/v1/wallets/me", headers=headers1)
        assert float(me1_after_trf.json()["balance"]) == 350000.00

        me2_after_trf = await client.get("/api/v1/wallets/me", headers=headers2)
        assert float(me2_after_trf.json()["balance"]) == 150000.00
