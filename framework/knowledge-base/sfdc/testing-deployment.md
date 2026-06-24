# Testing & Deployment (SFDX/CI)
_Last refreshed via SFDC Knowledge Swarm · Sources: 4 docs_

## Summary
Salesforce requires at least **75% Apex code coverage** to deploy to production or package, but every line of meaningful logic should be exercised with assertions, not just touched for coverage. The discipline has two halves: (1) writing fast, deterministic, self-contained Apex tests that mock external dependencies (callouts via `HttpCalloutMock`/`WebServiceMock`), build data through a `TestDataFactory`, and validate behavior with the `Assert` class; and (2) shipping that code through a source-driven SFDX pipeline — scratch orgs for dev, unlocked packages for modular metadata, and the `sf` CLI (`sf project deploy start`, `sf apex run test`) wired into CI so every commit is validated before it reaches sandbox → UAT → production.

> Note: The primary official URL (`apex_testing.htm`) and several Salesforce Developer doc pages are JavaScript-rendered and returned no fetchable body. Content below is grounded in the Salesforce HTTP-callout testing doc (referenced via search), the Apex Hours best-practices article, and a community Apex testing guide; numeric limits and API names are corroborated across these sources.

## Key concepts
- **Test class / method annotations** — `@isTest` marks a class or method as test-only (excluded from org code-size limits). `@isTest private class ...` is the convention. Individual methods are `@isTest static void`.
- **`@TestSetup`** — a `static void` method that runs once per test class before each test method; records it inserts are rolled back to that baseline state between methods. Centralizes data setup and reduces per-method DML.
- **`Test.startTest()` / `Test.stopTest()`** — wrap the code under test. They give a **fresh set of governor limits** for the enclosed block, and `stopTest()` forces any queued asynchronous work (`@future`, Queueable, Batch) to run synchronously so you can assert on its results.
- **Callout mocking** — by default test methods cannot make HTTP callouts; they fail. You supply mocks:
  - `HttpCalloutMock` interface → implement `HTTPResponse respond(HTTPRequest req)`, register with `Test.setMock(HttpCalloutMock.class, mockInstance)`.
  - `StaticResourceCalloutMock` / `MultiStaticResourceCalloutMock` → serve response bodies from static resources.
  - `WebServiceMock` → for SOAP/WSDL-generated stub callouts.
- **Assertions** — modern `Assert` class: `Assert.areEqual(expected, actual, msg)`, `Assert.isTrue/isFalse`, `Assert.isNotNull`, `Assert.fail`. (Legacy: `System.assertEquals`, `System.assert`.) Always pass a descriptive failure message.
- **`@isTest(SeeAllData=false)`** — the default; tests see only data they create. Avoid `SeeAllData=true` (brittle, depends on org data).
- **`System.runAs(user)`** — run a block as a specific user to test sharing, CRUD/FLS, and profile/permission behavior.
- **Salesforce DX building blocks** — `sfdx-project.json` (package directories + dependencies), scratch org definition file (e.g. `config/project-scratch-def.json`), source tracking (push/pull for scratch orgs), and **unlocked packages** for modular, versioned metadata in internal enterprise apps.
- **`sf` CLI** — `sf apex run test`, `sf project deploy start`, `sf project retrieve start`, `sf org create scratch`.

## Best practices / guardrails
- **Coverage is a floor, not a goal.** 75% is the deploy minimum; target **90%+** and assert real behavior. Coverage without assertions proves nothing.
- **One factory for data.** Centralize record creation in a `TestDataFactory` so a schema change is fixed in one place; never hardcode IDs.
- **Test the full matrix:** single record, **bulk (200+ records)** to catch governor-limit and non-bulkified logic, positive paths, negative/exception paths, and restricted-user access via `System.runAs`.
- **Mock all external dependencies** (`HttpCalloutMock`/`WebServiceMock`) so tests are deterministic and independent of network/external systems.
- **Wrap the unit under test in `Test.startTest()/stopTest()`** to isolate limits and flush async work before asserting.
- **Use `@TestSetup`** for shared data to keep methods fast and DRY.
- **CI on every commit:** create a scratch org from the definition file, install package dependencies, deploy/push source, run `sf apex run test --code-coverage`, then promote validated artifacts through sandbox → QA → UAT → production.
- **Use `sf project deploy start` (Metadata API) for sandboxes/prod**; source push/pull is for scratch orgs only.
- **Modularize metadata into unlocked packages** for version control, dependency management, and clean rollback.

