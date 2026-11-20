# PROJECT ACOM — ULTIMATE MASTER BLUEPRINT

## Version 2.0

**AI-Driven Autonomous Commerce Company | Local-First | Open-Source | One-Person Business**

| Field | Value |
|---|---|
| Project Owner | Founder / CEO |
| Operating Model | One Human + Multiple AI Agents |
| Infrastructure | Local Windows 11 + WSL2 + Docker |
| Business Model | Affiliate Commerce + Dropshipping + AI Product Discovery |
| Technology Policy | Free, Self-Hosted, Open-Source First |
| Current Stage | Local Development & Proof of Concept |
| Primary Objective | Build a profitable commerce company from zero with minimum capital and maximum AI-driven automation |

> **Document status:** APPROVED ARCHITECTURAL BASELINE — PENDING LOCAL VALIDATION.
> This file is the original intent. Where an ADR amends it, the ADR wins. Amendments
> are marked inline with `AMENDED (ADR-nnnn)`.

**Ratified amendments:**
- ADR-0001 — Affiliate engine precedes dropshipping engine (§20, §26)
- ADR-0002 — Node-RED deferred; orchestration via Frappe scheduler + Python runner (§6, §11, §20)
- ADR-0003 — Docker data-root stays on C: (disk constraint resolved) (§15)
- ADR-0004 — AI model ceiling for 4 GB VRAM / 16 GB RAM hardware (§10)

---

## 1. EXECUTIVE VISION

PROJECT ACOM is not just an e-commerce website.

It is an AI-driven commerce operating company designed to discover products, analyze markets, evaluate suppliers, publish product listings, manage customers, process orders, coordinate fulfillment, track revenue, and optimize business operations.

The company will operate with:

- One human founder acting as CEO and final decision-maker.
- AI agents handling research, marketing, content, operations, analytics, and customer support.
- Open-source ERP and automation infrastructure.
- A unified commerce platform.
- Automated workflows with approval controls for financial and high-risk activities.

### Core business objective

Generate revenue through two separate commerce channels:

**A. Affiliate Commerce**

Promote products from marketplaces such as Amazon, Flipkart, Meesho, Myntra, and other eligible affiliate networks. ACOM earns a commission when a referred customer completes an eligible purchase.

**B. Dropshipping Commerce**

Sell products through the ACOM-owned website. ACOM receives the customer's order and payment, purchases the product from an approved supplier, and coordinates direct fulfillment to the customer.

### Long-term vision

Build an AI-powered product discovery and shopping platform that can identify profitable opportunities, understand customer demand, and continuously improve its business performance.

The system must be modular, scalable, auditable, and maintainable by one founder.

---

## 2. CORE OPERATING PRINCIPLES

The following principles are mandatory.

- AI-first, not human-operated with AI assistance.
- One founder, minimal manual workload.
- Open-source and self-hosted software wherever practical.
- No Shopify.
- No paid SaaS dependencies for core operations.
- No unnecessary microservices.
- No duplicated business databases.
- No direct AI access to unrestricted database writes.
- No automatic financial commitments without defined authorization.
- Every important action must have a log and traceable result.
- Every automation must support failure recovery.
- Start small, validate revenue, and expand only when justified.

> **Important:** AI-driven does not mean blindly autonomous. The founder retains authority over payments, supplier commitments, legal compliance, exceptional refunds, and other high-risk actions.

---

## 3. BUSINESS REVENUE ARCHITECTURE

ACOM will operate two independent revenue engines.

### 3.1 Affiliate Commerce Engine

**Workflow**

1. AI researches potential products.
2. AI analyzes market demand and competition.
3. AI identifies eligible affiliate programs.
4. AI evaluates commission structures.
5. AI generates product content.
6. Approved products are published on the ACOM website.
7. Customer visits the product page.
8. Customer clicks the affiliate link.
9. Customer completes checkout on the marketplace.
10. Affiliate network reports conversion and commission.
11. ACOM reconciles earnings.

**Affiliate modules**

Affiliate Network Management · Affiliate Product Management · Product Research · Affiliate Link Management · Click Tracking · Campaign Tracking · Conversion Import · Commission Reconciliation · Performance Analytics

**Important rules**

- Do not assume a click means a sale.
- Do not record an estimated commission as realized revenue.
- Import conversion data only from authorized affiliate reports or APIs.
- Respect marketplace terms, attribution rules, content policies, and disclosure requirements.
- Display affiliate disclosures clearly.

### 3.2 Dropshipping Commerce Engine

**Workflow**

1. AI identifies a potential product.
2. AI researches suppliers.
3. Supplier information and pricing are verified.
4. Product is approved for sale.
5. Product is published on the ACOM storefront.
6. Customer places an order.
7. Payment gateway confirms successful payment.
8. ERPNext creates the sales transaction.
9. Supplier purchase order is generated.
10. Supplier receives the order.
11. Supplier fulfills the product.
12. Tracking information is updated.
13. Customer receives delivery updates.
14. Returns, refunds, and disputes are managed.
15. Revenue and costs are reconciled.

**Dropshipping modules**

