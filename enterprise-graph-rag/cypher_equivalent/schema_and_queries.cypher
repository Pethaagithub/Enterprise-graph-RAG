// ============================================================================
// Property-graph (Neo4j / Cypher) equivalent of the RDF ontology + queries.
//
// Not executed in this repo (no live Neo4j instance here) -- included to
// show the schema translation and to make the RDF-vs-property-graph
// trade-off concrete rather than abstract.
//
// KEY DIFFERENCE FROM THE RDF VERSION:
//   - RDF/OWL: relationships and attributes are both just "triples" (subject-
//     predicate-object). Reasoning (e.g. subclass inference, OWL entailment)
//     is a first-class citizen; global identity is via URIs, which makes it
//     natural to federate/link data across systems (an ERP + a CRM +
//     Workday all minting URIs in the same namespace conventions).
//   - Property graph/Cypher: nodes carry arbitrary key-value properties
//     directly (no need to reify every attribute as its own triple), and
//     relationships can themselves carry properties (e.g. a PLACES
//     relationship could carry an orderChannel property). This is usually
//     faster for multi-hop traversal queries and more natural for
//     engineers coming from a labeled-property-graph background -- but you
//     lose built-in standardized reasoning/inference and cross-vendor
//     interoperability that RDF/OWL gives you for free via shared vocabularies
//     (e.g. schema.org, SKOS) . In an enterprise semantic layer spanning many
//     source systems, this is the central design decision: RDF for
//     federation/interoperability across many external + internal sources,
//     property graphs for high-performance operational traversal once the
//     data is already harmonized.
// ============================================================================

// ---- Schema constraints (uniqueness) ----
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:SalesOrder) REQUIRE o.orderId IS UNIQUE;
CREATE CONSTRAINT invoice_id IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoiceId IS UNIQUE;

// ---- Example node/relationship creation (mirrors one customer from data/business_graph.ttl) ----
CREATE (c:Customer {id: 'customer_1', name: 'Doyle Ltd', segment: 'Enterprise', country: 'Japan'})
CREATE (o:SalesOrder {orderId: 'SO-1002', orderDate: date('2026-05-24'), status: 'Completed'})
CREATE (p:Product {name: 'CloudSuite-Pro', category: 'Software'})
CREATE (i:Invoice {invoiceId: 'INV-5002', amount: 18225.20, status: 'Unpaid', dueDate: date('2026-06-23')})
CREATE (c)-[:PLACES]->(o)
CREATE (o)-[:CONTAINS_LINE_ITEM {quantity: 12, unitPrice: 1518.77}]->(p)
CREATE (o)-[:GENERATES_INVOICE]->(i);

// ---- Q1 equivalent: overdue invoices with total owed per customer ----
MATCH (c:Customer)-[:PLACES]->(:SalesOrder)-[:GENERATES_INVOICE]->(i:Invoice {status: 'Overdue'})
RETURN c.name AS customerName, sum(i.amount) AS totalOverdue
ORDER BY totalOverdue DESC;

// ---- Q2 equivalent: revenue by segment (paid invoices only) ----
MATCH (c:Customer)-[:PLACES]->(:SalesOrder)-[:GENERATES_INVOICE]->(i:Invoice {status: 'Paid'})
RETURN c.segment AS segment, sum(i.amount) AS revenue
ORDER BY revenue DESC;

// ---- Q4 equivalent: completed orders with unpaid/overdue invoices (cash-collection risk) ----
MATCH (c:Customer)-[:PLACES]->(o:SalesOrder {status: 'Completed'})-[:GENERATES_INVOICE]->(i:Invoice)
WHERE i.status IN ['Unpaid', 'Overdue']
RETURN o.orderId, c.name AS customerName, i.status, i.amount
ORDER BY i.amount DESC;
