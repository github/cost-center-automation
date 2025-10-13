# Orphaned User Detection and Removal Feature

## Overview

This feature automatically detects and optionally removes "orphaned users" from cost centers. Orphaned users are those who are assigned to a cost center but are no longer members of the corresponding GitHub team.

## Why This Feature?

When teams change over time (members leave, are removed, or switch teams), their cost center assignments can become stale. This feature keeps cost centers synchronized with actual team membership by:

1. **Detecting** users in cost centers who are no longer in the corresponding team
2. **Reporting** these orphaned users with warnings
3. **Optionally removing** them based on configuration

## How It Works

### Detection Logic

For each cost center being managed:
1. Fetch the **expected members** from the GitHub team
2. Fetch the **current members** from the cost center API
3. Calculate orphaned users: `current_members - expected_members`
4. Log warnings for any orphaned users found

### Removal Logic (when enabled)

If `teams.remove_orphaned_users: true`:
- Automatically remove orphaned users from their cost centers
- Log success/failure for each removal
- Provide summary statistics

## Configuration

### Enable/Disable

Add to `config/config.yaml`:

```yaml
teams:
  enabled: true
  scope: "enterprise"  # or "organization"
  mode: "auto"
  
  # Orphaned user handling
  remove_orphaned_users: false  # Set to true to enable automatic removal
```

### Default Behavior

- **Default**: `false` (disabled)
- **When disabled**: Orphaned users are detected and logged but NOT removed
- **When enabled**: Orphaned users are detected and automatically removed

## Usage Examples

### Plan Mode (Preview)

```bash
# See what would happen (with removal disabled)
python main.py --teams-mode --assign-cost-centers --mode plan

# Output shows:
# MODE=plan: Orphaned user detection is DISABLED
# Users in cost centers but not in teams will remain assigned
```

```bash
# With removal enabled in config
python main.py --teams-mode --assign-cost-centers --mode plan

# Output shows:
# MODE=plan: Orphaned user detection is ENABLED
# In apply mode, users in cost centers but not in teams will be removed
```

### Apply Mode (Execution)

```bash
# Apply with removal disabled (default)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Adds users to cost centers but leaves orphaned users alone
```

```bash
# Apply with removal enabled
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Output includes:
# [INFO] Checking for orphaned users...
# [WARNING] ⚠️  Found 3 orphaned users in cost center 'Team: Frontend'
# [WARNING]    ⚠️  alice is in cost center but not in team
# [WARNING]    ⚠️  bob is in cost center but not in team
# [INFO] Removing 3 orphaned users from 'Team: Frontend'...
# [INFO] ✅ Successfully removed 3 users from cost center
# [INFO] 📊 Orphaned users summary: Found 3 orphaned users, successfully removed 3
```

## API Methods Added

### 1. `get_cost_center_members(cost_center_id)`

**Purpose**: Fetch current members of a cost center

**Endpoint**: `GET /enterprises/{enterprise}/settings/billing/cost-centers/{cost_center_id}`

**Returns**: List of usernames currently assigned to the cost center

**Example**:
```python
members = github_manager.get_cost_center_members("abc-123-def")
# Returns: ['alice', 'bob', 'charlie']
```

### 2. `remove_users_from_cost_center(cost_center_id, usernames)`

**Purpose**: Remove multiple users from a cost center

**Endpoint**: `DELETE /enterprises/{enterprise}/settings/billing/cost-centers/{cost_center_id}/resource`

**Parameters**:
- `cost_center_id`: ID of the cost center
- `usernames`: List of usernames to remove

**Returns**: Dict mapping username → success status (True/False)

**Example**:
```python
results = github_manager.remove_users_from_cost_center(
    "abc-123-def", 
    ["alice", "bob"]
)
# Returns: {'alice': True, 'bob': True}
```

## Implementation Details

### Files Modified

1. **`src/github_api.py`**
   - Added `get_cost_center_members()` method
   - Added `remove_users_from_cost_center()` method

2. **`src/config_manager.py`**
   - Added `teams_remove_orphaned_users` configuration property

3. **`src/teams_cost_center_manager.py`**
   - Added `_remove_orphaned_users()` private method
   - Modified `sync_team_assignments()` to call orphaned user detection
   - Added orphaned user handling in apply mode

4. **`config/config.yaml` & `config/config.example.yaml`**
   - Added `remove_orphaned_users` configuration option with documentation