Supplier Management · Supplier Product Catalog · Product Cost Management · Selling Price Management · Supplier Inventory Synchronization · Sales Order Management · Purchase Order Management · Fulfillment Tracking · Shipping Management · Returns and Refunds · Supplier Performance · Profitability Analytics

**Important rule**

Affiliate and Dropshipping must have separate checkout logic. An affiliate product redirects customers to an external marketplace. A dropshipping product uses ACOM's own checkout and payment workflow.

Never create an ACOM Sales Order for an affiliate purchase unless there is a separate legitimate transaction requiring it.

---

## 4. PRODUCT DISCOVERY AND PROFITABILITY ENGINE

This is one of the most important competitive advantages of ACOM.

The objective is not to publish thousands of products. The objective is to identify products that can generate sustainable profit.

**AI Product Hunter responsibilities**

- Discover product opportunities.
- Analyze market demand.
- Compare competing retail prices.
- Research supplier availability.
- Compare supplier prices.
- Estimate shipping and payment costs.
- Identify return and quality risks.
- Calculate estimated contribution margin.
- Recommend products for human approval.

**Product scoring model**

| Factor | Weight |
|---|---|
| Demand potential | 25% |
| Expected contribution margin | 25% |
| Competition | 15% |
| Supplier reliability | 15% |
| Return and quality risk | 10% |
| Shipping suitability | 10% |

The score is a decision-support tool, not proof of actual demand.

**Initial product selection policy**

Prefer:

- Lightweight products.
- Non-fragile products.
- Products with consistent supplier availability.
- Products with clear specifications.
- Products with manageable return rates.
- Products with reasonable contribution margins.

Avoid initially:

- High-return electronics.
- Fragile products.
- Products with uncertain quality.
- Products requiring complex warranties.
- Products with unclear regulatory requirements.
- Products with unreliable suppliers.

**Margin calculation**

Do not calculate profitability using selling price minus supplier cost alone.

```
Contribution Profit  = Selling Price
                     − Supplier Cost
                     − Shipping
                     − Payment Fees
                     − Packaging
                     − Expected Return Cost
                     − Other Variable Costs

Contribution Margin % = Contribution Profit / Selling Price × 100
```

Taxes collected on behalf of the government must be treated separately from business income and profitability.

A 35% margin can be used as an initial product-research target, but it must not become an inflexible rule for every category.

---

## 5. AI COMPANY ORGANIZATION

ACOM will use a multi-agent operating model. Each agent has a defined responsibility, permitted tools, input data, output format, and approval policy.

### 5.1 Executive AI Agents

**1. AI CEO / Business Strategist**

- Monitor company performance.
- Review business KPIs.
- Identify growth opportunities.
- Recommend business priorities.
- Evaluate operational bottlenecks.
- Prepare daily and weekly executive reports.

*Authority:* Recommendations only. Founder makes final strategic decisions.

**2. AI Product Hunter**

- Discover products.
- Analyze market opportunities.
- Compare competitor prices.
- Research suppliers.
- Calculate estimated margins.
- Recommend products.

*Output:* Structured JSON product research report.

**3. AI Supplier Research Agent**

- Identify potential suppliers.
- Collect supplier details.
- Compare pricing.
- Evaluate minimum order quantities.
- Track delivery and quality history.
- Recommend suppliers.

*Constraint:* Must not place orders or make supplier commitments without authorization.

**4. AI Listing & Content Agent**

- Generate product titles.
- Write product descriptions.
- Generate bullet points.
- Prepare SEO metadata.
- Create category descriptions.
- Prepare marketing copy.

*Constraint:* All generated content must be checked for factual accuracy and marketplace compliance.

**5. AI Marketing Agent**

- Prepare marketing campaigns.
- Generate social media content.
- Create SEO topic plans.
- Analyze campaign performance.
- Recommend content schedules.
- Monitor conversion performance.

**6. AI Customer Support Agent**

- Answer product questions.
- Explain shipping and delivery status.
- Collect customer information.
- Categorize complaints.
- Create support tickets.
- Escalate exceptional cases.

*Constraint:* Must not promise refunds, delivery dates, or warranties that are not confirmed by business records.

**7. AI Order Operations Agent**

- Monitor new orders.
- Check payment status.
- Check supplier availability.
- Identify delayed orders.
- Monitor fulfillment.
- Detect exceptions.
- Prepare escalation reports.

**8. AI Finance & Reconciliation Agent**

- Track sales.
- Track supplier costs.
- Track payment gateway settlements.
- Track affiliate commissions.
- Reconcile refunds.
- Calculate contribution profit.
- Identify missing transactions.

*Constraint:* Must never fabricate accounting entries or mark unverified revenue as received.

**9. AI Business Intelligence Agent**

- Generate daily dashboards.
- Analyze revenue.
- Calculate product profitability.
- Identify high-performing categories.
- Identify loss-making products.
- Recommend pricing changes.

**10. AI Compliance & Risk Agent**

- Check product claims.
- Check affiliate disclosures.
- Flag suspicious suppliers.
- Identify pricing anomalies.
- Monitor refund and dispute patterns.
- Flag GST and invoicing exceptions.

*Constraint:* Provides alerts and recommendations, not legal certification.

---

## 6. TECHNOLOGY STACK — FINAL RECOMMENDATION

