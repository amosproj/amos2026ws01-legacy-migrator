# Acceptance Baseline: `step-05` & `step-06` (`legacy-example-stages`)

This document defines the common reference baseline (`step-05` $\rightarrow$ `step-06`) for developing and evaluating the Sunset Tracker prototype against the derived IBM Application Modernization sample (`legacy-example-stages`).

---

## 1. Checkout & Repository Mechanics

### 1.1 Commands
```bash
git clone git@github.com:legacy-modernization-example/legacy-example-stages.git
cd legacy-example-stages

# Switch to baseline stages (initializes/updates submodules and compatibility symlinks)
./use-stage.sh step-05
./use-stage.sh step-06

# Discard untracked build/fix artifacts in submodules when switching stages
FORCE=1 ./use-stage.sh step-05
```

### 1.2 Working-Tree State & Parser Rules
Executing `./use-stage.sh <step>` performs three actions:
1. Checks out the stage tag in the umbrella repository.
2. Initializes and checks out only the stage-relevant Git submodules under `components/<name>` to the matching `<step>` tag.
3. Creates root-level **compatibility symlinks** defined in `stage.json` (`kompatibilitaets_links`) so original `scripts-docker/*.sh` scripts resolve legacy folder names.

* **Duplicate Ingestion Trap:** Static code/config parsers **must** scope traversal to `components/<name>` (or ignore root-level symlinks). Traversing the repository root while following symlinks parses every component twice (e.g., `components/monolith` and `./monolith-open-liberty`).
* **Root Documentation Snapshot:** Checking out `step-05` or `step-06` checks out the tag's snapshot of root markdown files. Commit `2fec621` on `main` only introduces minor neutral-wording edits in `README.md`, `WHY.md`, and `QUESTIONS.md`; all technical content and `step-06` checks are identical.

---

## 2. Repositories & Components (`stage.json`)

All component repositories live under the same GitHub org. Neither `step-05` nor `step-06` includes `frontend-microfrontends`, `frontend-react`, or `deployment`.

| Component (`components/*`) | Submodule Repo | `step-05` SHA (Origin: `fba9759`, 2020-12-07) | `step-05` Root Symlink | `step-06` SHA (Origin: `842d550`, 2020-12-14) | `step-06` Root Symlink |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `monolith` | `legacy-example-monolith` | `fc150cc` | `monolith-open-liberty` | `73ab85c` | `monolith-open-liberty-cloud-native` |
| `frontend-dojo` | `legacy-example-frontend-dojo` | `efe2253` | `frontend-dojo` | `3b8b20d` | `frontend-dojo` |
| `proxy` | `legacy-example-proxy` | `2345af9` | `proxy` | `c52d943` | `proxy` |
| `db2` | `legacy-example-db2` | `4f4f3d2` | `db2` | `129ed26` | `db2` |
| `catalog-service` | `legacy-example-catalog-service` | *Not present* | *None* | `474422c` | `service-catalog-quarkus` |

---

## 3. Catalog Service Extraction

**Verdict:** **Verified as the modelled baseline scenario between `step-05` and `step-06`, subject to two structural caveats.**

1. **Why it holds as the baseline scenario:**
   by an explicit stage-modelling decision (`STEPS.md` §3 `step-05`), `step-05` follows the original README's step-5 startup script and omits `catalog-service`. Consequently, the transition `step-05` $\rightarrow$ `step-06` cleanly models a Strangler Fig extraction of the Catalog bounded context:
   * `components/catalog-service` is added in `step-06`.
   * the active Nginx configuration switches `/CustomerOrderServicesWeb/jaxrs/Category` and `/Product` from the monolith to `storefront-catalog:8082`.
   * Asynchronous event coupling via Kafka (`product-price-updated`) becomes active: `catalog-service` publishes `productId#newPrice` on `PUT /Product/{id}`, and the monolith consumes it via `ProductPriceChanged` to update `LINE_ITEM.PRICE_CURRENT`.

2. **Caveat 1 — Chronological bleed-through into `step-05`:**
   In the original Git history (`HISTORY-ANALYSIS.md`), the proxy strangler switch and catalog service were committed in derived stages `step-04a`–`step-04d` (2020-11-25 to 2020-12-01), *before* Open Liberty (`step-05`, `fba9759`, 2020-12-07). As a result, `step-05` already contains preparatory artifacts from `step-04b`–`step-04d`:
   * `PRICE_CURRENT` column in `db2/createOrderDB.sql` and `LineItem.java`.
   * A random price-increase stub (`+10.00` on 50% of line items) in `CustomerOrderServicesImpl.loadCustomerHistory()`.
   * Inactive catalog configuration files (`proxy/nginx-catalog.conf`, `scripts-docker/docker-compose-catalog.yml`, `docker-compose-postgres-catalog.yml`, `docker-compose-kafka.yml`).

