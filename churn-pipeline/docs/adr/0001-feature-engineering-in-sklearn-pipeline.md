# Feature engineering lives in a persisted scikit-learn Pipeline

We keep every feature transform (categorical encoding, column selection) inside a
single scikit-learn `Pipeline` that also carries the XGBoost estimator, and we
persist that whole fitted object as the model artifact. dbt's job stops at
producing clean, typed feature columns; it does not encode or otherwise reshape
them.

The alternative — encoding categoricals in dbt and training on the encoded table
— was rejected because the API would then have to re-implement the same
transforms at serving time, and any divergence between the SQL and the serving
code causes train/serve skew. Keeping one fitted object as the single source of
truth means the API scores raw customer input with exactly the transforms the
model saw.

## Consequences

- The artifact is a pipeline, not a bare booster, so anything loading it needs
  scikit-learn and the same encoder configuration available.
- Feature logic is split: dbt owns naming/typing/joining, Python owns encoding.
  Changing a feature's type in dbt can still change the model's input, so the two
  must move together.
