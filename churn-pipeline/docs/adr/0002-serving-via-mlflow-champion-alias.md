# The API serves whichever model carries the `@champion` alias

Training registers every model version in the MLflow Model Registry under
`churn_xgboost`, and the API loads the version aliased `@champion` rather than a
fixed run ID or the newest run. Promotion to `@champion` is an explicit step.

We chose this over pinning a run ID — which turns every retrain into a code
change — and over "always load the newest version" — which lets an unvetted model
reach the API the moment any run finishes. The alias gives the API a stable
serving contract while keeping promotion a deliberate, reversible act.