3. **Caveat 2 — Co-occurring internal monolith refactoring in step-06:**
   `step-05` $\rightarrow$ `step-06` is not a pure strangler-routing change. The monolith simultaneously undergoes an internal cloud-native refactoring (`monolith-open-liberty` $\rightarrow$ `monolith-open-liberty-cloud-native`): collapsing 4 Maven modules (EAR + EJB + WAR + root) into a single Maven WAR project, replacing EJB (`@Stateless`, `@EJB`/JNDI) with CDI (`@ApplicationScoped`, `@Inject`), and adding MicroProfile Config, Reactive Messaging, Health probes, and a `/jaxrs/test` endpoint.

---

## 4. Component-Level Diff (`step-05` $\rightarrow$ `step-06`)

| Component | `step-05` State | `step-06` State | Key Structural & Behavioral Changes |
| :--- | :--- | :--- | :--- |
| **`monolith`** | 4 Maven modules (`CustomerOrderServices`, `CustomerOrderServicesWeb`, `CustomerOrderServicesApp`, `CustomerOrderServicesProject`) building an EAR; EJB 3 (`@Stateless`); Open Liberty (`kernel-slim-java11-openj9`, Java 8 source); listens on `:9080`. | Single-module Maven WAR (`pom.xml` + `Dockerfile.multistage` on `kernel-java11-openj9-ubi`); CDI 2.0 (`@ApplicationScoped`, `@Inject`); MicroProfile Config 1.4, Health 2.2, Reactive Messaging 1.0; listens on `:9088`. | EJB & JNDI lookup in `CustomerOrderResource` replaced by `@Inject`; random `+10` price stub in `CustomerOrderServicesImpl` commented out and replaced by `updateLineItem(productId, newPrice)` called by new Kafka consumer `ProductPriceChanged`; `InventoryResource` (`/jaxrs/test`) and `Inventory*Check` health probes added; `liberty/jvm.options` (JMX agent) removed; `CategoryResource` and `ProductResource` remain in codebase as unreachable dead code behind the proxy. *EJB leftover caveat:* `CustomerOrderServicesImpl` retains an unused `@EJB ProductSearchService productSearchService;` field even though `ProductSearchServiceImpl` had `//@Stateless` commented out (see §6.1 §8). |
| **`catalog-service`** | *Absent* | Quarkus `1.1.1.Final` (Java 11, synchronous JAX-RS + JPA/Panache, PostgreSQL `import.sql`, Vert.x Kafka producer + MP Reactive Messaging consumer); listens on `:8082` (host `:9083`). | Implements `GET /Category`, `GET /Product?categoryId=...`, and `PUT /Product/{id}` (persists price in Postgres and emits `productId#newPrice` to Kafka topic `product-price-updated`). Subscribes to its own topic in `ProductPriceChanged` (log-only). |
| **`proxy`** | Active config: `Dockerfile-splitted-frontend-open` $\rightarrow$ `nginx-splitted-frontend-open.conf`. | Active config: `Dockerfile-catalog-native` $\rightarrow$ `nginx-catalog-native.conf`. | Routes `/CustomerOrderServicesWeb/jaxrs/Category`, `/CustomerOrderServicesWeb/jaxrs/Product`, `/explorer`, and `/openapi` to `storefront-catalog:8082`; remaining `/CustomerOrderServicesWeb/jaxrs/` routes to `storefront-backend-open-native:9088`. |
| **`frontend-dojo`** | Serves Dojo 1.5 UI on Liberty (`:9080`, host `:9081`); requires local Dojo installation via `scripts/install-dojo.sh` and `fixes/jmx-agent.sh`. | Adds `Dockerfile.multistage` (`kernel-java11-openj9-ubi`); removes JMX agent from `liberty/jvm.options`. | Loads Dojo 1.5.0 from Google CDN (`index.html`, `dev_imports.css`, `built_imports.css`); updates order history column label from `"Current Amount"` to `"Current Price per Item"`; uses `/CustomerOrderServicesWeb/...` module paths (`ProductController.js`). |
| **`db2`** | Db2 `11.5.5.0` image (`storefront-db2:50000`), `createOrderDB.sql`, `orderdb-data.sql`. | Same schema and seed data; minor `Dockerfile` cleanup (`chmod +x`). | No schema or data diff between `step-05` and `step-06` (`PRICE_CURRENT` and commented-out `ORDER_FOREIGN2` FK are already present in `step-05`). |

---

## 5. Relevant Documents, Packages, Classes & Deployments

### 5.1 Reference Documents (`legacy-example-stages` root)