5. **`main.py`**
   - Display `remove_orphaned_users` status in configuration output

### Logging

The feature provides comprehensive logging:

- **INFO**: General operation status
- **WARNING**: Orphaned users detected
- **ERROR**: API failures or removal failures
- **DEBUG**: Detailed member counts

### Error Handling

- API failures are logged but don't stop execution
- Individual user removal failures are tracked separately
- Summary statistics show success/failure counts

## Use Cases

### Use Case 1: Team Restructuring

**Scenario**: Your engineering team is split into "Frontend" and "Backend" teams. Some engineers move from one team to another.

**Without this feature**:
- Users remain in their old cost center
- Cost reporting is inaccurate
- Manual cleanup required

**With this feature**:
```yaml
teams:
  remove_orphaned_users: true
```
- Users automatically removed from old cost center
- Added to new cost center
- Cost reporting stays accurate

### Use Case 2: Employee Departures

**Scenario**: Team members leave the company and are removed from GitHub teams.

**Without this feature**:
- Departed users remain in cost centers
- Inflated cost center counts
- Security/audit concerns

**With this feature**:
- Departed users automatically removed from cost centers
- Accurate headcount per cost center
- Clean audit trail

### Use Case 3: Temporary Team Assignments

**Scenario**: Users temporarily join teams for projects, then return to their main team.

**With this feature enabled**:
- Users are automatically moved back when they leave the temporary team
- No manual cleanup needed

## Best Practices

### 1. Test in Plan Mode First

Always run with `--mode plan` to see what changes would be made:

```bash
python main.py --teams-mode --assign-cost-centers --mode plan
```

### 2. Enable Gradually

Start with `remove_orphaned_users: false` to see how many orphaned users exist:

```bash
# Step 1: Run once to see orphaned users (they'll be logged as warnings)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Step 2: Review logs for orphaned users
# Step 3: If comfortable, enable removal
# Step 4: Run again with removal enabled
```

### 3. Regular Sync Schedule

Run teams sync regularly to keep cost centers up-to-date:

```bash
# Daily cron job
0 2 * * * cd /path/to/repo && python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

### 4. Monitor Logs

Review execution logs for:
- Number of orphaned users found
- Removal success rates
- Any API errors

### 5. Consider Impact

Before enabling `remove_orphaned_users: true`, consider:
- Do you have users manually added to cost centers outside of team membership?
- Are there legitimate reasons for users to be in cost centers but not teams?
- Do you have adequate logging/monitoring?

## Limitations

1. **Plan Mode**: Cannot show specific orphaned users in plan mode because cost centers may not exist yet. Orphaned user detection only runs in apply mode after cost centers are created/resolved.

2. **Manual Assignments**: If you manually add users to cost centers outside of this tool, they will be detected as orphaned and removed if they're not in the corresponding team.

3. **API Rate Limits**: Checking cost center membership adds API calls. Large numbers of cost centers may hit rate limits.

4. **Single Cost Center**: Remember, users can only belong to ONE cost center at a time (GitHub API constraint).

## Troubleshooting

### Orphaned users not being removed

**Check**:
1. Is `remove_orphaned_users: true` in config?
2. Running in `--mode apply` (not plan)?
3. Check logs for API errors

### False positives (users incorrectly identified as orphaned)

**Cause**: User is not in the team being synced

**Solutions**:
- Verify team membership in GitHub
- Check that correct teams are configured
- Review team mappings in manual mode

### API 404 errors when checking cost center members

**Cause**: Cost center doesn't exist yet (plan mode issue)

**Solution**: This is expected in plan mode. Orphaned detection only runs in apply mode.

## Future Enhancements

Potential improvements:
1. **Dry-run for orphaned users**: Show what would be removed without actually removing
2. **Whitelist**: Configure specific users to never be removed
3. **Notification**: Send alerts when orphaned users are found/removed
4. **Audit log export**: Export orphaned user reports to CSV

## Summary

The orphaned user detection and removal feature helps maintain clean, accurate cost center assignments by:

- ✅ **Detecting** users who shouldn't be in cost centers
- ✅ **Reporting** discrepancies with clear warnings  
- ✅ **Removing** orphaned users automatically (when enabled)
- ✅ **Working** with both organization and enterprise team scopes
- ✅ **Configurable** - enable/disable as needed
- ✅ **Safe** - disabled by default, clear logging, error handling

This keeps your cost center data synchronized with actual team membership over time with minimal manual intervention.
