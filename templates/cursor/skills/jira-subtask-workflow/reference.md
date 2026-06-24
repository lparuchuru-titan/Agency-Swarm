# Jira Subtask Reference

## Subtask summary naming

```
Dev Task — Pantheon 2026 Product2 bundle fields
PDS (Data) — Pantheon 2026 Product2 bundle fields
PDS (Permissions & Layout) — Pantheon 2026 Product2 bundle fields
PDS (QCP) — Pantheon quote line mappings
PDS (Manual Steps) — Pantheon 2026 bundle pricing
```

## File classification

| Path pattern | Bucket |
|--------------|--------|
| `force-app/**/classes/*.cls` | Dev Task |
| `force-app/**/lwc/**` | Dev Task |
| `force-app/**/objects/**` | Dev Task |
| `force-app/**/permissionsets/**` | Dev Task + PDS Permissions |
| `force-app/**/profiles/**` | Dev Task + PDS Permissions |
| `force-app/**/layouts/**` | Dev Task + PDS Permissions |
| `scripts/apex/**` | PDS Data |
| `*LookupData*`, `Bundle_Definition__c` data scripts | PDS Data |
| `*SBQQ*`, `*CPQ*`, `*Quote*` metadata | Dev Task + PDS QCP |

## Jira REST API

Create subtask (API v2):

```http
POST /rest/api/2/issue
{
  "fields": {
    "project": { "key": "SFDCLQ" },
    "parent": { "key": "SFDCLQ-7592" },
    "summary": "Dev Task — ...",
    "issuetype": { "name": "Sub-task" },
    "description": "..."
  }
}
```

Update description:

```http
PUT /rest/api/2/issue/SFDCLQ-xxxx
{ "fields": { "description": "..." } }
```

Description uses Jira wiki markup (`h2.`, `||table||`, `{code}`) for API v2.

## Atlassian API token

https://id.atlassian.com/manage-profile/security/api-tokens

## Example workflow (Pantheon)

```bash
# 1. Init for story SFDCLQ-7592
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/init-story.py SFDCLQ-7592 --push

# 2. Deploy to sandbox, then sync
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py -t SFDCLQ-7592 objects/Product2/fields/
sf project deploy start --manifest manifest/pantheon_cpq_deploy.xml --target-org NEXTGEN2

python3 ~/.cursor/skills/jira-subtask-workflow/scripts/sync-from-work.py \
  --deploy-command "sf project deploy start --manifest manifest/pantheon_cpq_deploy.xml --target-org NEXTGEN2" \
  --ticket SFDCLQ-7592 --push

# 3. Add manual step
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/add-pds-step.py \
  -t "Run bundle Apex scripts" \
  -s "sf apex run --file scripts/apex/pantheon/05_rebuild_bundles_from_package_def.apex --target-org <ORG>"
```