| Document | Role for Prototype Development & Verification |
| :--- | :--- |
| [`STEPS.md`](legacy-example-stages/STEPS.md) | Stage definitions, component lists, startup sequences, environment drift table (§4), and curl acceptance test specification (§5). |
| [`QUESTIONS.md`](legacy-example-stages/QUESTIONS.md) | Ground-truth acceptance test catalog (Q1–Q15) with explicit `step-06` verification checks (dated 2026-10-23) and arc42 diagram mappings (§5). |
| [`DOMAIN-MODEL.md`](legacy-example-stages/DOMAIN-MODEL.md) | Derived domain entities (§3), business rules R1–R12 (§4), table usage (§5), bounded contexts `Catalog` vs. `Customer and order` (§6), REST surface (§7), and Kafka event spec (§8). |
| [`ARCHITECTURE.md`](/legacy-example-stages/ARCHITECTURE.md) | Reference arc42 views (Context, Building Blocks for `step-03a`/`04a`/`06`/`08`, Runtime sequences, Deployment table) serving as target examples for OD-02 view generation. |
| [`HISTORY-ANALYSIS.md`](/legacy-example-stages/HISTORY-ANALYSIS.md) | Commit-level evidence for changes A1–A26 and folder purity analysis (§4). |
| [`DERIVATION.md`](/legacy-example-stages/DERIVATION.md) | Methodology of stage reconstruction, omitted files (proprietary JARs/Dojo), and build/runtime verification notes. |
| [`fixes/README.md`](/legacy-example-stages/fixes/README.md) | Documentation of non-invasive workarounds required to build/run historical containers in 2026. |
| [`acceptance/check.sh`](/legacy-example-stages/acceptance/check.sh) | Automated HTTP verification script (`bash acceptance/check.sh step-05` / `step-06`). |
| `docs/ORIGINAL-README.md` | Snapshot of IBM's original README at the respective stage commit (`fba9759` vs. `842d550`). |

### 5.2 Complete Package & Class Inventory

#### A. Monolith (`components/monolith`)
* **`step-05` Path Prefixes:**
  * `EJB`: `CustomerOrderServices/ejbModule/org/pwte/example/...`
  * `WAR`: `CustomerOrderServicesWeb/src/org/pwte/example/...`
* **`step-06` Path Prefix:** `src/main/java/org/pwte/example/...`

| Package | Class | Bounded Context | `step-05` Role | `step-06` Role & Transition Status |
| :--- | :--- | :--- | :--- | :--- |
| `org.pwte.example.app` (`05`) / `org.pwte.example` (`06`) | `CustomerServicesApp` (`05`) $\rightarrow$ `CustomerServicesApplication` (`06`) | Infrastructure | JAX-RS `@ApplicationPath("/jaxrs")` activator in WAR module. | Renamed to `CustomerServicesApplication` in root package. |
| `org.pwte.example` | `ProductPriceChanged` | Customer & Order / Messaging | *Not present* | **Added in `step-06`:** `@ApplicationScoped` Kafka consumer (`@Incoming("product-price-updated")`); parses `productId#newPrice` and calls `CustomerOrderServicesImpl.updateLineItem`. |
| `org.pwte.example` | `InventoryResource` | Infrastructure (Dead/Leftover) | *Not present* | **Added in `step-06`:** Leftover Open Liberty starter endpoint at `/jaxrs/test`. |
| `org.pwte.example.health` | `InventoryLivenessCheck`, `InventoryReadinessCheck` | Infrastructure | *Not present* | **Added in `step-06`:** MicroProfile `@Liveness` and `@Readiness` checks (`/health/live`, `/health/ready`). |
| `org.pwte.example.resources` | `CategoryResource` | Catalog | Active JAX-RS resource (`GET /Category`, `GET /Category/{id}`). | **Unreachable via proxy (Dead Code):** Uses `@Inject ProductSearchService`, still active on container port `:9088`, but shadowed by proxy route to `catalog-service`. |
| `org.pwte.example.resources` | `ProductResource` | Catalog | Active JAX-RS resource (`GET /Product?categoryId=...`, `GET /Product/{id}`). | **Unreachable via proxy (Dead Code):** Uses `@Inject ProductSearchService`, shadowed by proxy route to `catalog-service`. |
| `org.pwte.example.resources` | `CustomerOrderResource` | Customer & Order | Active JAX-RS resource (8 endpoints under `/Customer`); uses JNDI lookup with hardcoded `rbarcia`/`bl0wfish`. | **Active & Refactored:** Replaces JNDI lookup in constructor with `@Inject CustomerOrderServices`. |
| `org.pwte.example.service` | `ProductSearchService`, `ProductSearchServiceImpl` | Catalog | `@Stateless` EJB querying Db2 `CATEGORY`, `PRODUCT`, `PROD_CAT`. | **Unreachable via proxy (Dead Code):** Converted to `@ApplicationScoped` CDI bean (`//@Stateless` commented out); only called by unreachable `CategoryResource`/`ProductResource`. |
| `org.pwte.example.service` | `CustomerOrderServices`, `CustomerOrderServicesImpl` | Customer & Order | `@Stateless` EJB implementing cart/order logic (R1–R12); contains active random `+10` price stub in `loadCustomerHistory()`. | **Active & Refactored:** `@ApplicationScoped` CDI bean; random price stub commented out; adds `updateLineItem(String productId, String newPrice)` updating `LINE_ITEM.PRICE_CURRENT` for hardcoded user `rbarcia`. *Leftover:* retains orphaned `@EJB ProductSearchService productSearchService;` field (unused; see §6.1). |
| `org.pwte.example.domain` | `Category` | Catalog | JPA `@Entity` (`CATEGORY` table in Db2). | **Duplicated / Unreached via REST:** Still mapped in `persistence.xml` and Db2, but catalog queries are served by `catalog-service`. |
| `org.pwte.example.domain` | `Product` | Catalog (Coupled to Order) | JPA `@Entity` (`PRODUCT` table in Db2). | **Duplicated & Coupled:** Still referenced via `@ManyToOne` from `LineItem` (`addLineItem` reads product price from Db2 `PRODUCT`, which is never updated by Kafka events). |
| `org.pwte.example.domain` | `AbstractCustomer`, `BusinessCustomer`, `ResidentialCustomer`, `Address`, `Order`, `LineItem`, `LineItemId` | Customer & Order | Active JPA entities (`CUSTOMER`, `ORDERS`, `LINE_ITEM` in Db2); `LineItem` already includes `PRICE_CURRENT` and `insertable=false, updatable=false`. | **Active:** Unchanged domain logic; `LineItem.priceCurrent` is now populated via Kafka consumer rather than the random stub. |
| `org.pwte.example.exception` | `CategoryDoesNotExist`, `CustomerDoesNotExistException`, `GeneralPersistenceException`, `InvalidQuantityException`, `NoLineItemsException`, `OrderAlreadyOpenException`, `OrderModifiedException`, `OrderNotOpenException`, `ProductDoesNotExistException` | Shared / Domain Exceptions | Domain exceptions thrown by EJB services. | Unchanged (`CategoryDoesNotExist` is only thrown by unreachable `ProductSearchServiceImpl`). |

