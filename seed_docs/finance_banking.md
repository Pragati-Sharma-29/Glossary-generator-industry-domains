# Finance & Banking Glossary

Grounded in the **FIBO (Financial Industry Business Ontology)** published
by the EDM Council, supplemented with FINOS CDM concepts for trade
lifecycle and ACORD for insurance. Use when the dataset relates to
banking, capital markets, trading, lending, or insurance.

---

## Party

Any entity (person, organization, or system) capable of entering into a
financial agreement. The root concept in FIBO from which Customer,
Counterparty, Issuer, and similar roles derive.

- **Synonyms:** Entity, Legal Entity, Principal
- **Typical columns:** `party_id`, `entity_id`, `lei`, `counterparty_id`

## Legal Entity (LEI)

A 20-character alphanumeric code (ISO 17442) uniquely identifying a
legally distinct entity participating in a financial transaction.

- **Typical columns:** `lei`, `legal_entity_id`

## Customer

A Party with whom the financial institution has an account or
relationship. In retail banking this is typically a natural person; in
commercial banking it is a legal entity.

- **Synonyms:** Client, Accountholder
- **Typical columns:** `customer_id`, `client_id`, `cif_number`

## Account

A record of financial assets or liabilities held on behalf of a Customer
by a financial institution. FIBO classifies accounts as Deposit, Loan,
Credit, or Investment.

- **Synonyms:** Relationship, Facility
- **Typical columns:** `account_id`, `account_number`, `iban`

## IBAN (International Bank Account Number)

ISO 13616 standard account identifier used in international payments,
encoding country, check digits, and bank + account number.

- **Typical columns:** `iban`

## Account Balance

The monetary position of an Account at a point in time. Distinguish
ledger balance, available balance, and pending balance.

- **Typical columns:** `balance`, `ledger_balance`, `available_balance`,
  `current_balance`

## Transaction

A single recorded movement of monetary value between Accounts. Has a
direction (debit/credit), amount, currency, timestamp, and typically a
narrative or counterparty.

- **Synonyms:** Posting, Entry, Ledger Entry
- **Typical columns:** `transaction_id`, `txn_id`, `posting_id`,
  `entry_id`

## Debit / Credit

The direction of a Transaction. Debit increases assets or decreases
liabilities for the posting Account; Credit does the opposite.

- **Typical columns:** `debit_amount`, `credit_amount`, `direction`,
  `dr_cr_flag`

## Currency

The unit of monetary value, expressed as an ISO 4217 three-letter code
(USD, EUR, GBP, JPY).

- **Typical columns:** `currency`, `ccy`, `currency_code`

## Payment

The Transaction-level execution of transferring value from payer Account
to payee Account. Classified by rail (SWIFT, SEPA, ACH, Wire, Card).

- **Typical columns:** `payment_id`, `payment_reference`, `payment_type`,
  `payment_rail`

## Loan

A credit agreement under which the lender advances funds to the borrower,
repayable with interest per a schedule. Classified by purpose (mortgage,
auto, personal, commercial).

- **Synonyms:** Facility, Credit Agreement
- **Typical columns:** `loan_id`, `facility_id`, `account_id`

## Mortgage

A Loan secured by real property. Has LTV ratio, amortization schedule,
and collateral record.

- **Typical columns:** `mortgage_id`, `loan_id`, `ltv`, `collateral_value`

## Interest Rate

The periodic cost of a Loan expressed as a percentage of principal.
Distinguish nominal, effective, and APR.

- **Typical columns:** `interest_rate`, `apr`, `rate`, `coupon`

## Principal

The outstanding borrowed amount of a Loan, distinct from accrued
interest.

- **Typical columns:** `principal`, `outstanding_principal`,
  `original_principal`

## Security / Financial Instrument

A tradable financial asset: equity, bond, derivative, fund unit. FIBO's
top-level concept is **FinancialInstrument**. Identified canonically by
ISIN or CUSIP.

- **Synonyms:** Instrument, Asset
- **Typical columns:** `instrument_id`, `security_id`, `isin`, `cusip`,
  `ric`, `ticker`

## ISIN (International Securities Identification Number)

ISO 6166 twelve-character identifier for a financial instrument,
globally unique.

- **Typical columns:** `isin`

## Equity / Share

A FinancialInstrument representing ownership in a corporation.

- **Synonyms:** Stock, Share
- **Typical columns:** `ticker`, `symbol`, `share_class`

## Bond / Debt Instrument

A FinancialInstrument evidencing a loan from the holder to the issuer,
with coupon and maturity.

- **Typical columns:** `cusip`, `isin`, `maturity_date`, `coupon`

## Derivative

A FinancialInstrument whose value derives from an underlying asset or
reference rate. Subtypes: Option, Future, Swap, Forward.

- **Typical columns:** `instrument_id`, `underlying_id`, `strike`,
  `expiry`

## Trade

An agreement to exchange FinancialInstruments between two Parties on
specified terms. Distinct from the settlement that follows.

- **Synonyms:** Execution, Deal, Fill
- **Typical columns:** `trade_id`, `execution_id`, `deal_id`

## Settlement

