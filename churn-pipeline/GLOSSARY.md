# churn-pipeline

A local analytics platform that lands bank customer records in DuckDB, transforms
them with dbt, and scores each customer's likelihood of churning with an XGBoost
model. It exists to make churn prediction a repeatable, inspectable pipeline
rather than a one-off notebook.

## Language

**Customer**:
A bank customer, uniquely identified by `CustomerId`.
_Avoid_: Account, user, client

**Churn**:
The binary outcome for a Customer leaving the bank, recorded in the `Exited`
column (1 = left, 0 = stayed).
_Avoid_: Attrition, cancellation, closure

**Churn score**:
The model's estimated probability, between 0 and 1, that a Customer will churn.
_Avoid_: Churn probability, risk

**Predicted churn**:
The boolean label produced by applying the decision threshold to a Churn score.
_Avoid_: Churn flag, churn result

**Snapshot**:
The source data is a single static snapshot of Customers with no time dimension.
Predictions describe association within that snapshot, not a forecast of future
behaviour.
_Avoid_: Time series, history, cohort

**Feature**:
An input column the model uses to produce a Churn score. The feature set
excludes the identifier (`CustomerId`), the row index (`RowNumber`), and
`Surname`.
_Avoid_: Variable, predictor, attribute

**Champion**:
The single registered model version currently served by the API, identified by
the `@champion` alias in the MLflow Model Registry.
_Avoid_: Production, live, latest