#### B. Catalog Service (`components/catalog-service`, added in `step-06`)
* **Path Prefix:** `src/main/java/com/ibm/catalog/...`

| Class | Bounded Context | Role & Coupling in `step-06` |
| :--- | :--- | :--- |
| `Category` | Catalog | JPA `@Entity` (`category` table in Postgres, Panache `PanacheEntityBase`), defines named query `top.level.category`. |
| `Product` | Catalog | JPA `@Entity` (`product` table in Postgres), defines native query `product.by.cat.or.sub` joining `productcategory`. |
| `ProductCategory` | Catalog | JPA `@Entity` (`productcategory` join table in Postgres). |
| `CategoryResource` | Catalog | JAX-RS `@Path("/CustomerOrderServicesWeb/jaxrs/Category")`: implements `GET` (top-level categories). **Missing `GET /Category/{id}`** (returns HTTP 404). |
| `ProductResource` | Catalog | JAX-RS `@Path("/CustomerOrderServicesWeb/jaxrs/Product")`: implements `GET ?categoryId=...` and `PUT /{id}` (updates `price` in Postgres and sends `productId#price` to Kafka topic `product-price-updated` via Vert.x `KafkaProducer`). **Missing `GET /Product/{id}`** (returns HTTP 405). |
| `ProductPriceChanged` | Catalog / Messaging | `@ApplicationScoped` consumer (`@Incoming("product-price-updated")`) that logs the message emitted by `ProductResource`. |

#### C. Dojo Frontend (`components/frontend-dojo`)
* **Active Frontend Assets:** `CustomerOrderServicesWeb/WebContent/` (`index.html`, `dojo_depot/depot/ProductController.js`, `OrderHistoryController.js`, `AccountController.js`, `orderHistoryTemplate.html`, `theme/*.css`).
* **Embedded Dead Backend Copy:** `CustomerOrderServices/`, `CustomerOrderServicesApp/`, `CustomerOrderServicesTest/`, and `CustomerOrderServicesWeb/src/` contain a **166-file frozen copy of the Java EE monolith** from `step-04` (`ba97390`). It is built into the frontend container's EAR, but Nginx only routes `/` (static UI) to `storefront-frontend:9080`.

### 5.3 Active vs. Inactive Deployment & Configuration Files

Because `scripts-docker/` and `components/proxy/` retain files from earlier (`step-04a`–`04d`) and later (`step-07`) commits, config/topology parsers **must** filter by the active stage entrypoint rather than globbing all `*.yml` / `*.conf` files:

