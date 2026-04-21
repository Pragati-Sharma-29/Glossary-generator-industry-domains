# ERP & Supply Chain Glossary

Grounded in SAP ECC/S4HANA master and transactional tables, Oracle EBS,
and GS1 EPCIS supply-chain events. Use for material, procurement,
manufacturing, and logistics datasets.

---

## Material / Item

A physical or service item tracked in the ERP. SAP: **MATNR**. Identified
by internal material number; may also carry a GTIN for trade items.

- **Synonyms:** Part, Article, SKU, Component
- **Typical columns:** `material_id`, `matnr`, `item_id`, `part_number`

## Material Group

A classification of Materials used for reporting and purchasing strategy.

- **Typical columns:** `material_group`, `matkl`, `commodity_code`

## Bill of Materials (BOM)

A hierarchical list of component Materials required to produce a parent
Material.

- **Typical columns:** `bom_id`, `parent_material`, `component_material`,
  `quantity`

## Plant

A manufacturing or distribution location in the ERP. SAP: **WERKS**.

- **Synonyms:** Site, Facility
- **Typical columns:** `plant`, `plant_code`, `werks`, `site_id`

## Storage Location

A subdivision of a Plant used to track inventory more granularly.

- **Typical columns:** `storage_location`, `lgort`, `bin_id`

## Vendor / Supplier

A Party from whom Materials or services are procured. SAP: **LIFNR**.

- **Synonyms:** Supplier, Merchant
- **Typical columns:** `vendor_id`, `lifnr`, `supplier_id`

## Purchase Requisition

An internal request to procure Materials, preceding a Purchase Order.

- **Typical columns:** `requisition_id`, `pr_number`, `banfn`

## Purchase Order (PO)

A formal order placed with a Vendor for Materials at agreed terms. SAP:
**EKKO/EKPO**.

- **Typical columns:** `po_id`, `po_number`, `ebeln`

## Goods Receipt

The recording of Materials arriving from a Vendor against a PO; increases
inventory.

- **Typical columns:** `goods_receipt_id`, `gr_document`, `receipt_date`

## Invoice

A Vendor's demand for payment for Materials delivered. SAP: **RBKP/RSEG**.

- **Typical columns:** `invoice_id`, `invoice_number`, `belnr`

## Sales Order

A confirmed order from a Customer to be fulfilled by the enterprise.
SAP: **VBAK/VBAP**.

- **Typical columns:** `sales_order_id`, `so_number`, `vbeln`

## Delivery

A record of outbound shipment of Materials against a Sales Order.

- **Typical columns:** `delivery_id`, `delivery_number`, `lifex`

## Shipment / Consignment

A set of Deliveries transported together; may carry an SSCC identifier.

- **Typical columns:** `shipment_id`, `sscc`, `consignment_id`,
  `tracking_number`

## Inventory Movement

A logged change to Material stock: receipt, issue, transfer, scrap,
return. SAP: **MSEG**.

- **Synonyms:** Stock Movement, Goods Movement
- **Typical columns:** `movement_type`, `movement_id`, `bwart`

## Stock On Hand

The quantity of a Material physically available at a Storage Location.

- **Synonyms:** Inventory Level, Available Stock
- **Typical columns:** `stock_quantity`, `on_hand_qty`, `labst`

## Lot / Batch

A production or inbound batch of a Material, traceable for recall and
expiry. In pharma/food, required.

- **Typical columns:** `batch`, `lot_number`, `charg`

## Serial Number

A unique identifier for a single unit of a Material, used for warranty
and traceability.

- **Typical columns:** `serial_number`, `sernr`

## Work Order / Production Order

An instruction to produce a Material via a specified routing using listed
components.

- **Typical columns:** `work_order_id`, `production_order`, `aufnr`

## Routing / Operation

A sequence of Operations on Work Centers required to produce a Material.

- **Typical columns:** `routing_id`, `operation_id`, `work_center`

## Work Center