The objective is to use a small number of reliable technologies rather than introduce many overlapping systems.

| Layer | Selected Technology | Purpose |
|---|---|---|
| ERP | ERPNext | Business operations |
| Framework | Frappe Framework | Custom business applications |
| Custom App | `acom_core` | ACOM-specific business logic |
| Database | MariaDB | ERP data |
| Cache | Redis | Cache and queues |
| Background Jobs | Frappe Workers | Async business tasks |
| Frontend | Next.js | ACOM storefront |
| Frontend Language | TypeScript | Maintainable frontend UI |
| UI | Tailwind CSS | Storefront interface |
| Automation | ~~Node-RED~~ **Frappe Scheduler + Python runner** | Workflow automation `AMENDED (ADR-0002)` |
| Local AI Runtime | Ollama | Local LLM execution |
| AI Agent Orchestration | Python | Controlled agent execution |
| API | Frappe REST / Custom APIs | System integration |
| Local Containerization | Docker | Reproducible development |
| Development Environment | Windows 11 + WSL2 | Local infrastructure |
| Version Control | Git | Source control |
| Monitoring | Uptime Kuma / Docker health checks | Local monitoring |
| Logs | Docker logs + structured application logs | Troubleshooting |

### Optional technologies — only when justified

LiteLLM (multiple providers behind one interface) · Qdrant (vector search when retrieval needs it) · Playwright (authorized browser testing) · PostgreSQL (only if an independent service genuinely requires it) · Metabase (if ERPNext reports become insufficient) · MinIO (if local file storage becomes insufficient) · OpenTelemetry (when complexity warrants it).

Do not install every optional technology during the initial PoC.

### Technologies deliberately excluded

Shopify · paid automation platforms · Kubernetes · unnecessary microservices · multiple competing ERP databases · separate custom accounting software · proprietary AI APIs as mandatory dependencies · unnecessary message brokers when Frappe's existing queue infrastructure is sufficient.

---

## 7. ERP FOUNDATION — ERPNEXT + FRAPPE

ERPNext + Frappe will be the central business operating system. Do not build another complete ERP from scratch.

**Reuse ERPNext for:** Customer records · Supplier records · Items · Inventory · Sales Orders · Purchase Orders · Invoices · Payment Entries · Accounting · Taxes · Stock transactions · Returns.

Use custom Frappe applications only for ACOM-specific workflows.

### 7.1 Custom App Structure

Start with **ONE** custom app: `acom_core`.

Inside it, organize separate modules:

- Affiliate Commerce
- Dropshipping Commerce
- Product Intelligence
- Supplier Intelligence
- AI Operations
- Marketing Automation
- Analytics
- Integration Management

Do not create six separate apps at the beginning. Separate apps can be introduced later if independent deployment or maintenance genuinely requires them.

### 7.2 Initial Custom DocTypes

**Affiliate Product** — Product Name · Product SKU · Marketplace · Affiliate Network · Affiliate URL · Category · Commission Rate · Commission Type · Campaign · Product Status · Last Verified Date

**Affiliate Click** — Affiliate Product · Click ID · Campaign ID · Source · Referrer · Timestamp · Anonymous Session ID · Attribution Status

*Avoid collecting unnecessary personally identifiable information.*

**Dropshipping Product** — Product Name · Supplier SKU · ERPNext Item · Supplier · Supplier Cost · Selling Price · Shipping Cost · GST / HSN Information · Supplier Stock · Last Stock Sync · Product Status

**Supplier Performance** — Supplier · Orders Received · Orders Fulfilled · Average Dispatch Time · Cancellation Rate · Return Rate · Quality Issues · Reliability Score

**AI Task** — Task ID · Task Type · Input Reference · Model · Status · Retry Count · Created Time · Completed Time · Output Reference · Error Details

**AI Approval Request** — Request ID · Action Type · Related Document · AI Recommendation · Estimated Financial Impact · Approval Status · Approved By · Approval Timestamp

**Automation Event** — Event ID · Event Type · Source · Idempotency Key · Processing Status · Retry Count · Error Details · Created Time

### Important data-model rules

- Every dropshipping product must link to a valid ERPNext Item.
- Every dropshipping supplier must link to an ERPNext Supplier.
- Use ERPNext Customer records instead of inventing a second customer database.
- Use ERPNext's standard Sales Order and Purchase Order documents.
- Affiliate products are not inventory items unless there is a separate operational reason.
- Supplier SKU and ERPNext Item Code are different concepts and must be mapped explicitly.
- Use proper currency, price list, company, warehouse, tax, and customer configuration.

---

## 8. STOREFRONT ARCHITECTURE

The ACOM website will be built using Next.js.

**Suggested domain architecture**

- Main storefront: `www.acom-domain.in`
- ERP/API: internal local development endpoint initially
- Admin: Frappe Desk, accessible locally

**Main website sections**

Home · Discover Products · Categories · Trending Products · Deals · Affiliate Products · Shop Products · Product Details · About ACOM · Contact · Affiliate Disclosure · Privacy Policy · Terms and Conditions · Shipping and Returns

**Product types**

Every product must have an explicit sales type: `AFFILIATE` or `DROPSHIP`.

The storefront must display the correct purchase action based on the product type.

