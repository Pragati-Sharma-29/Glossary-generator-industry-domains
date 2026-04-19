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

---

# Network Management (FCAPS + 4G/5G Core)

Grounded in TM Forum eTOM (Fault / Performance / Configuration), 3GPP TS
28/32-series, and ITU-T M.3400. Use for OSS datasets: alarm stores,
performance counter dumps, network-element inventories, handover logs,
topology, and SLA reporting.

## Network Element (NE)

A managed node on the carrier's network: eNodeB/gNodeB, router, switch,
MSC, MME, AMF, UPF, OLT. Identified by a unique NE ID and carries type,
vendor, software version, and location.

- **Synonyms:** Node, Managed Element, Device
- **Typical columns:** `ne_id`, `node_id`, `element_id`, `device_id`,
  `ne_type`, `vendor`, `sw_version`

## Configuration Item (CI) / Parameter

A configurable attribute on a Network Element (transmit power, neighbor
list, PLMN, cell ID, handover threshold). Tracked by CM systems.

- **Synonyms:** Config Parameter, MO (Managed Object)
- **Typical columns:** `ci_id`, `parameter_name`, `mo_id`,
  `attribute_name`, `current_value`, `target_value`

## Alarm

A Network Element's notification of a fault condition. Has severity,
probable cause, event time, clear time, and affected NE. 3GPP TS 32.111
defines the model.

- **Synonyms:** Fault, Notification, Event (FM sense)
- **Typical columns:** `alarm_id`, `alarm_number`, `event_time`,
  `clear_time`, `probable_cause`, `specific_problem`, `managed_object`

## Alarm Severity

The urgency classification of an Alarm: Critical, Major, Minor, Warning,
Indeterminate, Cleared (ITU-T X.733).

- **Typical columns:** `severity`, `alarm_severity`, `perceived_severity`

## Root Cause / Correlation

The underlying Alarm or condition responsible for one or more derived
alarms. Correlation engines group symptoms to a single root cause to
reduce alarm storms.

- **Typical columns:** `root_cause_id`, `correlation_id`,
  `parent_alarm_id`, `is_root_cause`

## KPI (Key Performance Indicator)

A derived network performance metric: RAN accessibility, retainability,
mobility success, integrity, availability. Aggregated from Counters per
interval.

- **Synonyms:** Metric, Performance Indicator
- **Typical columns:** `kpi_id`, `kpi_name`, `kpi_value`,
  `measurement_period`, `granularity`

## Counter / Performance Measurement (PM)

A raw counter collected from a Network Element at a measurement interval
(typically 15 min). Examples: `RRC.ConnEstabAtt`, `PDCP.UpOctUl`,
`HO.IntraFreqExecSuccNB`. Counters feed into KPIs.

- **Synonyms:** PM Counter, Performance Sample
- **Typical columns:** `counter_name`, `counter_value`, `start_time`,
  `end_time`, `period_seconds`

## Radio Quality (RSRP / RSRQ / SINR)

LTE/5G signal quality measurements: Reference Signal Received Power,
Quality, and Signal-to-Interference-plus-Noise Ratio. Captured in UE
measurement reports and drive-test data.

- **Typical columns:** `rsrp`, `rsrq`, `sinr`, `rssi`, `cqi`

## Handover

The event of a UE moving from one serving Cell to another while active.
Has source cell, target cell, type (intra-frequency, inter-frequency,
inter-RAT), and outcome (success, failure, ping-pong).

- **Synonyms:** HO, Cell Reselection (idle mode)
- **Typical columns:** `handover_id`, `source_cell`, `target_cell`,
  `ho_type`, `ho_result`, `ho_duration_ms`

## Throughput

Data rate measured over a link or session. Uplink vs downlink; peak
vs average.

- **Typical columns:** `throughput_mbps`, `dl_throughput`,
  `ul_throughput`, `peak_throughput`

## Availability / MTBF / MTTR

Reliability metrics per Network Element or Service: availability % over
a window, Mean Time Between Failures, Mean Time To Repair.

- **Typical columns:** `availability_pct`, `mtbf`, `mttr`,
  `uptime_seconds`, `downtime_seconds`

## Bearer (4G)

An EPC logical connection carrying a QoS class for a UE's PDU traffic.
Default Bearer is always-on; Dedicated Bearers carry specific QCI
traffic.

- **Typical columns:** `bearer_id`, `eps_bearer_id`, `qci`

## PDU Session (5G)

A logical 5G data connection between a UE and the UPF, carrying one or
more QoS Flows, each with a 5QI. Successor to the 4G Bearer concept.

- **Typical columns:** `pdu_session_id`, `dnn`, `snssai`,
  `qos_flow_id`, `5qi`

## Network Slice (5G)

An isolated end-to-end logical network instance identified by S-NSSAI
(Slice/Service Type + Slice Differentiator). Typical slice types:
eMBB, URLLC, mMTC.

- **Typical columns:** `slice_id`, `s_nssai`, `sst`, `sd`,
  `slice_type`

## Core Network Function (NF)

A functional block in the core network. 4G EPC: MME, SGW, PGW, HSS,
PCRF. 5G SA: AMF, SMF, UPF, UDM, PCF, NRF, AUSF.

- **Synonyms:** Network Function, Core Node
- **Typical columns:** `nf_type`, `nf_instance_id`, `nf_name`

## Topology Link

A physical or logical connection between two Network Elements:
fiber span, microwave hop, logical tunnel. Used by inventory/GIS
systems.

- **Synonyms:** Link, Span, Circuit
- **Typical columns:** `link_id`, `a_end_ne`, `z_end_ne`,
  `link_type`, `capacity_mbps`, `distance_km`

## Work Order / Change Request

A tracked operational task against the network: truck roll, software
upgrade, configuration change, capacity augment. Tied to a Change
Advisory Board (CAB) approval in mature OSS.

- **Synonyms:** Change Ticket, Task Order
- **Typical columns:** `work_order_id`, `change_id`, `crq_number`,
  `scheduled_start`, `actual_start`, `engineer_id`

## SLA Compliance

Measurement of contracted service levels against targets (availability,
latency, packet loss). Breach records drive credits or penalties.

- **Typical columns:** `sla_id`, `target_value`, `measured_value`,
  `breach_flag`, `sla_credit_amount`
