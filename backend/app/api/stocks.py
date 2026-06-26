from fastapi import APIRouter


router = APIRouter()


@router.get("/stocks")

def get_stocks():

    return {"stocks": []}