- Affiliate product: **View Deal → External Affiliate Link**
- Dropshipping product: **Add to Cart → ACOM Checkout**

**API structure**

Public endpoints:

```
GET  /api/catalog
GET  /api/products/{slug}
GET  /api/categories
POST /api/affiliate/click
```

Protected customer endpoints:

```
POST /api/cart/validate
POST /api/checkout
GET  /api/orders/{order_id}
POST /api/support/tickets
```

Protected internal endpoints:

```
POST /api/internal/ai/result
POST /api/internal/supplier/sync
POST /api/internal/affiliate/import
POST /api/internal/automation/event
```

Public catalog APIs must return only approved public information. Do not expose supplier cost, private commission data, internal stock details, or confidential customer information.

---

## 9. SECURE ORDER PROCESSING

This is a critical business component.

**Dropshipping order sequence**

1. Customer submits checkout.
2. Backend validates the cart.
3. Backend retrieves the current product prices from ERPNext.
4. Backend verifies product status and supplier availability.
5. Backend creates a pending checkout/order record with an idempotency key.
6. Customer completes payment through a supported payment gateway.
7. Payment gateway sends a signed webhook.
8. Backend verifies the webhook signature.
9. Backend checks payment amount, currency, order reference, and transaction status.
10. Backend records payment confirmation.
11. ERPNext creates the Sales Order.
12. A Purchase Order draft is generated for the relevant supplier.
13. Supplier order authorization is checked.
14. Authorized Purchase Order is submitted.
15. Fulfillment tracking begins.

**Mandatory technical safeguards**

- Idempotency must be enforced using a database-backed unique key and transactional logic.
- Do not mark an order paid based on a frontend response.
- Never trust prices supplied by the browser.
- Verify supplier mapping on the backend.
- Verify payment webhook signatures.
- Handle repeated webhooks safely.
- Handle payment success followed by ERP failure through retryable jobs.
- Use an outbox/event pattern for reliable downstream processing.
- Record all important transaction references.

**Important checkout distinction**

Affiliate checkout must never enter the dropshipping payment workflow. Affiliate conversion tracking is reconciled using authorized network reports or APIs.

**Refund workflow**

1. Customer refund request.
2. Order and payment verification.
3. Refund eligibility check.
4. AI prepares recommendation.
5. Founder approval for exceptions.
6. Payment gateway refund.
7. ERPNext refund transaction.
8. Customer notification.
9. Reconciliation.

AI must not independently issue unrestricted refunds.

---

## 10. AI INFRASTRUCTURE — LOCAL-FIRST

The AI infrastructure must work without mandatory paid APIs.

### 10.1 Ollama

Ollama will host locally available open-weight language models.

**Responsibilities:** product research assistance · product description generation · content generation · supplier document analysis · customer query classification · report generation · internal decision support.

**Model selection must be based on:** RAM and GPU availability · model quality · response speed · context size · license and commercial-use terms.

Do not assume every model distributed through Ollama is automatically suitable for commercial use. Check the specific model license.

> `AMENDED (ADR-0004)` — this hardware (16 GB RAM, 4 GB VRAM) supports 3B models resident in VRAM and 7B models only on-demand with partial offload. See ADR-0004 for the approved model ceiling.

### 10.2 AI Agent Architecture

Build a controlled agent layer. Each agent must have:

Agent ID · Role · System instructions · Permitted tools · Input schema · Output schema · Execution timeout · Retry policy · Maximum token or resource budget · Approval policy · Audit logs.

AI agents should not directly access unrestricted MariaDB connections. They must use approved Frappe APIs and service methods.

### 10.3 AI Model Strategy

Use a model abstraction layer. Possible execution order:

1. Local Ollama model.
2. Alternative locally installed model.
3. Manual review queue if local inference fails.

Paid cloud AI must not become a required dependency. If a future external model is used, it must be explicitly enabled, budget-controlled, and compatible with data privacy requirements.

### 10.4 Hybrid AI Networking

For the initial all-local installation:

- No WireGuard is necessary if Ollama and ERPNext run on the same trusted machine.
- Use Docker networking or a controlled host endpoint.

If the AI server is a separate local machine later:

- Establish WireGuard.
- Permit only required private network routes.
- Restrict Ollama access.
- Authenticate all internal requests.
- Use signed webhooks.
- Never expose the Ollama port publicly.

---

## 11. NODE-RED AUTOMATION ENGINE

> `AMENDED (ADR-0002)` — Node-RED is **deferred**. The flows below are retained as the
> canonical specification of required behaviour. They are implemented in Phase 7 as
> Frappe scheduled jobs plus a Python agent runner inside `acom_core`. The
> `automation/` directory and JSON schemas remain in the repository so the flows can be
> ported to Node-RED later without redesign. All security controls in this section
> still apply to whatever executes the flows.

Node-RED will orchestrate workflows. It is not the primary business database or accounting system.

**Initial automation flows**

