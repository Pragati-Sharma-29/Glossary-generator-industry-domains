# Retail & E-commerce Glossary

Grounded in Google Cloud Retail API, GS1 identifier standards, schema.org
commerce vocabulary, and common e-commerce data models (commercetools,
Shopify, TheLook).

---

## Customer

A person or organization that purchases or is eligible to purchase goods or
services from the retailer. Unique across the retailer's records; may be
anonymous (guest) or authenticated.

- **Synonyms:** Buyer, Shopper, Account Holder, Consumer
- **Typical columns:** `customer_id`, `user_id`, `buyer_id`, `account_id`
- **Related terms:** Loyalty Member, Guest, Household, Contact

## Loyalty Member

A Customer enrolled in the retailer's rewards program. Identified by a
loyalty number distinct from any payment identity.

- **Synonyms:** Rewards Member, Club Member
- **Typical columns:** `loyalty_id`, `member_id`, `rewards_number`, `tier`

## Session

A single continuous period of user interaction with a digital storefront,
usually bounded by inactivity timeout (commonly 30 minutes).

- **Synonyms:** Visit, Browse Session
- **Typical columns:** `session_id`, `visit_id`, `ga_session_id`

## Event

A user-triggered action recorded by the storefront: view, click,
add-to-cart, search, purchase, remove-from-cart, wishlist-add. In Cloud
Retail API this maps to the **UserEvent** resource.

- **Synonyms:** Interaction, Hit, Action
- **Typical columns:** `event_id`, `hit_id`, `event_type`, `event_name`
- **Common event types:** `add-to-cart`, `purchase-complete`,
  `detail-page-view`, `home-page-view`, `search`, `category-page-view`,
  `checkout-start`, `add-to-wishlist`

## Product

A sellable item in the catalog. Identified canonically by a **GTIN**
(Global Trade Item Number, a GS1 standard — UPC/EAN/ISBN are variants).
Separate from SKU which is retailer-internal.

- **Synonyms:** Item, Article, Catalog Item
- **Typical columns:** `product_id`, `item_id`, `gtin`, `upc`, `ean`, `isbn`

## SKU (Stock Keeping Unit)

The retailer-internal identifier for a specific purchasable product
variant (size × color × etc.). Many SKUs can share one GTIN.

- **Synonyms:** Variant ID, Article Number
- **Typical columns:** `sku`, `variant_id`, `sku_number`

## Category

A hierarchical taxonomy node used to organize Products. Typically multiple
levels deep (Department → Category → Subcategory).

- **Synonyms:** Department, Taxonomy, Classification
- **Typical columns:** `category`, `category_id`, `department`, `taxonomy`

## Brand

The trademark or manufacturer name associated with a Product.

- **Typical columns:** `brand`, `brand_name`, `manufacturer`

## Price

The monetary value at which a Product is offered. Distinguish list price
(MSRP) from sale price from per-unit cost.

- **Synonyms:** List Price, Retail Price, Unit Price
- **Typical columns:** `price`, `list_price`, `sale_price`, `unit_price`,
  `cost`, `msrp`

## Inventory

The count of available units of a SKU at a location. Zero-valued rows are
significant (out-of-stock).

- **Synonyms:** Stock, On Hand
- **Typical columns:** `inventory_count`, `stock_on_hand`, `available_qty`

## Cart

A collection of intended Products a shopper has selected prior to
checkout. An open cart is distinct from an abandoned or converted cart.

- **Synonyms:** Basket, Bag
- **Typical columns:** `cart_id`, `basket_id`

## Order

A confirmed purchase transaction. In Cloud Retail API this is the
**PurchaseTransaction**. Has line items (OrderItems) and fulfillment state.

- **Synonyms:** Transaction, Purchase, Sale
- **Typical columns:** `order_id`, `transaction_id`, `purchase_id`,
  `order_number`

## Order Item (Line Item)

A single line within an Order: one SKU × quantity × unit price.

- **Synonyms:** Line Item, Order Line
- **Typical columns:** `order_item_id`, `line_item_id`, `line_id`

## Order Status

The fulfillment state of an Order: placed, paid, picked, shipped,
delivered, returned, cancelled, refunded.

- **Synonyms:** Fulfillment Status, State
- **Typical columns:** `status`, `order_status`, `fulfillment_state`

## Payment Method

The tender used to settle an Order: credit card, debit, wallet, gift card,
store credit, cash, BNPL.

- **Typical columns:** `payment_method`, `payment_type`, `tender_type`

## Shipping Address

The destination where the Order is delivered. Distinct from Billing
Address.

- **Typical columns:** `shipping_address`, `ship_to_address`,
  `delivery_address`

## Billing Address

The address associated with the payment method.

- **Typical columns:** `billing_address`, `bill_to_address`

## Discount / Promotion

A reduction applied to an Order or Order Item, typically triggered by a
promo code, loyalty tier, or automatic rule.

- **Synonyms:** Coupon, Promo, Offer
- **Typical columns:** `discount_amount`, `promo_code`, `coupon_code`,
  `promotion_id`