## Gotchas & limits
- **75% org-wide coverage** is enforced at deploy/package time; additionally **every trigger must have some coverage**.
- **Test data is not committed** to the database (rolled back after the test), so no cleanup is needed — but it also means you cannot rely on records persisting across separate test runs.
- **Callouts fail without a mock** — forgetting `Test.setMock` before `Test.startTest()` produces a `methodNotAllowed`/callout-not-allowed error.
- **`Test.setMock` must be called before `startTest()`** (or before the callout executes).
- **Async results aren't visible until after `Test.stopTest()`** — assert on future/queueable/batch outcomes only after the `stopTest()` call.
- **`SeeAllData=true`** makes tests dependent on org data and is fragile across orgs/refreshes — avoid it.
- **DML inside loops / SOQL inside loops** surfaces under bulk tests; tests that only insert one record hide non-bulkified code.
- **Scratch orgs are ephemeral** (expire, default ~7 days) — never store anything you need to keep; rebuild from source each CI run.

## Code / config patterns

```apex
// Test class: @TestSetup, bulk-friendly data, Test.startTest/stopTest, Assert class
@isTest
private class OpportunityServiceTest {

    @TestSetup
    static void setupTestData() {
        List<Account> accounts = new List<Account>();
        for (Integer i = 0; i < 200; i++) {          // bulk: 200 records
            accounts.add(new Account(
                Name = 'Test Account ' + i,
                Industry = 'Technology',
                AnnualRevenue = 5000000
            ));
        }
        insert accounts;
    }

    @isTest
    static void calculateDiscount_platinumTier_returns15Percent() {
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Test Opp', AccountId = acc.Id, Amount = 100000,
            CloseDate = Date.today().addDays(30), StageName = 'Prospecting'
        );
        insert opp;

        Test.startTest();
        Decimal discount = OpportunityService.calculateDiscount(opp.Id);
        Test.stopTest();

        Assert.areEqual(0.15, discount, 'Platinum should receive 15% discount');
    }
}
```

```apex
// HTTP callout mock: implement HttpCalloutMock, register with Test.setMock
@isTest
public class CustomerApiMock implements HttpCalloutMock {
    private Integer statusCode;
    private String responseBody;
    public CustomerApiMock(Integer statusCode, String responseBody) {
        this.statusCode = statusCode;
        this.responseBody = responseBody;
    }
    public HTTPResponse respond(HTTPRequest req) {
        HTTPResponse res = new HTTPResponse();
        res.setStatusCode(statusCode);
        res.setBody(responseBody);
        return res;
    }
}

@isTest
static void getCustomer_invalidId_throws404() {
    // setMock BEFORE startTest
    Test.setMock(HttpCalloutMock.class, new CustomerApiMock(404, '{"error":"Not found"}'));
    Test.startTest();
    try {
        CustomerApiClient.getCustomer('INVALID');
        Assert.fail('Expected a CalloutException');
    } catch (CalloutException e) {
        Assert.isTrue(e.getMessage().contains('404'), 'Error should mention 404');
    }
    Test.stopTest();
}
```

```bash
# sf CLI: scratch org + tests + deploy (CI pipeline shape)
sf org create scratch --definition-file config/project-scratch-def.json --alias ci --duration-days 1 --set-default
sf project deploy start --source-dir force-app          # push metadata
sf apex run test --code-coverage --result-format human --wait 10
sf apex run test --class-names OpportunityServiceTest --code-coverage   # targeted run

# Validate-only deploy to sandbox/prod (Metadata API)
sf project deploy start --manifest manifest/package.xml --test-level RunLocalTests --dry-run
```

```json
// sfdx-project.json — package dirs + dependencies for unlocked packaging
{
  "packageDirectories": [
    { "path": "force-app", "default": true, "package": "MyApp", "versionNumber": "1.0.0.NEXT" }
  ],
  "sourceApiVersion": "61.0",
  "namespace": "",
  "sfdcLoginUrl": "https://login.salesforce.com"
}
```

## Sources
- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing.htm (JS-rendered, no body returned; listed as primary topic)
- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_restful_http_testing.htm (Testing HTTP Callouts — HttpCalloutMock / Test.setMock, via search summary)
- https://www.apexhours.com/apex-test-class-best-practices/ (Apex test class best practices)
- https://sfdecoded.github.io/guides/apex-testing.html (Apex Testing Complete Guide — code patterns & sf CLI commands)
- https://gearset.com/solutions/deploy/salesforce-dx/ (SFDX deployment / scratch orgs in CI)
