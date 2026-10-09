"""Request and response models for the scoring API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Geography(str, Enum):
    france = "France"
    germany = "Germany"
    spain = "Spain"


class Gender(str, Enum):
    male = "Male"
    female = "Female"


class CustomerInput(BaseModel):
    """A single customer, given in raw (un-encoded) terms."""

    credit_score: int = Field(..., ge=300, le=900, description="Credit score")
    geography: Geography = Field(..., description="Country of the customer")
    gender: Gender
    age: int = Field(..., ge=18, le=100)
    tenure: int = Field(..., ge=0, le=10, description="Years with the bank")
    balance: float = Field(..., ge=0, description="Account balance")
    num_of_products: int = Field(..., ge=1, le=4)
    has_cr_card: int = Field(..., ge=0, le=1)
    is_active_member: int = Field(..., ge=0, le=1)
    estimated_salary: float = Field(..., ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "credit_score": 645,
                "geography": "Spain",
                "gender": "Male",
                "age": 44,
                "tenure": 8,
                "balance": 113755.78,
                "num_of_products": 2,
                "has_cr_card": 1,
                "is_active_member": 1,
                "estimated_salary": 112542.58,
            }
        }
    }


class Prediction(BaseModel):
    churn_score: float = Field(..., ge=0, le=1, description="Probability of churn")
    predicted_churn: bool
    threshold: float
    model_version: int
