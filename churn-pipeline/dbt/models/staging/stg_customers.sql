{#
    Typed, renamed view over the raw landing table.

    dbt's job stops at clean typing and naming; encoding for the model happens
    in the sklearn pipeline (see docs/adr/0001-feature-engineering-in-sklearn-pipeline.md).
    RowNumber and Surname are intentionally dropped.
#}
select
    cast("CustomerId" as bigint)      as customer_id,
    cast("CreditScore" as integer)    as credit_score,
    cast("Geography" as varchar)      as geography,
    cast("Gender" as varchar)         as gender,
    cast("Age" as integer)            as age,
    cast("Tenure" as integer)         as tenure,
    cast("Balance" as double)         as balance,
    cast("NumOfProducts" as integer)  as num_of_products,
    cast("HasCrCard" as integer)      as has_cr_card,
    cast("IsActiveMember" as integer) as is_active_member,
    cast("EstimatedSalary" as double) as estimated_salary,
    cast("Exited" as integer)         as exited
from {{ source('raw', 'customers') }}
where "CustomerId" is not null