A capacity resource (machine, line, crew) at which production Operations
execute.

- **Typical columns:** `work_center`, `arbpl`, `resource_id`

## UOM (Unit of Measure)

The unit in which a Material quantity is expressed: EA, KG, L, BOX, PLT.

- **Typical columns:** `uom`, `unit`, `unit_of_measure`, `meins`

## GTIN, GLN, SSCC

GS1 standard identifiers for trade item, location, and shipping container
respectively — see retail glossary. In ERP they appear on Material master,
Plant/Warehouse records, and Shipment documents.

## EPCIS Event

A GS1-standard supply-chain event record: ObjectEvent, AggregationEvent,
TransactionEvent, TransformationEvent. Captures what/when/where/why of
a movement.

- **Typical columns:** `event_id`, `event_type`, `event_time`,
  `biz_step`, `disposition`, `read_point`, `biz_location`

## Biz Step

The EPCIS business process step during which an Event occurred: shipping,
receiving, commissioning, decommissioning, packing.

- **Typical columns:** `biz_step`, `business_step`

## Disposition

The EPCIS post-Event state of the object: in_transit, in_progress,
active, damaged, destroyed, sold.

- **Typical columns:** `disposition`, `status`

---

# ERP / Supply Chain Metrics & KPIs

SCOR-model and APICS-standard operational measures. Surface as
``related_terms`` on Material, Inventory, and Order entities.

## Inventory Turnover

`COGS / average inventory value`. Annualized.

- **Related entities:** Material, Inventory
- **Typical columns:** `inventory_turns`, `turnover_ratio`

## Days Inventory Outstanding (DIO)

`365 / Inventory Turnover`. Days of inventory on hand.

- **Related entities:** Material, Inventory
- **Typical columns:** `dio`, `days_inventory`

## Days Sales Outstanding / Payables Outstanding (DSO / DPO)

Receivables / payables cycle times. Part of the cash conversion cycle.

- **Related entities:** Invoice, Sales Order
- **Typical columns:** `dso`, `dpo`

## Cash Conversion Cycle

`DIO + DSO − DPO`. Working-capital efficiency.

- **Related entities:** Invoice, Material
- **Typical columns:** `ccc`, `cash_cycle`

## On-Time Delivery (OTD)

Share of Deliveries completed by their promised date.

- **Related entities:** Delivery, Sales Order
- **Typical columns:** `otd`, `on_time_flag`

## Perfect Order Rate

Orders delivered complete, on time, damage-free, and with correct
documentation.

- **Related entities:** Sales Order, Delivery
- **Typical columns:** `perfect_order_rate`

## Order Fulfillment Cycle Time

Hours or days from Sales Order entry to Delivery completion.

- **Related entities:** Sales Order, Delivery
- **Typical columns:** `cycle_time`, `fulfillment_cycle_hours`

## Stock-out Rate / Fill Rate

Share of order lines that couldn't be filled from inventory on the
first attempt (stock-out), or conversely filled from stock (fill rate).

- **Related entities:** Inventory, Material
- **Typical columns:** `stockout_rate`, `fill_rate`

## Gross Margin Return on Investment (GMROI)

`Gross margin / average inventory cost`. Combines margin with
inventory efficiency.

- **Related entities:** Material, Inventory
- **Typical columns:** `gmroi`

## Supplier Defect Rate / PPM

Defective parts per million received from a Vendor. Quality metric.

- **Related entities:** Vendor, Goods Receipt
- **Typical columns:** `defect_ppm`, `supplier_defect_rate`

## Manufacturing Cycle Time

Time from Work Order release to production completion.

- **Related entities:** Work Order, Work Center
- **Typical columns:** `cycle_time`, `mfg_cycle_time`

## Overall Equipment Effectiveness (OEE)

`Availability × Performance × Quality`. Manufacturing productivity.

- **Related entities:** Work Center, Work Order
- **Typical columns:** `oee`, `availability`, `performance`,
  `quality_rate`