| Artifact Type | `step-05` Active Files | `step-06` Active Files | Inactive / Leftover Files Present in Tree (Must Ignore for Stage Topology) |
| :--- | :--- | :--- | :--- |
| **Start Scripts (`scripts-docker/`)** | `build-and-run-monolith-db2.sh` (or `run-monolith-db2.sh`), `build-and-run-splitted-frontend-open.sh` | `build-and-run-monolith-db2.sh`, `run-database-postgres-catalog.sh`, `run-kafka.sh`, `build-and-run-catalog.sh` |At `step-05`: `build-and-run-catalog*.sh`, `run-database-postgres-catalog.sh`, `run-kafka.sh`.<br>At `step-06`: `build-and-run-all-quarkus.sh`, `build-quarkus-and-run-catalog.sh`, `build-and-run-monolith-app-was90.sh`. |
| **Docker Compose (`scripts-docker/`)** | `docker-compose-monolith-db2.yml`, `docker-compose-splitted-frontend-open.yml` | `docker-compose-monolith-db2.yml`, `docker-compose-postgres-catalog.yml`, `docker-compose-kafka.yml`, `docker-compose-catalog-native.yml` | At `step-05`: `docker-compose-catalog.yml`, `docker-compose-postgres-catalog.yml`, `docker-compose-kafka.yml`, `docker-compose-monolith-app.yml`, `docker-compose-splitted-frontend.yml`.<br>At `step-06`: `docker-compose-all-quarkus.yml`, `docker-compose-catalog.yml`, `docker-compose-splitted-frontend*.yml`. |
| **Proxy (`components/proxy/`)** | `Dockerfile-splitted-frontend-open` $\rightarrow$ `nginx-splitted-frontend-open.conf` | `Dockerfile-catalog-native` $\rightarrow$ `nginx-catalog-native.conf` | At `step-05`: `Dockerfile-catalog`, `nginx-catalog.conf`, `nginx-monolith.conf`, `nginx-splitted-frontend.conf`.<br>At `step-06`: `Dockerfile-all-quarkus`, `nginx-all-quarkus.conf`, `nginx-catalog.conf`, `nginx-monolith.conf`, `nginx-splitted-frontend*.conf`. |
| **Database & App Config** | `components/db2/createOrderDB.sql`, `orderdb-data.sql`; `components/monolith/liberty/server.xml`, `server.env`, `CustomerOrderServices/ejbModule/META-INF/persistence.xml` | Same Db2 files; `components/monolith/src/main/liberty/config/server.xml`, `src/main/resources/META-INF/persistence.xml`, `microprofile-config.properties`; `components/catalog-service/src/main/resources/application.properties`, `import.sql` | `components/frontend-dojo/CustomerOrderServices/...` (frozen JPA/EJB config). |

---

## 6. Known Special Cases (derived from `STEPS.md`, `HISTORY-ANALYSIS.md`, `fixes/README.md`)

