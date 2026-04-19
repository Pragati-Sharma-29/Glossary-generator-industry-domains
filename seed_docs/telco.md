# Telecommunications Glossary

Grounded in TM Forum SID (Shared Information/Data Model), 3GPP
specifications, and CAMARA Commonalities. Use for carrier datasets
covering subscribers, services, network events, and CDR/billing.

---

## Subscriber

An individual or organization that has agreed to receive service from a
carrier under a Subscription. TM Forum: **Party Role** playing the
subscriber role.

- **Synonyms:** Customer, Account Holder
- **Typical columns:** `subscriber_id`, `customer_id`, `msisdn`

## MSISDN

Mobile Station International Subscriber Directory Number — the publicly
dialable phone number of a mobile Subscriber.

- **Typical columns:** `msisdn`, `phone_number`

## IMSI

International Mobile Subscriber Identity — a unique identifier on a SIM
card that authenticates a Subscriber on the network.

- **Typical columns:** `imsi`, `sim_id`

## IMEI

International Mobile Equipment Identity — unique identifier for a
physical device handset.

- **Typical columns:** `imei`, `device_id`, `handset_id`

## SIM

Subscriber Identity Module — the removable or embedded chip storing
IMSI and authentication keys.

- **Typical columns:** `sim_id`, `iccid`

## Service / Subscription

The contracted package (voice, SMS, data, broadband, IPTV) purchased by
the Subscriber. TM Forum: **ProductInventory / Service**.

- **Synonyms:** Product, Plan
- **Typical columns:** `service_id`, `plan_id`, `subscription_id`

## Rate Plan / Tariff

The pricing scheme applied to a Service: per-minute, per-MB, bucket,
unlimited, tiered.

- **Typical columns:** `rate_plan_id`, `tariff_id`, `plan_code`

## CDR (Call Detail Record)

A record of a single communication event: call, SMS, or data session.
Primary source for billing and network analytics.

- **Synonyms:** Usage Record, Event Record
- **Typical columns:** `cdr_id`, `record_id`, `event_id`

## Calling / Called Party

The originator (A-party) and recipient (B-party) of a call.

- **Typical columns:** `calling_number`, `a_number`, `called_number`,
  `b_number`, `origin`, `destination`

## Call Duration

The length of a voice call, typically in seconds.

- **Typical columns:** `duration`, `call_duration`, `seconds`

## Data Volume

The bytes transferred during a data Session: uplink + downlink.

- **Typical columns:** `data_volume`, `bytes_up`, `bytes_down`,
  `total_bytes`

## Cell / Base Station

A radio access node (eNodeB/gNodeB) serving a geographic area. A CDR
includes the serving Cell to enable geolocation-based analytics.

- **Synonyms:** Tower, Node
- **Typical columns:** `cell_id`, `enb_id`, `gnb_id`, `sector`,
  `location_area_code`

## LAC / TAC

Location Area Code (2G/3G) / Tracking Area Code (LTE/5G) — groupings of
Cells used for paging.

- **Typical columns:** `lac`, `tac`

## PLMN

Public Land Mobile Network — a carrier network identified by MCC + MNC.

- **Typical columns:** `plmn`, `mcc`, `mnc`

## Roaming

A Subscriber using service on a PLMN other than their home carrier's.
CDRs are exchanged via TAP3 files for billing settlement.

- **Typical columns:** `roaming_flag`, `visited_plmn`,
  `home_plmn`

## APN (Access Point Name)

The gateway through which a device's data Session is routed, defining
connectivity profile (internet, IMS, private).

- **Typical columns:** `apn`, `access_point_name`

## QoS / 5QI

Quality of Service class identifier; in 5G, 5QI. Determines scheduling
priority and latency characteristics.

- **Typical columns:** `qos_class`, `5qi`, `qci`

## Charging Event

A rating engine input: a unit of Service consumption priced against the
Rate Plan. Online (OCS) vs offline (CDR-based).

- **Typical columns:** `charging_id`, `event_type`, `rating_group`

## Balance

The remaining credit or allowance for a prepaid Subscriber. Prepaid OCS
systems decrement balance in real time.

- **Typical columns:** `balance`, `available_balance`, `credit_remaining`

## Top-up / Recharge

An increment to a prepaid Subscriber's Balance.

- **Typical columns:** `topup_id`, `recharge_amount`,
  `recharge_channel`

## Bill / Invoice

The periodic charge summary sent to a postpaid Subscriber. Contains
recurring Plan fees plus usage-based charges.

- **Typical columns:** `bill_id`, `invoice_id`, `bill_cycle`

## Churn

The termination of a Subscriber relationship. Distinguish voluntary
(Subscriber initiated) from involuntary (non-payment).

- **Typical columns:** `churn_flag`, `churn_date`, `churn_reason`

## Service Outage / Trouble Ticket

A recorded network fault or customer-reported degradation. Has start
time, end time, affected Cells or services, root cause.

- **Typical columns:** `outage_id`, `ticket_id`, `incident_id`,
  `root_cause`

## HLR / HSS

Home Location Register (2G/3G) / Home Subscriber Server (LTE/5G) — the
central Subscriber profile repository.

## MVNO / MNO

Mobile Virtual Network Operator (resells another's radio network) vs
Mobile Network Operator (owns the radio network).

- **Typical columns:** `mvno_flag`, `network_operator`, `brand_id`
