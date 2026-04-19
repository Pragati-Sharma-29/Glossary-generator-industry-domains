# Healthcare Glossary

Grounded in **HL7 FHIR R4** (clinical exchange), **OMOP CDM** (observational
research), and **IDMP** (ISO 11238/11239/11240/11615/11616 — Identification of
Medicinal Products, published by the EDM Council). Use for clinical,
claims, research, or pharmaceutical datasets.

---

## Patient

A person receiving or eligible to receive healthcare services. In FHIR
this is the **Patient** resource; in OMOP this is the **Person** table.
Identified by demographic fields plus a patient identifier.

- **Synonyms:** Person, Member, Beneficiary, Subject
- **Typical columns:** `patient_id`, `person_id`, `member_id`,
  `subject_id`, `mrn`

## MRN (Medical Record Number)

The hospital-internal identifier assigned to a Patient.

- **Typical columns:** `mrn`, `medical_record_number`, `chart_number`

## Practitioner

A healthcare professional (physician, nurse, pharmacist) who provides
services. In FHIR this is **Practitioner**; in claims data this is
typically the rendering provider.

- **Synonyms:** Provider, Physician, Clinician
- **Typical columns:** `provider_id`, `practitioner_id`, `npi`,
  `physician_id`

## NPI (National Provider Identifier)

A 10-digit identifier issued by CMS to US healthcare providers.

- **Typical columns:** `npi`, `rendering_npi`, `billing_npi`

## Organization / Payer

A legal entity that provides healthcare services (hospital, clinic) or
reimburses for them (insurer, government program).

- **Typical columns:** `organization_id`, `payer_id`, `facility_id`,
  `hospital_id`

## Encounter

An interaction between a Patient and a healthcare Provider. In FHIR
this is **Encounter**; in OMOP this is **Visit Occurrence**. Classified
by type: inpatient, outpatient, emergency, telemedicine.

- **Synonyms:** Visit, Admission, Appointment
- **Typical columns:** `encounter_id`, `visit_id`, `visit_occurrence_id`,
  `admission_id`

## Admission / Discharge

The start and end of an inpatient Encounter. Discharge carries a
disposition code (home, transfer, expired, AMA).

- **Typical columns:** `admission_date`, `discharge_date`,
  `discharge_disposition`, `length_of_stay`

## Condition / Diagnosis

A clinical problem assigned to a Patient. Coded with ICD-10-CM, SNOMED
CT, or OMOP concept IDs. In FHIR this is **Condition**; in OMOP,
**Condition Occurrence**.

- **Synonyms:** Diagnosis, Problem, Complaint
- **Typical columns:** `condition_id`, `diagnosis_id`, `icd_code`,
  `icd10_code`, `snomed_code`, `primary_diagnosis`

## Observation

A measurement or assertion about a Patient at a point in time: lab
result, vital sign, assessment. Coded with LOINC.

- **Synonyms:** Lab Result, Measurement, Finding
- **Typical columns:** `observation_id`, `measurement_id`, `loinc_code`,
  `value_numeric`, `unit`, `reference_range_low`, `reference_range_high`

## Procedure

A clinical action performed on a Patient. Coded with CPT, HCPCS, or
ICD-10-PCS. In FHIR, **Procedure**; in OMOP, **Procedure Occurrence**.

- **Synonyms:** Service, Intervention
- **Typical columns:** `procedure_id`, `cpt_code`, `hcpcs_code`,
  `procedure_date`

## Medication

A pharmaceutical substance administered to or prescribed for a Patient.
Under IDMP identified as a **Medicinal Product** (MPID) with ingredients
(PhPID), pharmaceutical form, and strength.

- **Synonyms:** Drug, Pharmaceutical, Rx
- **Typical columns:** `medication_id`, `drug_id`, `ndc_code`, `rxnorm_code`

## MPID (Medicinal Product Identifier)

ISO 11615 unique identifier for a Medicinal Product, per IDMP. Distinct
from the active ingredient.

- **Typical columns:** `mpid`, `product_id`

## PhPID (Pharmaceutical Product Identifier)

IDMP identifier for a specific combination of active substances and
pharmaceutical form, independent of brand.

- **Typical columns:** `phpid`, `ingredient_id`

## Active Substance / Ingredient

The therapeutically active component of a Medication. Identified per ISO
11238 substance ID.

- **Typical columns:** `ingredient_id`, `substance_id`, `active_ingredient`

## Dose / Dosage

The quantity of a Medication administered per unit time. Includes
strength and presentation (per IDMP ISO 11240).

- **Typical columns:** `dose`, `dosage`, `strength`, `dose_quantity`,
  `dose_unit`

## Route of Administration

How a Medication is delivered: oral, intravenous, topical, subcutaneous.
Controlled vocabulary per IDMP.

- **Typical columns:** `route`, `administration_route`

## Medication Statement / Prescription

A record that a Medication has been prescribed, dispensed, or
administered to a Patient.

- **Synonyms:** Prescription, Rx Order, Drug Exposure
- **Typical columns:** `prescription_id`, `rx_id`, `drug_exposure_id`,
  `days_supply`, `quantity_dispensed`

## Claim

A request for reimbursement submitted by a Provider or Patient to a
Payer for services rendered. Follows HIPAA X12 837 format.

- **Typical columns:** `claim_id`, `claim_number`

## Claim Line

A single billable service within a Claim, with its own CPT/HCPCS code,
units, and charge.

- **Typical columns:** `claim_line_id`, `service_line_id`,
  `line_number`

## Allowed Amount / Paid Amount / Charged Amount

The money fields of a Claim Line: what the Provider billed, what the
Payer allowed under contract, and what was actually paid after
deductible/copay.

- **Typical columns:** `charged_amount`, `allowed_amount`, `paid_amount`,
  `patient_responsibility`, `copay`, `coinsurance`, `deductible`

## Coverage / Plan

The insurance product under which a Patient is a Member. Has effective
start/end dates, plan type (HMO/PPO/HDHP), and benefit structure.

- **Synonyms:** Insurance Plan, Benefit Plan
- **Typical columns:** `coverage_id`, `plan_id`, `member_id`, `group_id`

## Provider Network

The set of Practitioners and Organizations contracted to deliver care
under a Coverage plan at in-network rates.

- **Typical columns:** `network_id`, `in_network_flag`

## ICD-10 Code

International Classification of Diseases, 10th revision. The standard
diagnosis coding system (ICD-10-CM in the US for billing).

- **Typical columns:** `icd_code`, `icd10_code`, `diagnosis_code`

## CPT / HCPCS Code

Current Procedural Terminology / Healthcare Common Procedure Coding
System — US standards for procedure coding.

- **Typical columns:** `cpt_code`, `hcpcs_code`, `procedure_code`

## LOINC Code

Logical Observation Identifiers Names and Codes — the standard for
laboratory and clinical observations.

- **Typical columns:** `loinc_code`, `observation_code`, `lab_code`

## SNOMED CT Concept

Systematized Nomenclature of Medicine — Clinical Terms — a comprehensive
clinical terminology used alongside or instead of ICD.

- **Typical columns:** `snomed_code`, `snomed_concept_id`