### 6.1 Static Analysis & Architectural Edge Cases
1. **Silent REST Migration Gaps (`Q2`):** In `step-06`, `nginx-catalog-native.conf` forwards prefix `/CustomerOrderServicesWeb/jaxrs/Category` and `/Product` to `catalog-service`, which only implements `GET /Category`, `GET /Product`, and `PUT /Product/{id}`. Legacy endpoints `GET /Category/{id}` (returns HTTP 404) and `GET /Product/{id}` (returns HTTP 405) break silently through the proxy despite still existing in the monolith's unreachable `CategoryResource`/`ProductResource`.
2. **Dangling Proxy Routes (`/explorer`, `/openapi`):** `nginx-catalog-native.conf` routes `/explorer` and `/openapi` to `storefront-catalog:8082`.
3. **Stale Duplicated Product Price (`Q9`, `Q13`):** Both Db2 (`PRODUCT`, `CATEGORY`, `PROD_CAT`) and Postgres (`product`, `category`, `productcategory`) hold catalog tables with separate seed scripts. When `PUT /Product/{id}` updates a price in Postgres and emits `product-price-updated`, `ProductPriceChanged` in the monolith only updates `LINE_ITEM.PRICE_CURRENT` for open/submitted orders of the hardcoded user `rbarcia`—it **never updates `PRODUCT.PRICE` in Db2**, leaving the monolith's product catalog stale when adding new items to the cart.
4. **Unused Legacy Db2 Tables (`Q4`, `Q8`):** Five tables in `components/db2/createOrderDB.sql` (`FAVORITES`, `SHIPPING_ADDRESS`, `CREDIT_INFO`, `ORDER_REC`, `CONTACT_NUMBERS`) have zero JPA entities or SQL references in any stage.
5. **Disabled Security & Hardcoded Principal (`A1`–`A3`, `Q11`):** Since `step-03a` (`da8a865`), `@RolesAllowed("SecureShopper")` and `web.xml` `<security-constraint>` are commented out, `loadCustomer()` hardcodes user `"rbarcia"`, and `step-05` JNDI lookups hardcode `rbarcia`/`bl0wfish`.
6. **JPA/Schema Workarounds (`A8`, `A9`, `Q11`):** Since `step-05`, foreign key `ORDER_FOREIGN2` (`LINE_ITEM.ORDER_ID -> ORDERS`) is commented out in `createOrderDB.sql`, `LineItem` sets `insertable=false, updatable=false` on `@ManyToOne` relations, and `CustomerOrderServicesImpl.addLineItem()` contains the `"super dirty hack"` `if (orderId == 0) orderId = 1`.
7. **Documentation Discrepancy in `ARCHITECTURE.md` §5.4:** `ARCHITECTURE.md` §5.4 states that `step-06` uses `nginx-catalog.conf` and forwards to `storefront-backend-open:9080`. In the actual `step-06` tag (`build-and-run-catalog.sh` and `QUESTIONS.md` Q4), `step-06` builds `Dockerfile-catalog-native` (`nginx-catalog-native.conf`) and forwards to `storefront-backend-open-native:9088`.
8. **Incomplete EJB-to-CDI Migration Leftovers (`CustomerOrderServicesImpl`, `CustomerOrderResource`):**
   In `step-06`, `CustomerOrderServicesImpl` is annotated with `@ApplicationScoped`, but still retains the field declaration `@EJB ProductSearchService productSearchService;` (line 229), while `ProductSearchServiceImpl` is no longer an EJB (`//@Stateless` is commented out, replaced by `@ApplicationScoped`).
   * **Runtime Behavior:** The monolith's Open Liberty `server.xml` configures `cdi-2.0` and omits the EJB feature (`ejbLite-3.2`). Because the EJB container feature is absent, Open Liberty's CDI runtime ignores the `@EJB` annotation rather than failing deployment with an unresolved injection error; the field remains `null`. No `NullPointerException` occurs at runtime because `productSearchService` was only called inside the random `+10` price stub in `loadCustomerHistory()`, which was commented out in `step-06` (`/* ... */`) when price updates moved to Kafka (`updateLineItem`). A similar inert EJB leftover exists in `CustomerOrderResource` (`@TransactionAttribute(TransactionAttributeType.NOT_SUPPORTED)`).
   * **Implication for Tooling / Static Analysis:** AST parsers scanning purely for `@EJB` annotations or imports will misidentify `CustomerOrderServicesImpl` as an EJB or as having an active dependency on `ProductSearchService`, even though the bean is managed by CDI, the EJB container is inactive, and the field is unused dead code.

### 6.2 Build & Runtime Special Cases (relevant for Running Containers)
If a developer runs the containers for dynamic checks (`bash acceptance/check.sh <step>`), the following environment-drift fixes (`fixes/README.md`) apply:

| Issue | `step-05` | `step-06` | Resolution / Note |
| :--- | :--- | :--- | :--- |
| **Missing Docker network `store-front-network`** | Created by `run-monolith-db2.sh` | Needed if starting compose directly | Run `bash fixes/docker-network.sh` before starting containers. |
| **Missing proprietary Db2 JDBC driver** | Needed | Needed | Run `bash fixes/db2-driver.sh` (downloads `db2jcc4.jar` from Maven Central). |
| **Db2 `populateDB.sh` connection drop (`SQL1024N`)** | Needed | Needed | Newer Bash uses `exec` on subshell commands, dropping the Db2 connection before `createOrderDB.sql` runs. Run `bash fixes/db2-populate.sh` after Db2 starts. |
| **Missing Prometheus JMX agent JAR (`jvm.options`)** | **Needed** (`monolith` & `frontend-dojo`) | **Not needed** (removed in `41f3d44`) | Run `bash fixes/jmx-agent.sh` on `step-05` before building images. |
| **Host port mapping mismatch (`9088:9080`)** | N/A (uses `9082:9080`) | **Present** in `docker-compose-catalog-native.yml` | `docker-compose-catalog-native.yml` maps host `:9088` to container `:9080`, but Open Liberty listens on `:9088` inside the container. Traffic via `proxy-nginx` (`:80` $\rightarrow$ `storefront-backend-open-native:9088`) works; direct calls to the monolith must run inside the Docker network. |
| **Java / Maven toolchain** | JDK 8 + Maven 3.8.x | JDK 11 (multistage Docker build) | `step-05` host Maven builds require JDK 8 and Maven 3.8.x; `step-06` builds inside Docker (`Dockerfile.multistage`). |

---