The completion of a Trade: delivery of the Instrument against payment.
Has a settlement date (T+1, T+2).

- **Typical columns:** `settlement_id`, `settlement_date`, `value_date`

## Position

The aggregate holding of a Security by a Party at a point in time, the
result of accumulated Trades.

- **Typical columns:** `position_id`, `holding_id`, `quantity`,
  `notional`

## Market Price / Quote

The observable price of a FinancialInstrument at a point in time, given
by an exchange or venue. Distinguish bid, ask, mid, last.

- **Typical columns:** `price`, `bid`, `ask`, `last_price`, `mid_price`

## Notional Amount

The face value of a derivative or bond used to compute cash flows.
Distinct from market value.

- **Typical columns:** `notional`, `face_value`, `par_amount`

## KYC / Customer Due Diligence

Processes under which a financial institution verifies Customer identity
and risk profile. Outputs: risk rating, PEP flag, sanctions flag.

- **Typical columns:** `kyc_status`, `risk_rating`, `pep_flag`,
  `sanctions_flag`

## AML (Anti-Money-Laundering) Alert

A flagged Transaction or pattern warranting investigation under AML
regulations.

- **Typical columns:** `alert_id`, `case_id`, `alert_reason`

## Branch

A physical or logical location of a financial institution where
Transactions are initiated.

- **Typical columns:** `branch_id`, `branch_code`, `sort_code`

## Policy (Insurance)

An insurance contract between Insurer and Insured, with coverage, premium,
term, and deductible. Adjacent to finance via ACORD data standards.

- **Typical columns:** `policy_id`, `policy_number`

## Premium

The payment made by the Insured to the Insurer to maintain coverage
under a Policy.

- **Typical columns:** `premium`, `premium_amount`

## Claim

A request for benefit under an insurance Policy after a covered loss
event.

- **Typical columns:** `claim_id`, `claim_number`, `loss_event_id`

---

# Finance / Banking Metrics & KPIs

Standard regulatory and performance measures. Surfaced as
``related_terms`` on the underlying entities.

## Net Interest Margin (NIM)

`(Interest income − interest expense) / average earning assets`. Core
profitability metric for banks.

- **Related entities:** Account, Loan, Deposit
- **Typical columns:** `nim`, `net_interest_margin`

## Return on Assets (ROA) / Return on Equity (ROE)

Net income over average assets (ROA) or equity (ROE). Bank-wide
profitability.

- **Related entities:** Account, Institution
- **Typical columns:** `roa`, `roe`

## Non-Performing Loan Ratio (NPL)

`NPLs / total loans`. NPL defined by days-past-due threshold (commonly
90).

- **Related entities:** Loan
- **Typical columns:** `npl_ratio`, `non_performing_ratio`

## Loan-to-Deposit Ratio (LDR)

`Loans / deposits`. Liquidity and lending-intensity metric.

- **Related entities:** Loan, Account
- **Typical columns:** `ldr`, `loan_to_deposit`

## CET1 Capital Ratio

Common Equity Tier 1 capital divided by risk-weighted assets. Basel III
core regulatory metric.

- **Related entities:** Account, Institution
- **Typical columns:** `cet1_ratio`, `tier1_ratio`

## Liquidity Coverage Ratio (LCR)

Basel III 30-day stress liquidity metric: `HQLA / net outflows`.

- **Related entities:** Account
- **Typical columns:** `lcr`

## Cost-to-Income Ratio

`Operating expenses / operating income`. Bank operational efficiency.

- **Related entities:** Account
- **Typical columns:** `cost_to_income`, `efficiency_ratio`

## Loss Given Default (LGD) / Probability of Default (PD)

Expected-loss inputs under IRB credit-risk modeling. EL = PD × LGD × EAD.

- **Related entities:** Loan, Customer
- **Typical columns:** `pd`, `lgd`, `ead`, `expected_loss`

## Value at Risk (VaR) / Expected Shortfall (ES)

Market-risk measures on a Trade or Portfolio at a confidence interval
and horizon.

- **Related entities:** Trade, Position, FinancialInstrument
- **Typical columns:** `var_95`, `var_99`, `expected_shortfall`, `es`

## Sharpe Ratio

`(Return − risk-free rate) / return std-dev`. Risk-adjusted return for
a portfolio.

- **Related entities:** Position, Portfolio
- **Typical columns:** `sharpe`, `sharpe_ratio`

## Assets Under Management (AUM)

Total market value of client assets managed. Primary scale metric for
asset managers.

- **Related entities:** Account, Position
- **Typical columns:** `aum`

## Loss Ratio (Insurance)

`Claims paid / premiums earned`. Insurance profitability.

- **Related entities:** Policy, Claim, Premium
- **Typical columns:** `loss_ratio`

## Combined Ratio (Insurance)

Loss ratio + expense ratio. <100% = underwriting profit.

- **Related entities:** Policy, Claim
- **Typical columns:** `combined_ratio`

## Days Payables / Receivables Outstanding (DPO / DSO)

Working-capital metrics.

- **Related entities:** Transaction, Account
- **Typical columns:** `dso`, `dpo`
