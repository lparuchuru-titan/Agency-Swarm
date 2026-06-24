# Lightning Web Components
_Last refreshed via SFDC Knowledge Swarm · Sources: 5 docs_

## Summary
Lightning Web Components (LWC) is Salesforce's standards-based UI framework built on native web components (custom elements, Shadow DOM, ES modules). Components are authored as a bundle (`.js`, `.html`, `.js-meta.xml`, optional `.css`). The framework manages a defined lifecycle — creating components, inserting them into the DOM, rendering them, and removing them — exposing hooks at each phase. Data flows reactively: public `@api` properties and tracked fields trigger re-render, parents talk to children via properties/methods, and children talk to parents via custom events. Salesforce data is read via the declarative `@wire` service (cacheable, reactive) or imperative Apex calls (user-driven, DML). This note focuses on lifecycle, reactivity, `@wire` vs imperative Apex, events, datatable, navigation, and performance.

## Key concepts

### Lifecycle hooks and execution order
The framework runs hooks in this order during creation/render:
1. **`constructor()`** — runs first when the component instance is created. Flows **parent to child**. Must call `super()` as the first statement. The element is **not yet in the DOM**, public `@api` properties are **not yet set**, and you cannot access child elements or attributes. Use only for cheap one-time setup.
2. **`connectedCallback()`** — fires when the element is **inserted into the DOM**. Flows **parent to child**. Public properties **are** available by now (assigned after construction, before this hook). Use for: subscribing to a Lightning Message Service channel, fetching data, setting up caches/listeners, navigating with `lightning/navigation`, interacting with third-party web components, adding an attribute to the host element. You still **cannot access child elements** (they don't exist yet). It can **fire more than once** (e.g. when list items are reordered), so guard one-time logic.
3. **`render()`** — optional; overrides the default rendering by returning an imported template. Rarely needed; only for conditionally choosing between multiple templates.
4. **`renderedCallback()`** — unique to LWC; runs after the component finishes rendering and template expressions are re-evaluated. Flows **child to parent** (children render before parents). Fires on **every** render, so use a `hasRendered` boolean for one-time work. **Do not mutate reactive state here** (public properties, fields, or wire-adapter config objects) — that retriggers rendering and can cause an **infinite loop**.
5. **`disconnectedCallback()`** — fires when the element is **removed from (or hidden in) the DOM**. Flows **parent to child**. Mirror `connectedCallback()` cleanup here: unsubscribe from message channels, remove event listeners, purge caches.
6. **`errorCallback(error, stack)`** — error boundary; captures errors from **descendant** components' lifecycle hooks and **template-declared** event handlers. It does **not** catch errors in the boundary component itself, nor errors from programmatically attached listeners. The framework unmounts the child that threw. Implement it in a dedicated boundary component wrapping the functional component.

### Reactivity
- Since **Spring '20, all fields are reactive by default** — `@track` is **not needed** for primitives or for reassigning whole objects/arrays. Use `@track` only when you mutate **internal** properties of an object or items inside an array in place.
- `@api` exposes a public, reactive property (parent → child data). Changing it re-renders the child.
- A `@wire` config that references a reactive property (prefixed with `$`, e.g. `$recordId`) re-invokes the adapter whenever that property changes.

### @wire vs imperative Apex
- **`@wire`** — declarative, reactive read. Best for read-only data tied to reactive inputs; the framework manages invocation, caching, and updates automatically. Apex method must be `@AuraEnabled(cacheable=true)`. Prefer wiring to a **property** over a function for simpler code. Salesforce reserves some performance enhancements for `@wire`, and it is the recommended default for reads.
- **Imperative Apex** — explicit call from JS (button click, event handler). Use for user-initiated actions, **DML/writes**, non-cacheable work, or when you need exact control over timing and error handling. Method need not be cacheable.
- **Data access hierarchy:** prefer Lightning Data Service / `lightning-record-*` (auto FLS/OLS, shared cache) for single-record CRUD; use Apex for aggregates, complex/bulk queries; GraphQL wire adapter for flexible cross-object reads.

### Events (child → parent)
- Dispatch `CustomEvent`; read data via `event.detail`.
- Event-name rules: lowercase, no spaces, no `on` prefix, underscores between words.
- By default events do **not** cross the shadow boundary; set `bubbles`/`composed` deliberately and sparingly.
- Cross-DOM / unrelated components: use **Lightning Message Service (LMS)**.

### lightning-datatable / tree-grid
- `lightning-datatable` renders tabular data from `data` + `columns`; supports inline edit, sorting, row selection, and infinite scroll/lazy loading via `enable-infinite-loading` and the `loadmore` event.
- `lightning-tree-grid` renders hierarchical rows (expand/collapse) using the same column model plus a `_children` key on rows.

### Navigation
- Use the `NavigationMixin` from `lightning/navigation`: `NavigationMixin.Navigate(pageReference)` and `NavigationMixin.GenerateUrl(pageReference)`.
- Common `pageReference` types: `standard__recordPage`, `standard__objectPage`, `standard__navItemPage`, `standard__webPage`.

## Best practices / guardrails
- Declare `@AuraEnabled(cacheable=true)` on read-only Apex and prefer `@wire` for reactive reads.
- Don't add `@track` to primitives; only for in-place mutation of nested objects/arrays.
- Use `lwc:if` / `lwc:elseif` / `lwc:else` for conditional rendering (removes nodes from the DOM rather than hiding via CSS).
- Always pair `connectedCallback()` setup with `disconnectedCallback()` cleanup to avoid memory leaks and lingering subscriptions.
- Use a `hasRendered` guard in `renderedCallback()` for one-time DOM work.
- Centralize error parsing with a shared `reduceErrors` utility; surface field-level errors near the point of failure and use toasts (`ShowToastEvent`) for action-triggered or multi-point failures.
- Wrap functional components in an `errorCallback()` boundary component for graceful degradation.
- Enforce FLS/OLS — prefer LDS; in Apex use `WITH USER_MODE` or `Security.stripInaccessible`.

## Gotchas & limits
- `constructor()` runs before `@api` props are set and before DOM insertion — don't read public props or query children there.
- Neither `constructor()` nor `connectedCallback()` can access child elements (children not rendered yet) — query DOM in `renderedCallback()`.
- `connectedCallback()` can fire multiple times — guard one-time logic.
- Mutating reactive state (props/fields/wire config) inside `renderedCallback()` causes infinite re-render loops.
- `errorCallback()` cannot catch errors in its own component or from programmatically added listeners — only descendant lifecycle hooks and template-declared handlers.
- `try/catch` only catches **synchronous** exceptions; for async (promises, `setTimeout`) use `.catch()` or `async/await` with try/catch.
- Wire errors surface in the destructured `error` property, not via try/catch.

## Code / config patterns

```javascript
// Lifecycle + reactive wire + imperative call
import { LightningElement, api, wire } from 'lwc';
import getContacts from '@salesforce/apex/ContactController.getContacts';
import saveContact from '@salesforce/apex/ContactController.saveContact';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';
import { reduceErrors } from 'c/ldsUtils';

export default class ContactList extends LightningElement {
    @api recordId;            // public, reactive; set after constructor
    contacts;
    error;
    hasRendered = false;

    // Reactive wire: re-runs whenever recordId changes
    @wire(getContacts, { accountId: '$recordId' })
    wiredContacts({ data, error }) {
        if (data) { this.contacts = data; this.error = undefined; }
        else if (error) { this.error = reduceErrors(error); this.contacts = undefined; }
    }

    connectedCallback() {
        // safe to read @api props here; cannot touch child DOM yet
    }

    renderedCallback() {
        if (this.hasRendered) return;     // one-time guard
        this.hasRendered = true;
        // one-time DOM work; do NOT mutate reactive state here
    }

    disconnectedCallback() {
        // mirror connectedCallback cleanup (unsubscribe, remove listeners)
    }

    // Imperative call for a user action / DML
    async handleSave() {
        try {
            await saveContact({ contact: this.draft });
            this.dispatchEvent(new ShowToastEvent({ title: 'Saved', variant: 'success' }));
            this.dispatchEvent(new CustomEvent('contactsaved', { detail: this.draft.Id }));
        } catch (e) {
            this.dispatchEvent(new ShowToastEvent({
                title: 'Error', message: reduceErrors(e).join(', '), variant: 'error'
            }));
        }
    }
}
```

```javascript
// Navigation with NavigationMixin
import { LightningElement } from 'lwc';
import { NavigationMixin } from 'lightning/navigation';

export default class OpenRecord extends NavigationMixin(LightningElement) {
    navigate(recordId) {
        this[NavigationMixin.Navigate]({
            type: 'standard__recordPage',
            attributes: { recordId, objectApiName: 'Account', actionName: 'view' }
        });
    }
}
```

```apex
// Cacheable read for @wire; non-cacheable write for imperative call
public with sharing class ContactController {
    @AuraEnabled(cacheable=true)
    public static List<Contact> getContacts(Id accountId) {
        return [SELECT Id, Name, Email FROM Contact
                WHERE AccountId = :accountId WITH USER_MODE];
    }

    @AuraEnabled
    public static Contact saveContact(Contact contact) {
        upsert as user contact;   // user-mode DML enforces CRUD/FLS
        return contact;
    }
}
```

```xml
<!-- Conditional rendering removes nodes from the DOM (not CSS-hidden) -->
<template>
    <template lwc:if={contacts}>
        <lightning-datatable
            key-field="Id"
            data={contacts}
            columns={columns}
            onrowselection={handleRowSelect}
            enable-infinite-loading
            onloadmore={loadMore}>
        </lightning-datatable>
    </template>
    <template lwc:else>
        <p>No contacts.</p>
    </template>
</template>
```

## Sources
- https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks.html
- https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks-dom.html
- https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks-rendered.html
- https://developer.salesforce.com/blogs/2020/08/error-handling-best-practices-for-lightning-web-components
- https://www.apexhours.com/lightning-web-components-lwc-part-2/
