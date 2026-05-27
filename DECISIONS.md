# Decisions

## SAP

Chosen subset: CSV exported from an SAP S/4 material document item view/OData service for fuel-relevant goods movements and procurement rows.

Why: enterprise teams often land SAP data through flat extracts even when the upstream object is OData, BAPI, or IDoc. A CSV lets analysts test messy SAP realities without implementing SAP authentication. The parser handles German headers, plant codes, mixed date formats, litres/gallons/MWh, material descriptions, cost centers, and material document numbers.

Ignored: IDoc segment nesting, batch characteristics, purchase order joins, vendor master joins, SAP authorization, reversals, and movement type semantics.

PM question: do analysts need goods issue data only, or both goods receipts and invoices for procurement-backed fuel?

## Utility electricity

Chosen subset: utility portal CSV modeled after Green Button / ESPI concepts: meter, usage period, usage unit, demand, tariff code, and bill id.

Why: facilities teams commonly export utility data from portals, and Green Button gives a realistic vocabulary for UsagePoint, MeterReading, IntervalBlock, billing summaries, and demand/cost function blocks. The prototype accepts bill-period totals rather than PDF bills because PDF extraction would consume the assignment without improving the data model.

Ignored: PDF bill OCR, interval-level load curves, time-of-use allocation, multiple meters rolled into one bill, net metering, and supplier-specific tariff math.

PM question: should we ingest bill totals for audit support, interval data for operations analytics, or both?

## Travel

Chosen subset: JSON export shaped like SAP Concur expense/card transactions with transaction dates, categories, amounts, hotel nights, airport codes, and employee home facility.

Why: travel platforms expose expense-like objects with transaction metadata, expense types, spend categories, currencies, vendors, and custom fields. For emissions, the key normalization problem is category-specific logic: flights need distance from airport pairs when the feed lacks mileage, hotels use nights, and ground travel uses distance.

Ignored: OAuth, itinerary APIs, cabin-class multipliers, radiative forcing, currency conversion, employee PII controls, and duplicate matching between card feed and expense report.

PM question: are travel emissions audited from expense transactions, booked itineraries, or reconciled trips?

## Review workflow

Rows import into `pending` review. Suspicious rows stay in the same queue with flags rather than a separate error-only screen because analysts need context across all incoming data. Failed raw records are counted at batch level and not normalized.

Approved rows can be locked for audit. A locked row cannot be changed via the API.