| Flow | Trigger and steps |
|---|---|
| 1. Product Research | Trigger → Product Research Request → Ollama → Structured JSON Validation → AI Review → Draft Product |
| 2. Content Generation | Product Approved → Listing Copywriter → Content Validation → Draft Update → Approval → Publish |
| 3. Supplier Monitoring | Scheduled Trigger → Supplier Stock Check → Compare Stock → Detect Changes → Update Draft Inventory → Alert |
| 4. Order Monitoring | ERPNext Order Event → Check Payment → Check Supplier → Check Fulfillment → Update Status → Notify |
| 5. Affiliate Reconciliation | Import Affiliate Report → Validate Records → Match Click / Campaign → Calculate Commission → Reconciliation Queue |
| 6. Finance Monitoring | Fetch Transactions → Reconcile → Identify Missing Records → Calculate Contribution Profit → Report |

**Security**

HTTP endpoints must implement actual HMAC verification. Checking whether a signature header exists is not authentication.

Required controls: HMAC-SHA256 · timestamp validation · replay protection · secret rotation · payload schema validation · rate limiting · request logging · retry handling.

---

## 12. FINANCIAL CONTROL SYSTEM

Financial accuracy is essential. ERPNext should remain the authoritative business record.

**Initial financial records**

Order Revenue · Supplier Cost · Shipping Cost · Payment Gateway Fees · Refunds · Affiliate Commission · Advertising Expense · Other Variable Costs · Contribution Profit

**Financial principles**

- Separate estimated revenue from confirmed revenue.
- Separate confirmed affiliate sales from pending commissions.
- Record refunds independently.
- Reconcile payment gateway settlements.
- Reconcile supplier invoices and payments.
- Keep an immutable audit trail for financial events.
- Use proper ERPNext accounting transactions for actual accounting.
- Do not implement a second accounting engine inside `acom_core`.

**The first financial dashboard should answer**

1. How much money did customers pay?
2. How much revenue is confirmed?
3. How much supplier cost is payable?
4. How much commission is pending?
5. How much was refunded?
6. What is the actual contribution profit?
7. How much cash is available?

---

## 13. CUSTOMER ACQUISITION AND MARKETING ENGINE

The company must acquire customers without depending entirely on paid advertising.

**Organic acquisition**

SEO product discovery · search-friendly category pages · helpful buying guides · social media content · product comparison content · short-form videos · email newsletters where consent is obtained · affiliate deal pages · customer referral programs.

**AI Marketing Agent**

- Research keywords.
- Identify customer search intent.
- Prepare content calendars.
- Generate drafts.
- Produce product-specific content.
- Track published content.
- Analyze clicks and conversions.
- Recommend improvements.

**Marketing KPI**

Organic traffic · product page visits · affiliate outbound clicks · affiliate conversion rate · dropshipping conversion rate · customer acquisition cost · repeat purchase rate · revenue per visitor · contribution profit per channel.

Do not publish AI-generated pages in bulk without quality control. Search visibility and customer trust depend on useful, accurate content.

---

## 14. SINGLE-FOUNDER OPERATING MODEL

The company should be designed around the founder's limited time.

**Founder responsibilities:** business strategy · final supplier approval · high-risk financial approvals · legal and compliance decisions · exceptional customer complaints · product launch approval · AI system governance.

**AI responsibilities:** research · drafting · categorization · monitoring · data preparation · reporting · routine support · workflow coordination · exception detection.

**Daily CEO dashboard**

Today's orders · pending payments · orders awaiting supplier action · delayed shipments · customer complaints · affiliate clicks · confirmed commissions · revenue · contribution profit · AI task failures · approval requests.

**Daily operating routine**

- **Morning:** AI prepares the business summary and identifies urgent exceptions.
- **During the day:** AI handles routine tasks and places exceptions into the approval queue.
- **Evening:** AI prepares a daily performance report and next-day action plan.

The goal is to make the founder a decision-maker rather than a manual data-entry operator.

---

## 15. LOCAL DEVELOPMENT INFRASTRUCTURE

**Hardware baseline:** 16 GB RAM.

**Recommended starting configuration**

- Windows 11
- WSL2
- Docker Desktop
- 4 CPU cores allocated to WSL2 initially
- 6–8 GB WSL2 memory allocation, adjusted based on actual host usage
- 2–4 GB swap, if needed
- Persistent Docker volumes

**Example `.wslconfig`**

```ini
[wsl2]
memory=8GB
processors=4
swap=4GB
localhostForwarding=true

[experimental]
sparseVHD=true
```

The exact memory allocation must be tested against actual CPU, RAM, disk, and Windows workload.

Do not run a large Ollama model simultaneously with the entire ERPNext stack if memory pressure becomes excessive. Use smaller models or run AI inference only when needed.

> `AMENDED (ADR-0004)` — on this 16 GB host, Windows consumes ~9 GB at idle. WSL2 is
> capped at **7 GB**, not 8 GB, to avoid host swap thrash.

**Docker strategy**

- Use the official Frappe Docker repository: https://github.com/frappe/frappe_docker
- Use a compatible, pinned set of Frappe, ERPNext, India Compliance, MariaDB, and Redis versions.
- Do not copy an incomplete custom Compose file and assume it is a complete ERPNext installation.
- Use the official Docker setup as the baseline and maintain a separate, version-controlled override for ACOM-specific configuration.

**Local development environment**

ERPNext Desk: local browser access · Next.js: local development server · Node-RED: deferred · Ollama: local inference endpoint · MariaDB: private Docker network only.

