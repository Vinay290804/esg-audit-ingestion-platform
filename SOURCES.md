# Sources

## SAP fuel and procurement

Researched format: SAP S/4 material document style exports, represented here as a CSV extract from an OData/CDS-backed material document item view rather than raw IDoc.

What I learned: material document rows carry posting context such as document reference, plant, material description, quantity, and base unit. In real SAP configurations those labels can be localized, so the sample includes German headers such as `Buchungsdatum`, `Werk`, `Menge`, and `Basismengeneinheit`.

Sample data: `sample_data/sap_material_documents.csv` includes litres, gallons, MWh, multiple date formats, an unknown plant code, and a suspiciously large diesel refill.

What would break in production: movement type logic, reversals, master-data joins, vendor-specific procurement classification, and SAP authorization are not implemented.

Reference: SAP Business Accelerator Hub material document item fields: https://api.sap.com/cdsviews/I_GOODSMOVEMENTDOCUMENTDEX/fields

## Utility electricity

Researched format: Green Button / ESPI-style usage data and utility portal exports.

What I learned: utility data is usually organized around usage points or meters, meter readings, interval blocks, usage summaries, tariff/cost information, and demand-related function blocks. Billing periods follow meter read cycles and often do not match calendar months.

Sample data: `sample_data/utility_electricity.csv` includes bill id, facility code, meter id, billing period, kWh/MWh usage, demand kW, tariff code, and total cost. One row uses a long billing period, one has high demand, and one has an unknown facility.

What would break in production: PDF bills, interval data, time-of-use tariffs, net metering, tax/fee allocation, and multiple meters per facility are not handled.

References:

- Green Button ESPI usage data schema: https://www.greenbuttonalliance.org/usage-data
- Green Button function blocks for interval, demand, cost, and retail meter data: https://www.greenbuttonalliance.org/cmd-function-blocks

## Corporate travel

Researched format: SAP Concur expense report and expense entry payloads.

What I learned: Concur-like feeds expose transaction dates, transaction currencies and amounts, expense types, spend categories, vendors, hotel dates, exceptions, and custom fields. Emissions logic varies by category: air travel uses route distance, lodging uses nights, and ground transport uses mileage or vehicle type.

Sample data: `sample_data/concur_travel_transactions.json` includes flights with airport codes and missing mileage, a hotel stay with nights, a rental car with distance, employee ids, home facility codes, amount, and currency.

What would break in production: itinerary reconciliation, duplicate card/expense rows, cabin class multipliers, missing airport pairs, travel policy exceptions, OAuth, and PII controls are not implemented.

Reference: SAP Help Portal, Concur expense report schema: https://help.sap.com/docs/SAP_CONCUR/27041ab78c844e679db485fff6f4033f/8d12726bd34f43238e04269939cfc59c.html