## 7. Ground-Truth Summary for `step-05` vs. `step-06`

| ID | Question Topic | `step-05` Ground Truth | `step-06` Ground Truth |
| :--- | :--- | :--- | :--- |
| **Q1** | **Replacement progress (overall & per bounded context)** | **0 of 2** bounded contexts extracted. Both **Catalog** (`Category`, `Product`) and **Customer/Order** (`Customer`, `Address`, `Order`, `LineItem`) are served by `monolith` (12 REST operations across 3 resources, 6 used Db2 tables). | **1 of 2** bounded contexts extracted. **Catalog** is served by `catalog-service` (Postgres: `category`, `product`, `productcategory`), implementing 2 of 12 legacy REST operations (`GET /Category`, `GET /Product`) + 1 new operation (`PUT /Product/{id}`). **Customer/Order** remains 100% in `monolith` (Db2, 8 REST operations + `/jaxrs/test`). |
| **Q2** | **Legacy features without target counterpart** | All 12 REST operations and both bounded contexts live solely in `monolith`. | Entire **Customer/Order** context (8 REST endpoints) + **silent gaps in Catalog**: `GET /Category/{id}` (HTTP 404) and `GET /Product/{id}` (HTTP 405) exist in `monolith` but are unimplemented in `catalog-service` while routed there by Nginx. |
| **Q3** | **Currently built in target system (code level)** | No target backend service in `stage.json` (`frontend-dojo` is separated into its own container since `step-04`). | `catalog-service` (Quarkus synchronous REST + Panache + Kafka producer) and `monolith` Kafka consumer (`ProductPriceChanged`). No target service exists for Customer/Order. |
| **Q4** | **Switched-off or unreachable legacy parts** | All 3 monolith JAX-RS resources are reachable via proxy. 5 Db2 tables (`FAVORITES`, `SHIPPING_ADDRESS`, `CREDIT_INFO`, `ORDER_REC`, `CONTACT_NUMBERS`) are unreferenced dead tables, plus the 166-file frozen backend inside `frontend-dojo`. | Same 5 unused Db2 tables + frozen `frontend-dojo` backend, **plus** monolith's `CategoryResource`, `ProductResource`, and `ProductSearchService*` are now **unreachable through `proxy-nginx`** (though still alive on container port `:9088`), and `CATEGORY`/`PRODUCT`/`PROD_CAT` in Db2 are duplicated. |
| **Q5** | **Remaining coupling between old and new** | Proxy routes `/` to `frontend-dojo:9080` and `/CustomerOrderServicesWeb/jaxrs/` to `storefront-backend-open:9080`. | (1) **Proxy routing** (`nginx-catalog-native.conf` splits paths between `catalog-service` and `monolith`); (2) **Kafka event** (`product-price-updated` payload `productId#newPrice` from `catalog-service` to `monolith`); (3) **Data duplication** (`PRODUCT`, `CATEGORY`, `PROD_CAT` kept in Db2 because `LineItem` references `Product`); (4) **No direct HTTP calls** between `catalog-service` and `monolith`; (5) `frontend-dojo` calls relative `/CustomerOrderServicesWeb/jaxrs/...` paths via proxy. |
| **Q6** | **Architectural seams & interfaces** | Browser $\leftrightarrow$ `proxy-nginx` (`:80`); `proxy-nginx` $\leftrightarrow$ `frontend-dojo` (`/`) and `monolith` (`/CustomerOrderServicesWeb/jaxrs/*`); `monolith` $\leftrightarrow$ `db2` (JDBC `:50000`); internal WAR $\leftrightarrow$ EJB boundary inside `monolith`. | Adds seam between **Catalog** and **Customer/Order** via Nginx path routing (`/Category`, `/Product`) and Kafka topic `product-price-updated`; internal EJB seam inside `monolith` is replaced by CDI (`@Inject`). |
| **Q7** | **Technologies & runtimes per component** | `monolith`: Open Liberty (`kernel-slim-java11-openj9`), Java 8 source, EJB 3, JPA 2.0, JAX-RS, JSON-B; `frontend-dojo`: WebSphere Liberty (`kernel-java8-openj9-ubi`), local Dojo 1.5; `db2`: Db2 11.5.5.0; `proxy`: `nginx:alpine`. | `monolith`: Open Liberty (`kernel-java11-openj9-ubi`), Java 8 source, CDI 2.0, JPA 2.2, MP Config 1.4 / Health 2.2 / Reactive Messaging 1.0; `catalog-service`: Quarkus `1.1.1.Final` (Java 11), Panache, Postgres, Vert.x Kafka; `frontend-dojo`: Liberty (`kernel-java11-openj9-ubi`), Dojo 1.5.0 via Google CDN; Kafka + Zookeeper. |
| **Q8** | **Candidates for next decommissioning** | 5 unused Db2 tables; 166-file frozen Java EE copy in `frontend-dojo`; random `+10` price stub in `CustomerOrderServicesImpl`. | (1) Unreachable `CategoryResource`, `ProductResource`, `ProductSearchService*`, `Category`, `CategoryDoesNotExist` in `monolith`; (2) `CATEGORY` and `PROD_CAT` tables in Db2 (and `PRODUCT` once `LineItem` decouples foreign key/entity reference); (3) 5 unused Db2 tables; (4) frozen Java EE copy in `frontend-dojo`; (5) leftover `/jaxrs/test` (`InventoryResource`); (6) leftover `@EJB` field in `CustomerOrderServicesImpl` and `@TransactionAttribute` in `CustomerOrderResource`. |
| **Q9** | **Cross-boundary change impact (price update flow)** | Price changes are faked in-process by the 50% `+10.00` random stub in `CustomerOrderServicesImpl.loadCustomerHistory()`. | Touch points span both systems: `catalog-service` `ProductResource.update` (`PUT /Product/{id}`), Kafka message format `productId#newPrice`, `monolith` `ProductPriceChanged` + `CustomerOrderServicesImpl.updateLineItem`, Db2 `LINE_ITEM.PRICE_CURRENT`, and `frontend-dojo` `orderHistoryTemplate.html`. **Defect:** Db2 `PRODUCT.PRICE` is never updated, so new cart items use stale Db2 prices. |
| **Q10** | **Undocumented legacy behavior (code-only rules)** | Rules R1–R11 in `DOMAIN-MODEL.md` §4: single open order per customer (R1), implicit cart creation (R3), quantity/amount aggregation (R4), price snapshot on `LineItem` (R5), `@Version` optimistic locking with `ETag`/`If-Match` (R6), unused customer discount flags (R10). | Same rules R1–R11 plus R12: Kafka price update only updates line items of hardcoded customer `rbarcia` (`loadCustomer()`). |
| **Q11** | **Security & quality risks introduced** | Authentication/authorization disabled (`@RolesAllowed` and `web.xml` constraints commented out), hardcoded principal `rbarcia`, hardcoded JNDI credentials `rbarcia`/`bl0wfish`, `ORDER_FOREIGN2` FK commented out, `if (orderId == 0) orderId = 1` hack, conditional GET (304) disabled. | Retains all `step-05` risks (except JNDI lookup is replaced by CDI `@Inject`), plus silent `catch (Exception e) {}` blocks in Kafka producer/consumer and unauthenticated `PUT /Product/{id}` price updates. |
| **Q12** | **Tests & verification coverage** | No unit/integration test module in `monolith@step-05` (`CustomerOrderServicesTest` only exists up to `step-04a` and inside `frontend-dojo`'s frozen copy). Verified externally via `acceptance/check.sh step-05` (6 HTTP checks). | Zero automated tests in `catalog-service`, `monolith`, or `proxy`. Verified externally via `acceptance/check.sh step-06` (8 HTTP checks: adds `PUT /Product/1` and Kafka price propagation check). |
| **Q13** | **Data consistency & ownership** | Single Db2 database (`orderdb`) owns all 6 active tables. | **Split & Divergent:** `catalog-service` (Postgres) owns catalog reads and price updates, while `monolith` (Db2) still owns a duplicate copy of `PRODUCT`, `CATEGORY`, `PROD_CAT` seeded independently and never synced on `PRODUCT.PRICE`. |
| **Q14** | **Documentation vs. code/history discrepancies** | Slide deck claims `step-05` is *"primarily changing image only"*, whereas code changed JSON stack to JSON-B, altered JPA mappings, commented out `ORDER_FOREIGN2`, and added the `orderId = 1` hack. | Original README presents chronological steps 1–10, whereas git history shows the proxy and catalog strangler switch (`2020-11-25`) predated Open Liberty (`2020-12-01`); `ARCHITECTURE.md` §5.4 names `nginx-catalog.conf` (`:9080`) instead of `nginx-catalog-native.conf` (`:9088`). |
| **Q15** | **Deployment & delivery maturity** | Local Docker Compose (`build-and-run-splitted-frontend-open.sh` + `run-monolith-db2.sh`); requires host Maven build (JDK 8) and 3 fix scripts (`db2-driver.sh`, `db2-populate.sh`, `jmx-agent.sh`). No CI/CD pipeline. | Local Docker Compose with multistage Docker builds (`build-and-run-catalog.sh` + Db2, Postgres, Kafka scripts); requires 3 fix scripts (`docker-network.sh`, `db2-driver.sh`, `db2-populate.sh`; `jmx-agent.sh` no longer needed). Host port `9088` is mis-mapped to container port `9080`. No CI/CD pipeline (Tekton starts at `step-09`). |
