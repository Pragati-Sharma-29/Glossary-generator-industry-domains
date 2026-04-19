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

---

# Automotive Metrics & KPIs

Dealer operations (NADA/JD-Power), OEM aftersales, and fleet/telematics
measures. Surface as ``related_terms`` on Vehicle, Sale, Repair Order,
Dealer entities.

## Sales Volume / Units Sold

Count of Sales in a period, often segmented by new vs used and by
model.

- **Related entities:** Sale, Vehicle
- **Typical columns:** `units_sold`, `sales_volume`

## Gross Margin per Vehicle

Sale price minus invoice cost, averaged per vehicle. Front-end gross
vs back-end gross (financing/warranty/add-ons).

- **Related entities:** Sale
- **Typical columns:** `front_gross`, `back_gross`,
  `gross_per_vehicle`

## Days to Close

Days from Inventory Vehicle listing to Sale. Measures lot velocity.

- **Related entities:** Inventory Vehicle, Sale
- **Typical columns:** `days_to_close`, `days_on_lot`

## Days Supply

`Inventory units / average daily sales`. Dealer stocking adequacy.

- **Related entities:** Inventory Vehicle
- **Typical columns:** `days_supply`

## Customer Satisfaction Index (CSI)

OEM-defined survey score on sales or service experience. Drives dealer
incentives.

- **Related entities:** Customer, Sale, Repair Order
- **Typical columns:** `csi`, `sales_csi`, `service_csi`

## Fixed First Visit (FFV)

Share of Repair Orders that resolved the concern without a return visit.

- **Related entities:** Repair Order
- **Typical columns:** `ffv_rate`, `fixed_first_visit`

## Service Retention Rate

Share of sold Customers who return for service over a period.

- **Related entities:** Customer, Repair Order
- **Typical columns:** `service_retention`

## Warranty Claim Rate / Warranty Cost per Vehicle

Claims per 1,000 vehicles in service; OEM quality + cost measure.

- **Related entities:** Warranty, Recall, Vehicle
- **Typical columns:** `warranty_claims_per_1000`,
  `warranty_cost_per_vehicle`

## Repair Orders per Technician / RO Hours

Productivity measures in fixed operations.

- **Related entities:** Repair Order, Service Line
- **Typical columns:** `ro_per_tech`, `flat_rate_hours`, `billed_hours`

## Floor Plan Expense

Interest cost on the dealer's inventory financing. Grows with aging
inventory.

- **Related entities:** Inventory Vehicle
- **Typical columns:** `floor_plan_expense`

## Fleet Utilization / Vehicle Availability

Time in service over total fleet time (for fleet and rental).

- **Related entities:** Vehicle, Driver
- **Typical columns:** `utilization`, `availability`

## Average Fuel Economy (Fleet)

Aggregate mpg or l/100km over a fleet and period. Telematics-derived.

- **Related entities:** Telematics Event, Vehicle
- **Typical columns:** `avg_mpg`, `fleet_mpg`

## Crash Rate / Fatality Rate

Per 100 million VMT (vehicle miles traveled). NHTSA safety metric.

- **Related entities:** Collision, Vehicle
- **Typical columns:** `crash_rate`, `fatality_rate_per_mvmt`
