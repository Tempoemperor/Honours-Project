from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# 1. Define the data model for a transaction
# This ensures that any data sent to the API matches this exact structure.
class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: float

@app.get("/")
def read_root():
    return {"message": "Welcome to the Blockchain API"}

# 2. Create a POST endpoint to receive transactions
# This route accepts a 'Transaction' object, validates it, and returns it.
@app.post("/transaction/")
def create_transaction(tx: Transaction):
    return {
        "message": "Transaction received successfully",
        "transaction_details": tx
    }