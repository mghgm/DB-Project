from fastapi import FastAPI, HTTPException, Query, Body
from decouple import config
import asyncpg
import secrets

from utils import ChargeRequest, ChargeResponse, ChargeAckRequest, ChargeAckResponse

app = FastAPI()

# PostgreSQL connection pool
DB_USER = config('DB_USER')
DB_PASSWORD = config('DB_PASSWORD')
DB_HOST = config('DB_HOST')
DB_NAME = config('DB_NAME')
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

async def get_balance(customer_phone_number: str) -> int:
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            query = "SELECT balance, customer_phone_number FROM wallet WHERE customer_phone_number = $1;"
            balance = await conn.fetchval(query, customer_phone_number)
            if balance is None:
                raise HTTPException(status_code=404, detail="Balance not found")
            return balance

@app.get("/balance")
async def balance_endpoint(customerPhoneNumber: str = Query(..., description="The user phone number")):
    try:
        balance = await get_balance(customerPhoneNumber)
        return {"customer_phone_number": customerPhoneNumber, "balance": balance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def create_charge(charge_request: ChargeRequest):
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    trx_id = await conn.fetchval("INSERT INTO transaction (status, amount) VALUES ($1, $2) RETURNING id", 'TO BE PAID', charge_request.amount)
                    token = secrets.token_hex(16)
                    await conn.execute("INSERT INTO charge (transaction_id, user_id, token) VALUES ($1, $2, $3)", trx_id, str(charge_request.user_id), token)
                    return trx_id, token
            except asyncpg.exceptions.UniqueViolationError:
                raise HTTPException(status_code=400, detail=f"Charge already exists")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating charge: {str(e)}")


ACK_URL = "http://localhost/charge_ack"
@app.post("/charge", response_model=ChargeResponse)
async def charge_endpoint(charge_request: ChargeRequest = Body(...)):
    try:
        trx_id, token = await create_charge(charge_request)
        return {"url": ACK_URL, "token": token, "trx_id": trx_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def acknowlege_charge(charge_ack_request: ChargeAckRequest):
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    trx_id = await conn.fetchval("SELECT transaction_id FROM charge WHERE user_id = $1 AND token = $2 AND transaction_id = $3",
                                                 charge_ack_request.user_id, charge_ack_request.token, charge_ack_request.trx_id)
                    if trx_id is None:
                        raise HTTPException(status_code=404, detail="No valid charge not found")

                    amount = await conn.fetchval("SELECT amount FROM transaction WHERE id = $1", trx_id)
                    await conn.execute("UPDATE transaction SET status = 'PAID' WHERE id = $1", trx_id)
                    await conn.execute("UPDATE wallet SET balance = balance + $1 WHERE customer_phone_number = $2", amount, charge_ack_request.user_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error acknowleging charge: {str(e)}")

@app.post("/charge_ack", response_model=ChargeAckResponse)
async def charge_ack_endpoint(charge_ack_request: ChargeAckRequest):
    print('sadfdsa')
    await acknowlege_charge(charge_ack_request) 

    return {"status": "verified"}

@app.get("/history", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    userId: int = Query(..., description="The user ID"),
    page: int = Query(1, description="The page number"),
    limit: int = Query(10, description="The number of items per page"),
    pool: asyncpg.Pool = Depends(get_pool)
):
    offset = (page - 1) * limit
    async with pool.acquire() as connection:
        try:
            query = """
                SELECT amount
                FROM transactions
                WHERE user_id = $1
                ORDER BY time DESC
                LIMIT $2 OFFSET $3
            """
            rows = await connection.fetch(query, userId, limit, offset)
            transactions = [
                Transaction(
                    time=row["time"].isoformat(),
                    amount=row["amount"],
                    cause=row["cause"]
                )
                for row in rows
            ]
            return {"transactions": transactions}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching transaction history: {str(e)}")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
