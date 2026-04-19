# CRM & Marketing Glossary

Grounded in Salesforce Sales Cloud / Service Cloud objects, HubSpot
schema, Google Ads / GA4 measurement, and generic marketing automation
platforms. Use for sales pipelines, customer service, and campaign
attribution datasets.

---

## Lead

An unqualified prospect who has shown some interest but has not been
validated as a sales opportunity. In Salesforce: **Lead** object;
converts into Account + Contact + Opportunity.

- **Synonyms:** Prospect, Inquiry
- **Typical columns:** `lead_id`, `prospect_id`

## Account

A company or organization that is a customer, partner, or competitor.
The top of the customer hierarchy in B2B CRM.

- **Synonyms:** Company, Organization, Customer Account
- **Typical columns:** `account_id`, `company_id`, `org_id`

## Contact

An individual person associated with an Account. Has email, phone,
title, and linked Activities.

- **Synonyms:** Person, Individual
- **Typical columns:** `contact_id`, `person_id`, `email`

## Opportunity

A potential revenue-generating deal with an Account. Has stage,
amount, close date, and probability.

- **Synonyms:** Deal, Pipeline Item
- **Typical columns:** `opportunity_id`, `deal_id`, `opp_id`,
  `amount`, `stage`, `close_date`, `probability`

## Pipeline Stage

The ordered step an Opportunity is in: Prospecting, Qualification,
Proposal, Negotiation, Closed Won, Closed Lost.

- **Synonyms:** Sales Stage, Deal Stage
- **Typical columns:** `stage`, `stage_name`, `pipeline_stage`

## Opportunity Amount

The expected or contracted revenue of an Opportunity. Distinguish weighted
(× probability) from unweighted.

- **Typical columns:** `amount`, `arr`, `tcv`, `mrr`, `contract_value`

## ARR / MRR

Annual / Monthly Recurring Revenue — subscription revenue metrics used
in SaaS CRM.

- **Typical columns:** `arr`, `mrr`, `recurring_revenue`

## Activity

A touchpoint with a Contact or Account: call, email, meeting, task,
note. Logs who/what/when.

- **Synonyms:** Task, Touchpoint, Engagement
- **Typical columns:** `activity_id`, `task_id`, `event_id`

## Campaign

A coordinated marketing effort tied to a goal: email blast, paid ad
flight, webinar, event. Has a budget and tracked members.

- **Typical columns:** `campaign_id`, `campaign_name`, `campaign_type`

## Campaign Member

A Lead or Contact who is a recipient or responder within a Campaign.

- **Typical columns:** `campaign_member_id`, `status`

## Case / Ticket

A service or support request raised by a Contact. Has a subject,
priority, status, and owner.

- **Synonyms:** Ticket, Incident, Support Request
- **Typical columns:** `case_id`, `ticket_id`, `incident_id`

## Case Status / Priority

The lifecycle state of a Case (New, Open, Pending, Resolved, Closed)
and its urgency (Low, Medium, High, Critical).

- **Typical columns:** `status`, `priority`, `severity`

## SLA (Service Level Agreement)

A committed response and resolution time for a Case, typically varying
by priority and customer tier.

- **Typical columns:** `sla_due_date`, `first_response_time`,
  `resolution_time`

## Owner

The internal user assigned to own a Lead, Account, Opportunity, or
Case.

- **Typical columns:** `owner_id`, `assigned_to`, `sales_rep_id`

## MQL / SQL

Marketing-Qualified Lead / Sales-Qualified Lead — scoring stages
indicating readiness to hand off between Marketing and Sales.

- **Typical columns:** `lead_status`, `qualification`, `mql_flag`,
  `sql_flag`

## Lead Source

The origin channel through which a Lead was acquired: web form, event,
referral, cold outbound, paid search.

- **Synonyms:** Source, Origin
- **Typical columns:** `lead_source`, `source`, `acquisition_channel`

## UTM Parameters

URL-embedded tracking codes (`utm_source`, `utm_medium`, `utm_campaign`,
`utm_term`, `utm_content`) used to attribute web traffic to campaigns.

- **Typical columns:** `utm_source`, `utm_medium`, `utm_campaign`,
  `utm_term`, `utm_content`

## Attribution Model

The rule used to assign credit for a conversion to touchpoints: last-click,
first-click, linear, time-decay, position-based, data-driven.

- **Typical columns:** `attribution_model`, `attribution_weight`

## Click / Impression

An ad display (Impression) and a click-through from that ad (Click).
Basic units of paid media measurement.

- **Typical columns:** `impressions`, `clicks`, `ctr`

## Conversion

A completed goal event tied to an Ad Click or Session: purchase, signup,
demo request, download.

- **Typical columns:** `conversion_id`, `conversion_value`, `goal_id`

## Session / User (GA4)

A Session is a period of continuous activity on a digital property; a
User is identified across Sessions by a client ID or user ID.

- **Typical columns:** `ga_session_id`, `user_pseudo_id`, `client_id`

## Bounce / Engagement Rate

Bounce: a Session with only one interaction. Engagement rate (GA4):
fraction of engaged Sessions.

- **Typical columns:** `bounce_rate`, `engagement_rate`,
  `engaged_sessions`

## Email Open / Click

Events recorded by marketing automation platforms tracking recipient
interaction with sent emails.

- **Typical columns:** `email_id`, `opened_at`, `clicked_at`,
  `bounced_at`, `unsubscribed_at`

## List / Segment

A named subset of Contacts/Leads defined by criteria, used as a
Campaign audience.

- **Typical columns:** `segment_id`, `list_id`, `audience_id`

## Customer Lifetime Value (CLV / LTV)

Predicted net revenue from a Customer over their entire relationship.

- **Typical columns:** `ltv`, `clv`, `customer_lifetime_value`
