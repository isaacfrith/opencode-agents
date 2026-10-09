{#
    One row per customer, in the exact shape the model expects.

    This is the boundary between the warehouse and the model: everything is
    typed and named, but nothing is encoded. The sklearn pipeline owns encoding.
#}
select
    customer_id,
    credit_score,
    geography,
    gender,
    age,
    tenure,
    balance,
    num_of_products,
    has_cr_card,
    is_active_member,
    estimated_salary,
    exited
from {{ ref('stg_customers') }}