All credentials must be stored in local environment files excluded from Git.

---

## 16. INDIA COMPLIANCE

Use the Frappe India Compliance application only after verifying its compatibility with the selected ERPNext/Frappe versions.

Official repository: https://github.com/resilient-tech/india-compliance

**Required business capabilities to validate**

GST configuration · GST tax templates · HSN/SAC handling · GST invoices · E-Invoice integration · E-Way Bill integration · credit notes · debit notes · applicable reporting.

Do not assume installation automatically guarantees regulatory compliance. GST registration, invoice rules, E-Invoice eligibility, E-Way Bill thresholds, and other requirements must be verified for the actual business model with an Indian CA and current official rules.

For the initial PoC, use dummy data only.

---

## 17. SECURITY AND DATA GOVERNANCE

Security requirements apply even when the application is local.

**Database** — no public database exposure · strong credentials · restricted application access · regular backups · tested restore process.

**API** — no unrestricted guest order creation · authentication for internal endpoints · rate limits for public endpoints · input validation · output filtering · idempotency · signed payment webhooks.

**AI** — no unrestricted database access · no unrestricted financial actions · no automatic supplier commitments · no unauthorized scraping · no disclosure of private customer data to external models · AI output must be validated before business execution.

**Payments** — use a legitimate payment gateway · never store card numbers, CVV, UPI PIN, or other payment authentication secrets · verify gateway callbacks and signatures · record gateway references and reconciliation status.

**Backup** — automated database backup · site files backup · configuration backup without exposing secrets · Git source control · restore testing.

A backup is not considered reliable until restoration has been successfully tested.

---

## 18. PROJECT REPOSITORY STRUCTURE

```
project-acom/
│
├── docs/
│   ├── MASTER_BLUEPRINT.md
│   ├── ARCHITECTURE_RULES.md
│   ├── FRAPPE_AGENT_RULES.md
│   ├── SECURITY_POLICY.md
│   ├── DATA_DICTIONARY.md
│   ├── API_CONTRACTS.md
│   ├── BUSINESS_WORKFLOWS.md
│   ├── ADR/
│   └── TEST_PLAN.md
│
├── infrastructure/
│   ├── docker/
│   ├── wsl/
│   ├── backup/
│   └── local-config/
│
├── apps/
│   ├── acom_core/
│   └── storefront/
│
├── automation/
│   ├── node-red/
│   ├── workflows/
│   └── schemas/
│
├── ai/
│   ├── agents/
│   ├── prompts/
│   ├── schemas/
│   ├── tools/
│   └── evaluation/
│
├── integrations/
│   ├── affiliate/
│   ├── suppliers/
│   ├── payments/
│   └── shipping/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── end-to-end/
│
├── scripts/
├── .env.example
├── .gitignore
└── README.md
```

Do not put secrets, real customer data, payment credentials, or production database dumps in Git.

---

## 19. CODING AGENT GOVERNANCE

Antigravity and other AI coding agents must operate under strict rules.

Create these mandatory files before implementation:

**`ARCHITECTURE_RULES.md`** — system boundaries · technology decisions · module responsibilities · data ownership · API contracts · naming conventions · security requirements · testing requirements.

**`FRAPPE_AGENT_RULES.md`** — use Frappe DocTypes and ORM · use supported document lifecycle methods · use hooks and service layers · never directly modify ERPNext core files · never manually modify ERPNext database schema · never bypass document validation without explicit review · use migrations and fixtures correctly · use documented APIs · avoid uncontrolled raw SQL · preserve compatibility with pinned framework versions.

**Agent execution protocol**

Every task must follow:

1. Read the architecture documents.
2. Inspect the existing repository.
3. Identify the exact task.
4. Propose a plan.
5. Implement only the requested scope.
6. Run relevant tests.
7. Review security implications.
8. Report changed files.
9. Report test results.
10. Wait for approval before moving to the next critical phase.

Agents must never silently change the approved architecture. No agent should claim a feature is complete without execution evidence.

---

## 20. IMPLEMENTATION ROADMAP

> `AMENDED (ADR-0001)` — Phase 4 and Phase 5 are **swapped**. The affiliate engine ships
> before the dropshipping transaction engine. Numbering below reflects the ratified
> order.

The project will be built in controlled phases.

### Phase 0 — Foundation

**Objectives:** verify local hardware · install Docker Desktop · configure WSL2 · create Git repository · create architecture documentation · pin software versions · establish development conventions.

**Exit criteria:** Docker runs reliably · repository is initialized · architecture rules are committed · environment can be reproduced.

### Phase 1 — ERPNext PoC

**Objectives:** install ERPNext using official Docker architecture · install compatible India Compliance app · create a dummy Company · configure currency · create Item Groups, Items, Suppliers, Customers · create a dummy Sales Order · create a dummy Purchase Order.

**Exit criteria:** ERPNext Desk works · standard documents work · migrations complete successfully · restarting containers does not lose data.

### Phase 2 — ACOM Core

**Objectives:** scaffold `acom_core` · create initial custom DocTypes · create Affiliate Product management · create Dropshipping Product management · implement supplier mapping · implement product status management · create internal service layer.

