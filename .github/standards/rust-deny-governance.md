# Rust deny governance standard

## Model

Use a hybrid model:

- Shared baseline policy comes from `.github/standards/rust-deny-baseline.toml`.
- Each repository keeps `configs/rust/deny.toml` as the effective cargo-deny config.
- Any repo-specific difference from the shared baseline is documented in `configs/rust/deny.deviations.toml`.

## Deviation contract

`configs/rust/deny.deviations.toml` uses `[[deviation]]` rows with these required fields:

- `id`: stable identifier of the overridden policy clause.
- `owner`: responsible team or package owner.
- `reason`: concrete rationale for the deviation.
- `expiry`: ISO date (`YYYY-MM-DD`) when the deviation must be revalidated.
- `review`: URL pointing to the reviewing PR in `bijux-std`.

## Governance policy

- Empty deviations are valid and represented as `deviation = []`.
- Expired deviations fail quality gates.
- Missing fields fail quality gates.
- `review` must reference `bijux-std`.

This keeps security guarantees unified while preserving justified domain-level strictness.
