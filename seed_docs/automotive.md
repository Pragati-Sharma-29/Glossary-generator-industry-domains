# Automotive Glossary

Grounded in the EDM Council Automotive ontology, schema.org's Vehicle /
automotive subtree, ISO 3779 (VIN), and common telematics / dealer
datasets.

---

## Vehicle

A motorized wheeled transport asset. In schema.org: **Vehicle** (parent
of Car, Motorcycle, BusOrCoach). Identified canonically by VIN.

- **Synonyms:** Unit, Asset
- **Typical columns:** `vehicle_id`, `vin`, `unit_number`

## VIN (Vehicle Identification Number)

ISO 3779 seventeen-character identifier uniquely assigned to each
Vehicle worldwide. Encodes manufacturer, model, year, plant, and serial.

- **Typical columns:** `vin`

## Make / Model / Trim / Model Year

Manufacturer (Make), nameplate (Model), equipment tier (Trim), and
production year.

- **Typical columns:** `make`, `model`, `trim`, `model_year`, `year`

## Body Type

Classification of vehicle form: Sedan, SUV, Coupe, Hatchback, Pickup,
Van, Wagon. schema.org uses `bodyType`.

- **Typical columns:** `body_type`, `body_style`, `segment`

## Fuel Type / Powertrain

Energy source: Gasoline, Diesel, Hybrid, PHEV, BEV, Hydrogen. schema.org:
`fuelType`.

- **Typical columns:** `fuel_type`, `powertrain`, `engine_type`

## Transmission

Drivetrain control type: Manual, Automatic, CVT, DCT.

- **Typical columns:** `transmission`, `trans_type`

## Engine Displacement

Total volume swept by all cylinders, typically in liters or cc.

- **Typical columns:** `engine_displacement`, `engine_size`,
  `displacement_liters`

## Horsepower / Torque

Peak engine output metrics.

- **Typical columns:** `horsepower`, `hp`, `torque`

## MPG / Fuel Economy

Fuel efficiency, usually in miles per gallon (US) or liters per 100 km
(EU). Separate city, highway, combined.

- **Typical columns:** `mpg_city`, `mpg_highway`, `mpg_combined`,
  `fuel_economy`, `l_per_100km`

## Odometer / Mileage

Accumulated distance driven.

- **Typical columns:** `odometer`, `mileage`, `km_driven`

## Owner

The Party holding title to the Vehicle. May differ from Operator/Driver.

- **Typical columns:** `owner_id`, `registered_owner`

## Registration / License Plate

The jurisdictional ID issued by a motor vehicle authority. Separate from
VIN.

- **Typical columns:** `license_plate`, `plate_number`, `registration_id`

## Dealer

A licensed entity that sells new or used Vehicles, often part of a
dealer group under a Make's network.

- **Typical columns:** `dealer_id`, `dealership_id`, `store_code`

## Dealer Group / OEM

The parent company operating multiple Dealers; the OEM (Original
Equipment Manufacturer) is the Make's producer.

- **Typical columns:** `dealer_group_id`, `oem`, `manufacturer`

## Inventory Vehicle

A Vehicle listed as for-sale on a Dealer's lot, distinct from a sold
Vehicle.

- **Typical columns:** `stock_number`, `inventory_id`, `status`

## Sale / Delivery

The transaction conveying ownership of a Vehicle to a Customer. Has a
sale price, financing terms, and trade-in reference.

- **Typical columns:** `sale_id`, `deal_id`, `delivery_date`,
  `sale_price`

## Trade-In

A Vehicle surrendered by the buyer as partial payment for a new Vehicle
purchase.

- **Typical columns:** `trade_in_vin`, `trade_in_value`,
  `appraised_value`

## Financing / Lease

Credit terms applied to a Sale. Loan (purchase with installment) vs
Lease (usage for a term with residual).

- **Typical columns:** `loan_id`, `lease_id`, `monthly_payment`,
  `term_months`, `residual_value`, `down_payment`, `apr`

## Warranty

The manufacturer's or extended service agreement covering defects for a
term and mileage.

- **Typical columns:** `warranty_id`, `warranty_type`,
  `warranty_end_date`, `warranty_miles`

## Service Appointment / Repair Order (RO)

A scheduled visit for maintenance or repair at a Dealer's service
department. RO is the work-order document.

- **Typical columns:** `repair_order_id`, `ro_number`,
  `appointment_id`

## Service Line / Operation

A single billable service on a Repair Order, keyed by OP code.

- **Typical columns:** `op_code`, `labor_operation`, `line_number`

## Part

A replacement or accessory component stocked by a Dealer or OEM parts
distributor.

- **Typical columns:** `part_id`, `part_number`, `oem_part_number`

## Recall

An OEM-initiated campaign to repair a safety defect in affected
Vehicles identified by VIN range.

- **Typical columns:** `recall_id`, `campaign_number`,
  `nhtsa_campaign_id`

## Telematics Event

A time-stamped data reading emitted by a connected Vehicle: GPS
location, speed, fuel level, DTC (diagnostic trouble code).

- **Typical columns:** `telematics_id`, `event_timestamp`, `latitude`,
  `longitude`, `speed`, `fuel_level`, `dtc_code`

## Diagnostic Trouble Code (DTC)

A standardized code (SAE J2012 / ISO 15031-6) reported by the vehicle's
OBD-II system identifying a fault condition.

- **Typical columns:** `dtc_code`, `fault_code`

## Driver / Operator

The person operating a Vehicle at a point in time; may differ from
Owner (fleet, rental, ride-share).

- **Typical columns:** `driver_id`, `operator_id`

## Collision / Incident

A reported crash involving a Vehicle. Severity and injury status are
commonly captured (NHTSA FARS schema).

- **Typical columns:** `incident_id`, `crash_id`, `severity`,
  `fatal_flag`, `injury_count`