**Exit criteria:** custom app installs successfully · DocTypes migrate correctly · permissions are verified · unit tests pass.

### Phase 3 — Storefront

**Objectives:** create Next.js application · home page · categories · product listing · product detail pages · connect public catalog API · implement affiliate redirects · implement dropshipping cart.

**Exit criteria:** both product types display correctly · affiliate products redirect correctly · supplier costs remain private · frontend never controls final selling prices.

### Phase 4 — Affiliate Engine *(moved earlier — ADR-0001)*

**Objectives:** affiliate network configuration · product catalog import · affiliate link management · click tracking · campaign tracking · conversion report import · commission reconciliation.

**Exit criteria:** affiliate clicks are recorded · conversion reports can be imported · pending commissions are distinguished from confirmed commissions · revenue reporting is accurate.

### Phase 5 — Dropshipping Transaction Engine *(moved later — ADR-0001)*

**Objectives:** implement checkout validation · integrate payment gateway test mode · verify signed payment webhooks · implement idempotency · create Sales Order · generate supplier Purchase Order drafts · implement supplier approval · implement fulfillment tracking · implement cancellation and refund handling.

**Exit criteria:** no duplicate orders · no unpaid order is treated as paid · payment and ERP records reconcile · supplier mapping is accurate · failed workflows can recover safely.

### Phase 6 — AI Agent Foundation

**Objectives:** install Ollama · select commercially appropriate local models · implement agent registry · define agent permissions · define JSON output schemas · implement AI task queue · implement retry handling · implement approval queue · implement execution logs.

**Exit criteria:** AI agents can perform controlled tasks · invalid AI output is rejected · AI failures do not interrupt ERPNext · AI cannot perform unauthorized financial actions.

### Phase 7 — Automation Engine

**Objectives:** install Node-RED *(deferred — ADR-0002)* · connect it to controlled internal APIs · implement HMAC verification · implement Product Research Flow · implement Content Generation Flow · implement Supplier Monitoring · implement Order Monitoring · implement Finance Reconciliation.

**Exit criteria:** each flow has a success path · each flow has a failure path · duplicate events are handled safely · every important action is logged.

### Phase 8 — Business Intelligence

**Objectives:** Daily CEO Dashboard · Product Profitability Dashboard · Supplier Performance Dashboard · Affiliate Performance Dashboard · Customer Support Dashboard · AI Operations Dashboard.

**Exit criteria:** founder can understand the company's condition from one dashboard · revenue and contribution profit are distinguishable · pending tasks and exceptions are visible.

### Phase 9 — End-to-End Local Validation

**Simulations:** product discovery · supplier verification · product approval · product publication · customer visit · affiliate click · dropshipping checkout · payment confirmation · Sales Order creation · Purchase Order creation · supplier fulfillment · delivery · refund simulation · financial reconciliation · AI failure and recovery.

**Exit criteria:** all critical tests pass · no duplicate financial transactions · no unauthorized actions · backup and restore work · all critical workflows have documented evidence.

No production deployment is included in this implementation stage. Everything remains local.

---

## 21. BUSINESS LAUNCH STRATEGY — FROM ZERO

Technology alone does not generate money. The first objective is to prove that ACOM can acquire customers and earn positive contribution profit.

### Stage A — Zero/Low Capital Validation

Start with affiliate commerce.

**Reasons:** no inventory investment · no supplier payment before customer purchase · no direct fulfillment responsibility · lower operational complexity · faster product-market validation.

**Initial target:** one or two product categories · a limited, curated product catalog · high-quality product research · useful buying guides · organic traffic acquisition.

Do not spend heavily on advertisements before conversion is demonstrated.

### Stage B — Controlled Dropshipping

After validating product demand:

- Select a small number of products.
- Verify suppliers manually.
- Confirm real supplier pricing.
- Confirm shipping timelines.
- Test sample quality.
- Verify return policies.
- Test payment and refund workflows.
- Start with a small catalog rather than hundreds of unverified products.

### Stage C — Growth

Once profitable unit economics are demonstrated: expand categories · add more suppliers · improve automated product discovery · improve content distribution · introduce customer retention campaigns · automate supplier synchronization · expand marketing channels.

### Stage D — Autonomous Operations

After the workflows have proven reliable: AI handles routine research · AI prepares listings · AI monitors inventory · AI prepares supplier orders · AI handles routine customer questions · AI generates performance reports · founder handles exceptions and strategic decisions.

Automation should increase gradually as evidence of reliability grows.

---

## 22. KEY PERFORMANCE INDICATORS

**Revenue** — Total Sales · Confirmed Affiliate Commission · Dropshipping Revenue · Refunds · Net Revenue.

**Profitability** — Supplier Cost · Shipping Cost · Payment Fees · Return Cost · Contribution Profit · Contribution Margin.

**Marketing** — Website Visitors · Organic Traffic · Affiliate Clicks · Conversion Rate · Revenue per Visitor · Customer Acquisition Cost.

**Operations** — Orders Pending · Orders Delayed · Supplier Fulfillment Rate · Cancellation Rate · Return Rate · Customer Complaints.

**AI Operations** — AI Tasks Completed · AI Task Failures · Retry Count · Approval Queue · Cost per AI Task · Time Saved.