## Return / RMA

A reversal of a purchase: one or more Order Items returned to the
retailer for refund or exchange.

- **Synonyms:** Refund, Reversal
- **Typical columns:** `return_id`, `rma_number`, `refund_id`

## Traffic Source

The channel that brought a user to the site: direct, organic search,
paid search, social, email, referral.

- **Synonyms:** Channel, Medium, Source
- **Typical columns:** `traffic_source`, `source`, `channel`, `medium`,
  `utm_source`

## URI / Page Path

The URL path of the page the user is on during an Event.

- **Synonyms:** Page, URL, Path
- **Typical columns:** `uri`, `page_path`, `url`, `page_location`

## User Agent / Device Type

Classification of the device used: desktop, mobile, tablet, app.

- **Typical columns:** `user_agent`, `device_type`, `device_category`,
  `browser`

## Fulfillment

The operational process of picking, packing, and shipping an Order.

- **Typical columns:** `warehouse_id`, `fulfillment_center`, `dc_id`,
  `tracking_number`, `carrier`

## GTIN (Global Trade Item Number)

GS1 standard numeric identifier for a trade item. Includes UPC-A (12
digits), EAN-13 (13 digits), and GTIN-14. Globally unique across
manufacturers.

- **Variants:** UPC, EAN, ISBN, JAN

## GLN (Global Location Number)

GS1 standard identifier for a physical or legal location: store, warehouse,
company entity, pickup point.

- **Typical columns:** `gln`, `location_id`, `store_id`, `warehouse_id`

## SSCC (Serial Shipping Container Code)

GS1 18-digit identifier for a logistics unit (pallet, carton) in
transit.

- **Typical columns:** `sscc`, `shipping_container_id`

---

# Retail / E-commerce Metrics & KPIs

Standard derived measures commonly computed from the entities above. The
agent surfaces these as ``related_terms`` on the parent entity (e.g.
AOV and Conversion Rate appear under Order).

## Gross Merchandise Value (GMV)

Total monetary value of Orders placed over a period, before refunds and
cancellations. `SUM(order.total)` over window.

- **Related entities:** Order, Order Item
- **Typical columns:** `gmv`, `gross_sales`

## Net Revenue

GMV minus returns, refunds, and discounts. The revenue figure that flows
to finance.

- **Related entities:** Order, Return
- **Typical columns:** `net_revenue`, `net_sales`

## Average Order Value (AOV)

`GMV / number of Orders`. Key monetization metric.

- **Related entities:** Order
- **Typical columns:** `aov`

## Conversion Rate

`Orders / Sessions` over a window. Measures funnel efficiency.

- **Related entities:** Session, Order
- **Typical columns:** `conversion_rate`, `cvr`

## Cart Abandonment Rate

`1 - (Orders from carts / carts created)`. High values flag checkout
friction.

- **Related entities:** Cart, Order
- **Typical columns:** `abandonment_rate`

## Click-Through Rate (CTR)

`Clicks / Impressions` for a product or ad placement.

- **Related entities:** Event, Product
- **Typical columns:** `ctr`, `click_through_rate`

## Revenue per Visitor (RPV)

`GMV / Sessions`. Combines conversion × AOV into one number.

- **Related entities:** Session
- **Typical columns:** `rpv`, `revenue_per_session`

## Customer Lifetime Value (CLV / LTV)

Predicted total Net Revenue from a Customer across their full
relationship.

- **Related entities:** Customer, Loyalty Member
- **Typical columns:** `clv`, `ltv`

## Customer Acquisition Cost (CAC)

Marketing spend divided by new Customers acquired. Pairs with CLV for
unit economics.

- **Related entities:** Customer, Campaign
- **Typical columns:** `cac`

## Repeat Purchase Rate

Share of Customers who place more than one Order in a window.

- **Related entities:** Customer, Order
- **Typical columns:** `repeat_rate`, `repeat_purchase_rate`

## Return Rate

`Returns / Orders` (count or value basis).

- **Related entities:** Return, Order
- **Typical columns:** `return_rate`

## Sell-Through Rate

Units sold divided by units received over a window. Measures inventory
velocity for a SKU.

- **Related entities:** Product, Inventory, Order Item
- **Typical columns:** `sell_through`, `sell_through_rate`

## Inventory Turnover

`Cost of goods sold / average Inventory value`. Annualized.

- **Related entities:** Inventory, Order Item
- **Typical columns:** `turnover`, `inventory_turns`

## Days Sales of Inventory (DSI)

`365 / Inventory Turnover`. Days to sell the average inventory.

- **Related entities:** Inventory
- **Typical columns:** `dsi`, `days_sales_inventory`

## Gross Margin

`(Net Revenue − COGS) / Net Revenue`. Profitability per unit sold.

- **Related entities:** Order Item, Product
- **Typical columns:** `gross_margin`, `margin_pct`

## Net Promoter Score (NPS)

Share of promoters minus share of detractors from customer surveys.
Customer-experience benchmark.

- **Related entities:** Customer
- **Typical columns:** `nps`
