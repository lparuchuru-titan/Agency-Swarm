# Jira Subtask Reference

## Subtask summary naming

```
Dev Task — Product2 bundle fields
PDS (Data) — Product2 bundle fields
PDS (Permissions & Layout) — Product2 bundle fields
PDS (QCP) — Quote line mappings
PDS (Manual Steps) — Bundle pricing
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
| Junction/config-object data scripts (e.g. `*LookupData*`, `Bundle_Definition__c`) | PDS Data |
| `*SBQQ*`, `*CPQ*`, `*Quote*` metadata | Dev Task + PDS QCP |

## Jira REST API

Create subtask (API v2):

```http
POST /rest/api/2/issue
{
  "fields": {
    "project": { "key": "PROJ" },
    "parent": { "key": "PROJ-1001" },
    "summary": "Dev Task — ...",
    "issuetype": { "name": "Sub-task" },
    "description": "..."
  }
}
```

Update description:

```http
PUT /rest/api/2/issue/PROJ-xxxx
{ "fields": { "description": "..." } }
```

Description uses Jira wiki markup (`h2.`, `||table||`, `{code}`) for API v2.

## Atlassian API token

https://id.atlassian.com/manage-profile/security/api-tokens

## Example workflow

```bash
# 1. Init for story PROJ-1001
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/init-story.py PROJ-1001 --push

# 2. Deploy to sandbox, then sync
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py -t PROJ-1001 objects/Product2/fields/
sf project deploy start --manifest manifest/my_deploy.xml --target-org MY_SANDBOX

python3 ~/.cursor/skills/jira-subtask-workflow/scripts/sync-from-work.py \
  --deploy-command "sf project deploy start --manifest manifest/my_deploy.xml --target-org MY_SANDBOX" \
  --ticket PROJ-1001 --push

# 3. Add manual step
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/add-pds-step.py \
  -t "Run bundle Apex scripts" \
  -s "sf apex run --file scripts/apex/bundles/05_rebuild_bundles_from_package_def.apex --target-org <ORG>"
```