**Business health** — Cash Available · Supplier Payables · Customer Refund Liabilities · Confirmed Receivables · Pending Affiliate Commissions.

---

## 23. RISK MANAGEMENT

| Risk | Mitigation |
|---|---|
| Supplier fraud | Supplier verification and sample testing |
| Incorrect stock data | Stock sync and order-time validation |
| Low-quality products | Quality checks and return monitoring |
| Affiliate attribution failure | Authorized conversion reconciliation |
| Payment fraud | Gateway verification and signed webhooks |
| Duplicate orders | Database-backed idempotency |
| AI hallucination | Schema validation and approval |
| AI failure | Retry queue and manual fallback |
| Customer complaints | Ticketing and escalation |
| Financial mismatch | Reconciliation and audit logs |
| Database corruption | Backups and restore tests |
| Agent code errors | Git, tests, reviews, and restricted scope |
| Regulatory changes | Current official requirements and CA review |

---

## 24. OFFICIAL AND OPEN-SOURCE PROJECT REFERENCES

Use official repositories and documentation as the source of truth.

**ERP and Framework**

- ERPNext: https://github.com/frappe/erpnext
- Frappe Framework: https://github.com/frappe/frappe
- Frappe Docker: https://github.com/frappe/frappe_docker
- ERPNext Documentation: https://docs.frappe.io/erpnext

**Indian Compliance**

- India Compliance: https://github.com/resilient-tech/india-compliance

**Frontend**

- Next.js: https://github.com/vercel/next.js
- Tailwind CSS: https://github.com/tailwindlabs/tailwindcss

**AI**

- Ollama: https://github.com/ollama/ollama
- Qdrant: https://github.com/qdrant/qdrant

**Automation**

- Node-RED: https://github.com/node-red/node-red

**Monitoring**

- Uptime Kuma: https://github.com/louislam/uptime-kuma

**Testing**

- Playwright: https://github.com/microsoft/playwright

**Infrastructure**

- Docker: https://github.com/moby/moby
- WireGuard: https://www.wireguard.com/

**Licensing policy**

Before adoption, review each project's license, dependency licenses, commercial-use terms, model licenses, and distribution obligations. ERPNext is GPLv3, while Frappe Framework is MIT. Do not assume all custom application licensing questions have the same answer. Obtain appropriate legal advice before distributing derivative software or offering a hosted commercial product.

---

## 25. FINAL CEO DECISIONS

| Decision | Final Selection |
|---|---|
| Business model | Affiliate + Dropshipping |
| Operating model | One founder + AI agents |
| ERP | ERPNext |
| Framework | Frappe |
| Custom app | One `acom_core` app initially |
| Database | MariaDB |
| Storefront | Next.js |
| Automation | Node-RED *(deferred — ADR-0002)* |
| Local AI | Ollama |
| Infrastructure | Docker + WSL2 |
| Current environment | Local only |
| Available RAM | 16 GB |
| Cloud production | Not in current scope |
| Shopify | Excluded |
| Paid SaaS dependency | Excluded from core architecture |
| Financial authority | Founder-controlled |
| AI database access | Restricted APIs only |
| Initial revenue strategy | Affiliate validation |
| Expansion strategy | Controlled dropshipping |
| Deployment priority | Local PoC first |

---

## 26. FIRST EXECUTION ORDER

Do not ask the coding agent to build the entire company in one prompt.

Execute in this exact order:

1. Inspect the Windows computer and verify CPU, RAM, disk, virtualization, WSL2, and Docker status.
2. Prepare the local development environment.
3. Clone the official Frappe Docker repository.
4. Pin compatible ERPNext, Frappe, MariaDB, Redis, and India Compliance versions.
5. Start the ERPNext environment.
6. Verify standard ERPNext business documents.
7. Create the ACOM Git repository and architecture documentation.
8. Scaffold `acom_core`.
9. Implement the first custom DocTypes.
10. Test the Frappe API.
11. Build the Next.js catalog.
12. Validate affiliate and dropshipping flows separately.
13. Implement payment test mode and order safety.
14. Introduce Ollama and the AI agent foundation.
15. Introduce Node-RED automation. *(deferred — ADR-0002)*
16. Build the CEO dashboard.
17. Run full end-to-end tests.
18. Review business economics before any real-money launch.

Every phase must pass its exit criteria before the next phase begins.

---

## FINAL STRATEGIC DIRECTIVE

PROJECT ACOM must not become an expensive technology experiment. It must become a business that makes money.

The founder's most valuable resource is time. AI must reduce repetitive work, improve decisions, and help the business operate with minimal human intervention.

The first milestone is not 10,000 products, 20 AI agents, or a complicated dashboard.

The first milestone is:

> Find one profitable product, acquire one real customer, complete one successful
> transaction, deliver the product, reconcile the money, and prove positive
> contribution profit.

Then repeat the process.

Once the system can reliably repeat that process, automate it, expand it, and scale it.

**PROJECT ACOM — One Founder. Multiple AI Agents. One Commerce Operating System. Built to Generate Revenue.**

---

*MASTER BLUEPRINT VERSION: 2.0*
*STATUS: APPROVED ARCHITECTURAL BASELINE — PENDING LOCAL VALIDATION*
